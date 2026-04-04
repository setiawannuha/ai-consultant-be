# INIT MODEL AI

import sys
import os
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.layers import Input
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime

# Setup Path agar bisa load connection
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider


def load_symbols(filename="symbols.txt"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, filename)
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def calculate_mfi(df, period=20):
    """Menghitung Money Flow Index (MFI)"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['volume']
    
    positive_flow = []
    negative_flow = []
    
    for i in range(1, len(typical_price)):
        if typical_price[i] > typical_price[i-1]:
            positive_flow.append(money_flow[i])
            negative_flow.append(0)
        else:
            positive_flow.append(0)
            negative_flow.append(money_flow[i])
            
    # Convert ke series untuk rolling sum
    pos_res = pd.Series(positive_flow).rolling(window=period).sum()
    neg_res = pd.Series(negative_flow).rolling(window=period).sum()
    
    mfr = pos_res / neg_res
    mfi = 100 - (100 / (1 + mfr))
    
    # Pad dengan NaN di awal agar panjangnya sama dengan dataframe original
    mfi_final = np.pad(mfi.values, (1, 0), mode='constant', constant_values=np.nan)
    return mfi_final


def get_mfi_status(mfi_value):
    if mfi_value >= 80: return "Overbought"
    elif mfi_value <= 20: return "Oversold"
    else: return "Netral"


def build_model(input_shape, output_days=3):
    model = Sequential([
        Input(shape=input_shape),
        LSTM(64, return_sequences=True),
        Dropout(0.2),
        LSTM(64, return_sequences=False),
        Dropout(0.2),
        Dense(32),
        Dense(output_days) # Output diubah menjadi 3 (H+1, H+2, H+3)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
    return model

def calculate_accuracy(actual, pred):
    mape = np.mean(np.abs((actual - pred) / actual))
    return (1 - mape) * 100

def train_stock_model(symbol):
    db = db_provider.get_database()
    cursor = db["stock_history"].find({"symbol": symbol}).sort("date", 1)
    df = pd.DataFrame(list(cursor))
    
    if df.empty: return

    df['mfi'] = calculate_mfi(df, period=20)
    df.dropna(subset=['mfi'], inplace=True)
    
    # Butuh data lebih banyak karena kita memprediksi hingga 3 hari ke depan
    # i + 60 (lookback) + 3 (target) = minimal 63 baris data bersih
    if len(df) <= 65:
        print(f"⚠️ Data {symbol} tidak cukup.")
        return

    features = ['open', 'high', 'low', 'close', 'volume', 'mfi']
    dataset = df[features].values
    
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(dataset)

    X, y = [], []
    prediction_days = 60 # Lookback tetap 60 hari
    target_days = 3      # Kita ingin memprediksi 3 hari ke depan

    for i in range(prediction_days, len(scaled_data) - target_days):
        # Input: 60 hari terakhir
        X.append(scaled_data[i-prediction_days:i, :])
        
        # Target: Ambil kolom 'close' (index 3) untuk 3 hari ke depan
        # scaled_data[i, 3]     -> Hari ke-1 (Besok)
        # scaled_data[i+1, 3]   -> Hari ke-2 (Lusa)
        # scaled_data[i+2, 3]   -> Hari ke-3 (Tulat)
        y.append([scaled_data[i, 3], scaled_data[i+1, 3], scaled_data[i+2, 3]])

    X, y = np.array(X), np.array(y)

    split = int(len(X) * 0.75)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = build_model((X_train.shape[1], X_train.shape[2]), output_days=target_days)
    model.fit(X_train, y_train, batch_size=32, epochs=15, verbose=0)

    # --- EVALUASI PER HARI ---
    predictions = model.predict(X_test, verbose=0)

    def inverse_transform_target(scaled_array, target_index=0):
        res = []
        for val in scaled_array:
            dummy = np.zeros((1, 6))
            dummy[0, 3] = val  # Index 3 adalah 'close'
            res.append(scaler.inverse_transform(dummy)[0, 3])
        return np.array(res)
    
    actual_h1 = inverse_transform_target(y_test[:, 0])
    pred_h1 = inverse_transform_target(predictions[:, 0])

    actual_h2 = inverse_transform_target(y_test[:, 1])
    pred_h2 = inverse_transform_target(predictions[:, 1])

    actual_h3 = inverse_transform_target(y_test[:, 2])
    pred_h3 = inverse_transform_target(predictions[:, 2])

    acc_h1 = calculate_accuracy(actual_h1, pred_h1)
    acc_h2 = calculate_accuracy(actual_h2, pred_h2)
    acc_h3 = calculate_accuracy(actual_h3, pred_h3)

    # Simpan Model
    model_path = os.path.join('app', 'ai-models', symbol.replace('.', '_'))
    if not os.path.exists(model_path): os.makedirs(model_path)
    model.save(os.path.join(model_path, 'model.keras'))

    print(f"\n📊 Real Result for {symbol} (Rupiah Based):")
    print(f"1. Akurasi Prediksi Besok (H+1): {acc_h1:.2f}%")
    print(f"2. Akurasi Prediksi Lusa  (H+2): {acc_h2:.2f}%")
    print(f"3. Akurasi Prediksi Tulat (H+3): {acc_h3:.2f}%")
    
    avg_acc = (acc_h1 + acc_h2 + acc_h3) / 3
    if avg_acc >= 90:
        print(f"✅ Status: LOLOS (Avg: {avg_acc:.2f})")
    else:
        print(f"❌ Status: TIDAK LOLOS (Avg: {avg_acc:.2f})")


if __name__ == "__main__":
    symbols = load_symbols()
    print(f"🤖 Memulai proses AI Training untuk {len(symbols)} saham...")
    for s in symbols:
        train_stock_model(s)