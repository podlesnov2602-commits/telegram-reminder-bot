import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# 🔑 Токен бота (ОСТОРОЖНО: хранить в коде небезопасно)
TOKEN = "8390901633:AAGWzRUhrm2qst2IDyk9tDwJvJvq2Lxv6Nw"

scheduler = BackgroundScheduler()
scheduler.start()

# Словарь для хранения напоминаний
reminders = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот-напоминалка.\n"
        "Напиши /napomni HH:MM текст, чтобы я напомнил.\n"
        "Например: /napomni 14:30 Позвонить маме."
    )

# Обработчик команды /napomni
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = context.args[0]
        reminder_text = " ".join(context.args[1:])

        if not reminder_text:
            await update.message.reply_text("❌ Укажи текст напоминания после времени.")
            return

        # Парсим время
        reminder_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now()
        reminder_datetime = datetime.combine(now.date(), reminder_time)

        if reminder_datetime < now:
            reminder_datetime += timedelta(days=1)

        chat_id = update.effective_chat.id
        reminders[chat_id] = (reminder_datetime, reminder_text)

        # Запускаем задачу
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=reminder_datetime,
            args=[context, chat_id, reminder_text]
        )

        await update.message.reply_text(
            f"✅ Напоминание установлено на {reminder_datetime.strftime('%H:%M')}."
        )

    except (IndexError, ValueError):
        await update.message.reply_text("❌ Формат: /napomni HH:MM текст")

# Функция отправки напоминания
async def send_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id, text):
    await context.bot.send_message(chat_id, f"⏰ Напоминание: {text}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("napomni", remind))  # Латиница в названии команды

    logging.info("Бот запущен")
    app.run_polling()
