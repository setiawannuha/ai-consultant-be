from connection.mongodb import db_provider

class StockHistoryRepository:
    def __init__(self):
        self.db = db_provider.get_database()
        self.collection = self.db['stock_history']

    def find(self, symbol, limit=100):
        # Mengambil data terbaru (sort date DESC) dengan limit tertentu
        cursor = self.collection.find({"symbol": symbol}).sort("date", -1).limit(limit)
        return list(cursor)