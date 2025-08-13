import os
import time
import json
import sqlite3
from datetime import datetime, timedelta
from dateutil import tz
from dateutil.parser import isoparse
from flask import Flask, request, abort, jsonify
import requests
from apscheduler.schedulers.background import BackgroundScheduler

# ========= НАСТРОЙКИ =========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
PUBLIC_URL     = os.environ.get("PUBLIC_URL")  # пример: https://telegram-reminder-bot-ecqb.onrender.com
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET") or (TELEGRAM_TOKEN[-8:] if TELEGRAM_TOKEN else "secret")
PORT           = int(os.environ.get("PORT", "10000"))

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан!")
if not PUBLIC_URL:
    raise ValueError("❌ PUBLIC_URL не задан! Укажи primary URL сервиса, например: https://...onrender.com")

API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
WEBHOOK_URL = f"{PUBLIC_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"

DB_PATH = os.path.join(os.path.dirname(__file__), "reminders.db")

# Рекомендуется в Render выставить переменную окружения: WEB_CONCURRENCY=1
# чтобы не было дублей отправок при нескольких воркерах.

# ========= БД =========
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            tz_offset_minutes INTEGER NOT NULL DEFAULT 0  -- смещение пользователя относительно UTC
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            due_at_ts INTEGER NOT NULL,                 -- время в UTC (epoch seconds)
            status TEXT NOT NULL DEFAULT 'pending',     -- pending | sending | sent | error
            created_at_ts INTEGER NOT NULL,
            sent_at_ts INTEGER
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders(status, due_at_ts);")
    conn.commit()
    conn.close()

init_db()

# ========= TELEGRAM =========
def tg_send_message(chat_id: int, text: str, reply_to_message_id: int | None = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    r = requests.post(f"{API}/sendMessage", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def tg_set_webhook():
    r = requests.post(f"{API}/setWebhook", json={
        "url": WEBHOOK_URL,
        # Если хочешь, можно включить проверку секретного заголовка:
        # "secret_token": WEBHOOK_SECRET,
        "drop_pending_updates": False,
        "allowed_updates": ["message"]
    }, timeout=15)
    try:
        ans = r.json()
    except Exception:
        ans = {"ok": False, "raw": r.text}
    print("📡 Результат установки вебхука:", ans, flush=True)

# Ставим вебхук НА СТАРТЕ процесса
tg_set_webhook()

# ========= ПАРСИНГ ВРЕМЕНИ =========
def parse_remind_time(raw: str, user_offset_min: int) -> tuple[int, str] | None:
    """
    Поддерживаем 2 формата:
    1) Абсолютное время: YYYY-MM-DD HH:MM  (считается по часовому поясу пользователя)
       пример: 2025-08-13 15:30 Позвонить
    2) Относительное: in 10m / in 2h / in 3d
       пример: in 45m Выпить воду
    Возвращает (due_at_ts_utc, остаток_текста) либо None.
    """
    s = raw.strip()

    # относительное "in ..."
    if s.lower().startswith("in "):
        # in 10m | in 2h | in 3d
        try:
            head, rest = s.split(maxsplit=2)[1:]  # "10m", "Текст..."
        except ValueError:
            return None
        num = ''.join(ch for ch in head if ch.isdigit())
        unit = ''.join(ch for ch in head if ch.isalpha()).lower()
        if not num or unit not in ("m", "h", "d"):
            return None
        n = int(num)
        delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
        due_local = datetime.utcnow() + timedelta(minutes=user_offset_min) + delta
        # Переводим локальное время пользователя обратно в UTC:
        due_utc = due_local - timedelta(minutes=user_offset_min)
        return int(due_utc.timestamp()), rest.strip()

    # абсолютное: "YYYY-MM-DD HH:MM ..."
    # пытаемся вытащить первые 16 символов под формат
    if len(s) >= 16 and s[4] == "-" and s[7] == "-" and s[10] == " " and s[13] == ":":
        dt_part = s[:16]  # "YYYY-MM-DD HH:MM"
        try:
            y, m, d = int(dt_part[0:4]), int(dt_part[5:7]), int(dt_part[8:10])
            hh, mm = int(dt_part[11:13]), int(dt_part[14:16])
            due_local = datetime(y, m, d, hh, mm)
            # переводим из локального времени пользователя в UTC
            due_utc = due_local - timedelta(minutes=user_offset_min)
            return int(due_utc.timestamp()), s[16:].strip()
        except Exception:
            return None

    # ISO-вариант (редко, но вдруг): 2025-08-13T15:30
    try:
        dt = isoparse(s.split()[0])
        # считаем это локальным временем пользователя без tzinfo
        if dt.tzinfo is None:
            due_utc = dt - timedelta(minutes=user_offset_min)
        else:
            due_utc = dt.astimezone(tz.UTC).replace(tzinfo=None)
        rest = s.replace(s.split()[0], "", 1).strip()
        return int(due_utc.timestamp()), rest
    except Exception:
        return None

# ========= ЛОГИКА НАПОМИНАНИЙ =========
def list_reminders_text(chat_id: int, user_offset_min: int) -> str:
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, text, due_at_ts FROM reminders
        WHERE chat_id=? AND status IN ('pending','sending')
        ORDER BY due_at_ts ASC
        LIMIT 20
    """, (chat_id,))
    rows = cur.fetchall()
    con.close()
    if not rows:
        return "У тебя нет запланированных напоминаний."
    lines = ["<b>Твои напоминания:</b>"]
    for r in rows:
        due_local = datetime.utcfromtimestamp(r["due_at_ts"]) + timedelta(minutes=user_offset_min)
        lines.append(f"• #{r['id']} — {due_local:%Y-%m-%d %H:%M} — {r['text']}")
    return "\n".join(lines)

def add_reminder(chat_id: int, text: str, due_at_ts: int):
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO reminders(chat_id, text, due_at_ts, status, created_at_ts)
        VALUES (?,?,?,?,?)
    """, (chat_id, text, due_at_ts, 'pending', int(time.time())))
    con.commit()
    rid = cur.lastrowid
    con.close()
    return rid

def delete_reminder(chat_id: int, rid: int) -> bool:
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM reminders WHERE id=? AND chat_id=? AND status IN ('pending','sending')",
                (rid, chat_id))
    ok = cur.rowcount > 0
    con.commit()
    con.close()
    return ok

def get_user_offset(chat_id: int) -> int:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT tz_offset_minutes FROM chats WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT OR IGNORE INTO chats(chat_id, tz_offset_minutes) VALUES (?,0)", (chat_id,))
        con.commit()
        con.close()
        return 0
    con.close()
    return int(row["tz_offset_minutes"])

def set_user_offset(chat_id: int, minutes: int):
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO chats(chat_id, tz_offset_minutes) VALUES (?,?) ON CONFLICT(chat_id) DO UPDATE SET tz_offset_minutes=excluded.tz_offset_minutes",
                (chat_id, minutes))
    con.commit()
    con.close()

def pick_and_mark_due(limit: int = 20):
    """
    Берём пачку просроченных 'pending' и атомно помечаем как 'sending',
    чтобы избежать дублей при редких гонках.
    """
    con = db()
    con.isolation_level = "EXCLUSIVE"
    cur = con.cursor()
    now_ts = int(time.time())
    cur.execute("""
        SELECT id FROM reminders
        WHERE status='pending' AND due_at_ts<=?
        ORDER BY due_at_ts ASC
        LIMIT ?
    """, (now_ts, limit))
    ids = [row["id"] for row in cur.fetchall()]
    sending = []
    for rid in ids:
        cur.execute("UPDATE reminders SET status='sending' WHERE id=? AND status='pending'", (rid,))
        if cur.rowcount:
            sending.append(rid)
    con.commit()
    con.close()
    return sending

def load_reminder(rid: int):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT * FROM reminders WHERE id=?", (rid,))
    row = cur.fetchone()
    con.close()
    return row

def mark_sent(rid: int):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE reminders SET status='sent', sent_at_ts=? WHERE id=?", (int(time.time()), rid))
    con.commit()
    con.close()

def mark_error(rid: int):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE reminders SET status='pending' WHERE id=?", (rid,))
    con.commit()
    con.close()

def tick_send_due():
    try:
        ids = pick_and_mark_due(30)
        for rid in ids:
            r = load_reminder(rid)
            if not r:
                continue
            chat_id = r["chat_id"]
            text = r["text"]
            try:
                tg_send_message(chat_id, f"⏰ Напоминание: {text}")
                mark_sent(rid)
            except Exception as e:
                print(f"Send error for #{rid}: {e}", flush=True)
                mark_error(rid)
    except Exception as e:
        print("tick error:", e, flush=True)

# Планировщик
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(tick_send_due, "interval", seconds=15, id="tick_send_due", max_instances=1, coalesce=True)
scheduler.start()

# ========= FLASK =========
app = Flask(__name__)

@app.get("/")
def root():
    return "OK, bot is running ✅"

@app.get("/health")
def health():
    return jsonify(ok=True, ts=int(time.time()))

@app.post(f"/webhook/{WEBHOOK_SECRET}")
def webhook():
    # Если включишь секретный заголовок в setWebhook, можно раскомментировать проверку ниже:
    # if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
    #     abort(401)

    update = request.get_json(force=True, silent=True) or {}
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")

    if not chat_id or not text:
        return jsonify(ok=True)

    # Команды
    if text.startswith("/start"):
        tg_send_message(chat_id, "Привет! Я бот-напоминалка.\n\n"
                                 "Команды:\n"
                                 "• /remind YYYY-MM-DD HH:MM Текст\n"
                                 "• /remind in 10m Текст  (m=минуты, h=часы, d=дни)\n"
                                 "• /list — показать запланированные\n"
                                 "• /delete ID — удалить по номеру\n"
                                 "• /settz +5  — часовой пояс (пример, GMT+5)\n")
        return jsonify(ok=True)

    if text.startswith("/help"):
        tg_send_message(chat_id, "Помощь:\n"
                                 "/remind 2025-08-13 15:30 Позвонить маме\n"
                                 "/remind in 45m Сделать перерыв\n"
                                 "/list — список\n"
                                 "/delete 12 — удалить напоминание №12\n"
                                 "/settz +5 — установить свой часовой пояс (по умолчанию UTC)")
        return jsonify(ok=True)

    if text.startswith("/settz"):
        arg = text.replace("/settz", "", 1).strip()
        # ожидаем +5, -3, +5:30 и т.п.
        try:
            if ":" in arg:
                sign = 1 if arg.strip().startswith("+") else -1
                hh, mm = arg.replace("+","").replace("-","").split(":", 1)
                minutes = sign * (int(hh) * 60 + int(mm))
            else:
                minutes = int(float(arg) * 60)  # "+5" -> 300
            set_user_offset(chat_id, minutes)
            tg_send_message(chat_id, f"Часовой пояс сохранён: {minutes:+d} минут относительно UTC")
        except Exception:
            tg_send_message(chat_id, "Неверный формат. Примеры: /settz +5  или  /settz -3:30")
        return jsonify(ok=True)

    if text.startswith("/list"):
        off = get_user_offset(chat_id)
        tg_send_message(chat_id, list_reminders_text(chat_id, off))
        return jsonify(ok=True)

    if text.startswith("/delete"):
        arg = text.replace("/delete", "", 1).strip()
        try:
            rid = int(arg)
            ok = delete_reminder(chat_id, rid)
            tg_send_message(chat_id, "Удалено." if ok else "Не найдено или уже отправлено.")
        except Exception:
            tg_send_message(chat_id, "Укажи номер, например: /delete 12")
        return jsonify(ok=True)

    if text.startswith("/remind"):
        rest = text.replace("/remind", "", 1).strip()
        off = get_user_offset(chat_id)
        parsed = parse_remind_time(rest, off)
        if not parsed:
            tg_send_message(chat_id, "Не понял время.\n"
                                     "Примеры:\n"
                                     "/remind 2025-08-13 15:30 Позвонить\n"
                                     "/remind in 45m Выйти на прогулку")
            return jsonify(ok=True)
        due_ts, msg = parsed
        if not msg:
            tg_send_message(chat_id, "Добавь текст напоминания после времени.")
            return jsonify(ok=True)
        rid = add_reminder(chat_id, msg, due_ts)
        due_local = datetime.utcfromtimestamp(due_ts) + timedelta(minutes=off)
        tg_send_message(chat_id, f"✅ Записал #{rid} на {due_local:%Y-%m-%d %H:%M}\nТекст: {msg}")
        return jsonify(ok=True)

    # Прочий текст — подсказываем помощь
    tg_send_message(chat_id, "Я понимаю команды /remind, /list, /delete, /settz. Напиши /help.")
    return jsonify(ok=True)

# WSGI точка входа для gunicorn: server:app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
