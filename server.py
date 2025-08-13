# server.py
import os
import json
from datetime import datetime
from flask import Flask, request
import requests
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = os.environ.get("TELEGRAM_TOKEN")  # токен из переменной окружения
SECRET_API = os.environ.get("SECRET_API")  # секретный ключ для добавления напоминаний
CHAT_IDS = [370958352, 7148028443]  # кому шлём

app = Flask(__name__)
scheduler = BackgroundScheduler(timezone="Asia/Almaty")
scheduler.start()

REMINDERS_FILE = "reminders.json"

# --- Функции для работы с напоминаниями ---
def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

# --- Отправка сообщений ---
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

# --- Проверка и отправка напоминаний ---
def check_reminders():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    reminders = load_reminders()
    new_list = []
    for r in reminders:
        if r["datetime"] == now:
            for cid in CHAT_IDS:
                send_message(cid, r["text"])
        else:
            new_list.append(r)
    save_reminders(new_list)

scheduler.add_job(check_reminders, "interval", minutes=1)

# --- Telegram webhook ---
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.json
    if "message" in update and "text" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"]
        if text.lower() == "/start":
            send_message(chat_id, "Привет! Я бот-напоминатель!")
    return "ok"

# --- API для добавления напоминаний ---
@app.route("/add", methods=["POST"])
def add_reminder():
    data = request.json
    if data.get("secret") != SECRET_API:
        return {"error": "unauthorized"}, 403
    
    reminder = {
        "text": data["text"],
        "datetime": data["datetime"]  # формат YYYY-MM-DD HH:MM
    }
    reminders = load_reminders()
    reminders.append(reminder)
    save_reminders(reminders)
    return {"status": "added", "reminder": reminder}

@app.route("/")
def home():
    return "Бот работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
