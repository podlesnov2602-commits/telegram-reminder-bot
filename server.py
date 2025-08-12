import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

# Получаем токен из переменной окружения
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден! Убедись, что он добавлен в переменные окружения Render.")

scheduler = BackgroundScheduler()
scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот-напоминалка. Используй команду /remind <минуты> <текст>.")

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(context.args[0])
        text = " ".join(context.args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)
        scheduler.add_job(send_reminder, 'date', run_date=remind_time, args=[update.message.chat_id, text])
        await update.message.reply_text(f"Напоминание установлено через {minutes} минут.")
    except (IndexError, ValueError):
        await update.message.reply_text("Формат: /remind <минуты> <текст>")

async def send_reminder(chat_id, text):
    app = ApplicationBuilder().token(TOKEN).build()
    await app.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("remind", remind))
    print("✅ Бот запущен...")
    app.run_polling()
