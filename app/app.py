from flask import Flask
from flask_cors import CORS
from src.routers.stock_prediction_router import stock_prediction_bp
from src.routers.stock_news_router import stock_news_bp
from src.routers.stock_portfolio_router import stock_portfolio_bp

def create_app():
    app = Flask(__name__)

    CORS(app)

    app.register_blueprint(stock_prediction_bp, url_prefix='/api/stocks/prediction')
    app.register_blueprint(stock_news_bp, url_prefix='/api/stocks/news')
    app.register_blueprint(stock_portfolio_bp, url_prefix='/api/stocks/portfolio')

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)