import logging
import ccxt
import os.path
from pprint import pprint
import pandas as pd
from datetime import datetime, timezone
from decimal import *
from time import sleep
import math
import json


class BinanceOrder:
    def __init__(self, api_key, api_secret):
        self.logger = setup_logger('binance_order')
        self.logger.info('Setting Binance Order Module...')
        self.binance = ccxt.binance(
            {'apiKey': api_key,
             'secret': api_secret,
             'enableRateLimit': False,
             })
        self.logger.info('Binance Order Module Setup Completed')

    def show_basic_info(self):
        print('Exchange Status')
        print(self.binance.fetch_status())
        print('\nExchange Data:')
        exchange_data = self.binance.publicGetExchangeInfo()
        print(exchange_data.keys())
        print('rateLimit:')
        pprint(exchange_data['rateLimits'])
        print('\nAPIs sample:')
        pprint(dir(self.binance)[len(dir(self.binance))-10:])

    def show_basic_market_info(self):
        market_data = self.binance.load_markets()
        pprint(market_data['BTC/USDT'])
        pprint(market_data.keys())
        ohlcv = bo.get_ohlcv('BTC/UDST', '1m')
        # print(ohlcv)
        # pprint(self.binance.fetch_ticker('BTC/USDT'))

    def check_exchange_status(self):
        exchange_status = self.binance.fetch_status()
        status = exchange_status['status']
        if status == 'ok':
            return True
        else:
            return False

    def check_ticker_status(self, symbol):
        market_data = self.binance.load_markets()
        if symbol not in market_data.keys():
            return False

        ticker_data = market_data[symbol]
        if ticker_data['active']:
            return True
        else:
            return False

    def get_ohlcv(self, symbol, interval):
        ohlcv_original = self.binance.fetch_ohlcv(symbol, interval)
        ohlcv = pd.DataFrame()
        ohlcv['timestamp'] = [int(ohlcv_list[0]/1000) for ohlcv_list in ohlcv_original]
        ohlcv['open'] = [ohlcv_list[1] for ohlcv_list in ohlcv_original]
        ohlcv['high'] = [ohlcv_list[2] for ohlcv_list in ohlcv_original]
        ohlcv['low'] = [ohlcv_list[3] for ohlcv_list in ohlcv_original]
        ohlcv['close'] = [ohlcv_list[4] for ohlcv_list in ohlcv_original]
        ohlcv['volume'] = [ohlcv_list[5] for ohlcv_list in ohlcv_original]

        utc_timezone = timezone.utc
        ohlcv['time'] = [datetime.fromtimestamp(timestamp, utc_timezone) for timestamp in ohlcv['timestamp']]
        ohlcv['year'] = [time.year for time in ohlcv['time']]
        ohlcv['month'] = [time.month for time in ohlcv['time']]
        ohlcv['day'] = [time.day for time in ohlcv['time']]
        ohlcv['hour'] = [time.hour for time in ohlcv['time']]
        return ohlcv

    @staticmethod
    def get_pivot(high, low, close, fibonacci=(0.236, 0.618, 1)):
        pivot = dict()
        pivot['p'] = (high + low + close) / 3.0
        pivot['r1'] = pivot['p'] + (high - low) * fibonacci[0]
        pivot['s1'] = pivot['p'] - (high - low) * fibonacci[0]
        pivot['r2'] = pivot['p'] + (high - low) * fibonacci[1]
        pivot['s2'] = pivot['p'] - (high - low) * fibonacci[1]
        pivot['r3'] = pivot['p'] + (high - low) * fibonacci[2]
        pivot['s3'] = pivot['p'] - (high - low) * fibonacci[2]
        for key in pivot:
            pivot[key] = round(float(pivot[key]), 2)
        return pivot

    def get_yearly_pivot(self, symbol):
        ohlcv = self.get_ohlcv(symbol, '1M')
        if ohlcv.loc[ohlcv['year'] != datetime.utcnow().year].empty:
            return False
        ohlcv = ohlcv.loc[ohlcv['year'] == datetime.utcnow().year-1]
        high = ohlcv['high'].max()
        low = ohlcv['low'].min()
        close = ohlcv['close'].iloc[-1]
        pivot = self.get_pivot(high, low, close)
        return pivot

    def get_monthly_pivot(self, symbol):
        ohlcv = self.get_ohlcv(symbol, '1M')
        if not len(ohlcv) > 1:
            return False
        high = ohlcv['high'].iloc[-2]
        low = ohlcv['low'].iloc[-2]
        close = ohlcv['close'].iloc[-2]
        pivot = self.get_pivot(high, low, close)
        return pivot

    def get_ticker_info(self, symbol):
        ticker_data = self.binance.fetch_ticker(symbol)
        market_data = self.binance.load_markets()
        pprint(self.binance.fetch_markets())
        ticker_info = dict()
        ticker_info['quote_volume'] = ticker_data['quoteVolume']
        ticker_info['ask'] = ticker_data['ask']
        ticker_info['bid'] = ticker_data['bid']
        ticker_info['last_price'] = round(Decimal(ticker_data['last']), 8)
        ticker_info['timestamp'] = int(ticker_data['timestamp']/1000)
        ticker_info['internal_symbol'] = ticker_data['info']['symbol']
        for ticker_filter in market_data[symbol]['info']['filters']:
            if ticker_filter['filterType'] == 'PRICE_FILTER':
                ticker_info['tick_size'] = float(ticker_filter['tickSize'])
        for ticker_filter in market_data[symbol]['info']['filters']:
            if ticker_filter['filterType'] == 'LOT_SIZE':
                ticker_info['step_size'] = float(ticker_filter['stepSize'])
        return ticker_info

    def get_open_orders(self):
        open_orders = self.binance.privateGetOpenOrders()
        return open_orders

    def get_open_orders_info(self):
        open_orders = self.get_open_orders()
        if open_orders:
            return [{'order_id': open_order['orderId'],
                     'order_list_id': open_order['orderListId'],
                     'internal_symbol': open_order['symbol']}
                    for open_order in open_orders]
        else:
            return []

    def cancel_order(self, symbol, order_id, order_list_id=-1, internal_symbol=False):
        if order_list_id != -1:
            param = {'symbol': symbol, 'orderListId': order_list_id}
            return self.binance.privateDeleteOrderList(param)
        elif internal_symbol:
            param = {'symbol': symbol, 'orderId': order_id}
            return self.binance.privateDeleteOrder(param)
        else:
            return self.binance.cancel_order(str(order_id), symbol)

    def cancel_all_order(self):
        self.logger.info('Cancel all order')
        orders_info = self.get_open_orders_info()
        result_list = []
        order_list_id_list = []

        for order_info in orders_info:
            internal_symbol = order_info['internal_symbol']
            order_id = order_info['order_id']
            order_list_id = order_info['order_list_id']
            if order_list_id in order_list_id_list:
                continue
            elif order_list_id != -1:
                order_list_id_list.append(order_list_id)
            result = self.cancel_order(internal_symbol, order_id, order_list_id=order_list_id, internal_symbol=True)
            result_list.append(result)
        self.logger.info(f'Cancel result: {result_list}')
        return True

    def get_balance(self, symbol=False, balance_type='total'):
        balance = self.binance.fetch_balance()
        if symbol:
            if balance_type == 'total':
                return balance[symbol]['total']
            elif balance_type == 'free':
                return balance[symbol]['free']
            elif balance_type == 'used':
                return balance[symbol]['used']
            else:
                raise NameError(f'Received {balance_type=}')
        else:
            return balance

    def create_order(self, symbol, side, amount, price=0, stop_price=0, order_type='market'):
        if order_type == 'market':
            self.logger.info(f'Create Order: {symbol=}, {side=}, {amount=}')
            return self.binance.create_order(symbol, order_type, side, amount)
        elif order_type == 'limit' and price:
            self.logger.info(f'Create Order: {symbol=}, {side=}, {amount=}, {price=}')
            return self.binance.create_order(symbol, order_type, side, amount, price)
        elif order_type == 'stop_limit' and price and stop_price:
            params = {'stopPrice': stop_price,
                      'type': 'stopLimit',
                      }
            self.logger.info(f'Create Order: {symbol=}, {side=}, {amount=}, {price=}, {params=}')
            return self.binance.create_order(symbol, 'limit', side, amount, price, params)
        else:
            raise NameError(f'Received {order_type=},{price=},{stop_price=}')

    def get_orderbook(self, symbol, limit=100):
        if limit > 5000:
            raise ValueError('Orderbook limit must be under 5000.')
        orderbook_data = self.binance.fetch_order_book(symbol, limit)
        orderbook = dict()
        orderbook['asks'] = orderbook_data['asks']
        orderbook['bids'] = orderbook_data['bids']
        return orderbook

    def sell_at_market(self, symbol):
        self.logger.info(f'Sell {symbol} at market')
        ticker, pair = symbol.split('/')
        ticker_balance = self.get_balance(symbol=ticker, balance_type='free')

        self.logger.info(f'{ticker} Balance: {ticker_balance}')
        order_result = self.create_order(symbol, 'sell', ticker_balance)
        self.logger.info(f'Order result: {order_result}')
        return True

    def buy_at_market(self, symbol, slip_rate=0.3):
        self.logger.info(f'Buy {symbol} at market')
        ticker, pair = symbol.split('/')
        pair_balance = self.get_balance(symbol=pair)
        self.logger.info(f'{pair} Balance: {pair_balance}')

        orderbook_limit = 100
        is_open = True
        max_try = 10
        while is_open and max_try:
            max_try -= 1
            orderbook = self.get_orderbook(symbol, limit=orderbook_limit)
            ask_volume = 0
            ask_price = 0
            for price, quantity in orderbook['asks']:
                ask_volume += price * quantity
                if pair_balance * (1 + slip_rate) < ask_volume:
                    ask_price = price
                    break
            if not ask_price:
                orderbook_limit += 100
                self.logger.info('Orderbook is weak. Enhance orderbook limit')
                continue

            self.logger.info(f'{symbol} Weighted average ask price: {ask_price}')
            amount = pair_balance / ask_price
            try:
                order_result = self.create_order(symbol, 'buy', amount)
            except ccxt.InsufficientFunds:
                self.logger.info(f'Insufficient funds when market buying. '
                                 f'Try again after 500ms. Remaining Try: {max_try}')
                sleep(0.5)
            else:
                self.logger.info(f'Order result: {order_result}')
                is_open = False
        return True if max_try else False

    def get_tickers_by_quote(self, quote):
        market_data = self.binance.load_markets()
        ticker_list = []
        for symbol in market_data.keys():
            _, pair = symbol.split('/')
            if quote == pair:
                ticker_list.append(symbol)
        return ticker_list


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
    bo = BinanceOrder(api_test['api_key'], api_test['api_secret'])
    # bo.show_basic_info()
    # bo.show_basic_market_info()

    # Test function
    # print('Exchange Status:', bo.check_exchange_status())
    # print('BTC/USDT ticker Status:', bo.check_ticker_status('BTC/USDT'))
    # print('BTC yearly Pivot:', bo.get_yearly_pivot('BTC/USDT'))
    # print('BTC monthly Pivot:', bo.get_monthly_pivot('BTC/USDT'))
    # pprint(bo.get_ticker_info('BTC/USDT'))
    # pprint(bo.get_open_orders())
    # print(bo.get_open_orders_info())
    # bo.cancel_order('BTC/USDT', order_id)
    # pprint(bo.cancel_all_order())
    # pprint(bo.get_balance())
    # pprint(bo.get_orderbook('BTC/USDT'))
    # bo.buy_at_market('ETH/BTC')
    # pprint(bo.get_tickers_by_quote('BTC'))
