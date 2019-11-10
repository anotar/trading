import logging
import threading
from time import sleep
import math
import pandas as pd
from datetime import datetime
import os.path
from pprint import pprint
from binance_alt_btc_day.binance_order import BinanceOrder


class BinanceAltBtcDayTrade:
    def __init__(self, api_key, api_secret):
        # basic setup
        self.logger = setup_logger('binance_abd_trade')
        self.logger.info("Setting Binance Alt/Btc Pair Trading Module...")
        self.bo = BinanceOrder(api_key, api_secret)




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
    binanceABDT = BinanceAltBtcDayTrade(api_test['api_key'], api_test['api_secret'])
