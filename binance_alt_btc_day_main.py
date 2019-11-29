from binance_abd_trade import BinanceAltBtcDayTrade
from time import sleep
import logging
import os
from logging import handlers


def setup_logger(name):
    log_dir = f'./log/{name}/'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    rotate_handler = handlers.TimedRotatingFileHandler(filename=log_dir, when='midnight', interval=1, encoding='utf-8')
    rotate_handler.setFormatter(formatter)
    logger.addHandler(rotate_handler)

    return logger


logger = setup_logger('binance_alt_btc_day_main')
logger.info('Set up Binance Alt Btc Day Trading...')

with open('api/binance_kjss970_naver.txt', 'r') as f:
    api_keys = f.readlines()
api_test = {'api_key': api_keys[0].rstrip('\n'), 'api_secret': api_keys[1]}
binanceABDT = BinanceAltBtcDayTrade(api_test['api_key'], api_test['api_secret'])

logger.info('Start Binance Alt Btc Day Trading')
binanceABDT.start_trade()
while True:
    sleep(10)

