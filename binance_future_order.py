import logging
import os.path
from binance_order import BinanceOrder
from pprint import pprint
from datetime import datetime, timezone
import pandas as pd


class BinanceFutureOrder(BinanceOrder):
    def __init__(self, api_key, api_secret):
        self.logger = setup_logger('binance_future_order')
        self.logger.info('Setting Binance Future Order Module...')
        super().__init__(api_key, api_secret)
        self.logger = setup_logger('binance_future_order')
        self.logger.info('Binance Future Order Module Setup Completed')

    def get_future_ohlcv(self, internal_symbol, interval, limit=False):
        if limit:
            param = {'symbol': internal_symbol, 'interval': interval}
            ohlcv_original = self._try_until_timeout(self.binance.fapiPublicGetKlines, param)
        else:
            param = {'symbol': internal_symbol, 'interval': interval, 'limit': limit}
            ohlcv_original = self._try_until_timeout(self.binance.fapiPublicGetKlines, param)
        if ohlcv_original in self.error_list:
            return pd.DataFrame()
        ohlcv = pd.DataFrame()
        ohlcv['timestamp'] = [int(ohlcv_list[0]/1000) for ohlcv_list in ohlcv_original]
        ohlcv['open'] = [float(ohlcv_list[1]) for ohlcv_list in ohlcv_original]
        ohlcv['high'] = [float(ohlcv_list[2]) for ohlcv_list in ohlcv_original]
        ohlcv['low'] = [float(ohlcv_list[3]) for ohlcv_list in ohlcv_original]
        ohlcv['close'] = [float(ohlcv_list[4]) for ohlcv_list in ohlcv_original]
        ohlcv['volume'] = [float(ohlcv_list[5]) for ohlcv_list in ohlcv_original]

        utc_timezone = timezone.utc
        ohlcv['time'] = [datetime.fromtimestamp(timestamp, utc_timezone) for timestamp in ohlcv['timestamp']]
        ohlcv['year'] = [time.year for time in ohlcv['time']]
        ohlcv['month'] = [time.month for time in ohlcv['time']]
        ohlcv['day'] = [time.day for time in ohlcv['time']]
        ohlcv['hour'] = [time.hour for time in ohlcv['time']]
        return ohlcv

    def get_future_monthly_pivot(self, internal_symbol):
        ohlcv = self.get_future_ohlcv(internal_symbol, '1M', limit=5)
        if ohlcv.empty:
            return False
        if not len(ohlcv) > 1:
            return False
        high = ohlcv['high'].iloc[-2]
        low = ohlcv['low'].iloc[-2]
        close = ohlcv['close'].iloc[-2]
        pivot = self.get_pivot(high, low, close)
        return pivot

    def get_last_price(self, internal_symbol):
        param = {'symbol': internal_symbol}
        ticker_info = self._try_until_timeout(self.binance.fapiPublicGetTickerPrice, param)
        if ticker_info in self.error_list:
            return False
        return float(ticker_info['price'])

    def get_future_ticker_info(self, internal_symbol):
        param = {'symbol': internal_symbol}
        recent_trades = self._try_until_timeout(self.binance.fapiPublicGetTrades, param)
        if recent_trades in self.error_list:
            return False
        last_trade = recent_trades[-1]
        ticker_info = {'last_price': float(last_trade['price']),
                       'timestamp': int(last_trade['time']) / 1000}
        return ticker_info

    def get_future_balance(self):
        balance_info = self._try_until_timeout(self.binance.fapiPrivateGetBalance)
        if balance_info in self.error_list:
            return False
        usdt_balance = float(balance_info[0]['balance'])
        return usdt_balance

    def liquidation_calculator(self, p, sr2):
        leverage = 0
        raise NotImplementedError
        return leverage

    # create margin order function


def setup_logger(name):
    log_dir = f'./log/{name}/'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logging.basicConfig(filename=f'{log_dir}{name}.log',
                        level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler())
    return logger


if __name__ == '__main__':
    with open('api/binance_ysjjah_gmail.txt', 'r') as f:
        api_keys = f.readlines()
    api_test = {'api_key': api_keys[0].rstrip('\n'), 'api_secret': api_keys[1]}
    bfo = BinanceFutureOrder(api_test['api_key'], api_test['api_secret'])

    param = {'symbol': 'BTCUSDT'}
    internal_symmbol = 'BTCUSDT'
    # print(bfo.binance.fapiPublicGetTickerPrice(param))
    # pprint(bfo.get_future_monthly_pivot(internal_symmbol))
    # print(bfo.get_last_price(internal_symmbol))
    # pprint(bfo.get_future_ticker_info(internal_symmbol))
    pprint(bfo.get_future_balance())