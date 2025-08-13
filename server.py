import os
import json
import threading
import time
from datetime import datetime, timedelta
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # токен бота из Render
WEBHOOK_URL = os.getenv("WEBHOOK_URL")        # твой домен из Render
SPREADSHEET_ID = "1_J8qvlkR2ekp5Q7_KxWoZyK3unAaWDTX_TMkM5erhSU"  # ID Google Sheets
CHAT_IDS = ["370958352", "7148028443"]  # кому отправлять напоминания

# === ПОДКЛЮЧЕНИЕ К GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("angelic-hexagon-468906-h0-b55ff80606dd.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# === ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЯ ===
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

# === ФУНКЦИЯ ПРОВЕРКИ НАПОМИНАНИЙ ===
def check_reminders():
    while True:
        try:
            reminders = sheet.get_all_records()
            now = datetime.now()
            for r in reminders:
                try:
                    reminder_time = datetime.strptime(r["datetime"], "%Y-%m-%d %H:%M")
                    if not r.get("done") and reminder_time <= now:
                        for chat_id in CHAT_IDS:
                            send_message(chat_id, f"🔔 Напоминание: {r['text']}")
                        sheet.update_cell(r["row"], r["done_col"], "yes")
                except Exception as e:
                    print(f"Ошибка в напоминании: {e}")
        except Exception as e:
            print(f"Ошибка чтения Google Sheets: {e}")
        time.sleep(60)

# === FLASK СЕРВЕР ===
app = Flask(__name__)

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    return {"ok": True}

@app.route("/", methods=["GET"])
def index():
    return "Бот запущен и ждет напоминаний!"

# === ЗАПУСК ПОТОКА ПРОВЕРКИ ===
threading.Thread(target=check_reminders, daemon=True).start()

# === УСТАНОВКА ВЕБХУКА ===
def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    data = {"url": f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"}
    r = requests.post(url, data=data)
    print("📡 Результат установки вебхука:", r.json())

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=10000)
