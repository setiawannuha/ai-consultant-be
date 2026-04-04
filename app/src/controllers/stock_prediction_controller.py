import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler

# Import internal services/utils
from src.utils.technical_indicators import TechnicalIndicatorService as TI
from src.services.prediction_service import PredictionService
from src.repositories.stock_history_repository import StockHistoryRepository
from src.repositories.stock_profile_repository import StockProfileRepository
from connection.redis import redis_provider

class StockPredictionController:
    def __init__(self):
        self.history_repo = StockHistoryRepository()
        self.profile_repo = StockProfileRepository()
        self.predict_service = PredictionService()
        self.redis = redis_provider.get_client()

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

    def _determine_action(self, last_price, fair_price, mfi_status, rsi_score, macd_hist, ai_pred_h1):
        """
        Logika Pengambilan Keputusan yang diperluas:
        - STRONG BUY: Murah + Oversold (mfi/rsi) + macd Momentum Positif + AI Naik
        - SELL: Mahal + Overbought + macd Momentum Negatif
        """
        is_cheap = last_price < fair_price
        ai_trend_up = ai_pred_h1 > last_price if ai_pred_h1 else False
        macd_positive = macd_hist > 0 if not pd.isna(macd_hist) else False
        
        if is_cheap:
            if (mfi_status == "Oversold" or rsi_score < 30) and ai_trend_up and macd_positive:
                return "STRONG BUY"
            elif mfi_status == "Overbought" or rsi_score > 70:
                return "HOLD" 
            else:
                return "WAIT / ACCUMULATE"
        else:
            if (mfi_status == "Overbought" or rsi_score > 70) and not macd_positive:
                return "SELL"
            else:
                return "HOLD"

    def get_detail(self, symbol: str):
        # 1. Cek Cache Redis
        cache_key = f"stock_detail:{symbol}"
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                print(f"🚀 [REDIS] Cache Hit: {symbol}")
                return json.loads(cached_data)
        except Exception as e:
            print(f"⚠️ Redis Error: {e}")

        # 2. Ambil Data Dasar
        prof = self.profile_repo.find_one(symbol)
        if not prof:
            return {"message": f"profile {symbol} tidak ditemukan"}

        limit = 120 
        all_history = self.history_repo.find(symbol, limit=limit)
        if not all_history or len(all_history) < limit:
            return {"message": "Data history tidak cukup (minimal 80)"}

        # 3. Proses DataFrame & Indikator
        df = pd.DataFrame(all_history).sort_values('date', ascending=True).reset_index(drop=True)
        
        # Kalkulasi via TechnicalIndicatorService (TI)
        df['mfi'] = TI.calculate_mfi(df)
        df['ma5'] = TI.calculate_ma(df, 5)
        df['ma20'] = TI.calculate_ma(df, 20)
        df['rsi'] = TI.calculate_rsi(df, 14)
        df['macd'], df['macd_signal'], df['macd_hist'] = TI.calculate_macd(df)
        
        # Bersihkan NaN dari mfi agar scaler tidak error
        df = df.dropna(subset=['mfi']).reset_index(drop=True)

        # 4. Prediksi AI
        model = self.predict_service.get_model(symbol)
        scaler = MinMaxScaler(feature_range=(0, 1))
        features = ['open', 'high', 'low', 'close', 'volume', 'mfi']
        scaler.fit(df[features].values)
        
        batch_predictions = self.predict_service.predict_batch(model, df, scaler) if model else {}

        # 5. Mapping Response
        df_display = df.tail(30).copy()
        history_response = []
        fair_price_graham = float(prof.get('fair_price_graham', 0) or 0)

        for i, row in df_display.iterrows():
            pred = batch_predictions.get(i)
            mfi_score = float(row['mfi'] or 0)
            rsi_score = float(row['rsi'] or 0)
            macd_hist = float(row['macd_hist'] or 0)
            
            mfi_status = self._get_mfi_status(mfi_score)
            ai_h1 = pred['h1'] if pred else None
            
            action = self._determine_action(
                row['close'], fair_price_graham, mfi_status, rsi_score, macd_hist, ai_h1
            )

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
                    "macd": {
                        "line": round(row['macd'], 2) if not pd.isna(row['macd']) else None,
                        "signal": round(row['macd_signal'], 2) if not pd.isna(row['macd_signal']) else None,
                        "hist": round(macd_hist, 2)
                    },
                    "mfi": {
                        "score": round(mfi_score, 2),
                        "status": mfi_status
                    }
                },
                "analysis": {
                    "fair_price_graham": fair_price_graham,
                    "is_cheap": row['close'] < fair_price_graham,
                    "action": action
                },
                "prediction": {"close": pred} if pred else None
            })

        # 6. Prediksi Masa Depan (Next Day)
        if model is not None:
            last_60 = df.tail(60)
            # Re-use predict_batch atau buat fungsi simple di service untuk 1 window
            future_pred_results = self.predict_service.predict_batch(model, last_60.reset_index(), scaler)
            # Ambil prediksi terakhir dari window terakhir
            future_key = list(future_pred_results.keys())[-1] if future_pred_results else None
            future_pred = future_pred_results[future_key] if future_key else None

            if future_pred:
                history_response.append({
                    "date": "Next Trading Day",
                    "analysis": {
                        "action": "PREDICTION ONLY"
                    },
                    "prediction": {"close": future_pred}
                })

        result = {
            "profile": prof,
            "history": history_response
        }

        # 7. Simpan ke Redis
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