import os
import time
import threading
import requests
from flask import Flask, request

# === НАСТРОЙКИ ===
TOKEN = os.getenv("BOT_TOKEN")  # Твой токен
CHAT_IDS = [370958352, 7148028443]  # Кому отправляем
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL Render

# Формат: ("дд.мм.гггг чч:мм", "Текст напоминания")
reminders = [
    ("14.08.2025 15:30", "💡 Проверить отчёт"),
    ("15.08.2025 10:00", "📦 Забрать посылку"),
]

# === ФУНКЦИИ ===
def send_message(text):
    for chat_id in CHAT_IDS:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text}
        )

def reminder_loop():
    while True:
        now = time.strftime("%d.%m.%Y %H:%M")
        for date_time, text in reminders:
            if now == date_time:
                send_message(text)
                time.sleep(60)  # Ждём минуту, чтобы не спамить
        time.sleep(20)  # Проверяем каждые 20 сек

# === FLASK ===
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        update = request.get_json()
        if "message" in update and "text" in update["message"]:
            text = update["message"]["text"]
            chat_id = update["message"]["chat"]["id"]
            if text.lower() == "/start":
                send_message("✅ Бот запущен. Напоминания будут приходить автоматически.")
        return "OK"
    return "Бот работает!"

# === СТАРТ ===
if __name__ == "__main__":
    # Устанавливаем вебхук
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    # Запускаем поток напоминаний
    threading.Thread(target=reminder_loop, daemon=True).start()
    # Flask сервер
    app.run(host="0.0.0.0", port=10000)
