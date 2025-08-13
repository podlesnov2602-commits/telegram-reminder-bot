import os
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify

# ==========================
# 🔧 Конфигурация из env
# ==========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # твой render URL
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")  # 1_J8qv... (ты уже дал)
GSA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")  # JSON сервис-аккаунта (целиком)

# Обязательная проверка
missing = [name for name, val in [
    ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
    ("WEBHOOK_URL", WEBHOOK_URL),
    ("GOOGLE_SHEET_ID", GOOGLE_SHEET_ID),
    ("GOOGLE_SERVICE_ACCOUNT_JSON", GSA_JSON),
] if not val]
if missing:
    raise ValueError(f"❌ Нет переменных окружения: {', '.join(missing)}")

# Твой часовой пояс (GMT+5 ≈ Asia/Yekaterinburg). Можно поменять при желании
LOCAL_TZ = ZoneInfo("Asia/Yekaterinburg")

# Два получателя, которые ты давал ранее
DEFAULT_CHAT_IDS = [
    "370958352",
    "7148028443",
]

# ==========================
# 📄 Работа с таблицей
# ==========================
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    info = json.loads(GSA_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPE)
    return gspread.authorize(creds)

def open_sheet():
    gc = get_gspread_client()
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    ws = sh.sheet1  # первый лист
    return ws

HEADERS = ["chat_id", "text", "date", "time", "tz", "status", "created_at", "sent_at"]

def ensure_headers(ws):
    values = ws.get_all_values()
    if not values:
        ws.append_row(HEADERS)
        return
    # Если заголовки есть, ничего не делаем
    if values[0] != HEADERS:
        # Перезаписывать не будем — просто выведем понятную ошибку
        # но для твоего удобства — попробуем подставить, если совсем другое
        ws.update("1:1", [HEADERS])

def sheet_is_empty(ws):
    return len(ws.get_all_values()) <= 1  # только заголовки или вообще пусто

def add_test_reminders_if_needed(ws):
    """Добавляет 2 тестовых напоминания для двух пользователей, если таблица пустая."""
    if not sheet_is_empty(ws):
        return

    now_local = datetime.now(LOCAL_TZ)
    r1_time = (now_local + timedelta(minutes=5)).time().strftime("%H:%M")
    r2_time = (now_local + timedelta(minutes=10)).time().strftime("%H:%M")
    date_str = now_local.date().isoformat()
    tz_str = "Asia/Yekaterinburg"

    rows = []
    for chat_id in DEFAULT_CHAT_IDS:
        rows.append([chat_id, "Тест №1 — проверка через 5 минут", date_str, r1_time, tz_str, "pending",
                     now_local.isoformat(), ""])
        rows.append([chat_id, "Тест №2 — проверка через 10 минут", date_str, r2_time, tz_str, "pending",
                     now_local.isoformat(), ""])

    ws.append_rows(rows, value_input_option="USER_ENTERED")

def parse_dt(date_str, time_str, tz_str):
    """Собираем aware-datetime из ячейки."""
    # Пытаемся интерпретировать TZ
    try:
        tz = ZoneInfo(tz_str) if tz_str else LOCAL_TZ
    except Exception:
        tz = LOCAL_TZ

    # Поддержка форматов 2025-08-13 и 13.08.2025
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        d = datetime.strptime(date_str, "%d.%m.%Y").date()

    # Поддержка HH:MM
    t = datetime.strptime(time_str, "%H:%M").time()

    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=tz)

def get_due_rows(ws, now_utc):
    """Возвращает список (row_index, row_values) для отправки."""
    values = ws.get_all_values()
    due = []
    if len(values) <= 1:
        return due

    # Построим карту заголовков
    headers = values[0]
    idx = {name: headers.index(name) for name in HEADERS}

    for i, row in enumerate(values[1:], start=2):  # реальный номер строки в гугл-таблице
        try:
            status = row[idx["status"]].strip().lower() if len(row) > idx["status"] else ""
            if status == "sent":
                continue

            chat_id = row[idx["chat_id"]].strip()
            text = row[idx["text"]].strip()
            date_str = row[idx["date"]].strip()
            time_str = row[idx["time"]].strip()
            tz_str = row[idx["tz"]].strip() if len(row) > idx["tz"] else ""
            if not (chat_id and text and date_str and time_str):
                continue

            run_dt = parse_dt(date_str, time_str, tz_str)
            run_utc = run_dt.astimezone(timezone.utc)

            # Отправляем если плановое время ≤ сейчас (UTC), с запасом в 60 сек
            if run_utc <= now_utc + timedelta(seconds=1):
                due.append((i, row))
        except Exception:
            # любую кривую строку просто скипаем
            continue

    return due

def mark_sent(ws, row_number):
    ws.update_cell(row_number, HEADERS.index("status") + 1, "sent")
    ws.update_cell(row_number, HEADERS.index("sent_at") + 1, datetime.now(timezone.utc).isoformat())

# ==========================
# ✉️ Отправка в Telegram
# ==========================
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception:
        return False

# ==========================
# ⏱ Фоновый планировщик
# ==========================
def scheduler_loop():
    time.sleep(3)  # подождём, пока Render поднимет сеть
    ws = None
    while True:
        try:
            if ws is None:
                ws = open_sheet()
                ensure_headers(ws)
                add_test_reminders_if_needed(ws)

            now_utc = datetime.now(timezone.utc)
            for row_number, row in get_due_rows(ws, now_utc):
                chat_id = row[HEADERS.index("chat_id")]
                text = row[HEADERS.index("text")]
                ok = send_message(chat_id, text)
                if ok:
                    mark_sent(ws, row_number)
                else:
                    # можно логировать/повторять позже — для простоты просто оставим pending
                    pass

        except Exception:
            # в случае ошибки переподключимся при следующем круге
            ws = None

        time.sleep(30)  # проверяем каждые 30 секунд

# ==========================
# 🌐 Flask + Webhook
# ==========================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    # Мы не обязаны что-то делать с апдейтами. Но если хочешь —
    # можно обработать /start:
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message") or {}
        text = (message.get("text") or "").strip()
        chat_id = (message.get("chat", {}) or {}).get("id")
        if text == "/start" and chat_id:
            send_message(chat_id, "Привет! Я работаю. Напоминания читаю из Google-таблицы и отправляю автоматически.")
    except Exception:
        pass
    return jsonify(ok=True)

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    payload = {"url": f"{WEBHOOK_URL}/webhook", "drop_pending_updates": True}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("📡 setWebhook:", r.json())
    except Exception as e:
        print("setWebhook error:", e)

# Запускаем всё при импортe модуля (как делает gunicorn)
set_webhook()
threading.Thread(target=scheduler_loop, daemon=True).start()

# Экспорт для gunicorn
# gunicorn server:app
