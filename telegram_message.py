import os
import telebot
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")

def send_telegram_message(text):
    try:
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="Markdown", disable_web_page_preview=True)
        print("✅ Telegram message sent")
    except Exception as e:
        print(f"❌ Telegram send failed: {str(e)}")

if __name__ == "__main__":
    send_telegram_message("Test: Telegram module works!")