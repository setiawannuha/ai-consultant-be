import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# Path connection
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider

# Cache untuk nilai kurs agar tidak fetch berulang kali dalam satu sesi
CURRENCY_CACHE = {"IDR": 1.0}

def load_symbols(filename="symbols.txt"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)
    if not os.path.exists(file_path):
        print(f"❌ File {file_path} tidak ditemukan!")
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]

def get_exchange_rate(from_currency):
    """Mendapatkan kurs dari from_currency ke IDR"""
    if from_currency == "IDR" or not from_currency:
        return 1.0
    
    if from_currency in CURRENCY_CACHE:
        return CURRENCY_CACHE[from_currency]
    
    try:
        ticker_name = f"{from_currency}IDR=X"
        rate_data = yf.Ticker(ticker_name)
        # Ambil harga closing terakhir
        rate = rate_data.history(period="1d")['Close'].iloc[-1]
        CURRENCY_CACHE[from_currency] = rate
        print(f"💱 Kurs 1 {from_currency} = {rate:,.2f} IDR")
        return rate
    except:
        print(f"⚠️ Gagal kurs {from_currency}, gunakan asumsi 1.0")
        return 1.0

def get_val(df, labels):
    if df is None or df.empty:
        return None
    for label in labels:
        if label in df.index:
            val = df.loc[label].iloc[0]
            if pd.notnull(val):
                return float(val)
    return None

def sync_company_profiles():
    symbols = load_symbols()
    if not symbols: return

    db = db_provider.get_database()
    collection = db["stock_profiles"]
    collection.create_index("Symbol", unique=True)

    for symbol in symbols:
        print(f"--- Fetching: {symbol} ---")
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # 1. Identifikasi Mata Uang
            original_currency = info.get('financialCurrency', 'IDR')
            rate = get_exchange_rate(original_currency)

            # 2. Ambil Data Laporan Keuangan
            income_stmt = ticker.financials 
            balance_sheet = ticker.balance_sheet

            # 3. Ekstraksi Data (Mentah)
            shares = info.get("sharesOutstanding")
            raw_revenue = info.get('totalRevenue')
            raw_price = info.get('currentPrice') or info.get('regularMarketPrice')
            raw_eps = info.get('trailingEps') or info.get('forwardEps')
            raw_pbv = info.get('priceToBook') / rate

            raw_net_profit = get_val(income_stmt, ['Net Income', 'Net Income Common Stockholders'])
            if raw_net_profit is None:
                if raw_eps is not None and shares is not None:
                    raw_net_profit = raw_eps * shares

            raw_equity = get_val(balance_sheet, ['Stockholders Equity', 'Total Equity Gross Minority Interest'])
            if raw_equity is None:
                bvps = info.get("bookValue")
                if bvps is not None and shares is not None:
                    raw_equity = bvps * shares
            
            # Fallback BVPS
            raw_bvps = None
            if raw_equity and shares:
                raw_bvps = raw_equity / shares
            else:
                raw_bvps = info.get('bookValue')

            # 4. KONVERSI KE IDR (Hanya jika rate != 1.0)
            revenue = raw_revenue * rate if raw_revenue else None
            net_profit = raw_net_profit * rate if raw_net_profit else None
            total_equity = raw_equity * rate if raw_equity else None
            last_price = raw_price
            eps = raw_eps
            bvps = raw_bvps * rate if raw_bvps else None
            market_cap = info.get('marketCap')
            pbv = raw_pbv or (last_price / raw_bvps if last_price and raw_bvps else None)

            # 5. Kalkulasi Harga Wajar (Setelah Konversi ke IDR agar apel ke apel)
            fair_price = None
            mos = None
            if eps and bvps and eps > 0 and bvps > 0:
                fair_price = (22.5 * eps * bvps) ** 0.5
                if last_price:
                    mos = (fair_price - last_price) / fair_price

            profile_data = {
                "Symbol": symbol,
                "ShortName": info.get('shortName'),
                "OriginalCurrency": original_currency,
                "ExchangeRateToIDR": rate,
                
                # Data dalam IDR
                "LastPrice": last_price,
                "MarketCap": market_cap,
                "TotalRevenue": revenue,
                "NetProfit": net_profit,
                "TotalEquity": total_equity,
                "EPS": eps,
                "BVPS": bvps,
                "FairPriceGraham": fair_price,
                
                # Ratios (Rasio tetap sama, tidak terpengaruh konversi mata uang)
                "PER": info.get('trailingPE'),
                "PBV": pbv,
                "MarginOfSafety": mos,
                "DividendYield": info.get('dividendYield'),
                
                "LastUpdated": datetime.now()
            }

            collection.update_one({"Symbol": symbol}, {"$set": profile_data}, upsert=True)
            print(f"✅ {symbol} Updated. Revenue: {revenue}, Profit: {net_profit}")
            print(f"✅ {symbol} ({original_currency} -> IDR). Price: {last_price:,.0f}")
            time.sleep(3)

        except Exception as e:
            print(f"❌ Error {symbol}: {e}")

if __name__ == "__main__":
    sync_company_profiles()