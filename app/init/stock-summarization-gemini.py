import sys
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from connection.mongodb import db_provider

load_dotenv()

API_BASE_URL = os.getenv("STOCK_API_URL")

db = db_provider.get_database() 
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model="gemini-2.5-flash"
folder_name = "stock-summarization"

def get_stock_data_from_api():
    try:
        print("📡 Mengambil data dari API...")
        response = requests.get(API_BASE_URL)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Gagal mengambil data API: {e}")
        return []

def get_recent_news():
    try:
        print("📰 Mengambil berita dari Database...")
        threshold = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M")
        
        news_cursor = db.stock_news.find({
            "date": {"$gte": threshold}
        }).sort("date", -1)
        
        return list(news_cursor)
    except Exception as e:
        print(f"❌ Gagal mengambil berita: {e}")
        return []

def get_portfolios():
    try:
        print("📂 Mengambil data portofolio dari Database...")
        portfolios_cursor = db.stock_portfolios.find(
            {}, 
            {"symbol": 1, "avg_price": 1, "total_lots": 1, "_id": 0}
        ).sort("total_lots", -1)
        return list(portfolios_cursor)
    except Exception as e:
        print(f"❌ Gagal mengambil portofolio: {e}")
        return []

def generate_ai_advice(stock_data, news_data, portfolios):
    simplified_stocks = []
    general_news = []
    used_news_indices = set()

    for item in stock_data:
        prof = item.get('profile', {})
        full_symbol = prof.get('symbol', "")
        clean_symbol = full_symbol.replace(".JK", "")
        
        last_hist = item['history'][-1] if item['history'] else {}
        
        related_news = []
        for idx, n in enumerate(news_data):
            article_text = n.get("article", "")
            if clean_symbol.upper() in article_text.upper():
                related_news.append(article_text)
                used_news_indices.add(idx)
        
        simplified_stocks.append({
            "symbol": full_symbol,
            "name": prof.get('short_name'),
            "price": prof.get('last_price'),
            "fair_price": prof.get('fair_price_graham'),
            "rsi": last_hist.get('indicators', {}).get('rsi'),
            "macd_hist": last_hist.get('indicators', {}).get('macd', {}).get('hist'),
            "mfi": last_hist.get('indicators', {}).get('mfi', {}).get('score'),
            "per": prof.get('per'),
            "pbv": prof.get('pbv'),
            "bvps": prof.get('bvps'),
            "specific_news": related_news
        })

    for idx, n in enumerate(news_data):
        if idx not in used_news_indices:
            general_news.append(n.get("article", ""))

    macro_context = " ".join(general_news[:10]) if general_news else "Kondisi pasar global stabil."

    prompt = f"""
    Tugas: Bertindak sebagai Senior Analyst (Dual Persona: Trader & Value Investor).
    Analisalah data saham dan berita berikut.

    DATA SAHAM (Sudah termasuk berita spesifik per emiten): 
    {json.dumps(simplified_stocks)}

    BERITA TERKINI (Konteks Makro/Pasar Umum): 
    {json.dumps(macro_context)}

    SAHAM YANG SAYA MILIKI (Portofolio):
    {json.dumps(portfolios)}

    WAJIB memberikan output dalam JSON MURNI dengan struktur berikut:
    {{
      "market_sentiment": "Analisis sentimen pasar berdasarkan Berita Terkini",
      "top_picks": {{
        "trader_speculative": [],
        "investor_safe_haven": [],
        "deep_value_multibagger": []
      }},
      "recommendations": [
        {{
          "symbol": "symbol",
          "potential": "Persentase potensi",
          "trader_analysis": "Hubungkan RSI/MACD dengan specific_news jika ada",
          "investor_analysis": "Hubungkan Fundamental dengan specific_news jika ada",
          "trader_recommendation": "BUY/SELL/HOLD",
          "investor_recommendation": "BUY/SELL/HOLD",
          "target_price": 0.0
        }}
      ],
      "portfolios_analysis": [
        {{
          "symbol": "symbol",
          "action": "HOLD/SELL/BUY",
          "target_price": 0.0,
          "reason": "Alasan berdasarkan kondisi pasar, analisa teknikal dan berita"
        }}
      ]
    }}

    ATURAN:
    1. Jika 'specific_news' mengandung berita negatif (sentimen buruk), turunkan skor 'potential' meskipun teknikal bagus.
    2. Jika 'specific_news' kosong, andalkan data teknikal dan fundamental sepenuhnya.
    3. Urutkan berdasarkan potential tertinggi.
    """

    print("🤖 Menghasilkan nasihat AI...")
    print("prompt", prompt)

    try:
        return prompt
        # response = client.models.generate_content(
        #     model=model,
        #     contents=prompt,
        #     config={
        #         'response_mime_type': 'application/json'
        #     }
        # )
        # return json.loads(response.text)
    except Exception as e:
        print(f"❌ Error Generating AI content: {e}")
        return None

def save_to_db(analysis_result):
    if not analysis_result:
        return

    try:
        full_data = {
            "date": datetime.now(),
            "market_sentiment": analysis_result.get("market_sentiment"),
            "top_picks": analysis_result.get("top_picks"),
            "recommendations": []
        }

        for rec in analysis_result.get("recommendations", []):
            rec["agent"] = model
            full_data["recommendations"].append(rec)

        result = db.stock_summarization.insert_one(full_data)
        print(f"✅ Data disimpan ke MongoDB dengan ID: {result.inserted_id}")
    except Exception as e:
        print(f"❌ Gagal menyimpan ke DB: {e}")

def main():
    stocks = get_stock_data_from_api()
    news = get_recent_news()
    portfolios = get_portfolios()
    
    if not stocks:
        print("⚠️ Data kosong.")
        return

    advice_json = generate_ai_advice(stocks, news, portfolios)
    
    # if advice_json:
    #     save_to_db(advice_json)
        
    #     if not os.path.exists(folder_name):
    #         os.makedirs(folder_name)
    #         print(f"📁 Folder {folder_name} berhasil dibuat.")
    #     timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    #     file_name = f"ai_analysis-{timestamp}.json"
    #     file_path = os.path.join(folder_name, file_name)
    #     try:
    #         with open(file_path, "w") as f:
    #             json.dump(advice_json, f, indent=2)
    #         print(f"✅ Analisis lokal disimpan di: {file_path}")
    #     except Exception as e:
    #         print(f"❌ Gagal menyimpan file lokal: {e}")

    #     print("🚀 Seluruh proses selesai!")

if __name__ == "__main__":
    main()