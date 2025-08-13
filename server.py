import os
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, jsonify

# -------------------- Конфиг --------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
WEBHOOK_BASE = os.environ["WEBHOOK_URL"].rstrip("/")

API_SECRET = os.environ.get("API_SECRET", "Test12345!")

# Получатели по умолчанию — твои ID
DEFAULT_CHAT_IDS = "370958352,7148028443"
CHAT_IDS = [
    int(x.strip())
    for x in os.environ.get("CHAT_IDS", DEFAULT_CHAT_IDS).split(",")
    if x.strip()
]

TIMEZONE = os.environ.get("TIMEZONE", "Asia/Tashkent")  # UTC+5 по умолчанию
TZ = ZoneInfo(TIMEZONE)

REM_FILE = "reminders.json"

# Интервалы
CHECK_INTERVAL_SEC = 30          # как часто проверяем напоминания
SEND_WINDOW_SEC = 59             # окно рассылки (на случай редкого тика)
# ------------------------------------------------

app = Flask(__name__)


# ----------- Утилиты хранения -----------
def _ensure_file():
    if not os.path.exists(REM_FILE):
        with open(REM_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def _load_all():
    _ensure_file()
    with open(REM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_all(items):
    tmp = REM_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, REM_FILE)

def _now_local():
    return datetime.now(TZ)

def _parse_local_dt(s: str) -> datetime:
    # Ожидаем формат "YYYY-MM-DD HH:MM" в ЛОКАЛЬНОМ времени (TIMEZONE)
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)

def _iso(dt: datetime) -> str:
    return dt.astimezone(TZ).isoformat(timespec="minutes")

# ----------- Отправка в Telegram -----------
def send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=data, timeout=10)
    except Exception:
        pass  # не падаем из-за сетевых сбоев

def broadcast(text: str, chat_ids=None):
    ids = chat_ids if chat_ids else CHAT_IDS
    for cid in ids:
        send_message(cid, text)

# ----------- Планировщик -----------
def scheduler_loop():
    # При первом старте — создадим два тестовых, если файл пуст
    items = _load_all()
    if not items:
        t1 = _now_local() + timedelta(minutes=2)
        t2 = _now_local() + timedelta(minutes=5)
        items.extend([
            {
                "id": uuid.uuid4().hex,
                "text": "Тест №1: напоминание через ~2 минуты",
                "run_at": _iso(t1),
                "sent": False,
                "chat_ids": CHAT_IDS,
                "created_by": "auto"
            },
            {
                "id": uuid.uuid4().hex,
                "text": "Тест №2: напоминание через ~5 минут",
                "run_at": _iso(t2),
                "sent": False,
                "chat_ids": CHAT_IDS,
                "created_by": "auto"
            },
        ])
        _save_all(items)

    while True:
        try:
            now = _now_local()
            items = _load_all()
            modified = False

            for it in items:
                if it.get("sent"):
                    continue
                run_at = datetime.fromisoformat(it["run_at"])
                # Шлём, когда настало время (с окном)
                if run_at <= now and (now - run_at).total_seconds() <= SEND_WINDOW_SEC:
                    text = it["text"]
                    cids = it.get("chat_ids") or CHAT_IDS
                    broadcast(f"🔔 Напоминание:\n{text}", chat_ids=cids)
                    it["sent"] = True
                    modified = True

            if modified:
                _save_all(items)
        except Exception:
            # Никогда не умираем
            pass

        time.sleep(CHECK_INTERVAL_SEC)

# ----------- Telegram webhook (минимум) -----------
@app.post("/telegram-webhook")
def telegram_webhook():
    # Обработаем только /start для ответа "я работаю"
    try:
        update = request.get_json(silent=True) or {}
        msg = (update.get("message") or update.get("edited_message")) or {}
        text = (msg.get("text") or "").strip().lower()
        chat = msg.get("chat") or {}
        cid = chat.get("id")

        if text.startswith("/start") and cid:
            send_message(cid, "Привет! Я работаю. Жду напоминаний 😉")
    except Exception:
        pass
    return jsonify(ok=True)

# ----------- Служебные маршруты -----------
@app.get("/")
def root():
    return "OK — Reminder bot is running"

@app.get("/health")
def health():
    return jsonify(ok=True, time=_iso(_now_local()))

# ----------- API для добавления/удаления/списка -----------
def _auth_ok(req):
    return req.headers.get("Authorization") == API_SECRET

@app.post("/add_reminder")
def add_reminder():
    if not _auth_ok(request):
        return jsonify(error="unauthorized"), 401

    data = request.get_json(force=True)
    text = str(data.get("text", "")).strip()
    when = str(data.get("time", "")).strip()  # "YYYY-MM-DD HH:MM" локальное
    chat_ids = data.get("chat_ids")  # опционально: [int, int]

    if not text or not when:
        return jsonify(error="fields 'text' and 'time' are required"), 400

    try:
        dt = _parse_local_dt(when)
    except Exception:
        return jsonify(error="time must be 'YYYY-MM-DD HH:MM' in local timezone"), 400

    item = {
        "id": uuid.uuid4().hex,
        "text": text,
        "run_at": _iso(dt),
        "sent": False,
        "chat_ids": chat_ids if isinstance(chat_ids, list) else CHAT_IDS,
        "created_by": "api"
    }
    items = _load_all()
    items.append(item)
    _save_all(items)
    return jsonify(ok=True, reminder=item)

@app.get("/list_reminders")
def list_reminders():
    if not _auth_ok(request):
        return jsonify(error="unauthorized"), 401
    return jsonify(items=_load_all())

@app.post("/delete_reminder")
def delete_reminder():
    if not _auth_ok(request):
        return jsonify(error="unauthorized"), 401
    data = request.get_json(force=True)
    rid = str(data.get("id", "")).strip()
    if not rid:
        return jsonify(error="field 'id' is required"), 400

    items = _load_all()
    new_items = [x for x in items if x["id"] != rid]
    _save_all(new_items)
    return jsonify(ok=True, deleted=(len(items) - len(new_items)))

@app.post("/test_notify")
def test_notify():
    if not _auth_ok(request):
        return jsonify(error="unauthorized"), 401
    broadcast("✅ Тестовое сообщение: бот на связи.")
    return jsonify(ok=True)

# ----------- Автозапуск: ставим webhook и поднимаем планировщик -----------
def ensure_webhook():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        target = f"{WEBHOOK_BASE}/telegram-webhook"
        resp = requests.post(url, json={"url": target}, timeout=10).json()
        print("📡 Результат установки вебхука:", resp, flush=True)
    except Exception as e:
        print("⚠️ setWebhook error:", e, flush=True)

def start_background_worker():
    th = threading.Thread(target=scheduler_loop, daemon=True)
    th.start()

# Важно: делаем это на импорт (для gunicorn)
ensure_webhook()
start_background_worker()

# Экспорт для gunicorn
app.wsgi_app  # noqa: keep app imported as module attribute
if __name__ == "__main__":
    # Локальный запуск (не используется на Render)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
