import pandas as pd
import numpy as np

class TechnicalIndicatorService:
    @staticmethod
    def calculate_mfi(df, period=20):
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        mf = tp * df['Volume']
        delta = tp.diff()
        pos_mf = pd.Series(np.where(delta > 0, mf, 0), index=df.index)
        neg_mf = pd.Series(np.where(delta < 0, mf, 0), index=df.index)
        pos_sum = pos_mf.rolling(window=period).sum()
        neg_sum = neg_mf.rolling(window=period).sum()
        mfr = pos_sum / (neg_sum + 1e-10)
        return 100 - (100 / (1 + mfr))

    @staticmethod
    def calculate_ma(df, period):
        return df['Close'].rolling(window=period).mean()

    @staticmethod
    def calculate_rsi(df, period=14):
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(df, slow=26, fast=12, signal=9):
        ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram