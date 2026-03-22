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
        threshold = (datetime.now() - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M")
        
        news_cursor = db.stock_news.find({
            "Date": {"$gte": threshold}
        }).sort("Date", -1).limit(15)
        
        return [
            {
                "Date": n.get("Date"),
                "Keywords": n.get("Keywords"),
                "Article": n.get("Article")
            } for n in news_cursor
        ]
    except Exception as e:
        print(f"❌ Gagal mengambil berita: {e}")
        return []

def generate_ai_advice(stock_data, news_data):
    simplified_stocks = []
    for item in stock_data:
        last_hist = item['History'][-1] if item['History'] else {}
        prof = item.get('Profile', {})
        
        simplified_stocks.append({
            "Symbol": prof.get('Symbol'),
            "Name": prof.get('ShortName'),
            "Price": prof.get('LastPrice'),
            "FairPrice": prof.get('FairPriceGraham'),
            "RSI": last_hist.get('Indicators', {}).get('RSI'),
            "MACD_Hist": last_hist.get('Indicators', {}).get('MACD', {}).get('Hist'),
            "MFI": last_hist.get('Indicators', {}).get('MFI', {}).get('Score'),
            "PER": prof.get('PER'),
            "PBV": prof.get('PBV'),
            "AI_Pred_H1": last_hist.get('Prediction', {}).get('Close', {}).get('H1')
        })

    prompt = f"""
    Tugas: Bertindak sebagai Senior Analyst (Dual Persona: Trader & Value Investor).
    Analisalah data saham dan berita berikut untuk memberikan insight market.

    DATA SAHAM: {json.dumps(simplified_stocks)}
    BERITA TERKINI: {json.dumps(news_data)}

    WAJIB memberikan output dalam JSON MURNI dengan struktur berikut:
    {{
      "market_sentiment": "Kalimat singkat kondisi pasar saat ini (Bullish/Bearish/Sideways)",
      "top_picks": {{
        "trader_speculative": ["Symbol saham"],
        "investor_safe_haven": ["Symbol saham"],
        "deep_value_multibagger": ["Symbol saham"]
      }},
      "recommendations": [
        {{
          "symbol": "Symbol",
          "potential": "Persentase potensi kenaikan/penurunan",
          "trader_analysis": "Analisis teknikal singkat (RSI/MACD)",
          "investor_analysis": "Analisis fundamental singkat (Fair Value/PER/PBV)",
          "trader_recommendation": "BUY/SELL/HOLD",
          "investor_recommendation": "BUY/SELL/HOLD",
          "target_price": 0.0
        }}
      ]
    }}

    TAMBAHAN ATURAN KHUSUS:
    1. TARGET_PRICE: Jangan hanya menyalin FairPriceGraham. Untuk TRADER, target_price adalah resistance terdekat. Untuk INVESTOR, gunakan target harga wajar yang realistis dalam 6 bulan.
    2. CAKUPAN: Array 'recommendations' HARUS berisi semua {len(simplified_stocks)} saham. Jangan ada yang terlewat.
    3. REALISME: Jika PBV > 10 dan PER > 100, berikan peringatan keras di 'investor_analysis' meskipun 'trader_analysis' menunjukkan sinyal beli.
    4. SORTING: Urutkan array 'recommendations' berdasarkan skor 'potential' tertinggi ke terendah.
    """

    print("🤖 Menghasilkan nasihat AI...")
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                'response_mime_type': 'application/json'
            }
        )
        return json.loads(response.text)
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
    
    if not stocks:
        print("⚠️ Data kosong.")
        return

    advice_json = generate_ai_advice(stocks, news)
    
    if advice_json:
        save_to_db(advice_json)
        
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            print(f"📁 Folder {folder_name} berhasil dibuat.")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        file_name = f"ai_analysis-{timestamp}.json"
        file_path = os.path.join(folder_name, file_name)
        try:
            with open(file_path, "w") as f:
                json.dump(advice_json, f, indent=2)
            print(f"✅ Analisis lokal disimpan di: {file_path}")
        except Exception as e:
            print(f"❌ Gagal menyimpan file lokal: {e}")

        print("🚀 Seluruh proses selesai!")

if __name__ == "__main__":
    main()