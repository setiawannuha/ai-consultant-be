from connection.mongodb import db_provider

class StockProfileRepository:
    def __init__(self):
        self.db = db_provider.get_database()
        self.collection = self.db['stock_profiles']

    def find_one(self, symbol: str):
        return self.collection.find_one({"symbol": symbol}, {"_id": 0})

    def find_all(self):
        return list(self.collection.find({}, {"_id": 0}))
    
    def find_all_paginated(self, skip=0, limit=10):
        return list(self.collection.find({}, {"_id": 0}).skip(skip).limit(limit))
    
    def count_all(self):
        return self.collection.count_documents({})