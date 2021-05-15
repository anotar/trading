import telegram
from telegram.ext import Updater, CommandHandler
import os
from time import sleep
from _datetime import datetime, timedelta

chat_token = '1399429065:AAEN51utgK06fv-oye88_HdBMSdd4KTgB_c'
chat_id = "379055568"
telegram_bot_switch = 1

bot = telegram.Bot(token=chat_token)
bot.sendMessage(chat_id=chat_id, text="안녕~")

# telegram bot updater
updater = Updater(token=chat_token, use_context=True)
dispatcher = updater.dispatcher


# telegram bot command handler
def help_message(update, context):
    context.bot.send_message(chat_id=chat_id, text="/kill_telegram_bot : 텔레그램 봇을 종료합니다.")
    context.bot.send_message(chat_id=chat_id, text="/kill_trading_bot : 트레이딩 봇을 종료합니다.")
    context.bot.send_message(chat_id=chat_id, text="/turn_on_trading_bot : 트레이딩 봇의 스위치를 킵니다.")


def kill_telegram_bot(update, context):
    global telegram_bot_switch
    telegram_bot_switch = 0


def kill_trading_bot(update, context):
    switch_stat = None
    with open('data/Binance/AltDailyTrading/bot_switch.txt', 'r') as bot_switch_txt:
        bot_switch_texts = bot_switch_txt.readlines()
        for file_text in bot_switch_texts:
            if "switch :" in file_text and "#" != file_text[0]:
                switch_stat = int(file_text.rstrip('\n').rstrip(' ')[-1])
                if switch_stat == 0:
                    bot.sendMessage(chat_id=chat_id, text="이미 트레이딩 봇 스위치가 꺼져있어요")
                elif switch_stat == 1:
                    bot.sendMessage(chat_id=chat_id, text="트레이딩 봇의 스위치를 내렸어요.")
    if switch_stat:
        with open('data/Binance/AltDailyTrading/bot_switch.txt', 'w') as bot_switch_txt:
            for file_text in bot_switch_texts:
                if "switch :" in file_text and "#" != file_text[0]:
                    bot_switch_txt.write(file_text.replace('1', '0'))
                else:
                    bot_switch_txt.write(file_text)


def turn_on_trading_bot(update, context):
    switch_stat = None
    with open('data/Binance/AltDailyTrading/bot_switch.txt', 'r') as bot_switch_txt:
        bot_switch_texts = bot_switch_txt.readlines()
        for file_text in bot_switch_texts:
            if "switch :" in file_text and "#" != file_text[0]:
                switch_stat = int(file_text.rstrip('\n').rstrip(' ')[-1])
                if switch_stat == 0:
                    bot.sendMessage(chat_id=chat_id, text="트레이딩 봇을 킬게요.")
                elif switch_stat == 1:
                    bot.sendMessage(chat_id=chat_id, text="이미 트레이딩 봇의 스위치가 켜져있어요")
    if not switch_stat:
        with open('data/Binance/AltDailyTrading/bot_switch.txt', 'w') as bot_switch_txt:
            for file_text in bot_switch_texts:
                if "switch :" in file_text and "#" != file_text[0]:
                    bot_switch_txt.write(file_text.replace('0', '1'))
                else:
                    bot_switch_txt.write(file_text)


help_handler = CommandHandler('help', help_message)
dispatcher.add_handler(help_handler)
telegram_bot_handler = CommandHandler('kill_telegram_bot', kill_telegram_bot)
dispatcher.add_handler(telegram_bot_handler)
trading_bot_switch_off_handler = CommandHandler('kill_trading_bot', kill_trading_bot)
dispatcher.add_handler(trading_bot_switch_off_handler)
trading_bot_switch_on_handler = CommandHandler('turn_on_trading_bot', turn_on_trading_bot)
dispatcher.add_handler(trading_bot_switch_on_handler)
updater.start_polling()

today = 0
while telegram_bot_switch:
    yesterday = (datetime.now() - timedelta(1)).strftime('%Y-%m-%d')
    log_file_name = 'log/binance_adt_main/binance_adt_main.log.'+yesterday

    if datetime.utcnow().day != today and datetime.utcnow().minute:
        today = datetime.utcnow().day
        if not os.path.exists(log_file_name):
            bot.sendMessage(chat_id=chat_id, text="어제 기록된 로그 파일이 없어. 자러 갈게")
            continue
        with open(log_file_name, 'r') as log:
            logs = log.readlines()
            error_flag = False
            error_list = list()
            for log_line in logs:
                if "ERROR" in log_line.upper():
                    error_flag = True
                    error_list.append(log_line.rstrip('\n'))
                elif "Estimated Balance in USDT" in log_line:
                    balance = str(round(float(log_line.rstrip('\n').split(" ")[-1]), 1))
            if error_flag:
                bot.sendMessage(chat_id=chat_id, text="=====ERROR LIST=====")
                for error_line in error_list[-10:]:
                    bot.sendMessage(chat_id=chat_id, text=error_line)
                bot.sendMessage(chat_id=chat_id, text="====================")
                bot.sendMessage(chat_id=chat_id, text="문제가 발생해 이를 보고합니다!")
            else:
                bot.sendMessage(chat_id=chat_id, text="근무 중 이상 무!")
    sleep(1)
updater.stop()
bot.sendMessage(chat_id=chat_id, text="텔레그램 봇을 종료합니다~")
