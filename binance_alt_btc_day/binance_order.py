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

        self.logger.info('Update market and ticker data at initial.')
        self.market_data, self.ticker_data = dict(), dict()
        self.open_order_data = []
        self.update_market_data()
        self.update_ticker_data()

        self.btc_minimum_order_size = 0.001 * 1.3
        self.usdt_minimum_order_size = 10 * 1.3

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
        ohlcv = bo.get_ohlcv('BTC/USDT', '1m')
        # print(ohlcv)
        # pprint(self.binance.fetch_ticker('BTC/USDT'))
        pprint(self.binance.fetch_markets())

    def check_exchange_status(self):
        exchange_status = self.binance.fetch_status()
        status = exchange_status['status']
        if status == 'ok':
            return True
        else:
            return False

    def update_market_data(self):
        self.market_data = self.binance.load_markets()

    def update_ticker_data(self):
        self.ticker_data = self.binance.publicGetTicker24hr()

    def check_ticker_status(self, symbol, data_update=True):
        if data_update:
            market_data = self.binance.load_markets()
        else:
            market_data = self.market_data
        if symbol not in market_data.keys():
            return False

        ticker_data = market_data[symbol]
        if ticker_data['active']:
            return True
        else:
            return False

    def get_ticker_info(self, symbol, data_update=True):
        ticker_data = self.binance.fetch_ticker(symbol)
        if data_update:
            market_data = self.binance.load_markets()
        else:
            market_data = self.market_data
        ticker_info = dict()
        ticker_info['quote_volume'] = ticker_data['quoteVolume']
        ticker_info['ask'] = ticker_data['ask']
        ticker_info['bid'] = ticker_data['bid']
        ticker_info['last_price'] = ticker_data['last']
        ticker_info['timestamp'] = int(ticker_data['timestamp']/1000)
        ticker_info['internal_symbol'] = ticker_data['info']['symbol']
        for ticker_filter in market_data[symbol]['info']['filters']:
            if ticker_filter['filterType'] == 'PRICE_FILTER':
                ticker_info['tick_size'] = float(ticker_filter['tickSize'])
        for ticker_filter in market_data[symbol]['info']['filters']:
            if ticker_filter['filterType'] == 'LOT_SIZE':
                ticker_info['step_size'] = float(ticker_filter['stepSize'])
        return ticker_info

    def get_ticker_statistics(self, symbol, internal_symbol=False, data_update=True):
        original_symbol = symbol
        if not internal_symbol:
            symbol = symbol.replace('/', '')
            is_valid_symbol = False
            for data in self.ticker_data:
                if symbol == data['symbol']:
                    is_valid_symbol = True
                    break
            if not is_valid_symbol:
                ticker_info = self.get_ticker_info(original_symbol)
                symbol = ticker_info['internal_symbol']

        ticker_24hr_stat = dict()
        if data_update:
            param = {'symbol': symbol}
            ticker_24hr_stat = self.binance.publicGetTicker24hr(param)
        else:
            for data in self.ticker_data:
                if symbol == data['symbol']:
                    ticker_24hr_stat = data
                    break

        if not ticker_24hr_stat:
            raise ValueError(f'Received {symbol}. ticker is invalid')

        ticker_stat = dict()
        ticker_stat['last_price'] = float(ticker_24hr_stat['lastPrice'])
        ticker_stat['quote_volume'] = float(ticker_24hr_stat['quoteVolume'])

        return ticker_stat

    def get_tickers_by_quote(self, quote, data_update=True):
        if data_update:
            market_data = self.binance.load_markets()
        else:
            market_data = self.market_data
        ticker_list = []
        for symbol in market_data.keys():
            _, pair = symbol.split('/')
            if quote == pair:
                ticker_list.append(symbol)
        return ticker_list

    def get_ohlcv(self, symbol, interval, limit=False):
        if limit:
            ohlcv_original = self.binance.fetch_ohlcv(symbol, interval, limit=limit)
        else:
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
            pivot[key] = float(pivot[key])
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

    def get_open_orders(self):
        open_orders = self.binance.privateGetOpenOrders()
        if open_orders:
            return [{'order_id': open_order['orderId'],
                     'order_list_id': open_order['orderListId'],
                     'internal_symbol': open_order['symbol'],
                     'original_quantity': open_order['origQty'],
                     'executed_quantity': open_order['executedQty'],
                     'timestamp': int(open_order['time'] // 1000)
                     }
                    for open_order in open_orders]
        else:
            return []

    def update_open_order_data(self):
        self.open_order_data = self.get_open_orders()

    def get_open_order_info(self, order_id, data_update=True):
        if data_update:
            open_orders = self.get_open_orders()
        else:
            open_orders = self.open_order_data
        for open_order in open_orders:
            if open_order['order_id'] == order_id:
                return open_order
        return False

    def get_order_stat(self, order_id, symbol):
        order_data = self.binance.fetch_order(order_id, symbol=symbol)
        order_stat = {'status': order_data['info']['status'].lower(),  # type: new, partially_filled, filled, canceled
                      'executed_quantity': order_data['info']['executedQty'],
                      }
        return order_stat

    def cancel_order(self, symbol, order_id, order_list_id=-1, internal_symbol=False):
        if order_list_id != -1:
            param = {'symbol': symbol, 'orderListId': order_list_id}
            return self.binance.privateDeleteOrderList(param)
        elif internal_symbol:
            param = {'symbol': symbol, 'orderId': order_id}
            return self.binance.privateDeleteOrder(param)
        else:
            return self.binance.cancel_order(str(order_id), symbol)

    def cancel_all_order(self, normal=True, oco=True):
        if oco:
            self.logger.info('Cancel all OCO order')
        if normal:
            self.logger.info('Cancel all normal order')
        if not oco and not normal:
            raise ValueError('Either OCO or normal should be True')
        orders_info = self.get_open_orders_info()
        result_list = []
        order_list_id_list = []

        for order_info in orders_info:
            internal_symbol = order_info['internal_symbol']
            order_id = order_info['order_id']
            order_list_id = order_info['order_list_id']
            if order_list_id in order_list_id_list:
                continue
            elif oco:
                if order_list_id != -1:
                    order_list_id_list.append(order_list_id)
            if normal:
                if order_list_id == -1:
                    order_list_id_list.append(order_list_id)
                else:
                    continue
            result = self.cancel_order(internal_symbol, order_id, order_list_id=order_list_id, internal_symbol=True)
            result_list.append(result)
        self.logger.info(f'Cancel result: {result_list}')
        return True

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

    def create_oco_order(self, symbol, side, amount, price, stop_price, limit_price,
                         time_in_force='GTC', internal_symbol=False):
        ticker_info = self.get_ticker_info(symbol)
        if not internal_symbol:
            symbol = ticker_info['internal_symbol']
        side = side.upper()
        # TODO: make valid precision
        amount = amount
        price = price
        stop_price = stop_price
        limit_price = limit_price
        self.logger.info(f'Create Order: {symbol=}, {side=}, {amount=}, {price=}, {stop_price=}, {limit_price=}')
        params = {'symbol': symbol,
                  'side': side,
                  'quantity': amount,
                  'price': price,
                  'stopPrice': stop_price,
                  'stopLimitPrice': limit_price,
                  'stopLimitTimeInForce': time_in_force}
        return self.binance.privatePostOrderOco(params)

    def get_orderbook(self, symbol, limit=100):
        if limit > 5000:
            raise ValueError('Orderbook limit must be under 5000.')
        orderbook_data = self.binance.fetch_order_book(symbol, limit)
        orderbook = dict()
        orderbook['asks'] = orderbook_data['asks']
        orderbook['bids'] = orderbook_data['bids']
        return orderbook

    def check_order_quantity(self, symbol, quantity):
        ticker_info = self.get_ticker_info(symbol, data_update=False)
        step_size = ticker_info['step_size']
        last_price = ticker_info['last_price']
        quote_quantity = quantity * last_price
        if quantity < step_size:
            return False
        ticker, pair = symbol.split('/')
        if pair == 'BTC':
            if quote_quantity < self.btc_minimum_order_size:
                return False
        elif pair == 'USDT':
            if quote_quantity < self.usdt_minimum_order_size:
                return False
        else:
            raise ValueError(f'{pair} pair order size is not defined')
        return True

    def sell_at_market(self, symbol, quantity=False):
        self.logger.info(f'Sell {symbol} at market')
        ticker, pair = symbol.split('/')
        if not quantity:
            quantity = self.get_balance(symbol=ticker, balance_type='free')
        if not self.check_order_quantity(symbol, quantity):
            self.logger.info(f'{pair} quantity({quantity}) is under minimum order size. Cancel order')
            return False

        self.logger.info(f'{ticker} Quantity: {quantity}')

        order_result = self.create_order(symbol, 'sell', quantity)
        self.logger.info(f'Order result: {order_result}')
        return True

    def buy_at_market(self, symbol, slip_rate=0.3, pair_quantity=False):
        self.logger.info(f'Buy {symbol} at market')
        ticker, pair = symbol.split('/')
        if not pair_quantity:
            pair_quantity = self.get_balance(symbol=pair)
        ticker_info = self.get_ticker_info(symbol, data_update=False)
        last_price = ticker_info['last_price']
        quantity = pair_quantity / last_price
        if not self.check_order_quantity(symbol, quantity):
            self.logger.info(f'{pair} quantity({quantity}) is under minimum order size. Cancel order')
            return False

        orderbook_limit = 100
        is_open = True
        max_try = 10
        while is_open and max_try:
            max_try -= 1
            orderbook = self.get_orderbook(symbol, limit=orderbook_limit)
            ask_volume = 0
            ask_quantity = 0
            weighted_ask_price = 0
            for price, quantity in orderbook['asks']:
                ask_volume += price * quantity
                ask_quantity += quantity
                if pair_quantity * (1 + slip_rate) < ask_volume:
                    weighted_ask_price = ask_volume / ask_quantity
                    break
            if not weighted_ask_price:
                orderbook_limit += 100
                self.logger.info('Orderbook is weak. Enhance orderbook limit')
                continue

            self.logger.info(f'{symbol} Weighted average ask price: {weighted_ask_price}')
            amount = pair_quantity / weighted_ask_price
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
    # pprint(bo.get_ticker_info('LTC/BTC'))
    # pprint(bo.get_open_orders())
    # print(bo.get_open_orders_info())
    # bo.get_order_stat(842733901, 'BTC/USDT')
    # bo.cancel_order('BTC/USDT', 842733901)
    # pprint(bo.cancel_all_order())
    # pprint(bo.get_balance())
    # pprint(bo.get_orderbook('BTC/USDT'))
    # bo.buy_at_market('FET/BTC')
    # pprint(bo.get_tickers_by_quote('BTC'))
    # pprint(bo.get_ticker_statistics('BTC/USDT'))
    # pprint(bo.binance.fetch_orders('LTC/BTC'))
    # pprint(bo.create_oco_order('BTC/USDT', 'sell', 0.01, 9000, 5000, 4000))
