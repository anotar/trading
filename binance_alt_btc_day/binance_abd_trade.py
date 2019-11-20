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
        self.logger.info("Setting Binance Alt/BTC Pair Trading Module...")
        self.bo = BinanceOrder(api_key, api_secret)

        self.trade_loop_interval = 1  # seconds
        self.trade_loop_checker = True
        self.trade_thread = threading.Thread()
        self.trade_loop_prev_time = {'hour_trade': 0,
                                     'minute_trade': 0,
                                     }

        self.logger.info('Binance Alt/BTC Pair Trading Module Setup Completed')

    def start_trade(self):
        self.logger.info('Setting up ABD Trade Loop...')
        self.trade_loop_checker = True

        def trade_loop():
            sleep(0.1)
            while self.trade_loop_checker:
                try:
                    self.trade()
                except Exception:
                    self.logger.exception('Caught Error in ABD Trade Loop')
                sleep(self.trade_loop_interval)

        self.trade_thread = threading.Thread(target=trade_loop)
        self.trade_thread.daemon = True
        self.trade_thread.start()
        self.logger.info('Start ABD Trade Loop')

    def stop_trade(self):
        self.trade_loop_checker = False
        # TODO: delete all pending order
        while self.trade_thread.is_alive():
            sleep(0.1)
        self.logger.info('Successfully Stopped ABD Trade Loop')

    def check_seconds(self, dict_key, time, time_type='second', time_sync_offset=1):
        if time_type == 'minute':
            time *= 60
        elif time_type == 'hour':
            time *= 60 * 60
        quotient_seconds = (self.bo.binance.seconds() - time_sync_offset) // time
        if quotient_seconds != self.trade_loop_prev_time[dict_key]:
            self.trade_loop_prev_time[dict_key] = quotient_seconds
            return True
        else:
            return False

    def trade(self):
        if self.check_seconds('hour_trade', 1, time_type='hour'):
            self.hour_trade()

        if self.check_seconds('minute_trade', 1, time_type='minute'):
            self.minute_trade()

    def hour_trade(self):
        self.logger.info('Starting Hour Trade...')
        # 비트 코인 가격수집
        # 비트 조건 확인 후 매도 매수 조건에 따라 거래
        # 매도 시 비트 우선 매도
        # 현재 진행중인 코인이 5개 미만일 떄
        # 알트코인 가격과 거래량 수집
        # 피봇아래거나 거래량이 적거나 가격이 지나치게 낮거나 Stable 페어인 ALT/BTC 페어 제거
        # 현재가격이 조건에 맞는 코인이 있는지 확인 후 조건에 맞으면 매수
        # 남은 코인 갯수에 따라 거래량 순으로 오더 배치

    def minute_trade(self):
        self.logger.info('Starting Minute Trade...')
        # 한개 이상의 진행중인 코인이 있을 떄
        # 진행중인 코인 가격과 오더북 수집
        # 시장가가 익절가 이상일 경우 익절 오더 배치
        # 손절가에 Stop Limit 오더 배치 (Stop 에서 최대 -10% 까지 Limit)


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

    binanceABDT.start_trade()
    sleep(10)
    binanceABDT.stop_trade()

