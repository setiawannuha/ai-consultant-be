import numpy as np
from pathlib import Path
from tensorflow.keras.models import load_model

class PredictionService:
    def __init__(self):
        self._model_cache = {}

    def get_model(self, symbol):
        if symbol in self._model_cache:
            return self._model_cache[symbol]

        model_folder = symbol.replace('.', '_')
        project_root = Path(__file__).resolve().parents[3]
        model_path = project_root / 'app' / 'ai-models' / model_folder / 'model.keras'

        if model_path.exists():
            model = load_model(str(model_path), compile=False)
            self._model_cache[symbol] = model
            return model
        return None

    def predict_batch(self, model, df, scaler):
        # Menggunakan fitur asli Anda: open, high, low, close, volume, mfi
        features = ['open', 'high', 'low', 'close', 'volume', 'mfi']
        scaled = scaler.transform(df[features].values)
        
        windows = [scaled[i-60:i] for i in range(60, len(scaled))]
        if not windows: return {}

        preds_scaled = model.predict(np.array(windows), verbose=0)
        results = {}
        
        for i, idx in enumerate(range(60, len(scaled))):
            res = []
            for j in range(3):
                dummy = np.zeros((1, 6))
                dummy[0, 3] = preds_scaled[i, j]
                res.append(float(scaler.inverse_transform(dummy)[0, 3]))
            results[idx] = {"h1": res[0], "h2": res[1], "h3": res[2]}
        return results