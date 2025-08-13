import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ==== Конфигурация через переменные окружения ====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]  # ОБЯЗАТЕЛЬНО задать в Render
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "webhook")  # задай рандомную строку
BASE_URL = os.environ.get("BASE_URL")  # можно не задавать; /setup сам определит домен

WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None

# ==== Flask ====
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# ==== PTB Application ====
application = Application.builder().token(TELEGRAM_TOKEN).build()

# ---- Handlers ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я работаю через webhook на Render ✅")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # здесь твоя логика; поставил echo, чтобы сразу видеть, что бот жив
    await update.message.reply_text(update.message.text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

_initialized = False

async def _init_and_set_webhook():
    """Инициализация PTB и установка webhook (один раз)."""
    global _initialized
    if _initialized:
        return
    await application.initialize()

    # Если BASE_URL не задан — webhook установим при заходе на /setup
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        app.logger.info(f"Webhook установлен: {WEBHOOK_URL}")
    else:
        app.logger.warning("BASE_URL не задан. Открой /setup, чтобы установить webhook.")
    _initialized = True

@app.get("/")
def root():
    # healthcheck для Render
    return "OK"

@app.get("/setup")
async def setup():
    """Установить/переустановить webhook без раскрытия токена."""
    await _init_and_set_webhook()

    # Если BASE_URL не был задан, определим домен из запроса и установим webhook
    if not BASE_URL:
        host_url = request.url_root.rstrip("/")  # например, https://telegram-reminder-bot-xxx.onrender.com
        url = f"{host_url}{WEBHOOK_PATH}"
        await application.bot.set_webhook(url=url, drop_pending_updates=True)
        app.logger.info(f"Webhook установлен через /setup: {url}")
        return jsonify({"status": "webhook set", "url": url})

    return jsonify({"status": "initialized", "webhook": WEBHOOK_URL})

@app.post(WEBHOOK_PATH)
async def telegram_webhook():
    """Приём апдейтов от Telegram и передача их в PTB."""
    await _init_and_set_webhook()
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "", 200

# В gunicorn точка входа — переменная app (Flask)
# Никакого polling и никакого запуска dev-сервера тут нет.
