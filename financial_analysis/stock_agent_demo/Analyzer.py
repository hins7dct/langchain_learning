# Analyzer.py
# This file contains the Analyzer class which is used to analyze the data
class Analyzer:
    """负责算各种指标，不关心数据从哪来"""
    def calc_ma(self, prices, window):
        return prices.tail(window).mean()

    def calc_rsi(self, prices):
        # 简化版 RSI 计算
        pass