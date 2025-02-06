# main.py
from telegram.ext import Updater
from telegram_handler import setup_dispatcher
import logging

def main():
    TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # Replace with your Telegram bot token
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher
    setup_dispatcher(dp)
    updater.start_polling()
    logging.info("Bot đã khởi chạy và đang lắng nghe tin nhắn...")
    updater.idle()

if __name__ == '__main__':
    main()
