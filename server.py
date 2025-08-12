import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Логирование
logging.basicConfig(level=logging.INFO)

# Токен из переменной окружения
TOKEN = os.getenv("BOT_TOKEN")

# Планировщик
scheduler = BackgroundScheduler()
scheduler.start()

# Функция отправки напоминания
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id, text = context.job.context
    await context.bot.send_message(chat_id=chat_id, text=f"🔔 Напоминание: {text}")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши в формате:\n/напомни HH:MM текст"
    )

# Команда /напомни
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = context.args[0]
        text = " ".join(context.args[1:])

        # Преобразуем время
        remind_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now()
        target = datetime.combine(now.date(), remind_time)

        if target < now:
            target += timedelta(days=1)

        # Добавляем задачу
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=target,
            args=[context],
            kwargs={},
            id=f"{update.effective_chat.id}_{time_str}",
            replace_existing=True
        )
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=target,
            args=[context],
            kwargs={},
            id=f"{update.effective_chat.id}_{time_str}",
            replace_existing=True
        )
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=target,
            args=[],
            kwargs={},
            id=None,
            replace_existing=False
        )

        # Передаём chat_id и текст как контекст
        scheduler.add_job(
            send_reminder,
            "date",
            run_date=target,
            args=[],
            kwargs={},
            id=None,
            replace_existing=False,
            jobstore=None,
            misfire_grace_time=None,
            coalesce=True,
            context=(update.effective_chat.id, text)
        )

        await update.message.reply_text(f"Напоминание установлено на {time_str}: {text}")

    except Exception as e:
        logging.error(e)
        await update.message.reply_text("Ошибка! Формат: /напомни HH:MM текст")

# Создаём приложение
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("напомни", remind))

if __name__ == "__main__":
    app.run_polling()
