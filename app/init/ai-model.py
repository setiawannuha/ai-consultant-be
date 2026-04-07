import sys
import os
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from sklearn.preprocessing import MinMaxScaler
import joblib
import time

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

def build_model(input_shape):
    # Output_days diubah menjadi 1 sesuai permintaan
    model = Sequential([
        Input(shape=input_shape),
        LSTM(64, return_sequences=True),
        Dropout(0.2), # 20% neuron dimatikan untuk mencegah overfitting
        LSTM(128, return_sequences=False),
        Dropout(0.1), # 10% neuron dimatikan untuk mencegah overfitting
        Dense(32, activation='relu'),
        Dense(1) # Memprediksi hanya 1 nilai (Close price besok)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
    return model

def calculate_accuracy(actual, pred):
    # Menggunakan MAPE (Mean Absolute Percentage Error) untuk akurasi dalam %
    mape = np.mean(np.abs((actual - pred) / actual))
    return max(0, (1 - mape) * 100)

def train_stock_model(symbol):
    db = db_provider.get_database()
    query = {
        "symbol": symbol,
        "date_key": { "$ne": None },
        "date": { "$ne": None },
        "adj_close": { "$ne": None },
        "close": { "$ne": None },
        "high": { "$ne": None },
        "low": { "$ne": None },
        "open": { "$ne": None },
        "volume": { "$ne": None },
        "ma5": { "$ne": None },
        "ma20": { "$ne": None },
        "ema10": { "$ne": None },
        "rsi": { "$ne": None },
        "macd": { "$ne": None },
        "macd_signal": { "$ne": None },
        "macd_hist": { "$ne": None },
        "stoch_k": { "$ne": None },
        "stoch_d": { "$ne": None },
        "bb_upper": { "$ne": None },
        "bb_middle": { "$ne": None },
        "bb_lower": { "$ne": None },
        "mfi": { "$ne": None },
        "obv": { "$ne": None },
        "volume_ma": { "$ne": None }
    }
    cursor = db["stock_history"].find(query).sort("date", 1)
    df = pd.DataFrame(list(cursor))
    
    if df.empty or len(df) < 100: 
        print(f"⚠️ Data {symbol} tidak cukup untuk training.")
        return

    # --- FEATURE SELECTION ---
    # Kita gunakan field yang sudah Anda simpan sebelumnya di database
    features = [
        'close', 'open', 'high', 'low', 'volume', 
        'ema10', 'ma20', 'rsi', 'macd_hist', 
        'stoch_k', 'mfi', 'bb_upper', 'bb_lower'
    ]
    
    # Pastikan tidak ada data null di kolom fitur yang dipilih
    df = df.dropna(subset=features)
    dataset = df[features].values
    
    # Scaler untuk semua fitur
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(dataset)

    X, y = [], []
    lookback_days = 20 # Melihat 20 hari ke belakang
    
    # Target adalah kolom 'close' (indeks 0 dalam list features)
    target_col_index = 0 

    for i in range(lookback_days, len(scaled_data) - 1):
        # Input: Data 20 hari terakhir (semua fitur)
        X.append(scaled_data[i-lookback_days:i, :])
        # Target: Harga 'close' 1 hari ke depan (H+1)
        y.append(scaled_data[i, target_col_index])

    X, y = np.array(X), np.array(y)

    # Split data (80% Train, 20% Test)
    split = int(len(X) * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    print(f"🔄 Training {symbol} dengan {len(features)} fitur...")
    model = build_model((X_train.shape[1], X_train.shape[2]))
    
    # Training dengan Early Stopping agar tidak overfitting
    callback = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True)
    model.fit(
        X_train, 
        y_train, 
        batch_size=32, 
        epochs=20, 
        verbose=1,
        validation_split=0.2,
        callbacks=[callback]
    )

    # --- EVALUASI ---
    predictions_scaled = model.predict(X_test, verbose=0)
    
    # Inverse transform untuk mendapatkan harga asli dalam Rupiah
    # Kita butuh dummy array karena scaler diekspektasi punya jumlah kolom yang sama (13 kolom)
    def inverse_val(scaled_val):
        dummy = np.zeros((len(scaled_val), len(features)))
        dummy[:, target_col_index] = scaled_val.flatten()
        return scaler.inverse_transform(dummy)[:, target_col_index]

    actual_prices = inverse_val(y_test)
    pred_prices = inverse_val(predictions_scaled)

    accuracy = calculate_accuracy(actual_prices, pred_prices)

    # Simpan Model & Scaler (Penting: Scaler harus disimpan untuk prediksi nantinya)
    model_dir = f"app/ai-models/{symbol.replace('.', '_')}"
    os.makedirs(model_dir, exist_ok=True)

    # 1. Simpan Model Keras
    model.save(f"{model_dir}/model.keras")
    
    # 2. Simpan Scaler (WAJIB!)
    scaler_filename = f"{model_dir}/scaler.joblib"
    joblib.dump(scaler, scaler_filename)
    
    # (Opsional) Simpan metadata akurasi
    print(f"✅ {symbol} Done | Akurasi H+1: {accuracy:.2f}%")
    tf.keras.backend.clear_session()

if __name__ == "__main__":
    symbols = load_symbols()
    for s in symbols:
        train_stock_model(s)
        time.sleep(2)