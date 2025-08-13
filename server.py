import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")

# Автоматически подставляем домен Render
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
if not WEBHOOK_URL:
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not hostname:
        raise ValueError("❌ Не удалось определить хост Render")
    WEBHOOK_URL = f"https://{hostname}/webhook"

@app.route("/")
def home():
    return "Бот работает! Перейдите по /set_webhook чтобы активировать."

@app.route("/set_webhook")
def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    r = requests.get(url, params={"url": WEBHOOK_URL})
    return r.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.json
    if update and "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMes_
