import logging
import ccxt
import os.path
from pprint import pprint
import pandas as pd
from datetime import datetime, timezone
from decimal import *
from time import sleep
import math
import json


class BinanceOrder:
    def __init__(self, api_key, api_secret):
        self.logger = setup_logger('binance_order')
        self.logger.info('Setting Binance Order Module...')
        self.binance = ccxt.binance(
            {'apiKey': api_key,
             'secret': api_secret,
             'enableRateLimit': False,
             })
        self.logger.info('Binance Order Module Setup Completed')

    def show_basic_info(self):
        print('Exchange Status')
        print(self.binance.fetch_status())
        print('\nExchange Data:')
        exchange_data = self.binance.publicGetExchangeInfo()
        print(exchange_data.keys())
        print('rateLimit:')
        pprint(exchange_data['rateLimits'])
        print('\nAPIs sample:')
        pprint(dir(self.binance)[len(dir(self.binance))-10:])

    def show_basic_market_info(self):
        market_data = self.binance.load_markets()
        pprint(market_data['BTC/USDT'])
        pprint(market_data.keys())
        ohlcv = bo.get_ohlcv('BTC/UDST', '1m')
        # print(ohlcv)
        # pprint(self.binance.fetch_ticker('BTC/USDT'))

    def check_exchange_status(self):
        exchange_status = self.binance.fetch_status()
        status = exchange_status['status']
        if status == 'ok':
            return True
        else:
            return False

    def check_ticker_status(self, symbol):
        market_data = self.binance.load_markets()
        if symbol not in market_data.keys():
            return False

        ticker_data = market_data[symbol]
        if ticker_data['active']:
            return True
        else:
            return False

    def get_ohlcv(self, symbol, interval):
        ohlcv_original = self.binance.fetch_ohlcv('BTC/USDT', '1M')
        ohlcv = pd.DataFrame()
        ohlcv['timestamp'] = [int(ohlcv_list[0]/1000) for ohlcv_list in ohlcv_original]
        ohlcv['open'] = [ohlcv_list[1] for ohlcv_list in ohlcv_original]
        ohlcv['high'] = [ohlcv_list[2] for ohlcv_list in ohlcv_original]
        ohlcv['low'] = [ohlcv_list[3] for ohlcv_list in ohlcv_original]
        ohlcv['close'] = [ohlcv_list[4] for ohlcv_list in ohlcv_original]
        ohlcv['volume'] = [ohlcv_list[5] for ohlcv_list in ohlcv_original]

        utc_timezone = timezone.utc
        ohlcv['time'] = [datetime.fromtimestamp(timestamp, utc_timezone) for timestamp in ohlcv['timestamp']]
        ohlcv['year'] = [time.year for time in ohlcv['time']]
        ohlcv['month'] = [time.month for time in ohlcv['time']]
        ohlcv['day'] = [time.day for time in ohlcv['time']]
        ohlcv['hour'] = [time.hour for time in ohlcv['time']]
        return ohlcv

    @staticmethod
    def get_pivot(high, low, close, fibonacci=(0.236, 0.618, 1)):
        pivot = dict()
        pivot['p'] = (high + low + close) / 3.0
        pivot['r1'] = pivot['p'] + (high - low) * fibonacci[0]
        pivot['s1'] = pivot['p'] - (high - low) * fibonacci[0]
        pivot['r2'] = pivot['p'] + (high - low) * fibonacci[1]
        pivot['s2'] = pivot['p'] - (high - low) * fibonacci[1]
        pivot['r3'] = pivot['p'] + (high - low) * fibonacci[2]
        pivot['s3'] = pivot['p'] - (high - low) * fibonacci[2]
        for key in pivot:
            pivot[key] = round(float(pivot[key]), 2)
        return pivot

    def get_yearly_pivot(self, symbol):
        ohlcv = self.get_ohlcv(symbol, '1m')
        if ohlcv.loc[ohlcv['year'] != datetime.utcnow().year].empty:
            return False
        ohlcv = ohlcv.loc[ohlcv['year'] == datetime.utcnow().year-1]
        high = ohlcv['high'].max()
        low = ohlcv['low'].min()
        close = ohlcv['close'].iloc[-1]
        pivot = self.get_pivot(high, low, close)
        return pivot

    def get_monthly_pivot(self, symbol):
        ohlcv = self.get_ohlcv(symbol, '1m')
        if not len(ohlcv) > 1:
            return False
        high = ohlcv['high'].iloc[-2]
        low = ohlcv['low'].iloc[-2]
        close = ohlcv['close'].iloc[-2]
        pivot = self.get_pivot(high, low, close)
        return pivot

    def get_ticker_info(self, symbol):
        ticker_data = self.binance.fetch_ticker(symbol)
        ticker_info = dict()
        ticker_info['last_price'] = round(Decimal(ticker_data['last']), 8)
        ticker_info['timestamp'] = int(ticker_data['timestamp']/1000)
        return ticker_info


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
    with open('api/binance_kjss970_naver.txt', 'r') as f:
        api_keys = f.readlines()
    api_test = {'api_key': api_keys[0].rstrip('\n'), 'api_secret': api_keys[1]}
    bo = BinanceOrder(api_test['api_key'], api_test['api_secret'])
    # bo.show_basic_info()
    # bo.show_basic_market_info()

    # Test function
    # print('Exchange Status:', bo.check_exchange_status())
    # print('BTC/USDT ticker Status:', bo.check_ticker_status('BTC/USDT'))
    # print('BTC yearly Pivot:', bo.get_yearly_pivot('BTC/USDT'))
    # print('BTC monthly Pivot:', bo.get_monthly_pivot('BTC/USDT'))
    pprint(bo.get_ticker_info('YOYOW/BTC'))
