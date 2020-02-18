import logging
import threading
from time import sleep
import math
import pandas as pd
from datetime import datetime
import os.path
from pprint import pprint
from binance_order import BinanceOrder
from copy import deepcopy


class BinanceBtcMonthlyTrade:
    def __init__(self, api_key, api_secret):
        # basic setup
        self.logger = setup_logger('binance_bmt_trade')
        self.logger.info("Setting Binance BTC Monthly Trading Module...")
        self.bo = BinanceOrder(api_key, api_secret)

        self.trade_loop_interval = 1  # seconds
        self.trade_loop_checker = True
        self.trade_thread = threading.Thread()
        self.trade_loop_prev_time = {'btc_trade': 0,
                                     'record': 0,
                                     }

        self.btc_trade_data = {'btc_status': 'init',  # 'buy' or 'sell'
                               'base_symbol': 'BTC/USDT',
                               }

        self.minute_timestamp = 60
        self.hourly_timestamp = 60 * 60
        self.daily_timestamp = 60 * 60 * 24

        self.logger.info('Binance BTC Monthly Trading Module Setup Completed')

    def start_trade(self):
        self.logger.info('Setting up BMT Trade Loop...')
        self.trade_loop_checker = True

        def trade_loop():
            sleep(0.1)
            while self.trade_loop_checker:
                try:
                    self.trade()
                except Exception:
                    self.logger.exception('Caught Error in BMT Trade Loop')
                sleep(self.trade_loop_interval)

        self.trade_thread = threading.Thread(target=trade_loop)
        self.trade_thread.daemon = True
        self.trade_thread.start()
        self.logger.info('Setup Completed. Start BMT Trade Loop')

    def stop_trade(self):
        self.trade_loop_checker = False
        max_try = 5
        while max_try:
            if self.bo.cancel_all_order():
                break
            max_try -= 1
        while self.trade_thread.is_alive():
            sleep(0.1)
        self.logger.info('Successfully Stopped BMT Trade Loop')

    def check_seconds(self, dict_key, time, time_type='second', time_sync_offset=1):
        if time_type == 'minute':
            time *= self.minute_timestamp
        elif time_type == 'hour':
            time *= self.hourly_timestamp
        elif time_type == 'day':
            time *= self.daily_timestamp
        quotient_seconds = (self.bo.binance.seconds() - time_sync_offset) // time
        if quotient_seconds != self.trade_loop_prev_time[dict_key]:
            self.trade_loop_prev_time[dict_key] = quotient_seconds
            return True
        else:
            return False

    def trade(self):
        if self.check_seconds('btc_trade', 1, time_type='day'):
            self.btc_trade()

        if self.check_seconds('record', 1, time_type='day'):
            self.record_information()

    def btc_trade(self):
        self.logger.info('Starting BTC Trade...')
        if not self.bo.check_exchange_status():
            self.logger.info('Exchange is Not Active. Exit BTC trade')

        symbol = self.btc_trade_data['base_symbol']
        pivot = self.bo.get_yearly_pivot(symbol)
        assert pivot
        self.logger.info(f'{symbol} Pivot: {pivot}')
        btc_info = self.bo.get_ticker_info(symbol)
        assert btc_info
        last_price = btc_info['last_price']
        hourly_interval = 3600
        if self.bo.binance.seconds() - hourly_interval > btc_info['timestamp']:
            self.logger.info('Last Transaction is too long ago. Exit BTC trade')
            return False
        ohlcv = self.bo.get_ohlcv(symbol, '1M', limit=5)
        assert not ohlcv.empty
        prev_close = ohlcv.iloc[-2]['close']

        btc_status = self.btc_trade_data['btc_status']
        self.logger.info(f'Current btc status is \'{btc_status}\'')
        if last_price < pivot['s1']:
            self.logger.info(f'{symbol}: Last Price is under Pivot S1')
            if self.btc_trade_data['btc_status'] != 'sell':
                self.logger.info(f'{symbol}: start sell BTC procedure')
                self.sell_all_btc()
                self.btc_trade_data['btc_status'] = 'sell'
                self.logger.info('Change btc status to \'sell\'')

        elif prev_close < pivot['p']:
            self.logger.info(f'{symbol}: Previous monthly close price is under Pivot P')
            if self.btc_trade_data['btc_status'] != 'sell':
                self.logger.info(f'{symbol}: Start sell BTC procedure')
                self.sell_all_btc()
                self.logger.info('Update previous month status')
                self.btc_trade_data['btc_status'] = 'sell'
                self.logger.info('Change btc status to \'sell\'')

        else:
            self.logger.info(f'{symbol}: Previous monthly close price is more than Pivot P')
            if self.btc_trade_data['btc_status'] != 'buy':
                self.logger.info(f'{symbol}: start buy BTC procedure')
                self.buy_all_btc()
                self.btc_trade_data['btc_status'] = 'buy'
                self.logger.info('Change btc status to \'buy\'')

        self.logger.info('Exit BTC Trade')

    def sell_all_btc(self):
        self.logger.info('Sell All BTC')
        symbol = self.btc_trade_data['base_symbol']
        assert self.bo.sell_at_market(symbol) not in self.bo.error_list

    def buy_all_btc(self, slip_rate=0.995):
        self.logger.info('Buy All BTC')
        symbol = self.btc_trade_data['base_symbol']
        assert self.bo.buy_at_market(symbol) not in self.bo.error_list

    def record_information(self, verbose=True):
        self.logger.info('Record Binance trading bot information')
        assert self.bo.update_ticker_data()
        ticker_info = self.bo.get_ticker_statistics('BTC/USDT', data_update=False)
        assert ticker_info
        btc_price = ticker_info['last_price']
        usdt_balance = 0

        balance = self.bo.get_balance('BTC')
        assert balance not in self.bo.error_list
        usdt_balance += balance * btc_price
        balance = self.bo.get_balance('USDT')
        assert balance not in self.bo.error_list
        usdt_balance += balance
        btc_balance = round(usdt_balance / btc_price, 3)

        # save balance data
        file_name = 'bot_data_history'
        record_dir = 'data/Binance/BtcMonthlyTrading/'
        if not os.path.exists(record_dir):
            os.makedirs(record_dir)
        balance_data = pd.DataFrame()
        if os.path.isfile(record_dir+file_name+'.csv'):
            balance_data = pd.read_csv('{}.csv'.format(record_dir+file_name))
        balance_dict = {
            'timestamp': self.bo.binance.seconds(),
            'time': self.bo.binance.iso8601(self.bo.binance.milliseconds()),
            'btc_balance': btc_balance,
            'usdt_balance': usdt_balance,
        }
        balance_data = balance_data.append(balance_dict, ignore_index=True)
        balance_data.to_csv("{}.csv".format(record_dir + file_name), mode='w', encoding='utf-8', index=False)
        self.logger.info('Trading data recorded')

        # Show trading data
        if verbose:
            self.logger.info(f'Estimated Balance in BTC: {btc_balance}')
            self.logger.info(f'Estimated Balance in USDT: {usdt_balance}')


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
    binanceBMT = BinanceBtcMonthlyTrade(api_test['api_key'], api_test['api_secret'])

    print('start trade')
    binanceBMT.start_trade()
    while True:
        sleep(100)
    print('stop trade')
    binanceBMT.stop_trade()

