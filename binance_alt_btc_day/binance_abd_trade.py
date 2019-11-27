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
                               'base_symbol': 'BTC/USDT',
                               }

        self.alt_trade_data = {'base_pair': 'init',  # 'BTC' or 'USDT'
                               'max_trade_limit': 5,
                               'trading_alts': [],
                               'open_alts': [],
                               'stable_list': ['USDT', 'BUSD', 'PAX', 'TUSD', 'USDC', 'NGN', 'USDS'],
                               'btc_pair_condition': {'min_volume': 100,
                                                      'min_price': 0.00000040,
                                                      },
                               'usdt_pair_condition': {'min_volume': 10 ** 6,
                                                       'not_stable': True
                                                       },
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
        self.bo.cancel_all_order()
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

    def btc_trade(self):
        self.logger.info('Starting BTC Trade...')
        if not self.bo.check_exchange_status():
            self.logger.info('Exchange is Not Active. Exit BTC trade')

        symbol = self.btc_trade_data['base_symbol']
        pivot = self.bo.get_yearly_pivot(symbol)
        self.logger.info(f'{symbol} Pivot: {pivot}')
        btc_info = self.bo.get_ticker_info(symbol)
        last_price = btc_info['last_price']
        hourly_interval = 3600
        if self.bo.binance.seconds() - hourly_interval > btc_info['timestamp']:
            self.logger.info('Last Transaction is too long ago. Exit BTC trade')
            return False
        month_now = datetime.utcnow().month

        btc_status = self.btc_trade_data['btc_status']
        self.logger.info(f'Current btc status is \'{btc_status}\'')
        if last_price < pivot['s1']:
            self.logger.info(f'{symbol}: Last Price is under Pivot S1')
            if self.btc_trade_data['btc_status'] != 'sell':
                self.logger.info(f'{symbol}: start sell procedure')
                self.sell_all_btc()
                self.btc_trade_data['btc_status'] = 'sell'
                self.logger.info('Change btc status to \'sell\'')

        elif last_price < pivot['p']:
            self.logger.info(f'{symbol}: Last Price is under Pivot P')
            if self.btc_trade_data['btc_status'] != 'sell':
                if self.btc_trade_data['prev_month'] is not month_now:
                    self.logger.info(f'{symbol}: New month. Start sell procedure')
                    self.sell_all_btc()
                    self.btc_trade_data['prev_month'] = month_now
                    self.logger.info('Update previous month status')
                    self.btc_trade_data['btc_status'] = 'sell'
                    self.logger.info('Change btc status to \'sell\'')
                else:
                    self.logger.info('Not new month. Passing under Pivot P trigger')
                    if self.btc_trade_data['btc_status'] != 'buy':
                        self.btc_trade_data['btc_status'] = 'buy'
                        self.logger.info('Change btc status to \'buy\'')

        else:
            self.logger.info(f'{symbol}: Last Price is more than Pivot P')
            if self.btc_trade_data['btc_status'] != 'buy':
                self.logger.info(f'{symbol}: start buy procedure')
                self.buy_all_btc()
                self.btc_trade_data['btc_status'] = 'buy'
                self.logger.info('Change btc status to \'buy\'')

        self.logger.info('Exit BTC Trade')

    def alt_trade(self):
        self.logger.info('Starting Alt Trade...')
        if not self.bo.check_exchange_status():
            self.logger.info('Exchange is Not Active. Exit Alt trade')

        btc_status = self.btc_trade_data['btc_status']
        base_pair = self.alt_trade_data['base_pair']
        self.logger.info(f'Current alt base pair is \'{base_pair}\'')
        self.bo.cancel_all_order(oco=False)
        if btc_status == 'buy' and base_pair != 'BTC':
            self.logger.info(f'BTC status has been changed to \'{btc_status}\'')
            self.sell_invalid_alts()
            self.logger.info('Change ALT/pair to BTC')
            self.alt_trade_data['base_pair'] = 'BTC'

        elif btc_status == 'sell' and base_pair != 'USDT':
            self.logger.info(f'BTC status has been changed to \'{btc_status}\'')
            self.sell_invalid_alts()
            self.logger.info('Change ALT/pair to USDT')
            self.alt_trade_data['base_pair'] = 'USDT'

        self.check_pivot_order()
        trading_alts = self.alt_trade_data['trading_alts']
        if trading_alts:
            self.logger.info(f'Current trading alts are {trading_alts}')
        else:
            self.logger.info('There is no trading alts')
        if len(trading_alts) <= self.alt_trade_data['max_trade_limit']:
            self.make_pivot_order()
        if len(self.alt_trade_data['trading_alts']) > 0:
            self.manage_pivot_order()

        self.logger.info('Exit Alt Trade')

    def sell_all_btc(self):
        self.logger.info('Sell All BTC')
        self.bo.cancel_all_order()
        symbol = self.btc_trade_data['base_symbol']
        self.bo.sell_at_market(symbol)

    def buy_all_btc(self, slip_rate=0.995):
        self.logger.info('Buy All BTC')
        symbol = self.btc_trade_data['base_symbol']
        self.bo.cancel_all_order()
        if not self.bo.sell_at_market(symbol):
            raise Exception(f'Cannot sell {symbol} at market')

    def check_pivot_order(self, btc_trigger_balance=0.01, usdt_trigger_balance=50):
        self.logger.info('Check open order located at pivot P.')
        open_alts = self.alt_trade_data['open_alts']
        self.bo.update_market_data()
        for open_alt in open_alts:
            symbol, pair = open_alt.split('/')
            balance = self.bo.get_balance(symbol=symbol)
            ticker_info = self.bo.get_ticker_info(open_alt, data_update=False)
            last_price = ticker_info['last_price']
            quote_balance = balance * last_price
            if pair == 'USDT':
                if quote_balance > usdt_trigger_balance:
                    self.logger.info(f'{open_alt}: Open order has been filled.')
                    self.alt_trade_data['trading_alts'].append(open_alt)
                    self.alt_trade_data['open_alts'].remove(open_alt)
            elif pair == 'BTC':
                if quote_balance > btc_trigger_balance:
                    self.logger.info(f'{open_alt}: Open order has been filled.')
                    self.alt_trade_data['trading_alts'].append(open_alt)
                    self.alt_trade_data['open_alts'].remove(open_alt)
            else:
                raise ValueError(f'{pair} pair does not defined')
        if open_alts != self.alt_trade_data['open_alts']:
            self.logger.info(f'Open alts is updated to {open_alts}')

    def make_pivot_order(self):
        self.logger.info('Make pivot Order.')
        base_pair = self.alt_trade_data['base_pair']
        self.logger.info('Update market and ticker data.')
        self.bo.update_market_data()
        self.bo.update_ticker_data()
        self.logger.info('Trading alts is below max trade limit. Find valid alts to trade')
        tickers = self.bo.get_tickers_by_quote(base_pair, data_update=False)
        self.logger.info(f'{base_pair} pair ticker count: {len(tickers)}')

        valid_ticker_list = []
        for ticker in tickers:
            if self.is_valid_alt(ticker, data_update=False):
                valid_ticker_list.append(ticker)
        self.logger.info(f'Valid ticker count: {len(valid_ticker_list)}')

        over_pivot_p_ticker_list = []
        buy_triggered_ticker_list = []
        for ticker in valid_ticker_list:
            pivot = self.bo.get_monthly_pivot(ticker)
            ticker_info = self.bo.get_ticker_statistics(ticker, data_update=False)
            if not pivot:
                continue
            ohlcv = self.bo.get_ohlcv(ticker, '1d', limit=10)
            prev_close = ohlcv.iloc[-2]['close']
            last_price = ticker_info['last_price']
            if prev_close >= pivot['p']:
                if last_price > pivot['p']:
                    over_pivot_p_ticker_list.append(ticker)
                else:
                    buy_triggered_ticker_list.append(ticker)
        self.logger.info(f'Buy triggered ticker count: {len(buy_triggered_ticker_list)}')
        self.logger.info(f'Over pivot p ticker count: {len(over_pivot_p_ticker_list)}')

        buy_max_limit = self.alt_trade_data['max_trade_limit'] - len(self.alt_trade_data['trading_alts'])
        if buy_triggered_ticker_list:
            self.logger.info('Buy under pivot ticker at market.')
            for ticker in buy_triggered_ticker_list:
                pair_balance = self.bo.get_balance(symbol=base_pair)
                quantity = pair_balance/buy_max_limit
                self.bo.buy_at_market(ticker, pair_quantity=quantity)
                self.alt_trade_data['trading_alts'].append(ticker)
                buy_max_limit -= 1
                if not buy_max_limit:
                    break
            trading_alts = self.alt_trade_data['trading_alts']
            self.logger.info(f'Trading alts is updated to {trading_alts}')
        if over_pivot_p_ticker_list and buy_max_limit:
            self.logger.info('Make order at pivot P')
            self.alt_trade_data['open_alts'].clear()
            for ticker in over_pivot_p_ticker_list:
                pair_balance = self.bo.get_balance(symbol=base_pair, balance_type='free')
                pivot = self.bo.get_monthly_pivot(ticker)
                quantity = pair_balance / buy_max_limit / pivot['p']
                order_result = self.bo.create_order(ticker, 'buy', quantity, price=pivot['p'], order_type='limit')
                self.logger.info(f'Order result: {order_result}')
                self.alt_trade_data['open_alts'].append(ticker)
                buy_max_limit -= 1
                if not buy_max_limit:
                    break
            open_alts = self.alt_trade_data['open_alts']
            self.logger.info(f'Current open alts is {open_alts}')

    def manage_pivot_order(self):
        self.logger.info('Manage pivot order.')
        # R2,3에 익절 오더 배치
        # 손절가에 Stop Limit 오더 배치 (Stop 에서 최대 -10% 까지 Limit)
        pass

    def is_valid_alt(self, symbol, data_update=True):
        if not self.bo.check_ticker_status(symbol, data_update=data_update):
            return False
        if symbol in self.alt_trade_data['trading_alts']:
            return False

        ticker, pair = symbol.split('/')

        ticker_info = self.bo.get_ticker_statistics(symbol, data_update=data_update)
        quote_volume = ticker_info['quote_volume']
        last_price = ticker_info['last_price']
        btc_condition = self.alt_trade_data['btc_pair_condition']
        usdt_condition = self.alt_trade_data['usdt_pair_condition']
        stable_list = self.alt_trade_data['stable_list']

        if pair == 'BTC':
            min_volume = btc_condition['min_volume']
            min_price = btc_condition['min_price']
            if quote_volume < min_volume:
                return False
            elif last_price < min_price:
                return False
        elif pair == 'USDT':
            min_volume = usdt_condition['min_volume']
            if quote_volume < min_volume:
                return False
            elif ticker in stable_list and usdt_condition['not_stable']:
                return False
        return True

    def sell_invalid_alts(self):
        self.logger.info('Sell invalid alts.')
        btc_base_symbol = self.btc_trade_data['base_symbol']

        if len(self.alt_trade_data['trading_alts']):
            self.logger.info('No trading alts.')
            return

        trading_alts = self.alt_trade_data['trading_alts'].copy()
        for symbol in trading_alts:
            ticker, pair = symbol.split('/')
            if pair == 'USDT':
                btc_symbol = ticker + '/BTC'
                if self.is_valid_alt(btc_symbol):
                    self.alt_trade_data['trading_alts'].remove(symbol)
                    self.alt_trade_data['trading_alts'].append(btc_symbol)
                if not self.bo.sell_at_market(symbol):
                    raise Exception(f'Cannot sell {symbol} at market')
                self.bo.buy_at_market(btc_base_symbol)
            elif pair == 'BTC':
                usdt_symbol = ticker + '/BTC'
                if self.is_valid_alt(usdt_symbol):
                    self.alt_trade_data['trading_alts'].remove(symbol)
                    self.alt_trade_data['trading_alts'].append(usdt_symbol)
                if not self.bo.sell_at_market(symbol):
                    raise Exception(f'Cannot sell {symbol} at market')
                if not self.bo.sell_at_market(btc_base_symbol):
                    raise Exception(f'Cannot sell {btc_base_symbol} at market')

        self.logger.info('Sold all invalid alts.')


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

