import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Получаем токен из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения")

# Создаём приложение Telegram
application = Application.builder().token(TOKEN).build()

# Flask сервер
app = Flask(__name__)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Бот успешно работает на Render 🚀")

# Регистрируем команду
application.add_handler(CommandHandler("start", start))

# Обработчик для вебхука
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok", 200

# Главная страница (для проверки)
@app.route("/")
def index():
    return "Бот работает!", 200

if __name__ == "__main__":
    # URL вебхука
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        raise ValueError("RENDER_EXTERNAL_URL не задан Render'ом")

    webhook_url = f"{render_url}/webhook/{TOKEN}"

    # Запускаем webhook сервер
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=f"webhook/{TOKEN}",
        webhook_url=webhook_url
    )
