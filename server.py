import os
import requests
from flask import Flask, request

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com

if not TOKEN:
    raise ValueError("❌ Переменная окружения TELEGRAM_TOKEN не установлена!")
if not WEBHOOK_URL:
    raise ValueError("❌ Переменная окружения WEBHOOK_URL не установлена!")

app = Flask(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Устанавливаем вебхук при старте
def set_webhook():
    url = f"{WEBHOOK_URL}/webhook"
    response = requests.get(f"{TELEGRAM_API_URL}/setWebhook", params={"url": url})
    print("📡 Результат установки вебхука:", response.json())

set_webhook()

# Обработка сообщений от Telegram
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text.lower() == "/start":
            send_message(chat_id, "Привет! Я работаю 🚀")
        else:
            send_message(chat_id, f"Ты написал: {text}")

    return "OK", 200

# Тестовая главная страница
@app.route("/", methods=["GET"])
def home():
    return "🤖 Telegram бот работает!", 200

# Функция отправки сообщений
def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
