import json
from datetime import datetime
from bson import ObjectId
from connection.mongodb import db_provider

class StockPortfolioController:
    def __init__(self):
        self.db = db_provider.get_database()
        self.portfolio_col = self.db.stock_portfolios
        self.history_col = self.db.stock_history

    def get_all(self):
        """Mengambil semua aset di portfolio dan menghitung profit/loss real-time"""
        portfolios = list(self.portfolio_col.find())
        results = []

        for item in portfolios:
            symbol = item['symbol']
            avg_price = item['avg_price']
            total_lots = item['total_lots']
            total_shares = total_lots * 100

            latest_history = self.history_col.find_one(
                {"Symbol": symbol},
                sort=[("Date", -1)]
            )

            current_price = latest_history['Close'] if latest_history else 0
            
            market_value = current_price * total_shares
            total_cost = avg_price * total_shares
            profit_loss_idr = market_value - total_cost
            
            if total_cost > 0:
                pl_percentage = (profit_loss_idr / total_cost) * 100
            else:
                pl_percentage = 0

            prefix = "+" if profit_loss_idr >= 0 else ""
            
            results.append({
                "_id": str(item['_id']),
                "symbol": symbol,
                "avg_price": avg_price,
                "current_price": current_price,
                "total_lots": total_lots,
                "total_cost": total_cost,
                "market_value": market_value,
                "pl_idr": profit_loss_idr,
                "pl_percentage": f"{prefix}{round(pl_percentage, 2)}%",
                "status": "PROFIT" if profit_loss_idr >= 0 else "LOSS"
            })

        return results

    def add_stock(self, symbol: str, avg_price: float, total_lots: int):
        """Menambah saham baru ke portfolio"""
        data = {
            "symbol": symbol.upper(),
            "avg_price": avg_price,
            "total_lots": total_lots,
            "created_at": datetime.now()
        }
        result = self.portfolio_col.insert_one(data)
        return {"message": "Saham berhasil ditambahkan", "id": str(result.inserted_id)}

    def update_stock(self, portfolio_id: str, avg_price: float = None, total_lots: int = None):
        """Update harga rata-rata atau jumlah lot"""
        update_data = {}
        if avg_price is not None: update_data["avg_price"] = avg_price
        if total_lots is not None: update_data["total_lots"] = total_lots
        update_data["updated_at"] = datetime.now()

        result = self.portfolio_col.update_one(
            {"_id": ObjectId(portfolio_id)},
            {"$set": update_data}
        )
        return {"updated_count": result.modified_count}

    def delete_stock(self, portfolio_id: str):
        """Menghapus saham dari portfolio"""
        result = self.portfolio_col.delete_one({"_id": ObjectId(portfolio_id)})
        return {"deleted_count": result.deleted_count}