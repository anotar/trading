# Trending based trading system
# Made by Jusang Kim from 2020.10.10

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


class BinanceAltDailyTrade:
    def __init__(self, api_key, api_secret):
        # basic setup
        self.logger = setup_logger('binance_adt_trade')
        self.logger.info("Setting Binance Alt Daily Trading Module...")
        self.bo = BinanceOrder(api_key, api_secret)

        self.trade_loop_interval = 1  # seconds
        self.trade_loop_checker = True
        self.trade_thread = threading.Thread()
        self.trade_loop_prev_time = {'alt_trade': 0,
                                     'record': 0,
                                     'data_update': 0,
                                     }

        self.alt_trade_data = {'prev_day': datetime.utcnow().day-1,
                               'base_pair': 'USDT',
                               'max_trade_limit': 3,
                               'trading_alts': {},  # {ticker: trading_alts_stat,}
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
                               'stable_list': ['USDT', 'BUSD', 'PAX', 'TUSD', 'USDC', 'NGN', 'USDS', 'EUR'],
                               'option_list': ['BULL', 'BEAR', 'UP', 'DOWN'],
                               'btc_pair_condition': {'min_volume': 100,
                                                      'min_price': 0.00000040,
                                                      },
                               'usdt_pair_condition': {'min_volume': 10 ** 6,
                                                       'not_stable': True,
                                                       'not_option': True,
                                                       },
                               }

        self.minute_timestamp = 60
        self.hourly_timestamp = 60 * 60
        self.daily_timestamp = 60 * 60 * 24

        self.logger.info('Binance Alt Daily Trading Module Setup Completed')

    def start_trade(self):
        self.logger.info('Setting up ADT Trade Loop...')
        self.trade_loop_checker = True

        def trade_loop():
            sleep(0.1)
            while self.trade_loop_checker:
                try:
                    self.trade()
                except Exception:
                    self.logger.exception('Caught Error in ADT Trade Loop')
                sleep(self.trade_loop_interval)

        self.trade_thread = threading.Thread(target=trade_loop)
        self.trade_thread.daemon = True
        self.trade_thread.start()
        self.logger.info('Setup Completed. Start ADT Trade Loop')

    def stop_trade(self):
        self.trade_loop_checker = False
        max_try = 5
        while max_try:
            if self.bo.cancel_all_order():
                break
            max_try -= 1
        while self.trade_thread.is_alive():
            sleep(0.1)
        self.logger.info('Successfully Stopped ADT Trade Loop')

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
        if self.check_seconds('alt_trade', 1, time_type='hour'):
            self.alt_trade()

        if self.check_seconds('record', 1, time_type='day'):
            self.record_information()

        if self.check_seconds('data_update', 1, time_type='day'):
            self.update_coin_data()

    def alt_trade(self, min_cost=150):
        self.logger.info('Starting Alt Trade...')
        max_trade_limit = self.alt_trade_data['max_trade_limit']
        self.logger.info(f'Current Max Trading Limit is {max_trade_limit}')
        if not self.bo.check_exchange_status():
            self.logger.info('Exchange is Not Active. Exit Alt trade')

        self.check_trading_alts()
        base_pair = self.alt_trade_data['base_pair']
        self.logger.info(f'Current alt base pair is \'{base_pair}\'')

        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        if trading_alts:
            self.logger.info(f'Current trading alts are {trading_alts}')
        else:
            self.logger.info('There is no trading alts')

        if not self.alt_trade_data['trading_alts']:
            assert self.bo.update_ticker_data()
            ticker_info = self.bo.get_ticker_statistics('BTC/USDT', data_update=False)
            assert ticker_info
            btc_price = ticker_info['last_price']
            usdt_balance = 0
            balance = self.bo.get_balance(symbol='BTC')
            assert balance not in self.bo.error_list
            usdt_balance += balance * btc_price
            balance = self.bo.get_balance(symbol='USDT')
            assert balance not in self.bo.error_list
            usdt_balance += balance
            max_trade_limit = int(usdt_balance // min_cost)
            max_trade_limit = 10 if max_trade_limit > 10 else max_trade_limit
            self.alt_trade_data['max_trade_limit'] = max_trade_limit
            self.logger.info(f'Change max trade limit to {max_trade_limit}')

        if len(trading_alts) <= self.alt_trade_data['max_trade_limit']:
            self.make_pivot_order()

        self.check_trading_alts()
        if len(self.alt_trade_data['trading_alts']) > 0:
            self.manage_trading_alts()

        self.logger.info('Exit Alt Trade')

    def make_pivot_order(self):
        self.logger.info('Start making pivot order sequence...')
        base_pair = self.alt_trade_data['base_pair']
        assert self.bo.update_market_data()
        assert self.bo.update_ticker_data()
        tickers = self.bo.get_tickers_by_quote(base_pair, data_update=False)
        self.logger.info(f'{base_pair} pair ticker count: {len(tickers)}')

        valid_ticker_list = []
        for ticker in tickers:
            if self.is_valid_alt(ticker, data_update=False):
                valid_ticker_list.append(ticker)
        self.logger.info(f'Valid ticker count: {len(valid_ticker_list)}')

        under_pivot_p_ticker_list = []
        buy_triggered_ticker_list = []
        buy_max_limit = self.alt_trade_data['max_trade_limit'] - len(self.alt_trade_data['trading_alts'])
        for ticker in valid_ticker_list:
            if buy_max_limit <= len(buy_triggered_ticker_list):
                break
            pivot = self.bo.get_monthly_pivot(ticker)
            if not pivot:
                continue
            ticker_info = self.bo.get_ticker_statistics(ticker, data_update=False)
            assert ticker_info
            ohlcv = self.bo.get_ohlcv(ticker, '1d', limit=5)
            assert not ohlcv.empty
            prev_close = ohlcv.iloc[-2]['close']
            penultimate_close = ohlcv.iloc[-3]['close'] = ohlcv.iloc[-3]['close']
            last_price = ticker_info['last_price']
            if penultimate_close < pivot['p'] <= prev_close:
                buy_triggered_ticker_list.append(ticker)
            if last_price < pivot['p']:
                under_pivot_p_ticker_list.append(ticker)
        self.logger.info(f'Buy triggered ticker count: {len(buy_triggered_ticker_list)}')
        self.logger.info(f'Under pivot p ticker ratio: {len(under_pivot_p_ticker_list)}/{len(valid_ticker_list)}')

        trade_count = 0
        if buy_triggered_ticker_list:
            self.logger.info('Buy under pivot ticker at market')
            for ticker in buy_triggered_ticker_list:
                pair_balance = self.bo.get_balance(symbol=base_pair, balance_type='free')
                self.logger.info(f'Current {base_pair} balance is {pair_balance}')
                assert pair_balance not in self.bo.error_list
                if buy_max_limit == (trade_count + 1):
                    self.logger.info(f'{ticker} is the last. Buy with remaining balance.')
                    total_balance = self.get_total_balance()
                    max_order_size = total_balance / buy_max_limit * 1.2
                    if pair_balance > max_order_size:
                        self.logger.info(f'Remaining balance{pair_balance} is over (total / n * 1.2). '
                                         f'Reducing to {max_order_size}')
                        pair_balance = max_order_size
                    quantity = pair_balance * 0.99
                    if quantity < 100:
                        self.logger.info(f'Current Quantity for {ticker} is less than 80 $.')
                        self.alt_trade_data['max_trade_limit'] -= 1
                        max_trade_limit = self.alt_trade_data['max_trade_limit']
                        self.logger.info(f'Change Max Trade Limit to {max_trade_limit}')
                else:
                    quantity = pair_balance / buy_max_limit
                self.logger.info(f'Buy {ticker} with {quantity}{base_pair}')
                trade_count += 1
                assert self.bo.buy_at_market(ticker, pair_quantity=quantity) not in (self.bo.error_list + [False])
                self.alt_trade_data['trading_alts'][ticker] = deepcopy(self.alt_trade_data['trading_alts_stat'])
            trading_alts = list(self.alt_trade_data['trading_alts'].keys())
            self.logger.info(f'Trading alts is updated to {trading_alts}')

        self.logger.info('Exit making pivot order sequence')

    def cancel_trading_alt_orders(self, trading_alt):
        self.logger.info(f'{trading_alt}: Cancel open orders')
        trading_alt_stat = self.alt_trade_data['trading_alts'][trading_alt]
        assert self.bo.update_open_order_data() not in self.bo.error_list
        if trading_alt_stat['stop_order_id']:
            stop_order_id = trading_alt_stat['stop_order_id']
            stop_order_info = self.bo.get_open_order_info(stop_order_id, data_update=False)
            assert stop_order_info not in self.bo.error_list
            if stop_order_info:
                self.logger.info(f'{trading_alt}: Cancel s1 stop order')
                try:
                    assert self.bo.cancel_order(trading_alt, stop_order_id)
                except:
                    stop_order_info = self.bo.get_open_order_info(stop_order_id)
                    if stop_order_info:
                        assert self.bo.cancel_order(trading_alt, stop_order_id)

        r3_order = trading_alt_stat['r3_order']
        if r3_order['order_list_id']:
            stop_order_id = r3_order['stop_order_id']
            stop_order_info = self.bo.get_open_order_info(stop_order_id, data_update=False)
            assert stop_order_info not in self.bo.error_list
            is_stop_order_canceled = False
            if stop_order_info:
                self.logger.info(f'{trading_alt}: Cancel r3 stop order')
                try:
                    assert self.bo.cancel_order(trading_alt, stop_order_id)
                except:
                    stop_order_info = self.bo.get_open_order_info(stop_order_id)
                    if stop_order_info:
                        assert self.bo.cancel_order(trading_alt, stop_order_id)
                is_stop_order_canceled = True

            limit_order_id = r3_order['limit_order_id']
            limit_order_info = self.bo.get_open_order_info(limit_order_id, data_update=False)
            assert limit_order_info not in self.bo.error_list
            if limit_order_info and not is_stop_order_canceled:
                self.logger.info(f'{trading_alt}: Cancel r3 limit order')
                try:
                    assert self.bo.cancel_order(trading_alt, limit_order_id)
                except:
                    stop_order_info = self.bo.get_open_order_info(limit_order_id)
                    if stop_order_info:
                        assert self.bo.cancel_order(trading_alt, limit_order_id)
            else:
                self.logger.info(f'{trading_alt}: r3 limit order is already canceled')

        r2_order = trading_alt_stat['r2_order']
        if r2_order['order_list_id']:
            stop_order_id = r2_order['stop_order_id']
            stop_order_info = self.bo.get_open_order_info(stop_order_id, data_update=False)
            assert stop_order_info not in self.bo.error_list
            is_stop_order_canceled = False
            if stop_order_info:
                self.logger.info(f'{trading_alt}: Cancel r2 stop order')
                try:
                    assert self.bo.cancel_order(trading_alt, stop_order_id)
                except:
                    stop_order_info = self.bo.get_open_order_info(stop_order_id)
                    if stop_order_info:
                        assert self.bo.cancel_order(trading_alt, stop_order_id)
                is_stop_order_canceled = True

            limit_order_id = r2_order['limit_order_id']
            limit_order_info = self.bo.get_open_order_info(r2_order['limit_order_id'], data_update=False)
            assert limit_order_info not in self.bo.error_list
            if limit_order_info and not is_stop_order_canceled:
                self.logger.info(f'{trading_alt}: Cancel r2 limit order')
                try:
                    assert self.bo.cancel_order(trading_alt, limit_order_id)
                except:
                    stop_order_info = self.bo.get_open_order_info(limit_order_id)
                    if stop_order_info:
                        assert self.bo.cancel_order(trading_alt, limit_order_id)
            else:
                self.logger.info(f'{trading_alt}: r2 limit order is already canceled')
        self.logger.info(f'{trading_alt}: Canceled all open orders')

    def check_trading_alts(self):
        self.logger.info('Checking trading alts status...')
        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        for trading_alt in trading_alts:
            ticker, pair = trading_alt.split('/')
            balance = self.bo.get_balance(ticker)
            assert balance not in self.bo.error_list
            trading_alt_stat = self.alt_trade_data['trading_alts'][trading_alt]
            if not self.bo.check_order_quantity(trading_alt, balance):
                self.cancel_trading_alt_orders(trading_alt)
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')

            total_stop_quantity = 0
            if trading_alt_stat['total_quantity']:
                if trading_alt_stat['stop_order_id']:
                    stop_order_info = self.bo.get_order_stat(trading_alt_stat['stop_order_id'], trading_alt)
                    assert stop_order_info
                    total_stop_quantity += stop_order_info['executed_quantity']

                r3_order = trading_alt_stat['r3_order']
                if r3_order['order_list_id']:
                    stop_order_info = self.bo.get_order_stat(r3_order['stop_order_id'], trading_alt)
                    assert stop_order_info
                    total_stop_quantity += stop_order_info['executed_quantity']
                    limit_order_info = self.bo.get_order_stat(r3_order['limit_order_id'], trading_alt)
                    assert limit_order_info
                    trading_alt_stat['r3_quantity'] = limit_order_info['executed_quantity']
                    if limit_order_info['status'] == 'filled':
                        trading_alt_stat['r3_filled'] = True

                r2_order = trading_alt_stat['r2_order']
                if r2_order['order_list_id']:
                    stop_order_info = self.bo.get_order_stat(r2_order['stop_order_id'], trading_alt)
                    assert stop_order_info
                    total_stop_quantity += stop_order_info['executed_quantity']
                    limit_order_info = self.bo.get_order_stat(r2_order['limit_order_id'], trading_alt)
                    assert limit_order_info
                    trading_alt_stat['r2_quantity'] = limit_order_info['executed_quantity']
                    if limit_order_info['status'] == 'filled':
                        trading_alt_stat['r2_filled'] = True

                trading_alt_stat['s1_quantity'] = total_stop_quantity
        self.logger.info('Checked all trading alts status')

    def manage_trading_alts(self, r2_quantity_ratio=0.2, r3_quantity_ratio=0.3, limit_price_ratio=0.1,
                            r2_hard_profit_ratio=0.15, r3_hard_profit_ratio=0.3):
        self.logger.info('Managing trading alts order...')
        trading_alts = list(self.alt_trade_data['trading_alts'].keys())
        assert self.bo.update_market_data()
        day_now = datetime.utcnow().day
        new_day = False
        if self.alt_trade_data['prev_day'] is not day_now:
            new_day = True
            self.alt_trade_data['prev_day'] = day_now

        for trading_alt in trading_alts:
            trading_alt_stat = self.alt_trade_data['trading_alts'][trading_alt]
            ticker, pair = trading_alt.split('/')
            ticker_info = self.bo.get_ticker_info(trading_alt)
            assert ticker_info
            last_price = ticker_info['last_price']
            ticker_balance = self.bo.get_balance(ticker)
            assert ticker_info not in self.bo.error_list

            pivot = self.bo.get_monthly_pivot(trading_alt)
            assert pivot
            r3_price = pivot['r3']
            r2_price = pivot['r2']
            pivot_price = pivot['p']
            stop_price = pivot['s1']
            stop_limit_price = stop_price * (1 - limit_price_ratio)

            ohlcv = self.bo.get_ohlcv(trading_alt, '1d', limit=5)
            assert not ohlcv.empty
            prev_close = ohlcv.iloc[-2]['close']

            if not trading_alt_stat['total_quantity']:
                trading_alt_stat['total_quantity'] = ticker_balance

            if last_price <= stop_price:
                self.logger.info(f'{trading_alt}: Last price is under Pivot s1')
                self.cancel_trading_alt_orders(trading_alt)
                sleep(0.3)  # for account state stabilization
                assert self.bo.sell_at_market(trading_alt) not in self.bo.error_list
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')
                continue
            elif prev_close < pivot_price and new_day:
                self.logger.info(f'{trading_alt}: Previous daily close price is under pivot P')
                self.cancel_trading_alt_orders(trading_alt)
                sleep(0.3)  # for account state stabilization
                assert self.bo.sell_at_market(trading_alt) not in self.bo.error_list
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')
                continue
            elif trading_alt_stat['s1_quantity']:
                self.logger.info(f'{trading_alt}: Stop order has been triggered')
                self.cancel_trading_alt_orders(trading_alt)
                assert self.bo.sell_at_market(trading_alt) not in self.bo.error_list
                del self.alt_trade_data['trading_alts'][trading_alt]
                self.logger.info(f'{trading_alt} is deleted from trading alts')
                continue

            r3_amount = trading_alt_stat['total_quantity'] * r3_quantity_ratio
            r2_amount = trading_alt_stat['total_quantity'] * r2_quantity_ratio
            stop_amount = ticker_balance - r3_amount - r2_amount

            if not trading_alt_stat['r3_order']['order_list_id']:
                self.logger.info(f'{trading_alt}: Create pivot r3 OCO order')

                if r3_price < last_price:
                    self.logger.info(f'Last price is greater than R3 price. '
                                     f'change R3 price to (Last price + {r3_hard_profit_ratio * 100}%)')
                    r3_price *= 1 + r3_hard_profit_ratio

                r3_order_result = self.bo.create_oco_order(trading_alt, 'sell', r3_amount, r3_price,
                                                           stop_price, stop_limit_price)
                assert r3_order_result
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

                if r2_price < last_price:
                    self.logger.info(f'Last price is greater than R2 price. '
                                     f'change R2 price to (Last price + {r2_hard_profit_ratio * 100}%)')
                    r2_price *= 1 + r2_hard_profit_ratio

                r2_order_result = self.bo.create_oco_order(trading_alt, 'sell', r2_amount, r2_price,
                                                           stop_price, stop_limit_price)
                assert r2_order_result
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
                assert stop_order_result
                trading_alt_stat['stop_order_id'] = stop_order_result['id']
        self.logger.info('Managed all trading alts order')

    def is_valid_alt(self, symbol, data_update=True):
        if not self.bo.check_ticker_status(symbol, data_update=data_update):
            return False
        if symbol in self.alt_trade_data['trading_alts'].keys():
            return False

        ticker, pair = symbol.split('/')

        ticker_info = self.bo.get_ticker_statistics(symbol, data_update=data_update)
        assert ticker_info

        quote_volume = ticker_info['quote_volume']
        last_price = ticker_info['last_price']
        btc_condition = self.alt_trade_data['btc_pair_condition']
        usdt_condition = self.alt_trade_data['usdt_pair_condition']
        stable_list = self.alt_trade_data['stable_list']
        option_list = self.alt_trade_data['option_list']

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
            for option in option_list:
                if option in ticker and usdt_condition['not_option']:
                    return False
        return True

    def record_information(self, verbose=True):
        self.logger.info('Record Binance trading bot information')
        assert self.bo.update_ticker_data()
        ticker_info = self.bo.get_ticker_statistics('BTC/USDT', data_update=False)
        assert ticker_info
        btc_price = ticker_info['last_price']
        usdt_balance = self.get_total_balance(update=False)
        btc_balance = round(usdt_balance / btc_price, 3)

        # save balance data
        file_name = 'bot_data_history'
        record_dir = 'data/Binance/AltDailyTrading/'
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

    def get_total_balance(self, update=True):
        if update:
            assert self.bo.update_ticker_data()
        usdt_balance = 0
        balance = self.bo.get_balance('USDT')
        assert balance not in self.bo.error_list
        usdt_balance += balance

        for trading_alt in self.alt_trade_data['trading_alts']:
            ticker, pair = trading_alt.split('/')
            balance = self.bo.get_balance(ticker)
            assert balance not in self.bo.error_list
            ticker_info = self.bo.get_ticker_statistics(trading_alt, data_update=False)
            assert ticker_info
            last_price = ticker_info['last_price']
            value = balance * last_price
            usdt_balance += value
        return usdt_balance

    def update_coin_data(self):
        self.logger.info('Update ALT Coin Deny List')
        file_name = 'coin_list'
        record_dir = 'data/Binance/CoinData/'
        if not os.path.exists(record_dir):
            raise FileNotFoundError('CoinData Folder is not exist.')

        coin_data = pd.read_csv('{}.csv'.format(record_dir+file_name))
        stable_list = coin_data['stable_list'].dropna().values.tolist()
        option_list = coin_data['option_list'].dropna().values.tolist()
        stable_list = [stable_coin.replace(" ", "") for stable_coin in stable_list]
        option_list = [option_pair.replace(" ", "") for option_pair in option_list]

        if self.alt_trade_data['stable_list'] == stable_list:
            self.logger.info("Current stable list is not updated.")
        else:
            old_stable_list = self.alt_trade_data['stable_list']
            self.alt_trade_data['stable_list'] = stable_list
            self.logger.info(f"Stable list is updated from {old_stable_list} to {stable_list}")
        if self.alt_trade_data['option_list'] == option_list:
            self.logger.info("Current option list is not updated.")
        else:
            old_option_list = self.alt_trade_data['option_list']
            self.alt_trade_data['option_list'] = option_list
            self.logger.info(f"Option list is updated from {old_option_list} to {option_list}")

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
    binanceADT = BinanceAltDailyTrade(api_test['api_key'], api_test['api_secret'])

    print('start trade')
    binanceADT.start_trade()
    while True:
        sleep(100)
    print('stop trade')
    binanceADT.stop_trade()

