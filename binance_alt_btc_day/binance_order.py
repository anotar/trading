import logging
import ccxt
import os.path
from pprint import pprint
import pandas as pd
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
        # market_data = self.binance.load_markets()
        # pprint(dir(self.binance))

        for i in range(1,10):
            self.binance.load_markets()
            self.binance.fetch_ohlcv('BTC/USDT', '1d')
            exchange_data = self.binance.publicGetExchangeInfo()
        print(exchange_data.keys())
        pprint(exchange_data['rateLimits'])
        pprint(exchange_data['exchangeFilters'])


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
