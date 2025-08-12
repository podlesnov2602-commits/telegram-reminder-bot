import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

TOKEN = os.getenv("BOT_TOKEN", "8390901633:AAGWzRUhrm2qst2IDyk9tDwJvJvq2Lxv6Nw")
URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

# Создаём Telegram-приложение
application = Application.builder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши: 'Напомни через 10 минут выпить воду' или 'Напомни завтра в 10:00 оплатить интернет'.")


async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "через" in text and "минут" in text:
        try:
            minutes = int(text.split("через")[1].split("минут")[0].strip())
            time = datetime.now() + timedelta(minutes=minutes)
            scheduler.add_job(lambda: application.bot.send_message(update.effective_chat.id, f"Напоминаю: {text}"), 'date', run_date=time)
            await update.message.reply_text(f"Напоминание через {minutes} минут установлено!")
        except:
            await update.message.reply_text("Не понял время. Пример: 'Напомни через 5 минут выпить чай'.")
    else:
        await update.message.reply_text("Формат пока поддерживает только 'через X минут'.")


# Регистрируем команды и обработчики
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_reminder))


@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


@app.route('/')
async def set_webhook():
    await application.bot.set_webhook(URL)
    return "Webhook set", 200


if __name__ == '__main__':
    import asyncio
    asyncio.get_event_loop().run_until_complete(application.bot.set_webhook(URL))
    app.run(host="0.0.0.0", port=5000)
