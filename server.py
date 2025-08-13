import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Забираем токен из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("Переменная окружения TELEGRAM_TOKEN не задана!")

# Домен твоего бота на Render
WEBHOOK_URL = f"https://telegram-reminder-bot-ecqb.onrender.com"

# Создаём Flask
app = Flask(__name__)

# Создаём Telegram приложение
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Пример команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот успешно запущен на Render 🚀")

application.add_handler(CommandHandler("start", start))

# Flask endpoint для Telegram webhook
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

# Главная страница
@app.route("/")
def index():
    return "Бот работает!", 200

if __name__ == "__main__":
    # Настройка вебхука
    application.bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
