import os
import json
import time
import sqlite3
import threading
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import requests
from flask import Flask, request, jsonify, abort

# -------------------- Конфигурация --------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]  # обязателен
API_SECRET = os.getenv("API_SECRET", "supersecret")     # секрет для внешнего API (для меня)
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "+05:00")          # твой пояс по умолчанию (GMT+5)

# Попробуем собрать URL вебхука автоматически, если WEBHOOK_URL не задан
BASE_URL = os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL") or (BASE_URL.rstrip("/") + "/webhook" if BASE_URL else None)
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL/WEBHOOK_BASE_URL/RENDER_EXTERNAL_URL не заданы и их нельзя вывести автоматически.")

ADMIN_IDS = []
raw_admins = os.getenv("ADMIN_IDS", "")
if raw_admins.strip():
    for part in raw_admins.replace(" ", "").split(","):
        if part:
            ADMIN_IDS.append(int(part))

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

DB_PATH = "reminders.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("reminder-bot")

app = Flask(__name__)

# -------------------- Утилиты времени --------------------
def parse_tz_offset(tz_str: str) -> timezone:
    """
    tz_str вида '+05:00' или '-03:30'
    """
    if not tz_str or len(tz_str) < 3:
        tz_str = DEFAULT_TZ
    sign = 1 if tz_str.startswith("+") else -1
    hh, mm = tz_str[1:].split(":")
    return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))

def local_to_utc(dt_local_str: str, tz_str: Optional[str]) -> datetime:
    """
    dt_local_str: 'YYYY-MM-DD HH:MM' в локальном поясе tz_str (или DEFAULT_TZ)
    возвращает UTC-aware datetime
    """
    tz = parse_tz_offset(tz_str or DEFAULT_TZ)
    naive = datetime.strptime(dt_local_str.strip(), "%Y-%m-%d %H:%M")
    aware = naive.replace(tzinfo=tz)
    return aware.astimezone(timezone.utc)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

# -------------------- База данных --------------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                send_at_utc TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_due ON reminders(send_at_utc)")
    log.info("✅ DB инициализирована")

# -------------------- Телеграм --------------------
def tg_send_message(chat_id: int, text: str) -> bool:
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
        if r.status_code == 429:
            retry = r.json().get("parameters", {}).get("retry_after", 1)
            time.sleep(retry)
            r = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
        ok = r.ok and r.json().get("ok", False)
        if not ok:
            log.warning(f"✖️ Не удалось отправить {chat_id}: {r.text}")
        return ok
    except Exception as e:
        log.exception(f"Ошибка отправки {chat_id}: {e}")
        return False

def set_webhook():
    r = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": WEBHOOK_URL, "allowed_updates": ["message"]})
    try:
        log.info(f"📡 Результат установки вебхука: {r.json()}")
    except Exception:
        log.info(f"📡 setWebhook HTTP {r.status_code}")

# -------------------- Планировщик --------------------
STOP_FLAG = False

def scheduler_loop():
    log.info("⏰ Планировщик запущен")
    while not STOP_FLAG:
        try:
            # Берём все просроченные или текущие напоминания (с небольшим буфером)
            due_ts = now_utc().isoformat()
            with db() as conn:
                rows = conn.execute(
                    "SELECT * FROM reminders WHERE send_at_utc <= ? ORDER BY id LIMIT 50",
                    (due_ts,)
                ).fetchall()

            for row in rows:
                rid = row["id"]
                chat_id = row["chat_id"]
                text = row["text"]
                ok = tg_send_message(chat_id, text)
                with db() as conn:
                    if ok:
                        conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))
                    else:
                        # на случай сбоя: попробуем ещё через минуту, максимум 5 попыток
                        if row["attempts"] >= 5:
                            conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))
                        else:
                            new_time = (datetime.fromisoformat(row["send_at_utc"]).replace(tzinfo=timezone.utc)
                                        + timedelta(minutes=1)).isoformat()
                            conn.execute(
                                "UPDATE reminders SET attempts = attempts + 1, send_at_utc = ? WHERE id = ?",
                                (new_time, rid)
                            )
        except Exception as e:
            log.exception(f"Сбой планировщика: {e}")

        time.sleep(20)  # проверяем каждые 20 сек

# -------------------- Вспомогательное --------------------
def require_secret(req):
    sec = req.headers.get("X-Api-Secret") or req.args.get("secret")
    if sec != API_SECRET:
        abort(401, "Unauthorized")

def add_many_reminders(chat_ids: List[int], text: str, dt_local: str, tz_str: Optional[str]) -> int:
    utc_dt = local_to_utc(dt_local, tz_str)
    utc_iso = utc_dt.isoformat()
    created = now_utc().isoformat()
    count = 0
    with db() as conn:
        for cid in chat_ids:
            conn.execute(
                "INSERT INTO reminders (chat_id, text, send_at_utc, created_at_utc) VALUES (?, ?, ?, ?)",
                (int(cid), text, utc_iso, created)
            )
            count += 1
    return count

# -------------------- Flask маршруты --------------------
@app.get("/")
def root():
    return "OK", 200

@app.post("/webhook")
def webhook():
    update = request.get_json(force=True, silent=True) or {}
    msg = update.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    # Простой /start
    if text == "/start":
        tg_send_message(chat_id, "Привет! Я работаю. Формат для добавления: \n/add 2025-08-14 10:00 Напомни позвонить")
        return jsonify(ok=True)

    # Команда /add YYYY-MM-DD HH:MM Текст (локальное время, пояс по умолчанию DEFAULT_TZ)
    if text.startswith("/add "):
        try:
            _, rest = text.split(" ", 1)
            dt_part = rest[:16]  # 'YYYY-MM-DD HH:MM'
            user_text = rest[17:].strip()
            if not user_text:
                raise ValueError("пустой текст")
            add_many_reminders([chat_id], user_text, dt_part, DEFAULT_TZ)
            tg_send_message(chat_id, f"✅ Напоминание поставлено на {dt_part} ({DEFAULT_TZ})")
        except Exception as e:
            tg_send_message(chat_id, f"❌ Ошибка формата. Пример: /add 2025-08-14 10:00 Позвонить. Детали: {e}")
        return jsonify(ok=True)

    # Справка
    if text in ("/help", "help", "?"):
        tg_send_message(chat_id, "Команды:\n/start\n/add YYYY-MM-DD HH:MM Текст (время по твоему поясу)")
        return jsonify(ok=True)

    # Молчим на остальное
    return jsonify(ok=True)

# ----------- Внешний API для добавления напоминаний (для меня) -----------
@app.post("/api/add_reminder")
def api_add():
    require_secret(request)
    data = request.get_json(force=True)
    # Пример JSON:
    # { "chat_ids": [123, 456], "text": "Тест из API", "when": "2025-08-14 09:30", "tz": "+05:00" }
    chat_ids = data.get("chat_ids")
    text = data.get("text")
    when = data.get("when")
    tz = data.get("tz") or DEFAULT_TZ

    if not chat_ids or not text or not when:
        abort(400, "chat_ids, text, when обязательны")

    count = add_many_reminders(chat_ids, text, when, tz)
    return jsonify(ok=True, inserted=count)

@app.get("/api/list")
def api_list():
    require_secret(request)
    with db() as conn:
        rows = conn.execute("SELECT id, chat_id, text, send_at_utc, attempts FROM reminders ORDER BY send_at_utc").fetchall()
    return jsonify([dict(r) for r in rows])

@app.post("/api/delete")
def api_delete():
    require_secret(request)
    rid = (request.get_json(force=True) or {}).get("id")
    if not rid:
        abort(400, "id обязателен")
    with db() as conn:
        conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))
    return jsonify(ok=True)

# -------------------- Старт --------------------
init_db()
set_webhook()

# Запуск планировщика в фоне
threading.Thread(target=scheduler_loop, daemon=True).start()

# Экспорт для gunicorn
app = app
