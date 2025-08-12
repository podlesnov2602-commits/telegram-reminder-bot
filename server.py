import os
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Читаем токен из переменной окружения
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден. Добавьте его в Environment Variables на Render.")

# Создаем приложение Telegram
app = Application.builder().token(TOKEN).build()

# Планировщик
scheduler = AsyncIOScheduler()
scheduler.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот-напоминалка.\n"
        "Напиши команду /remind <минуты> <текст>, и я напомню.\n"
        "Например: /remind 1 покормить кота"
    )

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(context.args[0])
        text = " ".join(context.args[1:])
        if not text:
            await update.message.reply_text("Пожалуйста, укажите текст напоминания.")
            return

        remind_time = datetime.now() + timedelta(minutes=minutes)

        scheduler.add_job(
            send_reminder,
            "date",
            run_date=remind_time,
            args=[update.effective_chat.id, text],
        )

        await update.message.reply_text(
            f"Напоминание через {minutes} мин.: {text}"
        )
    except (IndexError, ValueError):
        await update.message.reply_text("Формат: /remind <минуты> <текст>")

async def send_reminder(chat_id: int, text: str):
    try:
        await app.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")

# Регистрируем команды
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("remind", remind))

if __name__ == "__main__":
    logger.info("Бот запущен")
    app.run_polling()
