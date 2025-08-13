import os
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")  # Токен берём из переменных окружения

app = Flask(__name__)

# Создаём приложение Telegram
application = Application.builder().token(TOKEN).build()

# Пример команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и готов работать!")

application.add_handler(CommandHandler("start", start))

# Flask — чтобы Render видел, что сервис запущен
@app.route("/")
def home():
    return "Бот работает!"

# Запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
