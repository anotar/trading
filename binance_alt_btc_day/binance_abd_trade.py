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
        self.trade_loop_prev_time = {'btc_trade': 0,
                                     'alt_trade': 0,
                                     }

        self.btc_trade_data = {'prev_month': datetime.utcnow().month,
                               'btc_status': 'init',  # 'buy' or 'sell'
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
        self.logger.info('Setup Completed. Start ABD Trade Loop')

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
        elif time_type == 'day':
            time *= 60 * 60 * 24
        quotient_seconds = (self.bo.binance.seconds() - time_sync_offset) // time
        if quotient_seconds != self.trade_loop_prev_time[dict_key]:
            self.trade_loop_prev_time[dict_key] = quotient_seconds
            return True
        else:
            return False

    def trade(self):
        if self.check_seconds('btc_trade', 1, time_type='hour'):
            self.btc_trade()

        if self.check_seconds('alt_trade', 1, time_type='minute'):
            self.alt_trade()

    def btc_trade(self, symbol='BTC/USDT'):
        self.logger.info('Starting BTC Trade...')
        pivot = self.bo.get_yearly_pivot(symbol)
        btc_info = self.bo.get_ticker_info(symbol)
        last_price = btc_info['last_price']
        hourly_interval = 3600
        if self.bo.binance.seconds() - hourly_interval > btc_info['timestamp']:
            return False

        month_now = datetime.utcnow().month
        if last_price < pivot['s1']:
            self.logger.info(f'{symbol}: Last Price is under Pivot S1')
            if self.btc_trade_data['btc_status'] is not 'sell':
                self.logger.info(f'{symbol}: current btc status is not \'sell\'. start sell procedure')
                self.sell_all_coin()
                self.btc_trade_data['btc_status'] = 'sell'
        elif last_price < pivot['p']:
            self.logger.info(f'{symbol}: Last Price is under Pivot P')
            if self.btc_trade_data['btc_status'] is not 'sell':
                self.logger.info(f'{symbol}: current btc status is not \'sell\'.')
                if self.btc_trade_data['prev_month'] != month_now:
                    self.logger.info(f'{symbol}: New month. Start sell procedure')
                    self.btc_trade_data['prev_month'] = month_now
                    self.sell_all_coin()
                    self.btc_trade_data['btc_status'] = 'sell'
                else:
                    self.logger.info(f'{symbol}: Not new month. Passing under Pivot P trigger')
        else:
            self.logger.info(f'{symbol}: Last Price is more than Pivot P')
            if self.btc_trade_data['btc_status'] is not 'buy':
                self.logger.info(f'{symbol}: current btc status is not \'buy\'. start buy procedure')
                self.buy_btc_all()
                self.btc_trade_data['btc_status'] = 'buy'
        self.logger.info('Exit BTC Trade')

    def alt_trade(self):
        self.logger.info('Starting Alt Trade...')
        # 현재 진행중인 코인이 5개 미만일 떄
        # 알트코인 가격과 거래량 수집
        # 피봇아래거나 거래량이 적거나 가격이 지나치게 낮거나 Stable 페어인 ALT/BTC 페어 제거
        # 현재가격이 조건에 맞는 코인이 있는지 확인 후 조건에 맞으면 매수
        # 남은 코인 갯수에 따라 거래량 순으로 오더 배치
        # 한개 이상의 진행중인 코인이 있을 떄
        # 진행중인 코인 가격과 오더북 수집
        # 시장가가 익절가 이상일 경우 익절 오더 배치
        # 손절가에 Stop Limit 오더 배치 (Stop 에서 최대 -10% 까지 Limit)
        self.logger.info('Exit Alt Trade')

    def sell_all_coin(self):
        pass
        # cancel all order
        # check balance
        # sell all at market price

    def buy_btc_all(self):
        pass
        # cancel all order
        # check balance
        # buy btc all


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
    binanceABDT = BinanceAltBtcDayTrade(api_test['api_key'], api_test['api_secret'])

    print('start trade')
    binanceABDT.start_trade()
    sleep(100)
    print('stop trade')
    binanceABDT.stop_trade()

