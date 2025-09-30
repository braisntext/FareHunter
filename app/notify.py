# app/notify.py — versión simple y robusta vía HTTP API
import os, requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT")

class Notifier:
    def __init__(self):
        self.token = TELEGRAM_TOKEN
        # Permite varios chats separados por coma: "12345,-100666..."
        self.chats = [c.strip() for c in (TELEGRAM_CHAT or "").split(",") if c.strip()]

    def send(self, text: str):
        if not (self.token and self.chats):
            print("[ALERTA] (sin token/chat) ", text); return
        for cid in self.chats:
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    data={"chat_id": cid, "text": text, "disable_web_page_preview": True},
                    timeout=15
                )
                r.raise_for_status()
            except Exception as e:
                print(f"[ALERTA][ERROR chat {cid}] {e}")
