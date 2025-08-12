import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") or "8390901633:AAGWzRUhrm2qst2IDyk9tDwJvJvq2Lxv6Nw"
URL = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")

app = Flask(__name__)

# Создаём экземпляр бота
application = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен! 🚀")

application.add_handler(CommandHandler("start", start))

# Flask маршрут для вебхука
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"

# Главная страница
@app.route("/")
def index():
    return "Bot is running ✅"

if __name__ == "__main__":
    # Устанавливаем вебхук при старте
    import asyncio
    async def set_webhook():
        webhook_url = f"{URL}/webhook/{TOKEN}"
        await application.bot.set_webhook(webhook_url)
        print(f"Webhook установлен: {webhook_url}")

    asyncio.get_event_loop().run_until_complete(set_webhook())

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
