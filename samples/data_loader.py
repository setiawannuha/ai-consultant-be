import yfinance as yf
import pandas as pd

def get_stock_data(ticker, start_date, end_date):
    """
    Mengambil data saham dari Yahoo Finance
    """
    print(f"Mengambil data untuk {ticker}...")
    
    # Download data
    data = yf.download(ticker, start=start_date, end=end_date)
    
    if data.empty:
        print("Data tidak ditemukan. Periksa ticker atau rentang tanggal.")
        return None
    
    return data

# Contoh penggunaan
ticker_symbol = "BBCA.JK" # Anda bisa ganti dengan BBCA.JK untuk BCA atau lainnya
start = "2015-01-01"
end = "2023-12-31"

df = get_stock_data(ticker_symbol, start, end)

# Tampilkan 5 data teratas
print(df.head())