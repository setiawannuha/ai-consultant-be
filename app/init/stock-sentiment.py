import sys
import os
import ollama
import json
from datetime import datetime, timedelta
from pymongo import UpdateOne

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider

class SentimentGenerator:
    def __init__(self):
        self.db = db_provider.get_database()
        self.model = "qwen2.5:7b"

    def get_closest_prices(self, symbols, news_date_str):
        """Mencari harga penutupan terdekat untuk daftar simbol saham"""
        prices = {}
        try:
            target_date = datetime.strptime(news_date_str, "%Y-%m-%d %H:%M")
            for symbol in symbols:
                price_data = self.db.stock_history.find_one({
                    "symbol": symbol,
                    "date": {"$gte": target_date}
                }, sort=[("date", 1)])
                prices[symbol] = price_data["close"] if price_data else None
        except Exception as e:
            print(f"Error fetching prices: {e}")
        return prices

    def analyze_news(self, news_item):
        """Proses berita menggunakan Qwen2.5 untuk ekstraksi atomic"""
        prompt = f"""
        Analyze this stock market news. Identify sentiment and all mentioned Indonesian stock tickers (ending in .JK).
        
        News Headline/Article: {news_item.get('article', '')} 

        Output ONLY a strictly formatted JSON:
        {{
            "sentiment_score": float (-1.0 to 1.0),
            "impact_magnitude": int (1-5),
            "affected_sectors": ["SectorName"],
            "confidence_score": int (1-10),
            "event_category": "CategoryName",
            "related_commodity": "CommodityName or None",
            "related_stocks": ["TICKER.JK"],
            "reasoning_summary": "sentence logic for this sentiment",
            "is_ambiguous": bool (true if news has conflicting positive and negative points)
        }}
        """
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt, format="json")
            return json.loads(response['response'])
        except Exception as e:
            print(f"Ollama Error: {e}")
            return None

    def generate_sentiments(self):
        # 1. Ambil berita 2 hari terakhir berdasarkan scraped_at
        two_days_ago = datetime.now() - timedelta(days=2)
        news_cursor = self.db.stock_news.find({
            "scraped_at": {"$gte": two_days_ago}
        })

        for news in news_cursor:
            news_id = news['_id']
            print(f"--- Processing News ID: {news_id} ---")
            
            try:
                # 2. Analisis Atomic dengan Qwen
                analysis = self.analyze_news(news)
                if not analysis:
                    continue
                
                # 3. Ambil harga untuk semua saham yang terkait
                stocks = analysis.get('related_stocks', [])
                prices_map = self.get_closest_prices(stocks, news['date'])
                
                # 4. Susun data Atomic (Satu Berita = Satu Dokumen)
                atomic_sentiment = {
                    "news_id": news_id,
                    "source": news.get('from'),
                    "date": news['date'],
                    "sentiment": {
                        "score": analysis.get('sentiment_score'),
                        "magnitude": analysis.get('impact_magnitude'),
                        "confidence": analysis.get('confidence_score')
                    },
                    "context": {
                        "category": analysis.get('event_category'),
                        "sectors": analysis.get('affected_sectors'),
                        "commodity": analysis.get('related_commodity'),
                        "is_ambiguous": analysis.get('is_ambiguous', False)
                    },
                    "related_market_data": [
                        {"symbol": s, "price_at_news": prices_map.get(s)} for s in stocks
                    ],
                    "reasoning": analysis.get('reasoning_summary'),
                    "generated_at": datetime.now()
                }

                # 5. Simpan/Update ke MongoDB (Upsert berdasarkan news_id)
                self.db.stock_sentiments.update_one(
                    {"news_id": news_id},
                    {"$set": atomic_sentiment},
                    upsert=True
                )
                print(f"✅ Successfully processed and saved sentiment for news: {news_id}")
                
            except Exception as e:
                print(f"❌ Critical Error processing news {news_id}: {e}")

if __name__ == "__main__":
    generator = SentimentGenerator()
    generator.generate_sentiments()