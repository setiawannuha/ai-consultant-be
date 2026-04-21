from datetime import datetime
from src.repositories.stock_profile_repository import StockProfileRepository
from src.repositories.stock_history_repository import StockHistoryRepository
from src.repositories.stock_analyzed_repository import StockAnalyzedRepository
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

class StockAnalyzedController:
    def __init__(self):
        self.profile_repo = StockProfileRepository()
        self.history_repo = StockHistoryRepository()
        self.analyzed_repo = StockAnalyzedRepository()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def create_analysis(self, symbol: str):
        date = datetime.now().strftime("%Y-%m-%d")
        detail = self.analyzed_repo.find_by_symbol_and_date(symbol, date)
        if detail:
            return {"message": f"{symbol} already exist"}, 500
        profile = self.profile_repo.find_one(symbol)
        if not profile:
            return {"message": f"Profile for {symbol} not found"}, 404
        histories = self.history_repo.find(symbol, limit=20)
        
        formatted_history = []
        for h in histories:
            formatted_history.append({
                "date": h.get("date"),
                "open": h.get("open"),
                "high": h.get("high"),
                "low": h.get("low"),
                "close": h.get("close"),
                "bb_lower": h.get("bb_lower"),
                "bb_middle": h.get("bb_middle"),
                "bb_upper": h.get("bb_upper"),
                "ema10": h.get("ema10"),
                "ma20": h.get("ma20"),
                "ma5": h.get("ma5"),
                "macd": h.get("macd"),
                "macd_hist": h.get("macd_hist"),
                "macd_signal": h.get("macd_signal"),
                "mfi": h.get("mfi"),
                "obv": h.get("obv"),
                "rsi": h.get("rsi"),
                "volume": h.get("volume"),
                "volume_ma": h.get("volume_ma")
            })

        def get_default_broker_summary():
            return {
                "foreign_buy": None,
                "foreign_sell": None,
                "broker_summary": [
                    {
                        "broker_code": None,
                        "lot_buy": None,
                        "lot_sell": None,
                        "price_buy_average": None,
                        "price_sell_average": None
                    } for _ in range(3)
                ]
            }

        analyzed_data = {
            "symbol": symbol,
            "date": date,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "bvps": profile.get("bvps"),
            "dividend_yield": profile.get("dividend_yield"),
            "pbv": profile.get("pbv"),
            "per": profile.get("per"),
            "market_cap": profile.get("market_cap"),
            "eps": profile.get("eps"),
            "net_profit": profile.get("net_profit"),
            "total_equity": profile.get("total_equity"),
            "history": formatted_history,
            "broker_summary": {
                "1D": get_default_broker_summary(),
                "1W": get_default_broker_summary(),
                "1M": get_default_broker_summary(),
                "3M": get_default_broker_summary()
            },
        }
        self.analyzed_repo.insert(analyzed_data)
        return {"message": "Analysis created successfully", "symbol": symbol}, 201

    def get_all(self, symbol=None, date=None):
        results = self.analyzed_repo.find_filtered(symbol, date)
        return results

    def get_detail(self, symbol, date):
        detail = self.analyzed_repo.find_by_symbol_and_date(symbol, date)
        if not detail:
            return {"message": "Data not found"}, 404
        return detail

    def update_data(self, symbol, date, payload):
        result = self.analyzed_repo.update(symbol, date, payload)
        if result.matched_count == 0:
            return {"message": "Data not found to update"}, 404
        return {"message": "Data updated successfully"}, 200

    def delete_data(self, symbol, date):
        result = self.analyzed_repo.delete(symbol, date)
        if result.deleted_count == 0:
            return {"message": "Data not found to delete"}, 404
        return {"message": "Data deleted successfully"}, 200
    
    def analyze(self, symbol, date):
        detail = self.analyzed_repo.find_by_symbol_and_date(symbol, date)
        if not detail:
            return {"message": "Data not found"}, 404
        data_ai_ready = self._format_to_ai_ready(detail)
        if isinstance(data_ai_ready, tuple):
            return data_ai_ready
        prompt = f"""Anda adalah seorang analis saham/trader profesional (Certified Securities Analyst). 
Analisis data berikut dan berikan rekomendasi investasi yang objektif.

DATA SAHAM:
{data_ai_ready}

ATURAN OUTPUT (WAJIB DIPATUHI):
- DILARANG menggunakan kalimat pembuka (seperti: "Berdasarkan data...", "Ini adalah analisis...")
- DILARANG menggunakan kalimat penutup (seperti: "Semoga bermanfaat", "Investasi berisiko...")
- DILARANG menggunakan Markdown tebal (**) yang berlebihan.
- LANGSUNG berikan hasil sesuai format di bawah ini.

FORMAT OUTPUT:
Keputusan Investasi: [BUY/HOLD/SELL]
Alasan: [Analisis tren & fundamental dalam maksimal 2-3 kalimat saja]

[Hanya jika keputusan BUY, tambahkan]:
Area Entry (Beli): [Harga dalam IDR]
Target Profit 1: [Harga dalam IDR]
Target Profit 2: [Harga dalam IDR]
Stop Loss: [Harga dalam IDR]"""
        try:
            # response = self.client.models.generate_content(
            #     model="gemini-2.5-flash",
            #     contents=prompt
            # )
            ai_content = ""
            # ai_content = response.text
            self.analyzed_repo.update_response(symbol, date, prompt, ai_content)
            return {
                "symbol": symbol,
                "date": date,
                # "recommendation": ai_content
            }, 200
        except Exception as e:
            return {"message": f"Error generating AI response: {str(e)}"}, 500

    def _format_to_ai_ready(self, data):
        profile_header = "stock profile:\ndate,symbol,total_equity,dividend_yield,bvps,eps,market_cap,net_profit,pbv,per\n"
        profile_row = f"{data.get('date')},{data.get('symbol')},{data.get('total_equity')},{data.get('dividend_yield')}," \
                      f"{data.get('bvps')},{data.get('eps')},{data.get('market_cap')},{data.get('net_profit')}," \
                      f"{data.get('pbv')},{data.get('per')}\n\n"
        summary_header = "broker summary:\nperiod,foreign_buy,foreign_sell\n"
        summary_rows = ""
        details_header = "broker details:\nperiod,broker_code,lot_buy,lot_sell,price_buy_average,price_sell_average\n"
        details_rows = ""
        periods = ["1D", "1W", "1M", "3M"]
        broker_data = data.get("broker_summary", {})
        for p in periods:
            val = broker_data.get(p, {})
            summary_rows += f"{p},{val.get('foreign_buy')},{val.get('foreign_sell')}\n"
            for broker in val.get("broker_summary", []):
                if broker.get("broker_code"):
                    row_data = [
                        p,
                        str(broker.get("broker_code") or ""),
                        str(broker.get("lot_buy") or ""),
                        str(broker.get("lot_sell") or ""),
                        str(broker.get("price_buy_average") or ""),
                        str(broker.get("price_sell_average") or "")
                    ]
                    details_rows += ",".join(row_data).rstrip(",") + "\n"
        history_header = "\nstock price histories:\ndate,open,high,low,close,ema10,ma20,ma5,macd,macd_hist,macd_signal,mfi,obv,rsi,volume,volume_ma\n"
        history_rows = ""
        for h in data.get("history", []):
            h_row = [
                str(h.get("date")), str(h.get("open")), str(h.get("high")), str(h.get("low")),
                str(h.get("close")), str(h.get("ema10")), str(h.get("ma20")), str(h.get("ma5")),
                str(h.get("macd")), str(h.get("macd_hist")), str(h.get("macd_signal")),
                str(h.get("mfi")), str(h.get("obv")), str(h.get("rsi")),
                str(h.get("volume")), str(h.get("volume_ma"))
            ]
            history_rows += ",".join(h_row) + "\n"
        final_output = (
            profile_header + profile_row +
            summary_header + summary_rows + "\n" +
            details_header + details_rows +
            history_header + history_rows
        )
        
        return final_output