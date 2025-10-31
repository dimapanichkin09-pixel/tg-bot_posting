import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz
import time

# ---------- НАСТРОЙКИ ----------
TOKEN = "8384727802:AAHZnmECivmQpT274V0gnw4tOVcQWmoimcs"
CHANNEL = "@DniproLive_news"

# Два админа
ADMINS = [981142988, 7535293788]

bot = telebot.TeleBot(TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

tz = pytz.timezone("Europe/Kiev")
pending_posts = {}  # {user_id: {"content": str, "media": dict, "time": datetime}}

# ---------- КЛАВИАТУРЫ ----------
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Выложить пост")
    return kb

def post_options():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Выложить сейчас", callback_data="post_now"))
    kb.add(types.InlineKeyboardButton("Отложить", callback_data="post_later"))
    return kb

def time_options():
    kb = types.InlineKeyboardMarkup()
    now = datetime.now(tz)
    for i in range(1, 13):  # каждые 30 минут, 6 часов
        t = now + timedelta(minutes=30*i)
        kb.add(types.InlineKeyboardButton(t.strftime("%Y-%m-%d %H:%M"), callback_data=f"time_{t.strftime('%Y-%m-%d %H:%M')}"))
    return kb

# ---------- ФУНКЦИИ ----------
def is_admin(user_id):
    return user_id in ADMINS

def send_post_to_channel(content, media=None):
    if media:
        if media['type'] == 'photo':
            bot.send_photo(CHANNEL, media['file_id'], caption=content)
        elif media['type'] == 'video':
            bot.send_video(CHANNEL, media['file_id'], caption=content)
    else:
        bot.send_message(CHANNEL, content)

def schedule_post(user_id, post_time):
    post = pending_posts[user_id]
    scheduler.add_job(send_post_to_channel, 'date', run_date=post_time, args=[post['content'], post['media']])
    pending_posts[user_id]['time'] = post_time

# ---------- ОБРАБОТКА СООБЩЕНИЙ ----------
@bot.message_handler(commands=['start'])
def start(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "У вас нет доступа.")
        return
    bot.send_message(message.chat.id, "Привет! Выбери действие:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "Выложить пост")
def create_post(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "У вас нет доступа.")
        return
    bot.send_message(message.chat.id, "Отправь текст и/или фото/видео для поста.")
    bot.register_next_step_handler(message, handle_post_content)

def handle_post_content(message):
    user_id = message.from_user.id
    media = None
    content = message.caption if message.caption else message.text

    if message.photo:
        media = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.video:
        media = {"type": "video", "file_id": message.video.file_id}

    pending_posts[user_id] = {"content": content, "media": media, "time": None}
    bot.send_message(message.chat.id, "Выбери действие:", reply_markup=post_options())

# ---------- CALLBACK QUERY ----------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    if user_id not in pending_posts:
        bot.answer_callback_query(call.id, "Нет подготовленного поста.")
        return

    if call.data == "post_now":
        post = pending_posts.pop(user_id)
        send_post_to_channel(post['content'], post['media'])
        bot.answer_callback_query(call.id, "Пост опубликован!")
    elif call.data == "post_later":
        bot.edit_message_text("Выбери время публикации:", call.message.chat.id, call.message.message_id, reply_markup=time_options())
    elif call.data.startswith("time_"):
        post_time_str = call.data[5:]
        post_time = tz.localize(datetime.strptime(post_time_str, "%Y-%m-%d %H:%M"))
        schedule_post(user_id, post_time)
        bot.edit_message_text(f"Пост запланирован на {post_time_str}", call.message.chat.id, call.message.message_id)

# ---------- БЕСКОНЕЧНЫЙ ЦИКЛ ----------
while True:
    try:
        bot.infinity_polling(timeout=60)
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)  # ждём 5 секунд перед перезапуском
