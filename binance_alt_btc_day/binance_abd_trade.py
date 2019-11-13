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
        
    # 분봉으로 거래

    # 코인 가격과 거래량 수집

    # 비트 조건 확인 후 매도 매수 조건에 따라 거래
    
    # 현재 진행중인 코인이 5개 미만일 떄
    # 피봇아래거나 거래량이 적거나 가격이 지나치게 낮거나 Stable 페어인 ALT/BTC 페어 제거
    # 현재가격이 조건에 맞는 코인이 있는지 확인 후 조건에 맞으면 매수
    # 남은 코인 갯수에 따라 거래량 순으로 오더 배치
    
    # 한개 이상의 진행중인 코인이 있을 떄
    # 시장가가 익절가 이상일 경우 익절 오더 배치
    # 손절가에 Stop Limit 오더 배치
    


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
