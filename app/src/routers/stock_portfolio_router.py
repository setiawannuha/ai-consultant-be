from flask import Blueprint, request, jsonify
from src.controllers.stock_portfolio_controller import StockPortfolioController

# Inisialisasi Blueprint (seperti Router di FastAPI)
stock_portfolio_bp = Blueprint('portfolio', __name__)
controller = StockPortfolioController()

@stock_portfolio_bp.route('/', methods=['GET'])
def get_all_portfolio():
    """Mengambil semua daftar saham di portfolio beserta Profit/Loss"""
    try:
        results = controller.get_all()
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_portfolio_bp.route('/', methods=['POST'])
def add_to_portfolio():
    """Menambahkan saham baru ke dalam portfolio"""
    try:
        data = request.get_json()
        
        # Validasi sederhana
        if not all(k in data for k in ("symbol", "avg_price", "total_lots")):
            return jsonify({"error": "Missing fields"}), 400
            
        result = controller.add_stock(
            symbol=data['symbol'],
            avg_price=float(data['avg_price']),
            total_lots=int(data['total_lots'])
        )
        return jsonify(result), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@stock_portfolio_bp.route('/<portfolio_id>', methods=['PUT'])
def update_portfolio(portfolio_id):
    """Mengubah harga rata-rata atau jumlah lot berdasarkan ID"""
    try:
        data = request.get_json()
        avg_price = data.get('avg_price')
        total_lots = data.get('total_lots')
        
        result = controller.update_stock(
            portfolio_id, 
            avg_price=float(avg_price) if avg_price else None,
            total_lots=int(total_lots) if total_lots else None
        )
        
        if result["updated_count"] == 0:
            return jsonify({"message": "Tidak ada perubahan data"}), 404
            
        return jsonify({"message": "Update berhasil"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@stock_portfolio_bp.route('/<portfolio_id>', methods=['DELETE'])
def delete_from_portfolio(portfolio_id):
    """Menghapus saham dari portfolio berdasarkan ID"""
    try:
        result = controller.delete_stock(portfolio_id)
        if result["deleted_count"] == 0:
            return jsonify({"error": "Data tidak ditemukan"}), 404
            
        return jsonify({"message": "Saham berhasil dihapus dari portfolio"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400