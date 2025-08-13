import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", f"https://{os.getenv('RENDER_SERVICE_ID')}.onrender.com")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в переменных окружения!")

WEBHOOK_URL = f"{BASE_URL}/webhook/{TOKEN}"

# Flask приложение
app = Flask(__name__)

# Telegram Application
telegram_app = Application.builder().token(TOKEN).build()


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-напоминалка. 🚀")


telegram_app.add_handler(CommandHandler("start", start))


# Роут для Telegram webhook
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok"


# Корневой роут (проверка работы)
@app.route("/")
def index():
    return "✅ Бот работает и вебхук установлен!"


# Устанавливаем вебхук при старте
@app.before_first_request
def set_webhook():
    try:
        logger.info(f"Устанавливаю вебхук: {WEBHOOK_URL}")
        telegram_app.bot.set_webhook(url=WEBHOOK_URL)
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {e}")


if __name__ == "__main__":
    # Локальный запуск
    telegram_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=f"webhook/{TOKEN}",
        webhook_url=WEBHOOK_URL
    )
