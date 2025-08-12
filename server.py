import os
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging

# Логирование
logging.basicConfig(level=logging.INFO)

# Берём токен из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден. Установите переменную окружения BOT_TOKEN.")

# Создаём приложение Telegram
app_tg = ApplicationBuilder().token(BOT_TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я твой бот.")

app_tg.add_handler(CommandHandler("start", start))

# Flask-сервер
app = Flask(__name__)

@app.route("/")
def home():
    return "Бот работает!"

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app_tg.bot)
    app_tg.update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    # Устанавливаем webhook при старте
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{BOT_TOKEN}"
    app_tg.bot.set_webhook(url=webhook_url)
    logging.info(f"Webhook установлен: {webhook_url}")

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
