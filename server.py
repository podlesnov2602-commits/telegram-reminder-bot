import os
import json
import threading
import time
from datetime import datetime, timedelta
import requests
from flask import Flask, request

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Берёт токен из переменной окружения на Render
USER_IDS = [370958352, 7148028443]  # ID получателей
TIMEZONE_OFFSET = 5  # GMT+5

REMINDERS_FILE = "reminders.json"
CHECK_INTERVAL = 30  # секунд

app = Flask(__name__)

# ===== ФУНКЦИИ =====
def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def send_message(user_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": user_id, "text": text})

def check_reminders():
    while True:
        reminders = load_reminders()
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        updated = []
        for r in reminders:
            remind_time = datetime.strptime(r["time"], "%Y-%m-%d %H:%M")
            if now >= remind_time:
                for uid in USER_IDS:
                    send_message(uid, f"🔔 Напоминание: {r['text']}")
            else:
                updated.append(r)
        if len(updated) != len(reminders):
            save_reminders(updated)
        time.sleep(CHECK_INTERVAL)

# ===== ТЕСТОВЫЕ НАПОМИНАНИЯ =====
def create_test_reminders():
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    test_data = [
        {"time": (now + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M"), "text": "Тестовое напоминание через 5 минут"},
        {"time": (now + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"), "text": "Тестовое напоминание через 10 минут"}
    ]
    save_reminders(test_data)

# ===== ОБРАБОТЧИКИ =====
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.json
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "").strip()
            if text.lower() == "/start":
                send_message(chat_id, "✅ Бот работает. Напоминания будут приходить автоматически.")
    return "OK"

# ===== ЗАПУСК =====
if __name__ == "__main__":
    if not os.path.exists(REMINDERS_FILE):
        create_test_reminders()
    threading.Thread(target=check_remin_
