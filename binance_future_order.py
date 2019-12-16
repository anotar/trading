import logging
import os.path
from binance_order import BinanceOrder


class BinanceFutureOrder(BinanceOrder):
    def __init__(self, api_key, api_secret):
        self.logger = setup_logger('binance_future_order')
        self.logger.info('Setting Binance Future Order Module...')
        super().__init__(api_key, api_secret)
        self.logger = setup_logger('binance_future_order')
        self.logger.info('Binance Future Order Module Setup Completed')


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

    pram = {'type': 'futures'}
    print(bfo.binance.fetch_balance(params=pram))