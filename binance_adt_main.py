from binance_adt_trade import BinanceAltDailyTrade
from time import sleep
import logging
import os
from logging import handlers


def setup_logger(name):
    log_dir = f'./log/{name}/'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    rotate_handler = handlers.TimedRotatingFileHandler(
        filename=log_dir+name+'.log', when='midnight', interval=1, encoding='utf-8')
    rotate_handler.setFormatter(formatter)
    logger.addHandler(rotate_handler)

    return logger


logger = setup_logger('binance_adt_main')
logger.info('Set up Binance Alt Daily Trading...')

with open('api/binance_kjss970_naver.txt', 'r') as f:
    api_keys = f.readlines()
api_test = {'api_key': api_keys[0].rstrip('\n'), 'api_secret': api_keys[1]}
binanceADT = BinanceAltDailyTrade(api_test['api_key'], api_test['api_secret'])

logger.info('Start Binance Alt Daily Trading')
binanceADT.start_trade()
bot_kill_switch = 0
while not bot_kill_switch:
    with open('data/binance/AltDailyTrading/kill_switch.txt', 'r') as kill_switch_txt:
        kill_switch_texts = kill_switch_txt.readlines()
        for file_text in kill_switch_texts:
            if "switch :" in file_text and "#" != file_text[0]:
                switch_stat = int(file_text.rstrip('\n').rstrip(' ')[-1])
                if bot_kill_switch != switch_stat:
                    bot_kill_switch = switch_stat
                    if bot_kill_switch:
                        logger.info("Bot kill switch is turned On")
                        logger.info("Terminating the bot...")
                        break
                    else:
                        logger.info("Bot kill switch is turned Off")
    sleep(1)
logger.info("Bot terminated.")