import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
if not WEBHOOK_URL:
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if hostname:
        WEBHOOK_URL = f"https://{hostname}/webhook"
    else:
        raise ValueError("❌ WEBHOOK_URL не задан и Render не передал домен!")


def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.get(url, params={"url": WEBHOOK_URL})
    print("📡 Результат установки вебхука:", r.json())


# Устанавливаем вебхук при старте сервера
with app.app_context():
    set_webhook()


@app.route("/")
def home():
    return "✅ Бот работает!"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json
    if update and "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"Вы написали: {text}"
        })

    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
