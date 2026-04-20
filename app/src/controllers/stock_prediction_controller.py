import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
import joblib
import os

# Import internal services/utils
from src.services.prediction_service import PredictionService
from src.repositories.stock_history_repository import StockHistoryRepository
from src.repositories.stock_profile_repository import StockProfileRepository
from connection.redis import redis_provider

use_prediction = False
class StockPredictionController:
    def __init__(self):
        self.history_repo = StockHistoryRepository()
        self.profile_repo = StockProfileRepository()
        self.predict_service = PredictionService()
        self.redis = redis_provider.get_client()
        self.features = [
            'close', 'open', 'high', 'low', 'volume', 
            'ema10', 'ma20', 'rsi', 'macd_hist', 
            'stoch_k', 'mfi', 'bb_upper', 'bb_lower'
        ]

    def _get_seconds_until_midnight(self):
        """Menghitung sisa detik sampai jam 23:59:59 hari ini untuk TTL Redis"""
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        return int((midnight - now).total_seconds())

    def _get_mfi_status(self, score):
        """Helper untuk menentukan status berdasarkan skor mfi"""
        if score >= 80: return "Overbought"
        elif score <= 20: return "Oversold"
        else: return "Netral"

    def _get_scaler(self, symbol: str):
        symbol_path = symbol.replace('.', '_')
        scaler_path = f"app/ai-models/{symbol_path}/scaler.joblib"
        if os.path.exists(scaler_path):
            return joblib.load(scaler_path)
        return None

    def get_detail(self, symbol: str):
        # 1. Cek Cache Redis
        cache_key = f"stock_detail:{symbol}"
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            print(f"⚠️ Redis Error: {e}")

        # 2. Ambil Data Dasar
        prof = self.profile_repo.find_one(symbol)
        if not prof: return {"message": f"profile {symbol} tidak ditemukan"}

        limit = 120 
        all_history = self.history_repo.find(symbol, limit=limit)
        if not all_history or len(all_history) < 80:
            return {"message": "Data history tidak cukup"}

        # 3. Proses DataFrame
        df = pd.DataFrame(all_history).sort_values('date', ascending=True).reset_index(drop=True)
        df = df.dropna(subset=self.features).reset_index(drop=True)

        # 4. Load Model & Scaler
        model = self.predict_service.get_model(symbol)
        scaler = self._get_scaler(symbol)
        if not use_prediction:
            model = None
            scaler = None
        
        # 5. Mapping Response (Looping 30 hari terakhir)
        df_display = df.tail(30).copy()
        history_response = []
        fair_price_graham = float(prof.get('fair_price_graham', 0) or 0)
        lookback = 22 # Sesuaikan dengan lookback_days training

        for i, row in df_display.iterrows():
            # Logika Prediksi untuk baris ini
            ai_h1 = None
            if not use_prediction:
                ai_h1 = 0
            if model and scaler and i >= lookback:
                try:
                    # Ambil window data sebelum hari ini untuk prediksi besoknya
                    window_data = df[self.features].iloc[i-lookback:i].values
                    scaled_window = scaler.transform(window_data)
                    pred_raw = model.predict(np.array([scaled_window]), verbose=0)
                    
                    # Inverse transform
                    dummy = np.zeros((1, len(self.features)))
                    dummy[0, 0] = pred_raw[0, 0]
                    ai_h1 = float(scaler.inverse_transform(dummy)[0, 0])
                except Exception: ai_h1 = None

            mfi_score = float(row['mfi'] or 0)
            rsi_score = float(row['rsi'] or 0)
            macd_hist = float(row['macd_hist'] or 0)
            mfi_status = self._get_mfi_status(mfi_score)

            history_response.append({
                "symbol": row['symbol'],
                "date": row['date'],
                "high": row['high'],
                "low": row['low'],
                "close": row['close'],
                "volume": row['volume'],
                "indicators": {
                    "ma5": round(row['ma5'], 2) if not pd.isna(row['ma5']) else None,
                    "ma20": round(row['ma20'], 2) if not pd.isna(row['ma20']) else None,
                    "rsi": round(rsi_score, 2),
                    "ema10": round(row['ema10'], 2),
                    "bb_upper": round(row['bb_upper'], 2),
                    "bb_middle": round(row['bb_middle'], 2),
                    "bb_lower": round(row['bb_lower'], 2),
                    "macd": {
                        "line": round(row['macd'], 2) if not pd.isna(row['macd']) else None,
                        "signal": round(row['macd_signal'], 2) if not pd.isna(row['macd_signal']) else None,
                        "hist": round(macd_hist, 2)
                    },
                    "mfi": { "score": round(mfi_score, 2), "status": mfi_status }
                },
                "analysis": {
                    "fair_price_graham": fair_price_graham,
                    "is_cheap": row['close'] < fair_price_graham,
                },
                "prediction": {"close": {
                    "h1": round(ai_h1, 2) if ai_h1 is not None else None
                }} if ai_h1 is not None else None
            })

        # 6. Prediksi Masa Depan (H+1 dari data terakhir)
        if model and scaler and len(df) >= lookback:
            last_window = df[self.features].tail(lookback).values
            scaled_last = scaler.transform(last_window)
            f_pred_raw = model.predict(np.array([scaled_last]), verbose=0)
            
            dummy_f = np.zeros((1, len(self.features)))
            dummy_f[0, 0] = f_pred_raw[0, 0]
            future_val = float(scaler.inverse_transform(dummy_f)[0, 0])

            history_response.append({
                "date": "Next Trading Day",
                "prediction": {"close": {"h1": round(future_val, 2)}}
            })
        elif not use_prediction:
            history_response.append({
                "date": "Next Trading Day",
                "prediction": {"close": {"h1": 0}}
            })

        result = { "profile": prof, "history": history_response }
        self._save_to_cache(cache_key, result)
        return result

    def _save_to_cache(self, key, data):
        def datetime_handler(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            elif pd.isna(obj):
                return None
            raise TypeError(f"Object {type(obj)} not serializable")

        try:
            ttl = self._get_seconds_until_midnight()
            json_data = json.dumps(data, default=datetime_handler)
            self.redis.setex(key, ttl, json_data)
        except Exception as e:
            print(f"⚠️ Redis Save Error: {e}")

    def get_list(self):
        # Implementasi get_list bisa memanggil get_detail untuk tiap simbol
        # atau disederhanakan sesuai kebutuhan profil
        profiles = self.profile_repo.find_all()
        return [self.get_detail(p['symbol']) for p in profiles]