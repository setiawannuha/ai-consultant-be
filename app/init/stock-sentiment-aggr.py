import sys
import os
from datetime import datetime, timedelta
import pandas as pd # Menggunakan pandas agar perhitungan statistik lebih mudah

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider

class SentimentAggregator:
    def __init__(self):
        self.db = db_provider.get_database()

    def aggregate_daily_sentiment(self, days_back=1):
        """Menggabungkan data atomic menjadi data agregat per saham per hari"""
        
        # 1. Ambil data dari stock_sentiments (Lapis 1)
        start_date = datetime.now() - timedelta(days=days_back)
        cursor = self.db.stock_sentiments.find({
            "generated_at": {"$gte": start_date}
        })
        
        raw_data = list(cursor)
        if not raw_data:
            print("No new sentiment data to aggregate.")
            return

        # 2. Flatten data untuk diproses dengan Pandas
        flattened = []
        for doc in raw_data:
            for market in doc.get('related_market_data', []):
                flattened.append({
                    "symbol": market['symbol'],
                    "score": doc['sentiment']['score'],
                    "magnitude": doc['sentiment']['magnitude'],
                    "confidence": doc['sentiment']['confidence'],
                    "is_ambiguous": doc['context']['is_ambiguous'],
                    "reasoning": doc['reasoning'],
                    "category": doc['context']['category'],
                    "date_str": doc['date'][:10] # Ambil YYYY-MM-DD saja
                })

        df = pd.DataFrame(flattened)

        # 3. Grouping per Symbol dan per Hari
        grouped = df.groupby(['symbol', 'date_str'])

        for (symbol, date_str), group in grouped:
            if symbol is None: continue

            # Hitung Weighted Sentiment: (Score * Magnitude * Confidence) / Total Weight
            group['weight'] = group['magnitude'] * group['confidence']
            weighted_score = (group['score'] * group['weight']).sum() / group['weight'].sum()
            
            # Hitung Volatilitas (Standard Deviation dari score)
            # Semakin tinggi, semakin bertolak belakang berita di hari itu
            sentiment_volatility = group['score'].std() if len(group) > 1 else 0

            # Gabungkan kesimpulan narasi
            all_reasonings = " | ".join(group['reasoning'].unique())

            # 4. Susun Data Otak
            brain_data = {
                "symbol": symbol,
                "date_key": date_str,
                "summary_stats": {
                    "mean_score": round(group['score'].mean(), 2),
                    "weighted_score": round(weighted_score, 2),
                    "volatility": round(sentiment_volatility, 2),
                    "news_count": len(group),
                    "ambiguity_ratio": group['is_ambiguous'].mean()
                },
                "event_distribution": group['category'].value_counts().to_dict(),
                "narrative_pool": all_reasonings,
                "last_updated": datetime.now(),
                "status": "Ready for Frontier Analysis"
            }

            # 5. Upsert ke stock_sentiment_aggr
            self.db.stock_sentiment_aggr.update_one(
                {"symbol": symbol, "date_key": date_str},
                {"$set": brain_data},
                upsert=True
            )
            print(f"🧠 Aggregated 'Brain Data' for {symbol} on {date_str}")

if __name__ == "__main__":
    aggregator = SentimentAggregator()
    aggregator.aggregate_daily_sentiment(days_back=3)