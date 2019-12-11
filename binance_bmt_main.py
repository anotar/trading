from binance_bmt_trade import BinanceBtcMonthlyTrade
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

    rotate_handler = handlers.TimedRotatingFileHandler(
        filename=log_dir+name+'.log', when='W0', encoding='utf-8')
    rotate_handler.setFormatter(formatter)
    logger.addHandler(rotate_handler)

    return logger


logger = setup_logger('binance_bmt_main')
logger.info('Set up Binance BTC Monthly Trading...')

with open('api/binance_ysjjdh_gmail.txt', 'r') as f:
    api_keys = f.readlines()
api_test = {'api_key': api_keys[0].rstrip('\n'), 'api_secret': api_keys[1]}
binanceBMT = BinanceBtcMonthlyTrade(api_test['api_key'], api_test['api_secret'])

logger.info('Start Binance BTC Monthly Trading')
binanceBMT.start_trade()
while True:
    sleep(10)

