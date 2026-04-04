from connection.mongodb import db_provider

class StockNewsRepository:
    def __init__(self):
        self.db = db_provider.get_database()
        self.collection = self.db['stock_news']

    def find_all(self):
        cursor = (
            self.collection
            .find({}, {"_id": 0})
            .sort("date", -1)
        )
        return list(cursor)