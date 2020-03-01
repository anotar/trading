import logging
import threading
from time import sleep
import math
import pandas as pd
from datetime import datetime
import os.path
from pprint import pprint
from binance_future_order import BinanceFutureOrder
from copy import deepcopy


class BinanceBtcFutureWeeklyHourTrade:
    def __init__(self, api_key, api_secret):
        # basic setup
        self.logger = setup_logger('binance_bfwht_trade')
        self.logger.info("Setting Binance BTC Future Weekly Hour Trading Module...")
        self.bfo = BinanceFutureOrder(api_key, api_secret)

        self.trade_loop_interval = 1  # seconds
        self.trade_loop_checker = True
        self.trade_thread = threading.Thread()
        self.trade_loop_prev_time = {'btc_trade': 0,
                                     'record': 0,
                                     }

        self.btc_trade_data = {'btc_status': 'init',  # 'long' or 'short' or 'liq'
                               'base_symbol': 'BTC/USDT',
                               'internal_symbol': 'BTCUSDT',
                               'liquidation_timestamp': 0,
                               'leverage': 0,
                               'position_quantity': 0,
                               }

        self.minute_timestamp = 60
        self.hourly_timestamp = 60 * 60
        self.daily_timestamp = 60 * 60 * 24

        self.logger.info('Binance BTC Future Weekly Hour Trading Module Setup Completed')

    def start_trade(self):
        self.logger.info('Setting up BFWHT Trade Loop...')
        self.trade_loop_checker = True

        def trade_loop():
            sleep(0.1)
            while self.trade_loop_checker:
                try:
                    self.trade()
                except Exception:
                    self.logger.exception('Caught Error in BFWHT Trade Loop')
                sleep(self.trade_loop_interval)

        self.trade_thread = threading.Thread(target=trade_loop)
        self.trade_thread.daemon = True
        self.trade_thread.start()
        self.logger.info('Setup Completed. Start BFWHT Trade Loop')

    def stop_trade(self):
        self.trade_loop_checker = False
        max_try = 5
        while max_try:
            if self.bfo.cancel_all_order():
                break
            max_try -= 1
        while self.trade_thread.is_alive():
            sleep(0.1)
        self.logger.info('Successfully Stopped BFWHT Trade Loop')

    def check_seconds(self, dict_key, time, time_type='second', time_sync_offset=1):
        if time_type == 'minute':
            time *= self.minute_timestamp
        elif time_type == 'hour':
            time *= self.hourly_timestamp
        elif time_type == 'day':
            time *= self.daily_timestamp
        quotient_seconds = (self.bfo.binance.seconds() - time_sync_offset) // time
        if quotient_seconds != self.trade_loop_prev_time[dict_key]:
            self.trade_loop_prev_time[dict_key] = quotient_seconds
            return True
        else:
            return False

    def trade(self):
        if self.check_seconds('btc_trade', 1, time_type='hour'):
            self.future_trade()

        if self.check_seconds('record', 1, time_type='day'):
            self.record_information()

    def future_trade(self):
        self.logger.info('Starting BTC Future Trade...')
        if not self.bfo.check_exchange_status():
            self.logger.info('Exchange is Not Active. Exit BTC trade')

        symbol = self.btc_trade_data['base_symbol']
        internal_symbol = self.btc_trade_data['internal_symbol']
        pivot = self.bfo.get_future_weekly_pivot(internal_symbol)
        assert pivot
        self.logger.info(f'{symbol} Future Pivot: {pivot}')
        btc_info = self.bfo.get_future_ticker_info(internal_symbol)
        assert btc_info
        last_price = btc_info['last_price']
        hourly_interval = 3600
        if self.bfo.binance.seconds() - hourly_interval > btc_info['timestamp']:
            self.logger.info('Last Transaction is too long ago. Exit BTC trade')
            return False
        ohlcv = self.bfo.get_future_ohlcv(internal_symbol, '4h', limit=5)
        assert not ohlcv.empty
        prev_open = ohlcv.iloc[-2]['open']
        prev_close = ohlcv.iloc[-2]['close']

        assert self.check_liquidation()
        liquidation_timestamp = self.btc_trade_data['liquidation_timestamp']
        if liquidation_timestamp:
            quotient_day = self.bfo.binance.seconds() // (self.hourly_timestamp * 4)
            liquidation_day = liquidation_timestamp // (self.hourly_timestamp * 4)
            if quotient_day != liquidation_day:
                self.btc_trade_data['btc_status'] = 'init'
                self.btc_trade_data['liquidation_timestamp'] = 0

        btc_status = self.btc_trade_data['btc_status']
        if btc_status == 'init':
            if prev_close >= pivot['p'] >= prev_open:
                assert self.switch_position('long', pivot)
                self.btc_trade_data['btc_status'] = 'long'
            elif prev_close < pivot['p'] <= prev_open:
                assert self.switch_position('short', pivot)
                self.btc_trade_data['btc_status'] = 'short'
        elif btc_status == 'long':
            if prev_close < pivot['p']:
                assert self.switch_position('short', pivot)
                self.btc_trade_data['btc_status'] = 'short'
        elif btc_status == 'short':
            if prev_close > pivot['p']:
                assert self.switch_position('long', pivot)
                self.btc_trade_data['btc_status'] = 'long'

        self.logger.info('Exit Future Trade')

    def switch_position(self, side, pivot, position_by_balance=0.7, profit_order_ratio=0.5, price_outer_ratio=0.14):
        if side == 'long':
            sr2 = pivot['s2']
        else:
            sr2 = pivot['r2']
        internal_symbol = self.btc_trade_data['internal_symbol']
        assert self.bfo.cancel_all_future_order(internal_symbol)
        assert self.bfo.close_position(internal_symbol)
        last_price = self.bfo.get_last_price(internal_symbol)
        assert last_price
        balance = self.bfo.get_future_balance()
        assert balance
        balance *= position_by_balance
        leverage, quantity = self.bfo.sr2_liquidation_calculator(last_price, sr2, balance, side)
        limit_quantity = quantity * profit_order_ratio
        self.btc_trade_data['leverage'] = leverage

        assert self.bfo.change_margin_type(internal_symbol, 'isolated')
        assert self.bfo.set_leverage(internal_symbol, leverage)

        if side == 'long':
            market_order_result = self.bfo.create_future_order(internal_symbol, 'buy', 'market', quantity)
            assert market_order_result
            self.logger.info(f'Long position market order result: {market_order_result}')

            stop_order_result = self.bfo.create_future_order(internal_symbol, 'sell', 'stop_market',
                                                             quantity, stop_price=pivot['s1'], reduce_only=True)
            assert stop_order_result
            self.logger.info(f'Long position stop order result: {stop_order_result}')

            last_price = self.bfo.get_last_price(internal_symbol)
            assert last_price
            limit_price = 0
            if last_price < pivot['r1']:
                limit_price = pivot['r1']
            elif last_price < pivot['r2']:
                limit_price = pivot['r2']
            elif last_price < pivot['r3']:
                limit_price = pivot['r3']
            if not limit_price or limit_price > (last_price * (1 + price_outer_ratio)):
                limit_price = last_price * (1 + price_outer_ratio)
            limit_order_result = self.bfo.create_future_order(internal_symbol, 'sell', 'limit',
                                                              limit_quantity, price=limit_price, reduce_only=True)
            assert limit_order_result
            self.logger.info(f'Long position limit profit order result: {limit_order_result}')
        else:
            market_order_result = self.bfo.create_future_order(internal_symbol, 'sell', 'market', quantity)
            assert market_order_result
            self.logger.info(f'Short position market order result: {market_order_result}')

            stop_order_result = self.bfo.create_future_order(internal_symbol, 'buy', 'stop_market',
                                                             quantity, stop_price=pivot['r1'], reduce_only=True)
            assert stop_order_result
            self.logger.info(f'Short position stop order result: {stop_order_result}')

            last_price = self.bfo.get_last_price(internal_symbol)
            assert last_price
            limit_price = 0
            if last_price > pivot['s1']:
                limit_price = pivot['s1']
            elif last_price > pivot['s2']:
                limit_price = pivot['s2']
            elif last_price > pivot['s3']:
                limit_price = pivot['s3']
            if not limit_price or limit_price < (last_price * (1 - price_outer_ratio)):
                limit_price = last_price * (1 - price_outer_ratio)
            limit_order_result = self.bfo.create_future_order(internal_symbol, 'buy', 'limit',
                                                              limit_quantity, price=limit_price, reduce_only=True)
            assert limit_order_result
            self.logger.info(f'Short position limit profit order result: {limit_order_result}')
        return True

    def check_liquidation(self):
        self.logger.info('Check position status')
        internal_symbol = self.btc_trade_data['internal_symbol']
        btc_status = self.btc_trade_data['btc_status']
        position_info = self.bfo.get_position_information(internal_symbol)
        assert position_info
        position_amount = float(position_info['positionAmt'])
        if btc_status != 'init' and not position_amount and not self.btc_trade_data['liquidation_timestamp']:
            self.btc_trade_data['liquidation_timestamp'] = self.bfo.binance.seconds()
            self.logger.info('There is no position. Liquidated.')
        return True

    def record_information(self, verbose=True):
        self.logger.info('Record Binance trading bot information')
        assert self.bfo.update_ticker_data()
        ticker_info = self.bfo.get_ticker_statistics('BTC/USDT', data_update=False)
        assert ticker_info
        btc_price = ticker_info['last_price']
        usdt_balance = 0

        balance = self.bfo.get_balance('BTC')
        assert balance not in self.bfo.error_list
        usdt_balance += balance * btc_price
        balance = self.bfo.get_balance('USDT')
        assert balance not in self.bfo.error_list
        usdt_balance += balance
        balance = self.bfo.get_future_balance()
        assert balance
        usdt_balance += balance
        btc_balance = round(usdt_balance / btc_price, 3)

        # save balance data
        file_name = 'bot_data_history'
        record_dir = 'data/Binance/BtcFutureWeeklyHourTrading/'
        if not os.path.exists(record_dir):
            os.makedirs(record_dir)
        bot_data = pd.DataFrame()
        if os.path.isfile(record_dir+file_name+'.csv'):
            bot_data = pd.read_csv('{}.csv'.format(record_dir+file_name))
        bot_data_dict = {
            'timestamp': self.bfo.binance.seconds(),
            'time': self.bfo.binance.iso8601(self.bfo.binance.milliseconds()),
            'btc_balance': btc_balance,
            'usdt_balance': usdt_balance,
            'leverage': self.btc_trade_data['leverage'],
        }
        bot_data = bot_data.append(bot_data_dict, ignore_index=True)
        bot_data.to_csv("{}.csv".format(record_dir + file_name), mode='w', encoding='utf-8', index=False)
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
    with open('api/binance_ysjjkh_gmail.txt', 'r') as f:
        api_keys = f.readlines()
    api_test = {'api_key': api_keys[0].rstrip('\n'), 'api_secret': api_keys[1]}
    binanceBFWHT = BinanceBtcFutureWeeklyHourTrade(api_test['api_key'], api_test['api_secret'])

    print('start trade')
    binanceBFWHT.start_trade()
    while True:
        sleep(100)
    print('stop trade')
    binanceBFWHT.stop_trade()

