import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен бота берём из переменной окружения
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # адрес вебхука (твой домен на Render)

if not BOT_TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")
if not WEBHOOK_URL:
    raise ValueError("❌ Переменная окружения WEBHOOK_URL не установлена!")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Установка вебхука при старте
def setup_webhook():
    url = f"{TELEGRAM_API_URL}/setWebhook"
    response = requests.post(url, data={"url": WEBHOOK_URL})
    print("Webhook setup response:", response.json())

setup_webhook()

@app.route("/", methods=["GET"])
def home():
    return "Бот работает!", 200

@app.route("/", methods=["POST"])
def webhook():
    update = request.get_json()

    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "Привет! Я работаю на Render 🚀")
        else:
            send_message(chat_id, f"Ты написал: {text}")

    return "", 200

def send_message(chat_id, text):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
