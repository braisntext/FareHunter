import os
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT")

class Notifier:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None
    def send(self, text: str):
        if self.bot and TELEGRAM_CHAT:
            self.bot.send_message(chat_id=TELEGRAM_CHAT, text=text, disable_web_page_preview=True)
        else:
            print("[ALERTA]", text)
