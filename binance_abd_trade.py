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

        self.alt_trade_data = {'prev_day': datetime.utcnow().day,
                               'base_pair': 'init',  # 'BTC' or 'USDT'
                               'max_trade_limit': 5,
                               'trading_alts': {}, # {ticker: trading_alts_stat,}
                               'trading_alts_stat': {'total_quantity': 0,
                                                     's1_quantity': 0,
                                                     'r3_filled': False,
                                                     'r2_filled': False,
                                                     'stop_order_id': 0,
                                                     'r3_order': {
                                                         'order_list_id': 0,
                                                         'limit_order_id': 0,
                                                         'stop_order_id': 0,
                                                     },
                                                     'r2_order': {
                                                         'order_list_id': 0,
                                                         'limit_order_id': 0,
                                                         'stop_order_id': 0,
                                                     },
                                                     },
                               'open_alts': {},  # {ticker: open_alts_stat,}
                               'open_alts_stat': {'order_id': 0,
                                                  'timestamp': 0,
                                                  },
                               'stable_list': ['USDT', 'BUSD', 'PAX', 'TUSD', 'USDC', 'NGN', 'USDS'],
                               'btc_pair_condition': {'min_volume': 100,
                                                      'min_price': 0.00000040,
                                                      },
                               'usdt_pair_condition': {'min_volume': 10 ** 6,
                                                       'not_stable': True
                                                       },
                               }

        self.minute_timestamp = 60
        self.hourly_timestamp = 60 * 60
        self.daily_timestamp = 60 * 60 * 24

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

        if self.check_seconds('alt_trade', 1, time_type='minute'):  # 1 hour in practice
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

        self.check_trading_alts()
        btc_status = self.btc_trade_data['btc_status']
        base_pair = self.alt_trade_data['base_pair']
        self.logger.info(f'Current alt base pair is \'{base_pair}\'')

        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        open_alts = list(self.alt_trade_data['open_alts'].keys())
        if trading_alts:
            self.logger.info(f'Current trading alts are {trading_alts}')
        else:
            self.logger.info('There is no trading alts')
        if open_alts:
            self.logger.info(f'Current open alts is {open_alts}')
        else:
            self.logger.info('There is no open alts')

        if btc_status == 'buy' and base_pair != 'BTC':
            self.logger.info(f'BTC status has been changed to \'{btc_status}\'')
            self.check_trading_alts()
            self.sell_invalid_alts()
            self.logger.info('Change ALT/pair to BTC')
            self.alt_trade_data['base_pair'] = 'BTC'

        elif btc_status == 'sell' and base_pair != 'USDT':
            self.logger.info(f'BTC status has been changed to \'{btc_status}\'')
            self.check_trading_alts()
            self.sell_invalid_alts()
            self.logger.info('Change ALT/pair to USDT')
            self.alt_trade_data['base_pair'] = 'USDT'

        self.manage_pivot_order()
        if len(trading_alts) <= self.alt_trade_data['max_trade_limit']:
            self.make_pivot_order()

        self.check_trading_alts()
        if len(self.alt_trade_data['trading_alts']) > 0:
            self.manage_trading_alts()

        self.logger.info('Exit Alt Trade')

    def sell_all_btc(self):
        self.logger.info('Sell All BTC')
        self.delete_open_alts_orders()
        symbol = self.btc_trade_data['base_symbol']
        self.bo.sell_at_market(symbol)

    def buy_all_btc(self, slip_rate=0.995):
        self.logger.info('Buy All BTC')
        symbol = self.btc_trade_data['base_symbol']
        self.delete_open_alts_orders()
        if not self.bo.sell_at_market(symbol):
            raise Exception(f'Cannot sell {symbol} at market')

    def delete_open_alts_orders(self):
        self.logger.info('Delete open alts orders')
        self.bo.update_open_order_data()
        open_alts = self.alt_trade_data['open_alts']
        for ticker in open_alts:
            order_id = open_alts[ticker]['order_id']
            order_info = self.bo.get_open_order_info(order_id, data_update=False)
            if order_info:
                self.logger.info(f'{ticker}: Cancel open order')
                self.bo.cancel_order(ticker, order_id)
        self.alt_trade_data['open_alts'] = dict()
        self.logger.info('Open alts is cleared')

    def manage_pivot_order(self, executed_quantity_ratio=0.5):
        self.logger.info('Managing pivot open order...')
        open_alts = list(self.alt_trade_data['open_alts'].keys())
        self.bo.update_open_order_data()
        self.bo.update_market_data()
        for open_alt in open_alts:
            order_id = self.alt_trade_data['open_alts'][open_alt]['order_id']
            open_order = self.bo.get_open_order_info(order_id, data_update=False)
            order_stat = self.bo.get_order_stat(order_id, open_alt)
            if not open_order and order_stat['status'] == 'filled':
                self.logger.info(f'{open_alt}: Open order has been filled')
                self.alt_trade_data['trading_alts'][open_alt] = deepcopy(self.alt_trade_data['trading_alts_stat'])
                del self.alt_trade_data['open_alts'][open_alt]
            else:
                if open_order['timestamp'] < (self.bo.binance.seconds() - self.hourly_timestamp):
                    self.logger.info(f'{open_alt}: Cancel open order')
                    self.bo.cancel_order(open_alt, order_id)
                    filled_ratio = open_order['executed_quantity'] / open_order['original_quantity']
                    if filled_ratio >= executed_quantity_ratio:
                        self.logger.info(f'{open_alt}: Open order has been {filled_ratio*100}% filled. '
                                         f'Move to trading alts')
                        trading_alts_stat = self.alt_trade_data['trading_alts_stat']
                        self.alt_trade_data['trading_alts'][open_alt] = deepcopy(trading_alts_stat)
                        del self.alt_trade_data['open_alts'][open_alt]
                    else:
                        self.logger.info(f'{open_alt}: Open order is created 1 hour before. Delete from open alts')
                        self.bo.sell_at_market(open_alt)
                        del self.alt_trade_data['open_alts'][open_alt]

        if open_alts != list(self.alt_trade_data['open_alts'].keys()):
            self.logger.info(f'Open alts is updated to {open_alts}')
        self.logger.info('Exit Managing pivot open order sequence')

    def make_pivot_order(self):
        self.logger.info('Start making pivot order sequence...')
        base_pair = self.alt_trade_data['base_pair']
        self.bo.update_market_data()
        self.bo.update_ticker_data()
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
            buy_max_limit = self.alt_trade_data['max_trade_limit'] - len(self.alt_trade_data['trading_alts'])
            if buy_max_limit <= (len(over_pivot_p_ticker_list) + len(buy_triggered_ticker_list)):
                break
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

        if buy_triggered_ticker_list:
            self.logger.info('Buy under pivot ticker at market')
            for ticker in buy_triggered_ticker_list:
                pair_balance = self.bo.get_balance(symbol=base_pair)
                quantity = pair_balance/buy_max_limit
                self.bo.buy_at_market(ticker, pair_quantity=quantity)
                self.alt_trade_data['trading_alts'][ticker] = self.alt_trade_data['trading_alts_stat']
            trading_alts = list(self.alt_trade_data['trading_alts'].keys())
            self.logger.info(f'Trading alts is updated to {trading_alts}')

        if over_pivot_p_ticker_list:
            self.logger.info('Make order at pivot P')
            open_alts = self.alt_trade_data['open_alts']

            for open_alt in open_alts:
                if open_alt not in over_pivot_p_ticker_list:
                    self.logger.info(f'{open_alt} is not in open alts. Delete from open alts')
                    self.logger.info(f'{open_alt}: Cancel open order')
                    self.bo.cancel_order(open_alt, open_alts[open_alt]['order_id'])
                    ticker, pair = open_alt.split('/')
                    balance = self.bo.get_balance(ticker)
                    if self.bo.check_order_quantity(open_alt, balance):
                        self.bo.sell_at_market(open_alt)
                    del self.alt_trade_data['open_alts'][open_alt]

            for ticker in over_pivot_p_ticker_list:
                if ticker in self.alt_trade_data['open_alts'].keys():
                    self.logger.info(f'{ticker}: Open order is already made')
                    continue
                pair_balance = self.bo.get_balance(symbol=base_pair, balance_type='free')
                pivot = self.bo.get_monthly_pivot(ticker)
                quantity = pair_balance / buy_max_limit / pivot['p']
                order_result = self.bo.create_order(ticker, 'buy', quantity, price=pivot['p'], order_type='limit')
                self.logger.info(f'Order result: {order_result}')
                self.alt_trade_data['open_alts'][ticker] = deepcopy(self.alt_trade_data['open_alts_stat'])
                self.alt_trade_data['open_alts'][ticker]['order_id'] = int(order_result['id'])

            if open_alts.keys() != self.alt_trade_data['open_alts'].keys():
                self.logger.info(f'Open alts is updated to {list(open_alts.keys())}')
        self.logger.info('Exit making pivot order sequence')

    def cancel_trading_alt_orders(self, trading_alt):
        self.logger.info(f'{trading_alt}: Cancel open orders')
        trading_alt_stat = self.alt_trade_data['trading_alts'][trading_alt]
        self.bo.update_open_order_data()
        if trading_alt_stat['stop_order_id']:
            stop_order_id = trading_alt_stat['stop_order_id']
            stop_order_info = self.bo.get_open_order_info(stop_order_id, data_update=False)
            if stop_order_info:
                self.logger.info(f'{trading_alt}: Cancel s1 stop order')
                self.bo.cancel_order(trading_alt, stop_order_id)

        r3_order = trading_alt_stat['r3_order']
        if r3_order['order_list_id']:
            stop_order_id = r3_order['stop_order_id']
            stop_order_info = self.bo.get_open_order_info(stop_order_id, data_update=False)
            if stop_order_info:
                self.logger.info(f'{trading_alt}: Cancel r3 stop order')
                self.bo.cancel_order(trading_alt, stop_order_id)

            limit_order_id = r3_order['limit_order_id']
            limit_order_info = self.bo.get_open_order_info(limit_order_id, data_update=False)
            if limit_order_info:
                self.logger.info(f'{trading_alt}: Cancel r3 limit order')
                self.bo.cancel_order(trading_alt, limit_order_id)

        r2_order = trading_alt_stat['r2_order']
        if r2_order['order_list_id']:
            stop_order_id = r2_order['stop_order_id']
            stop_order_info = self.bo.get_open_order_info(stop_order_id, data_update=False)
            if stop_order_info:
                self.logger.info(f'{trading_alt}: Cancel r2 stop order')
                self.bo.cancel_order(trading_alt, stop_order_id)

            limit_order_id = r2_order['limit_order_id']
            limit_order_info = self.bo.get_open_order_info(r2_order['limit_order_id'], data_update=False)
            if limit_order_info:
                self.logger.info(f'{trading_alt}: Cancel r2 limit order')
                self.bo.cancel_order(trading_alt, limit_order_id)
        self.logger.info(f'{trading_alt}: Canceled all open orders')

    def check_trading_alts(self):
        self.logger.info('Checking trading alts status...')
        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        for trading_alt in trading_alts:
            ticker, pair = trading_alt.split('/')
            balance = self.bo.get_balance(ticker)
            trading_alt_stat = self.alt_trade_data['trading_alts'][trading_alt]
            if not self.bo.check_order_quantity(trading_alt, balance):
                self.cancel_trading_alt_orders(trading_alt)
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')

            total_stop_quantity = 0
            if trading_alt_stat['total_quantity']:
                if trading_alt_stat['stop_order_id']:
                    stop_order_info = self.bo.get_order_stat(trading_alt_stat['stop_order_id'], trading_alt)
                    total_stop_quantity += stop_order_info['executed_quantity']

                r3_order = trading_alt_stat['r3_order']
                if r3_order['order_list_id']:
                    stop_order_info = self.bo.get_order_stat(r3_order['stop_order_id'], trading_alt)
                    total_stop_quantity += stop_order_info['executed_quantity']
                    limit_order_info = self.bo.get_order_stat(r3_order['limit_order_id'], trading_alt)
                    trading_alt_stat['r3_quantity'] = limit_order_info['executed_quantity']
                    if limit_order_info['status'] == 'filled':
                        trading_alt_stat['r3_filled'] = True

                r2_order = trading_alt_stat['r2_order']
                if r2_order['order_list_id']:
                    stop_order_info = self.bo.get_order_stat(r2_order['stop_order_id'], trading_alt)
                    total_stop_quantity += stop_order_info['executed_quantity']
                    limit_order_info = self.bo.get_order_stat(r2_order['limit_order_id'], trading_alt)
                    trading_alt_stat['r2_quantity'] = limit_order_info['executed_quantity']
                    if limit_order_info['status'] == 'filled':
                        trading_alt_stat['r2_filled'] = True

                trading_alt_stat['s1_quantity'] = total_stop_quantity
        self.logger.info('Checked all trading alts status')

    def manage_trading_alts(self, r2_quantity_ratio=0.2, r3_quantity_ratio=0.3, limit_price_ratio=0.1):
        self.logger.info('Managing trading alts order...')
        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        self.bo.update_market_data()
        day_now = datetime.utcnow().day
        new_day = False
        if self.alt_trade_data['prev_day'] is not day_now:
            new_day = True
            self.alt_trade_data['prev_day'] = day_now

        for trading_alt in trading_alts:
            trading_alt_stat = self.alt_trade_data['trading_alts'][trading_alt]
            ticker, pair = trading_alt.split('/')
            ticker_info = self.bo.get_ticker_info(trading_alt)
            last_price = ticker_info['last_price']
            ticker_balance = self.bo.get_balance(ticker)

            pivot = self.bo.get_monthly_pivot(trading_alt)
            r3_price = pivot['r3']
            r2_price = pivot['r2']
            pivot_price = pivot['p']
            stop_price = pivot['s1']
            stop_limit_price = stop_price * (1 - limit_price_ratio)

            if not trading_alt_stat['total_quantity']:
                trading_alt_stat['total_quantity'] = ticker_balance

            if last_price <= stop_price:
                self.logger.info(f'{trading_alt}: Last price is under Pivot s1')
                self.bo.sell_at_market(trading_alt)
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')
                continue

            if last_price < pivot_price and new_day:
                self.logger.info(f'{trading_alt}: Previous daily close price is under pivot P')
                self.bo.sell_at_market(trading_alt)
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')
                continue

            if trading_alt_stat['s1_quantity']:
                self.logger.info(f'{trading_alt}: Stop order has been triggered')
                self.bo.sell_at_market(trading_alt)
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')
                continue

            r3_amount = trading_alt_stat['total_quantity'] * r3_quantity_ratio
            r2_amount = trading_alt_stat['total_quantity'] * r2_quantity_ratio
            stop_amount = ticker_balance - r3_amount - r2_amount

            if not trading_alt_stat['r3_order']['order_list_id']:
                self.logger.info(f'{trading_alt}: Create pivot r3 OCO order')
                r3_order_result = self.bo.create_oco_order(trading_alt, 'sell', r3_amount, r3_price,
                                                           stop_price, stop_limit_price)
                trading_alt_stat['r3_order']['order_list_id'] = r3_order_result['orderListId']
                for order_report in r3_order_result['orderReports']:
                    order_type = order_report['type']
                    if order_type == 'STOP_LOSS_LIMIT':
                        trading_alt_stat['r3_order']['stop_order_id'] = order_report['orderId']
                    elif order_type == 'LIMIT_MAKER':
                        trading_alt_stat['r3_order']['limit_order_id'] = order_report['orderId']
                    else:
                        raise ValueError(f'Uncaught order type: {order_type}')

            if not trading_alt_stat['r2_order']['order_list_id']:
                self.logger.info(f'{trading_alt}: Create pivot r2 OCO order')
                r2_order_result = self.bo.create_oco_order(trading_alt, 'sell', r2_amount, r2_price,
                                                           stop_price, stop_limit_price)
                trading_alt_stat['r2_order']['order_list_id'] = r2_order_result['orderListId']
                for order_report in r2_order_result['orderReports']:
                    order_type = order_report['type']
                    if order_type == 'STOP_LOSS_LIMIT':
                        trading_alt_stat['r2_order']['stop_order_id'] = order_report['orderId']
                    elif order_type == 'LIMIT_MAKER':
                        trading_alt_stat['r2_order']['limit_order_id'] = order_report['orderId']
                    else:
                        raise ValueError(f'Uncaught order type: {order_type}')

            if not trading_alt_stat['stop_order_id']:
                self.logger.info(f'{trading_alt}: Create stop order')
                stop_order_result = self.bo.create_order(trading_alt, 'sell', stop_amount, price=stop_limit_price,
                                                         stop_price=stop_price, order_type='stop_limit')
                trading_alt_stat['stop_order_id'] = stop_order_result['id']
        self.logger.info('Managed all trading alts order')

    def is_valid_alt(self, symbol, data_update=True):
        if not self.bo.check_ticker_status(symbol, data_update=data_update):
            return False
        if symbol in self.alt_trade_data['trading_alts'].keys():
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
        self.logger.info('Sell invalid alts')
        btc_base_symbol = self.btc_trade_data['base_symbol']

        if len(self.alt_trade_data['trading_alts']):
            self.logger.info('No trading alts')
            return

        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        for symbol in trading_alts:
            ticker, pair = symbol.split('/')
            trading_alts_stat = self.alt_trade_data['trading_alts_stat']
            if pair == 'USDT':
                btc_symbol = ticker + '/BTC'
                if self.is_valid_alt(btc_symbol):
                    self.cancel_trading_alt_orders(symbol)
                    del self.alt_trade_data['trading_alts'][symbol]
                    self.alt_trade_data['trading_alts'][btc_symbol] = deepcopy(trading_alts_stat)
                else:
                    if not self.bo.sell_at_market(symbol):
                        raise Exception(f'Cannot sell {symbol} at market')
                    self.bo.buy_at_market(btc_base_symbol)
            elif pair == 'BTC':
                usdt_symbol = ticker + '/BTC'
                if self.is_valid_alt(usdt_symbol):
                    self.cancel_trading_alt_orders(symbol)
                    del self.alt_trade_data['trading_alts'][symbol]
                    self.alt_trade_data['trading_alts'][usdt_symbol] = deepcopy(trading_alts_stat)
                else:
                    if not self.bo.sell_at_market(symbol):
                        raise Exception(f'Cannot sell {symbol} at market')
                    if not self.bo.sell_at_market(btc_base_symbol):
                        raise Exception(f'Cannot sell {btc_base_symbol} at market')

        self.logger.info('Sold all invalid alts')


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
    while True:
        sleep(100)
    print('stop trade')
    binanceABDT.stop_trade()

