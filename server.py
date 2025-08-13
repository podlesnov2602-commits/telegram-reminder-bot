import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = f"https://telegram-reminder-bot-ecqb.onrender.com/{TOKEN}"

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context):
    await update.message.reply_text("Привет! Я твой бот напоминаний.")

# Регистрируем обработчики
application.add_handler(CommandHandler("start", start))

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

@app.route('/')
def index():
    return "Бот работает!"

if __name__ == '__main__':
    # Устанавливаем вебхук при запуске
    import requests
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL
    )
