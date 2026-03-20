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
        """Helper untuk menentukan status berdasarkan skor MFI"""
        if score >= 80: return "Overbought"
        elif score <= 20: return "Oversold"
        else: return "Netral"

    def _determine_action(self, last_price, fair_price, mfi_status, rsi_score, macd_hist, ai_pred_h1):
        """
        Logika Pengambilan Keputusan yang diperluas:
        - STRONG BUY: Murah + Oversold (MFI/RSI) + MACD Momentum Positif + AI Naik
        - SELL: Mahal + Overbought + MACD Momentum Negatif
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
            return {"message": f"Profile {symbol} tidak ditemukan"}

        limit = 120 
        all_history = self.history_repo.find(symbol, limit=limit)
        if not all_history or len(all_history) < limit:
            return {"message": "Data history tidak cukup (minimal 80)"}

        # 3. Proses DataFrame & Indikator
        df = pd.DataFrame(all_history).sort_values('Date', ascending=True).reset_index(drop=True)
        
        # Kalkulasi via TechnicalIndicatorService (TI)
        df['MFI'] = TI.calculate_mfi(df)
        df['MA5'] = TI.calculate_ma(df, 5)
        df['MA20'] = TI.calculate_ma(df, 20)
        df['RSI'] = TI.calculate_rsi(df, 14)
        df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = TI.calculate_macd(df)
        
        # Bersihkan NaN dari MFI agar scaler tidak error
        df = df.dropna(subset=['MFI']).reset_index(drop=True)

        # 4. Prediksi AI
        model = self.predict_service.get_model(symbol)
        scaler = MinMaxScaler(feature_range=(0, 1))
        features = ['Open', 'High', 'Low', 'Close', 'Volume', 'MFI']
        scaler.fit(df[features].values)
        
        batch_predictions = self.predict_service.predict_batch(model, df, scaler) if model else {}

        # 5. Mapping Response
        df_display = df.tail(30).copy()
        history_response = []
        fair_price_graham = float(prof.get('FairPriceGraham', 0) or 0)

        for i, row in df_display.iterrows():
            pred = batch_predictions.get(i)
            mfi_score = float(row['MFI'] or 0)
            rsi_score = float(row['RSI'] or 0)
            macd_hist = float(row['MACD_Hist'] or 0)
            
            mfi_status = self._get_mfi_status(mfi_score)
            ai_h1 = pred['H1'] if pred else None
            
            action = self._determine_action(
                row['Close'], fair_price_graham, mfi_status, rsi_score, macd_hist, ai_h1
            )

            history_response.append({
                "Symbol": row['Symbol'],
                "Date": row['Date'],
                "High": row['High'],
                "Low": row['Low'],
                "Close": row['Close'],
                "Volume": row['Volume'],
                "Indicators": {
                    "MA5": round(row['MA5'], 2) if not pd.isna(row['MA5']) else None,
                    "MA20": round(row['MA20'], 2) if not pd.isna(row['MA20']) else None,
                    "RSI": round(rsi_score, 2),
                    "MACD": {
                        "Line": round(row['MACD'], 2) if not pd.isna(row['MACD']) else None,
                        "Signal": round(row['MACD_Signal'], 2) if not pd.isna(row['MACD_Signal']) else None,
                        "Hist": round(macd_hist, 2)
                    },
                    "MFI": {
                        "Score": round(mfi_score, 2),
                        "Status": mfi_status
                    }
                },
                "Analysis": {
                    "FairPriceGraham": fair_price_graham,
                    "IsCheap": row['Close'] < fair_price_graham,
                    "Action": action
                },
                "Prediction": {"Close": pred} if pred else None
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
                    "Date": "Next Trading Day",
                    "Analysis": {
                        "Action": "PREDICTION ONLY"
                    },
                    "Prediction": {"Close": future_pred}
                })

        result = {
            "Profile": prof,
            "History": history_response
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
        return [self.get_detail(p['Symbol']) for p in profiles]