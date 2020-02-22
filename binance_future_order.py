import logging
import os.path
from binance_order import BinanceOrder
from pprint import pprint
from datetime import datetime, timezone
import pandas as pd


class BinanceFutureOrder(BinanceOrder):
    def __init__(self, api_key, api_secret):
        self.logger = setup_logger('binance_future_order')
        self.logger.info('Setting Binance Future Order Module...')
        super().__init__(api_key, api_secret)
        self.logger = setup_logger('binance_future_order')
        self.logger.info('Binance Future Order Module Setup Completed')

        self.side_type = ['long', 'short']
        self.contract_spec = [(50000, 0.004, 0),  # (Position Bracket, Maintenance Margin Rate, Maintenance Amount)
                              (250000, 0.005, 50),
                              (1000000, 0.01, 1300),
                              (5000000, 0.025, 16300)]

        self.btc_spec = {'tick_size': 0.01,
                         'minimum_quantity': 0.001,
                         'maximum_quantity': 1000,
                         }

    def get_future_ohlcv(self, internal_symbol, interval, limit=False):
        if limit:
            param = {'symbol': internal_symbol, 'interval': interval}
            ohlcv_original = self._try_until_timeout(self.binance.fapiPublicGetKlines, param)
        else:
            param = {'symbol': internal_symbol, 'interval': interval, 'limit': limit}
            ohlcv_original = self._try_until_timeout(self.binance.fapiPublicGetKlines, param)
        if ohlcv_original in self.error_list:
            return pd.DataFrame()
        ohlcv = pd.DataFrame()
        ohlcv['timestamp'] = [int(ohlcv_list[0]/1000) for ohlcv_list in ohlcv_original]
        ohlcv['open'] = [float(ohlcv_list[1]) for ohlcv_list in ohlcv_original]
        ohlcv['high'] = [float(ohlcv_list[2]) for ohlcv_list in ohlcv_original]
        ohlcv['low'] = [float(ohlcv_list[3]) for ohlcv_list in ohlcv_original]
        ohlcv['close'] = [float(ohlcv_list[4]) for ohlcv_list in ohlcv_original]
        ohlcv['volume'] = [float(ohlcv_list[5]) for ohlcv_list in ohlcv_original]

        utc_timezone = timezone.utc
        ohlcv['time'] = [datetime.fromtimestamp(timestamp, utc_timezone) for timestamp in ohlcv['timestamp']]
        ohlcv['year'] = [time.year for time in ohlcv['time']]
        ohlcv['month'] = [time.month for time in ohlcv['time']]
        ohlcv['day'] = [time.day for time in ohlcv['time']]
        ohlcv['hour'] = [time.hour for time in ohlcv['time']]
        return ohlcv

    def get_future_monthly_pivot(self, internal_symbol):
        ohlcv = self.get_future_ohlcv(internal_symbol, '1M', limit=5)
        if ohlcv.empty:
            return False
        if not len(ohlcv) > 1:
            return False
        high = ohlcv['high'].iloc[-2]
        low = ohlcv['low'].iloc[-2]
        close = ohlcv['close'].iloc[-2]
        pivot = self.get_pivot(high, low, close)
        return pivot

    def get_last_price(self, internal_symbol):
        param = {'symbol': internal_symbol}
        ticker_info = self._try_until_timeout(self.binance.fapiPublicGetTickerPrice, param)
        if ticker_info in self.error_list:
            return False
        return float(ticker_info['price'])

    def get_future_ticker_info(self, internal_symbol):
        param = {'symbol': internal_symbol}
        recent_trades = self._try_until_timeout(self.binance.fapiPublicGetTrades, param)
        if recent_trades in self.error_list:
            return False
        last_trade = recent_trades[-1]
        ticker_info = {'last_price': float(last_trade['price']),
                       'timestamp': int(last_trade['time']) / 1000}
        return ticker_info

    def get_future_balance(self):
        balance_info = self._try_until_timeout(self.binance.fapiPrivateGetBalance)
        if balance_info in self.error_list:
            return False
        usdt_balance = float(balance_info[0]['balance'])
        return usdt_balance

    def liquidation_price_calculator(self, entry_price, quantity, balance, side):
        direction = 0
        if side not in self.side_type:
            return False
        elif side == 'short':
            direction = -1
        elif side == 'long':
            direction = 1
        usdt_quantity = entry_price * quantity
        maintenance_margin_rate = 0
        maintenance_amount = 0
        for level in self.contract_spec:
            position_bracket = level[0]
            if position_bracket >= usdt_quantity:
                maintenance_margin_rate = level[1]
                maintenance_amount = level[2]
                break
            else:
                continue
        if not maintenance_margin_rate:
            raise ValueError(f'Quantity {quantity} at price {entry_price} over trading bot spec')
        liquidation_price = (balance + maintenance_amount - (direction * quantity * entry_price)) /\
                            (quantity * (maintenance_margin_rate - direction))
        return round(liquidation_price, 2)

    def sr2_liquidation_calculator(self, entry_price, sr2, balance, side):
        self.logger.info(f'SR2 liquidation price calculation starts. {side} at {entry_price} SR2 {sr2} with {balance}')
        leverage = 0
        prev_lev_liq_price = 0
        if side not in self.side_type:
            return False
        elif side == 'short':
            is_over_sr2 = False
            while not is_over_sr2 or leverage > 125:
                leverage += 1
                quantity = round(leverage * balance / entry_price, 3)
                liquidation_price = self.liquidation_price_calculator(entry_price, quantity, balance, 'short')
                if liquidation_price < sr2:
                    leverage -= 1
                    is_over_sr2 = True
                else:
                    prev_lev_liq_price = liquidation_price
        elif side == 'long':
            is_under_sr2 = False
            while not is_under_sr2:
                leverage += 1
                quantity = round(leverage * balance / entry_price, 3)
                liquidation_price = self.liquidation_price_calculator(entry_price, quantity, balance, 'long')
                if liquidation_price > sr2 or leverage > 125:
                    leverage -= 1
                    is_under_sr2 = True
                else:
                    prev_lev_liq_price = liquidation_price
        quantity = round(leverage * balance / entry_price, 3)
        self.logger.info(f'Calculated leverage is {leverage}. Estimated liquidation price is {prev_lev_liq_price}')
        return leverage, quantity

    def cancel_all_future_order(self, internal_symbol):
        self.logger.info('Cancel all order')
        param = {'symbol': internal_symbol}
        cancel_result = self._try_until_timeout(self.binance.fapiPrivateDeleteAllOpenOrders, param,)
        if cancel_result in self.error_list:
            return False
        self.logger.info(f'Cancel result: {cancel_result}')
        return True

    def get_position_information(self):
        position_information = self._try_until_timeout(self.binance.fapiPrivateGetPositionRisk)
        if position_information in self.error_list:
            return False
        return position_information

    def change_margin_type(self, internal_symbol, margin_type):
        upper_type = margin_type.upper()
        margin_type_list = ['ISOLATED', 'CROSSED']
        if upper_type not in margin_type_list:
            raise ValueError(f'{upper_type} type is not defined')

        self.logger.info(f'Change margin type to {upper_type}')
        position_information = self.get_position_information()
        assert position_information
        for ticker_position in position_information:
            if ticker_position['symbol'] == internal_symmbol:
                if ticker_position['marginType'] == 'isolated' and upper_type == 'ISOLATED':
                    self.logger.info(f'Current margin type is already isolated margin')
                    return True
                elif ticker_position['marginType'] == 'cross' and upper_type == 'CROSSED':
                    self.logger.info(f'Current margin type is already cross margin')
                    return True
        param = {'symbol': internal_symbol,
                 'marginType': upper_type
                 }
        change_result = self._try_until_timeout(self.binance.fapiPrivatePostMarginType, param)
        if change_result in self.error_list:
            return False
        self.logger.info(f'Change result: {change_result}')
        return True

    def set_leverage(self, internal_symbol, leverage):
        self.logger.info(f'Set leverage to {leverage}')
        leverage = int(leverage)
        if leverage > 125 or leverage < 1:
            raise ValueError(f'Leverage {leverage} should be between 1 to 125 as a integer')
        param = {'symbol': internal_symbol,
                 'leverage': leverage,
                 }
        set_result = self._try_until_timeout(self.binance.fapiPrivatePostLeverage, param)
        if set_result in self.error_list:
            return False
        self.logger.info(f'Set result: {set_result}')
        return True

    def create_future_order(self, internal_symbol, side, order_type, amount, price=0, stop_price=0,
                            time_in_force='GTC'):
        side = side.upper()
        order_type = order_type.upper()
        assert side in ['BUY', 'SELL']
        assert order_type in ['LIMIT', 'MARKET', 'STOP', 'STOP_MARKET']
        param = dict()
        amount = self.amount_to_precision(internal_symbol, amount)

        if order_type == 'LIMIT':
            price = self.price_to_precision(internal_symbol, price)
            param = {'symbol': internal_symbol,
                     'side': side,
                     'quantity': amount,
                     'price': price,
                     'stopLimitTimeInForce': time_in_force}
        elif order_type == 'MARKET':
            param = {'symbol': internal_symbol,
                     'side': side,
                     'quantity': amount,
                     }
        elif order_type == 'STOP':
            price = self.price_to_precision(internal_symbol, price)
            stop_price = self.price_to_precision(internal_symbol, stop_price)
            param = {'symbol': internal_symbol,
                     'side': side,
                     'quantity': amount,
                     'price': price,
                     'stopPrice': stop_price,
                     }
        elif order_type == 'STOP_MARKET':
            stop_price = self.price_to_precision(internal_symbol, stop_price)
            param = {'symbol': internal_symbol,
                     'side': side,
                     'quantity': amount,
                     'stopPrice': stop_price,
                     }

        order_result = self._try_until_timeout(self.binance.fapiPrivatePostOrder, param)
        if order_result in self.error_list:
            return False
        else:
            return order_result

    def amount_to_precision(self, internal_symbol, amount):
        assert internal_symbol == 'BTCUSDT'
        tick_size = self.btc_spec['tick_size']
        minimum_quantity = self.btc_spec['minimum_quantity']
        maximum_quantity = self.btc_spec['maximum_quantity']
        precise_amount = str((amount // minimum_quantity) * minimum_quantity)
        return precise_amount

    def price_to_precision(self, internal_symbol, price):
        assert internal_symbol == 'BTCUSDT'
        tick_size = self.btc_spec['tick_size']
        minimum_quantity = self.btc_spec['minimum_quantity']
        maximum_quantity = self.btc_spec['maximum_quantity']
        precise_amount = str((price // tick_size) * tick_size)
        return precise_amount

    def close_position(self, internal_symbol):
        raise NotImplementedError

    # create margin order function


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
    bfo = BinanceFutureOrder(api_test['api_key'], api_test['api_secret'])

    param = {'symbol': 'BTCUSDT'}
    internal_symmbol = 'BTCUSDT'
    # print(bfo.binance.fapiPublicGetTickerPrice(param))
    # pprint(bfo.get_future_monthly_pivot(internal_symmbol))
    # print(bfo.get_last_price(internal_symmbol))
    # pprint(bfo.get_future_ticker_info(internal_symmbol))
    # pprint(bfo.get_future_balance())
    # print(bfo.liquidation_price_calculator(10800, 100, 100000, 'short'))
    # print(bfo.sr2_liquidation_calculator(9813, 9130, 100, 'long'))
    # print(bfo.cancel_all_future_order(internal_symmbol))
    # print(bfo.change_margin_type(internal_symmbol, 'crossed'))
    # pprint(bfo.get_position_information())
    # pprint(bfo.set_leverage(internal_symmbol, 13))
