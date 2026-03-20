from connection.mongodb import db_provider

class StockHistoryRepository:
    def __init__(self):
        self.db = db_provider.get_database()
        self.collection = self.db['stock_history']

    def find(self, symbol, limit=100):
        # Mengambil data terbaru (sort Date DESC) dengan limit tertentu
        cursor = self.collection.find({"Symbol": symbol}).sort("Date", -1).limit(limit)
        return list(cursor)