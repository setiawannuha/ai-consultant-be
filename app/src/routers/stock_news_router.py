from flask import Blueprint, jsonify, request
from src.controllers.stock_news_controller import StockNewsController

# Inisialisasi Blueprint Flask
stock_news_bp = Blueprint('stock_news', __name__)
controller = StockNewsController()

@stock_news_bp.route('/list', methods=['GET'])
def get_list():
    """Endpoint untuk mendapatkan semua list news saham"""
    try:
        data = controller.get_list()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500