import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Читаем токен из переменной окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")

# Создаем Flask-приложение
app = Flask(__name__)

# Хранилище задач для напоминаний
reminders = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-напоминалка ⏰\nИспользуй /remind <секунды> <текст>")

# Команда /remind
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = int(context.args[0])
        text = " ".join(context.args[1:])
        user_id = update.effective_user.id

        if not text:
            await update.message.reply_text("❌ Укажи текст напоминания!")
            return

        await update.message.reply_text(f"✅ Напоминание установлено через {delay} секунд.")

        # Запускаем отложенное сообщение
        asyncio.create_task(send_reminder(user_id, text, delay, context))
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Формат: /remind <секунды> <текст>")

# Отправка напоминания
async def send_reminder(user_id, text, delay, context):
    await asyncio.sleep(delay)
    await context.bot.send_message(chat_id=user_id, text=f"🔔 Напоминание: {text}")

# Настройка вебхука
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

@app.route("/")
def index():
    return "✅ Бот запущен!"

if __name__ == "__main__":
    # Создаем приложение Telegram
    application = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("remind", remind))

    # Запускаем Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
