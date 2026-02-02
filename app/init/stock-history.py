# INIT DATA SAHAM KE DATABASE (HISTORICAL PRICE)

import sys
import os
import yfinance as yf
from datetime import datetime
import pandas as pd
from datetime import date
import time

# Agar file main.py bisa menemukan folder app/connection
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from connection.mongodb import db_provider

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

    # Pastikan index unik agar tidak ada duplikat per tanggal per saham
    collection.create_index([("Date", 1), ("Symbol", 1)], unique=True)

    print(f"🚀 Mengambil data historis dari {start_date} hingga {end_date}...")

    for symbol in symbols:
        print(f"\n--- Fetching {symbol} ---")
        try:
            # 2. Fetch data dengan range tanggal tertentu
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, auto_adjust=False)

            if df.empty:
                print(f"⚠️ Data untuk {symbol} tidak ditemukan pada rentang tanggal tersebut.")
                continue

            # Reset index agar tanggal menjadi kolom
            df.index = df.index.tz_localize(None)
            df = df.reset_index()

            # Menghitung jumlah baris untuk progress log
            rows_processed = 0

            for _, row in df.iterrows():
                # Pastikan format tanggal konsisten (YYYY-MM-DD)
                date_str = row['Date'].strftime('%Y-%m-%d')
                
                # Konversi row ke dictionary
                stock_data = row.to_dict()
                
                # Menghilangkan objek Timestamp/Datetime agar kompatibel dengan MongoDB BSON
                stock_data["Symbol"] = symbol
                stock_data["Date"] = date_str
                
                # 3. Logika Upsert: Gunakan $setOnInsert jika hanya ingin simpan data baru
                # atau gunakan $set jika ingin menimpa data lama dengan data terbaru dari API
                collection.update_one(
                    {"Date": date_str, "Symbol": symbol},
                    {"$setOnInsert": stock_data},
                    upsert=True
                )
                rows_processed += 1

            print(f"✅ Selesai memproses {symbol}: {rows_processed} baris data.")
            time.sleep(3)

        except Exception as e:
            print(f"❌ Gagal mengambil data {symbol}: {e}")

if __name__ == "__main__":
    # Tentukan range tanggal di sini
    # Tip: Gunakan rentang yang masuk akal agar tidak terkena limit API
    START = "2026-01-10"
    END = date.today().isoformat()
    
    fetch_and_save_stock_data(START, END)
    print("\n✅ Sinkronisasi database history selesai.")