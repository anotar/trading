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
    print(bfo.sr2_liquidation_calculator(9813, 9130, 100, 'long'))
