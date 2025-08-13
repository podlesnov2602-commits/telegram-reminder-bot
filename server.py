import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Переменные окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5000")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в переменных окружения!")

WEBHOOK_URL = f"{BASE_URL}/webhook/{TOKEN}"

# Flask
app = Flask(__name__)

# Telegram Application
telegram_app = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-напоминалка 🚀")

telegram_app.add_handler(CommandHandler("start", start))

# Webhook endpoint
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok"

# Index
@app.route("/")
def index():
    return "✅ Бот работает и вебхук установлен!"

# Установка вебхука при старте сервера
def setup_webhook():
    try:
        logger.info(f"Устанавливаю вебхук: {WEBHOOK_URL}")
        telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {e}")

# Вызываем настройку вебхука один раз при запуске
setup_webhook()

if __name__ == "__main__":
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=f"webhook/{TOKEN}",
        webhook_url=WEBHOOK_URL
    )
