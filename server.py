import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request
import requests
import threading
import time

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8390901633:AAGWzRUhrm2qst2IDyk9tDwJvJvq2Lxv6Nw")
BOT_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
CHAT_IDS = [370958352, 7148028443]  # кому будут приходить уведомления
TIMEZONE_OFFSET = 5  # разница в часах (GMT+5)

REMINDERS_FILE = "reminders.json"

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

# === СОЗДАНИЕ ФАЙЛА ЕСЛИ ЕГО НЕТ ===
if not os.path.exists(REMINDERS_FILE):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    logging.info(f"Файл {REMINDERS_FILE} создан.")

# === ФУНКЦИИ ===
def load_reminders():
    with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def add_reminder(text, remind_time):
    reminders = load_reminders()
    reminders.append({"text": text, "time": remind_time})
    save_reminders(reminders)
    logging.info(f"Добавлено напоминание: {text} на {remind_time}")

def send_message(chat_id, text):
    requests.post(BOT_URL, json={"chat_id": chat_id, "text": text})

def check_reminders():
    while True:
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        now_str = now.strftime("%Y-%m-%d %H:%M")
        reminders = load_reminders()
        new_list = []
        for r in reminders:
            if r["time"] == now_str:
                for chat_id in CHAT_IDS:
                    send_message(chat_id, f"🔔 Напоминание: {r['text']}")
                logging.info(f"Отправлено напоминание: {r['text']}")
            else:
                new_list.append(r)
        save_reminders(new_list)
        time.sleep(60)  # проверяем каждую минуту

# === ЗАПУСК ФОНА ===
threading.Thread(target=check_reminders, daemon=True).start()

# === FLASK ПРИЛОЖЕНИЕ ===
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.get_json()
        logging.info(f"Получено: {data}")
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")

            if text.startswith("/add"):
                try:
                    _, date_str, time_str, *reminder_text = text.split()
                    reminder_text = " ".join(reminder_text)
                    remind_time = f"{date_str} {time_str}"
                    add_reminder(reminder_text, remind_time)
                    send_message(chat_id, f"✅ Напоминание добавлено на {remind_time}")
                except Exception as e:
                    send_message(chat_id, "❌ Формат: /add YYYY-MM-DD HH:MM текст")
            elif text.startswith("/list"):
                reminders = load_reminders()
                if reminders:
                    msg = "\n".join([f"{r['time']} — {r['text']}" for r in reminders])
                else:
                    msg = "Нет активных напоминаний."
                send_message(chat_id, msg)
            else:
                send_message(chat_id, "Привет! Я работаю.\n"
                                       "Добавить: /add YYYY-MM-DD HH:MM текст\n"
                                       "Список: /list")
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
