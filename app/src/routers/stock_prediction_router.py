from flask import Blueprint, jsonify, request
from src.controllers.stock_prediction_controller import StockPredictionController

# Inisialisasi Blueprint Flask
stock_prediction_bp = Blueprint('stock_prediction', __name__)
controller = StockPredictionController()

@stock_prediction_bp.route('/list', methods=['GET'])
def get_list():
    """Endpoint untuk mendapatkan semua list saham + prediksi"""
    try:
        data = controller.get_list()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stock_prediction_bp.route('/detail/<string:symbol>', methods=['GET'])
def get_detail(symbol):
    """Endpoint untuk mendapatkan detail 1 saham + semua history + prediksi"""
    try:
        data = controller.get_detail(symbol)
        if "message" in data:
            return jsonify(data), 404
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500