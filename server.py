import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler
import requests

# Получаем токен из переменной окружения
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден! Добавь его в Render → Environment Variables.")

# URL для вебхука
WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context):
    await update.message.reply_text("Привет! Я бот напоминаний и я уже работаю 😊")

# Регистрируем обработчик команды
application.add_handler(CommandHandler("start", start))

# Приём обновлений от Telegram
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

# Главная страница
@app.route("/")
def index():
    return "✅ Бот запущен и ждёт команды!"

# Запуск
if __name__ == "__main__":
    # Устанавливаем вебхук
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL
    )
