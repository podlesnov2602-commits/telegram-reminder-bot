import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

# Включаем логи
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Берем токен из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Добавь его в Environment Variables на Render.")

app = Flask(__name__)

# Создаём приложение бота
application = Application.builder().token(TOKEN).build()

# Пример команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я работаю на Render 🚀")

application.add_handler(CommandHandler("start", start))

# Маршрут для webhook
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
