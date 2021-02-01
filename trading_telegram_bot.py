import telegram
import os
from time import sleep
from _datetime import datetime, timedelta

chat_token = '1399429065:AAEN51utgK06fv-oye88_HdBMSdd4KTgB_c'
chat_id = "379055568"

bot = telegram.Bot(token=chat_token)
bot.sendMessage(chat_id=chat_id, text="안녕~")

a_week_balance = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
prev_average_balance = 0.0
while(True):
    yesterday = (datetime.now() - timedelta(1)).strftime('%Y-%m-%d')
    log_file_name = 'log/binance_adt_main/binance_adt_main.log.'+yesterday
    if not os.path.exists(log_file_name):
        bot.sendMessage(chat_id=chat_id, text="어제 기록된 로그 파일이 없어. 자러 갈게")
        sleep(60*60*24)  # 24 hours
        bot.sendMessage(chat_id=chat_id, text="다시 일을 시작해볼까?")
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
            a_week_balance = a_week_balance[1:] + [float(balance)]
            a_week_balance_non_zero = [daily_balance for daily_balance in a_week_balance if daily_balance]
            if a_week_balance_non_zero:
                average_balance = sum(a_week_balance_non_zero) / len(a_week_balance_non_zero)
            else:
                average_balance = 0.0
            # bot.sendMessage(chat_id=chat_id, text=f"Weekly Average Balance : {round(average_balance)} USDT")
            if prev_average_balance:
                change_rate = (average_balance - prev_average_balance) / prev_average_balance
            else:
                change_rate = -666
            # this price change rate display function is malfunction.
            # bot.sendMessage(chat_id=chat_id, text=f"Weekly Average Change Rate : {round(change_rate, 1)}%")
            bot.sendMessage(chat_id=chat_id, text="근무 중 이상 무!")
            prev_average_balance = average_balance
    sleep(60*60*24)  # 24 hours
