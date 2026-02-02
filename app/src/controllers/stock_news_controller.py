from src.repositories.stock_news_repository import StockNewsRepository

class StockNewsController:
    def __init__(self):
        self.news_repo = StockNewsRepository()

    def get_list(self):
        news = self.news_repo.find_all()
        response = []
        for data in news:
            response.append(data)
        return response