# Telegram Reminder Bot — @Napominalka_Dars_bot

Это Telegram-бот для создания напоминаний.  
Ты отправляешь команду `/remind`, бот сохраняет напоминание и отправляет его в нужное время.

---

## ?? Как запустить бота

### 1. Клонируем или создаём проект
Создай папку `telegram-reminder-bot` и положи в неё файлы:
- `server.py` — код бота
- `requirements.txt` — зависимости
- `Procfile` — инструкция для запуска
- `README.md` — это руководство

---

### 2. Загрузка на GitHub
1. Зайди на [GitHub](https://github.com).
2. Нажми **New repository** > введи имя `telegram-reminder-bot` > **Create repository**.
3. Перетащи все файлы проекта в репозиторий.
4. Нажми **Commit changes**.

---

### 3. Развёртывание на Railway
1. Перейди на [Railway](https://railway.app).
2. Нажми **New Project** > **Deploy from GitHub Repo** > выбери свой репозиторий.
3. Зайди во вкладку **Variables** и добавь переменные:
TOKEN=8390901633:AAGWzRUhrm2qst2IDyk9tDwJvJvq2Lxv6Nw

yaml
Копировать
Редактировать
4. Нажми **Deploy**.
5. Railway даст тебе **ссылку на бота** — бот будет доступен 24/7.

---

## ?? Команды бота
- `/start` — приветственное сообщение.
- `/remind HH:MM текст` — создать напоминание.
- `/list` — показать список напоминаний.
- `/clear` — (в этой версии нет, можно добавить) удалить все напоминания.

---

## ?? Зависимости
- Flask
- pyTelegramBotAPI
- gunicorn

---

### Пример использования
/remind 14:30 Позвонить клиенту
/remind 07:00 Проснуться
/list

yaml
Копировать
Редактировать

---

?? Автор: @Napominalka_Dars_bot