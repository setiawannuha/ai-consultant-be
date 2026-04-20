from flask import Flask
from flask_cors import CORS
from src.routers.stock_prediction_router import stock_prediction_bp
from src.routers.stock_news_router import stock_news_bp
from src.routers.stock_portfolio_router import stock_portfolio_bp
from src.routers.stock_analyzed_router import stock_analyzed_bp

def create_app():
    app = Flask(__name__)

    CORS(app)

    app.register_blueprint(stock_prediction_bp, url_prefix='/api/stocks/prediction')
    app.register_blueprint(stock_news_bp, url_prefix='/api/stocks/news')
    app.register_blueprint(stock_portfolio_bp, url_prefix='/api/stocks/portfolio')
    app.register_blueprint(stock_analyzed_bp, url_prefix='/api/stocks/analyze')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)