import os
import telebot
from flask import Flask, request
from datetime import datetime, timedelta
import threading
import time

TOKEN = os.environ.get("TOKEN", "8390901633:AAGWzRUhrm2qst2IDyk9tDwJvJvq2Lxv6Nw")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

reminders = []

def reminder_checker():
    while True:
        now = datetime.now()
        for r in reminders[:]:
            if now >= r["time"]:
                bot.send_message(r["chat_id"], f"? Напоминание: {r['text']}")
                reminders.remove(r)
        time.sleep(30)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Отправь команду в формате:\n/remind HH:MM текст")

@bot.message_handler(commands=['remind'])
def remind(message):
    try:
        parts = message.text.split(" ", 2)
        time_str = parts[1]
        text = parts[2]
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()
        remind_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if remind_time < now:
            remind_time += timedelta(days=1)
        reminders.append({"time": remind_time, "text": text, "chat_id": message.chat.id})
        bot.reply_to(message, f"? Напоминание установлено на {remind_time.strftime('%H:%M')}")
    except:
        bot.reply_to(message, "? Формат: /remind HH:MM текст")

@bot.message_handler(commands=['list'])
def list_reminders(message):
    if reminders:
        reply = "?? Список напоминаний:\n" + "\n".join(
            [f"{r['time'].strftime('%H:%M')} — {r['text']}" for r in reminders if r["chat_id"] == message.chat.id]
        )
    else:
        reply = "?? У тебя нет напоминаний."
    bot.reply_to(message, reply)

@app.route("/" + TOKEN, methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Бот работает!"

if __name__ == "__main__":
    threading.Thread(target=reminder_checker, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
