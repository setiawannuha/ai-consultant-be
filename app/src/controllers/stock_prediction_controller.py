import os
import numpy as np
import pandas as pd
import json
from datetime import datetime, timedelta
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
from src.repositories.stock_history_repository import StockHistoryRepository
from src.repositories.stock_profile_repository import StockProfileRepository
from connection.redis import redis_provider
from pathlib import Path

class StockPredictionController:
    def __init__(self):
        self.history_repo = StockHistoryRepository()
        self.profile_repo = StockProfileRepository()
        self.redis = redis_provider.get_client()
        self._model_cache = {} 

    def _get_seconds_until_midnight(self):
        """Menghitung sisa detik sampai jam 23:59:59 hari ini"""
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        return int((midnight - now).total_seconds())

    def _get_model(self, symbol):
        if symbol in self._model_cache:
            return self._model_cache[symbol]

        model_folder = symbol.replace('.', '_')
        current_file = Path(__file__).resolve()
        project_root = current_file.parents[3] 
        model_path = project_root / 'app' / 'ai-models' / model_folder / 'model.keras'

        if model_path.exists():
            try:
                print(f"📡 Memuat model dari disk ke RAM: {symbol}")
                model = load_model(str(model_path))
                self._model_cache[symbol] = model
                return model
            except Exception as e:
                print(f"❌ Error loading model: {e}")
                return None
        return None

    def _calculate_mfi(self, df, period=20):
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        mf = tp * df['Volume']
        delta = tp.diff()
        pos_mf = pd.Series(
            np.where(delta > 0, mf, 0),
            index=df.index
        )
        neg_mf = pd.Series(
            np.where(delta < 0, mf, 0),
            index=df.index
        )
        pos_sum = pos_mf.rolling(window=period, min_periods=period).sum()
        neg_sum = neg_mf.rolling(window=period, min_periods=period).sum()
        mfr = pos_sum / (neg_sum + 1e-10)
        mfi = 100 - (100 / (1 + mfr))
        return mfi

    def _predict_sequence(self, model, df_subset, scaler):
        """Melakukan prediksi berdasarkan potongan dataframe 60 hari"""
        features = ['Open', 'High', 'Low', 'Close', 'Volume', 'MFI']
        input_data = df_subset[features].values
        
        # Scaling berdasarkan data 60 hari tersebut
        scaled_input = scaler.transform(input_data)
        X_input = np.array([scaled_input])
        
        prediction_scaled = model.predict(X_input, verbose=0)
        
        res = []
        for i in range(3):
            dummy = np.zeros((1, 6))
            dummy[0, 3] = prediction_scaled[0, i]
            res.append(float(scaler.inverse_transform(dummy)[0, 3]))
        
        return {"H1": res[0], "H2": res[1], "H3": res[2]}
    
    def _get_mfi_status(self, score):
        """Helper untuk menentukan status berdasarkan skor MFI"""
        if score >= 80:
            return "Overbought"
        elif score <= 20:
            return "Oversold"
        else:
            return "Netral"
        
    def _determine_action(self, last_price, fair_price, mfi_status, ai_pred_h1):
        """
        Logika Pengambilan Keputusan:
        1. STRONG BUY: Harga < Graham (Murah) DAN MFI Oversold DAN AI Prediksi Naik
        2. WAIT / WEAK BUY: Harga < Graham (Murah) TAPI MFI Netral/Overbought
        3. HOLD: Harga di sekitar Graham ATAU AI Prediksi Turun padahal MFI bagus
        4. SELL: Harga > Graham (Mahal) DAN MFI Overbought
        """
        is_cheap = last_price < fair_price
        ai_trend_up = ai_pred_h1 > last_price if ai_pred_h1 else False
        
        if is_cheap:
            if mfi_status == "Oversold" and ai_trend_up:
                return "STRONG BUY"
            elif mfi_status == "Overbought":
                return "HOLD" # Murah tapi sudah lari kencang, jangan kejar
            else:
                return "WAIT"
        else:
            if mfi_status == "Overbought":
                return "SELL"
            else:
                return "HOLD"

    def get_detail(self, symbol: str):
        # 1. Cek Cache Redis Terlebih Dahulu
        cache_key = f"stock_detail:{symbol}"
        try:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                print(f"🚀 [REDIS] Mengambil data cache untuk {symbol}")
                return json.loads(cached_data)
        except Exception as e:
            print(f"⚠️ Redis Error: {e}")

        # 2. Jika tidak ada di cache, jalankan kalkulasi berat
        prof = self.profile_repo.find_one(symbol)
        all_history = self.history_repo.find(symbol)
        
        if not all_history or len(all_history) < 80:
            return {"message": "Data history tidak cukup (minimal 80)"}

        df = pd.DataFrame(all_history)
        df = df.sort_values('Date', ascending=True)
        df['MFI'] = self._calculate_mfi(df)
        df = df.dropna(subset=['MFI']).reset_index(drop=True)

        fair_price_graham = prof.get('FairPriceGraham', 0)
        model = self._get_model(symbol)
        history_response = []
        
        scaler = MinMaxScaler(feature_range=(0, 1))
        features = ['Open', 'High', 'Low', 'Close', 'Volume', 'MFI']
        scaler.fit(df[features].values)

        df_list = df.to_dict('records')
        
        for i in range(len(df_list)):
            current_row = df_list[i].copy()
            prediction = None
            last_price = current_row['Close']
            mfi_score = float(current_row['MFI'])
            mfi_status = self._get_mfi_status(mfi_score)

            if model is not None and i >= 60:
                df_subset = df.iloc[i-60:i]
                if len(df_subset) == 60:
                    prediction = self._predict_sequence(model, df_subset, scaler)
            
            ai_h1 = prediction['H1'] if prediction else None
            action = "HOLD"
            if prediction:
                action = self._determine_action(last_price, fair_price_graham, mfi_status, ai_h1)

            history_response.append({
                "Symbol": current_row['Symbol'],
                "Date": current_row['Date'],
                "High": current_row['High'],
                "Low": current_row['Low'],
                "Close": last_price,
                "Volume": current_row['Volume'],
                "MFI": {
                    "Score": round(mfi_score, 2),
                    "Status": mfi_status,
                    "FairPriceGraham": round(fair_price_graham, 2),
                    "IsCheap": last_price < fair_price_graham,
                    "Action": action
                },
                "Prediction": {"Close": prediction} if prediction else None
            })

        if model is not None:
            last_60 = df.tail(60)
            future_pred = self._predict_sequence(model, last_60, scaler)
            last_close = df['Close'].iloc[-1]
            last_mfi_score = float(df['MFI'].iloc[-1])
            last_mfi_status = self._get_mfi_status(last_mfi_score)
            future_action = self._determine_action(last_close, fair_price_graham, last_mfi_status, future_pred['H1'])

            history_response.append({
                "Date": "Next Trading Day",
                "High": None, "Low": None, "Close": None, "Volume": None,
                "MFI": {
                    "Score": round(last_mfi_score, 2),
                    "Status": last_mfi_status,
                    "FairPriceGraham": round(fair_price_graham, 2),
                    "Action": future_action
                },
                "Prediction": {"Close": future_pred}
            })

        result = {
            "Profile": prof,
            "History": history_response
        }

        # 3. Simpan Hasil ke Redis dengan TTL sampai tengah malam
        def datetime_handler(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        try:
            ttl = self._get_seconds_until_midnight()
            json_data = json.dumps(result, default=datetime_handler)
            self.redis.setex(cache_key, ttl, json_data)
            print(f"💾 [REDIS] Data {symbol} disimpan. Kedaluwarsa dalam {ttl} detik.")
        except Exception as e:
            print(f"⚠️ Gagal menyimpan ke Redis: {e}")

        return result

    def get_list(self):
        # Untuk get_list, kita simpan cache-nya juga secara global (opsional)
        cache_key = "stock_list:all"
        cached_list = self.redis.get(cache_key)
        if cached_list:
            return json.loads(cached_list)

        profiles = self.profile_repo.find_all()
        response = []

        for prof in profiles:
            detail = self.get_detail(prof['Symbol'])
            if "History" in detail:
                detail['History'] = detail['History'][-30:]
                response.append(detail)
        
        # Simpan cache list dengan TTL yang sama
        self.redis.setex(cache_key, self._get_seconds_until_midnight(), json.dumps(response))
        return response