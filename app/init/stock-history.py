# INIT DATA SAHAM KE DATABASE (HISTORICAL PRICE)

import sys
import os
import yfinance as yf
from datetime import datetime
import pandas as pd
import numpy as np
from datetime import date
import time
from pymongo import UpdateOne
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands
from ta.volume import OnBalanceVolumeIndicator, MFIIndicator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from connection.mongodb import db_provider

def calculate_indicators(df):
    """
    Menghitung indikator menggunakan pustaka 'ta'.
    Jika data history tidak mencukupi, secara otomatis akan menghasilkan NaN.
    """
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    # 1. MA5 & MA20
    df['ma5'] = SMAIndicator(close=close, window=5).sma_indicator()
    df['ma20'] = SMAIndicator(close=close, window=20).sma_indicator()

    # 2. EMA (10 untuk jangka pendek)
    df['ema10'] = EMAIndicator(close=close, window=10).ema_indicator()

    # 3. RSI (14)
    df['rsi'] = RSIIndicator(close=close, window=14).rsi()

    # 4. MACD (12, 26, 9)
    macd_init = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df['macd'] = macd_init.macd()
    df['macd_signal'] = macd_init.macd_signal()
    df['macd_hist'] = macd_init.macd_diff()

    # 5. Stochastic (14, 3)
    stoch_init = StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
    df['stoch_k'] = stoch_init.stoch()
    df['stoch_d'] = stoch_init.stoch_signal()

    # 6. Bollinger Bands (20, 2)
    bb_init = BollingerBands(close=close, window=20, window_dev=2)
    df['bb_upper'] = bb_init.bollinger_hband()
    df['bb_middle'] = bb_init.bollinger_mavg()
    df['bb_lower'] = bb_init.bollinger_lband()

    # 7. MFI (14)
    df['mfi'] = MFIIndicator(high=high, low=low, close=close, volume=volume, window=14).money_flow_index()

    # 8. OBV
    df['obv'] = OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()

    # 9. Volume MA (20)
    df['volume_ma'] = SMAIndicator(close=volume, window=20).sma_indicator()

    # Konversi NaN ke None agar bisa masuk MongoDB sebagai null
    df = df.replace({np.nan: None})
    
    return df

def load_symbols(filename="symbols.txt"):
    """Membaca daftar simbol dari file eksternal berdasarkan lokasi skrip"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)

    if not os.path.exists(file_path):
        print(f"❌ File {file_path} tidak ditemukan!")
        return []
        
    with open(file_path, "r") as f:
        # Mengambil baris yang tidak kosong dan membersihkan whitespace
        return [line.strip() for line in f if line.strip()]

def fetch_and_save_stock_data(start_date, end_date):
    """
    start_date & end_date format: 'YYYY-MM-DD'
    """
    # 1. Load daftar kode saham dari file eksternal
    symbols = load_symbols()
    
    if not symbols:
        print("⚠️ Tidak ada simbol yang diproses.")
        return

    db = db_provider.get_database()
    collection = db["stock_history"]
    collection.create_index([("date_key", 1), ("symbol", 1)], unique=True)

    print(f"🚀 Mengambil data historis dari {start_date} hingga {end_date}...")
    start_dt_obj = datetime.strptime(start_date, '%Y-%m-%d')
    buffer_start = (start_dt_obj - pd.Timedelta(days=100)).strftime('%Y-%m-%d')

    for symbol in symbols:
        print(f"\n--- Fetching {symbol} ---")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=buffer_start, end=end_date, auto_adjust=False)

            if df.empty:
                print(f"⚠️ Data untuk {symbol} tidak ditemukan pada rentang tanggal tersebut.")
                continue

            # Reset index agar tanggal menjadi kolom
            df.index = df.index.tz_localize(None)
            df = df.reset_index()
            df = calculate_indicators(df)

            # Filter data: hanya ambil data dari start_date asli
            df['Date_Str'] = df['Date'].dt.strftime('%Y-%m-%d')
            df_filtered = df[df['Date_Str'] >= start_date]

            # Menghitung jumlah baris untuk progress log
            rows_processed = 0
            operations = []

            for _, row in df_filtered.iterrows():
                date_str = row['Date_Str']
                stock_data = {}
                
                stock_data["symbol"] = symbol
                stock_data["date_key"] = date_str
                stock_data["date"] = pd.to_datetime(row['Date'])
                stock_data['adj_close'] = row['Adj Close']
                stock_data['close'] = row['Close']
                stock_data['dividends'] = row['Dividends']
                stock_data['high'] = row['High']
                stock_data['low'] = row['Low']
                stock_data['open'] = row['Open']
                stock_data['stock_splits'] = row['Stock Splits']
                stock_data['volume'] = row['Volume']
                stock_data['ma5'] = row['ma5']
                stock_data['ma20'] = row['ma20']
                stock_data['ema10'] = row['ema10']
                stock_data['rsi'] = row['rsi']
                stock_data['macd'] = row['macd']
                stock_data['macd_signal'] = row['macd_signal']
                stock_data['macd_hist'] = row['macd_hist']
                stock_data['stoch_k'] = row['stoch_k']
                stock_data['stoch_d'] = row['stoch_d']
                stock_data['bb_upper'] = row['bb_upper']
                stock_data['bb_middle'] = row['bb_middle']
                stock_data['bb_lower'] = row['bb_lower']
                stock_data['mfi'] = row['mfi']
                stock_data['obv'] = row['obv']
                stock_data['volume_ma'] = row['volume_ma']
                
                operations.append(
                    UpdateOne(
                        {"date_key": date_str, "symbol": symbol},
                        {"$setOnInsert": stock_data},
                        upsert=True
                    )
                )
                rows_processed += 1

            if operations:
                collection.bulk_write(operations)
            print(f"✅ Selesai memproses {symbol}: {rows_processed} baris data.")
            time.sleep(3)

        except Exception as e:
            print(f"❌ Gagal mengambil data {symbol}: {e}")

if __name__ == "__main__":
    START = "2026-04-01"
    END = date.today().isoformat()
    
    fetch_and_save_stock_data(START, END)
    print("\n✅ Sinkronisasi database history selesai.")