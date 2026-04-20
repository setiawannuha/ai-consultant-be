from flask import Blueprint, jsonify, request
from src.controllers.stock_analyzed_controller import StockAnalyzedController

stock_analyzed_bp = Blueprint('stock_analyze', __name__)
controller = StockAnalyzedController()

@stock_analyzed_bp.route('/create', methods=['POST'])
def init():
    data = request.get_json()
    symbol = data.get('symbol')
    if not symbol:
        return jsonify({"message": "Symbol is required"}), 400
    result, status_code = controller.create_analysis(symbol)
    return jsonify(result), status_code


@stock_analyzed_bp.route('/list', methods=['GET'])
def get_stock_analyzed():
    symbol = request.args.get('symbol')
    date = request.args.get('date')
    results = controller.get_all(symbol, date)
    return jsonify(results), 200


@stock_analyzed_bp.route('/detail', methods=['GET'])
def get_detail():
    symbol = request.args.get('symbol')
    date = request.args.get('date')
    if not symbol or not date:
        return jsonify({"message": "Symbol and date are required"}), 400
    result = controller.get_detail(symbol, date)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result), 200


@stock_analyzed_bp.route('/update', methods=['PUT'])
def update_stock_analyzed():
    data = request.get_json()
    symbol = data.get('symbol')
    date = data.get('date')
    payload = data.get('payload')
    if not symbol or not date or not payload:
        return jsonify({"message": "Symbol, date, and payload are required"}), 400
    result, status_code = controller.update_data(symbol, date, payload)
    return jsonify(result), status_code


@stock_analyzed_bp.route('/delete', methods=['DELETE'])
def delete_stock_analyzed():
    symbol = request.args.get('symbol')
    date = request.args.get('date')
    if not symbol or not date:
        return jsonify({"message": "Symbol and date are required"}), 400
    result, status_code = controller.delete_data(symbol, date)
    return jsonify(result), status_code


@stock_analyzed_bp.route('/', methods=['GET'])
def analyze():
    symbol = request.args.get('symbol')
    date = request.args.get('date')
    if not symbol or not date:
        return jsonify({"message": "Symbol and date are required"}), 400
    result = controller.analyze(symbol, date)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result), 200