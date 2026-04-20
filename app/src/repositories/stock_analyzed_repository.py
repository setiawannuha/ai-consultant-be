from connection.mongodb import db_provider
from datetime import datetime

class StockAnalyzedRepository:
    def __init__(self):
        self.db = db_provider.get_database()
        self.collection = self.db['stock_analyzed']

    def insert(self, data):
        return self.collection.insert_one(data)

    def find_filtered(self, symbol=None, date=None):
        query = {}
        if symbol:
            query["symbol"] = symbol
        if date:
            query["date"] = date
            
        cursor = self.collection.find(query, {"_id": 0}).sort("date", -1)
        return list(cursor)

    def find_by_symbol_and_date(self, symbol, date):
        return self.collection.find_one({"symbol": symbol, "date": date}, {"_id": 0})

    def update(self, symbol, date, updated_data):
        return self.collection.update_one(
            {"symbol": symbol, "date": date},
            {"$set": updated_data}
        )

    def update_response(self, symbol, date, prompt, ai_response):
        return self.collection.update_one(
            {"symbol": symbol, "date": date},
            {"$set": {"gemini_response": ai_response, "prompt": prompt, "updated_at": datetime.now()}}
        )

    def delete(self, symbol, date):
        return self.collection.delete_one({"symbol": symbol, "date": date})