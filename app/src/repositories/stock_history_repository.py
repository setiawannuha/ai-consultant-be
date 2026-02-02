from connection.mongodb import db_provider

class StockHistoryRepository:
    def __init__(self):
        self.db = db_provider.get_database()
        self.collection = self.db['stock_history']

    def find(self, symbol: str = None):
        # Jika symbol ada, buat filter. Jika tidak, gunakan dict kosong {}
        query = {"Symbol": symbol} if symbol else {}
        
        # Menjalankan find dengan query dinamis
        cursor = self.collection.find(query, {"_id": 0}) 
        return list(cursor)