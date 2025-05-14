
import telebot
from telebot import types
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = -1002612055353
ADMIN_ID = 470240474

bot = telebot.TeleBot(TOKEN)

waiting_for_message = {}
pending_messages = {}

FILTER_FILE = 'filter_words.json'
if os.path.exists(FILTER_FILE):
    with open(FILTER_FILE, 'r', encoding='utf-8') as f:
        filter_words = json.load(f)
else:
    filter_words = []

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📝 Надіслати повідомлення")
    markup.row("ℹ️ Про мене", "📄 Допомога")
    markup.row("☕ Донат", "❌ Вийти")
    bot.send_message(message.chat.id, "Привіт! Обери дію з меню нижче:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["ℹ️ Про мене", "📄 Допомога", "☕ Донат", "❌ Вийти"])
def handle_menu_buttons(message):
    if message.text == "ℹ️ Про мене":
        bot.send_message(message.chat.id, "Я бот, що передає повідомлення для публікації в канал новин Ctrl.Tap")
    elif message.text == "📄 Допомога":
        bot.send_message(message.chat.id, "Натисни '📝 Надіслати повідомлення', напиши текст — і я передам його адміну")
    elif message.text == "☕ Донат":
        bot.send_message(message.chat.id, "Підтримати проєкт: Ctrl.Tap https://send.monobank.ua/jar/7F8qg5rR9c")
    elif message.text == "❌ Вийти":
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "Меню приховано. Напиши /start, щоб повернутись.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📝 Надіслати повідомлення")
def prompt_for_message(message):
    bot.send_message(message.chat.id, "✉️ Напиши повідомлення (можна додати фото або відео).")
    waiting_for_message[message.chat.id] = True

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data.split('_')
    action = data[0]
    msg_id = int(data[1])
    user_id = int(data[2])

    if msg_id in pending_messages:
        entry = pending_messages.pop(msg_id)

        if action == "approve":
            if entry.get('media'):
                file_id = entry['media']
                caption = entry.get('text', '')
                send_func = getattr(bot, f"send_{entry['type']}")
                send_func(CHANNEL_ID, file_id, caption=caption)
            else:
                bot.send_message(CHANNEL_ID, entry['text'])
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

        elif action == "delete":
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

        elif action == "reply":
            bot.send_message(call.message.chat.id, "💬 Напиши відповідь для користувача:")
            waiting_for_message[call.message.chat.id] = ("reply", user_id)

@bot.message_handler(commands=['launch'])
def launch_post(message):
    if message.from_user.id != ADMIN_ID:
        return

    text = (
        "🚀 Ctrl.Tap офіційно стартує!\n\n"
        "Тут ви знайдете найцікавіші новини, думки, меми та дотики до світу технологій і життя.\n\n"
        "Дякуємо, що з нами — буде гаряче 🔥\n"
        "Підписуйся, коментуй, надсилай свої повідомлення прямо в бота ✉️"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✉️ Написати боту", url="https://t.me/CtrlTaps_Bot"))

    bot.send_message(CHANNEL_ID, text, reply_markup=markup)
    bot.send_message(message.chat.id, "✅ Пост опубліковано.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_id = message.from_user.id
    name = message.from_user.first_name or "Без імені"

    if isinstance(waiting_for_message.get(user_id), tuple):
        mode, target_id = waiting_for_message[user_id]
        if mode == "reply":
            bot.send_message(target_id, f"📢 Відповідь від адміністратора: {message.text}")
            bot.send_message(user_id, "✅ Відповідь надіслано.")
            waiting_for_message.pop(user_id)
        return

    if waiting_for_message.get(user_id):
        waiting_for_message.pop(user_id)

        if message.content_type == 'text':
            lowered = message.text.lower()
            if any(word in lowered for word in filter_words):
                bot.send_message(user_id, "⛔ Повідомлення містить заборонені слова.")
                return

        if user_id != ADMIN_ID:
            msg_id = message.message_id
            content = message.text if message.content_type == 'text' else '<мультимедійне>'
            pending_messages[msg_id] = {
                'text': f"📨 Повідомлення від {name} (ID: {user_id}):{content}",
                'from_id': user_id
            }

            if message.content_type != 'text':
                if message.content_type == 'photo':
                    file_id = message.photo[-1].file_id
                else:
                    file_id = getattr(message, message.content_type).file_id
                pending_messages[msg_id]['media'] = file_id
                pending_messages[msg_id]['type'] = message.content_type

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Опублікувати", callback_data=f"approve_{msg_id}_{user_id}"),
                types.InlineKeyboardButton("❌ Видалити", callback_data=f"delete_{msg_id}_{user_id}"),
                types.InlineKeyboardButton("💬 Відповісти", callback_data=f"reply_{msg_id}_{user_id}")
            )

            if message.content_type == 'text':
                bot.send_message(ADMIN_ID, pending_messages[msg_id]['text'], reply_markup=markup)
            else:
                send_func = getattr(bot, f'send_{message.content_type}')
                send_func(ADMIN_ID, pending_messages[msg_id]['media'], caption=pending_messages[msg_id]['text'], reply_markup=markup)

            bot.send_message(user_id, "✅ Повідомлення передано адміністратору.")

        else:
            if message.content_type == 'text':
                if message.text.startswith('/'):
                    return
                bot.send_message(CHANNEL_ID, message.text)
            else:
                if message.content_type == 'photo':
                    file_id = message.photo[-1].file_id
                else:
                    file_id = getattr(message, message.content_type).file_id
                send_func = getattr(bot, f'send_{message.content_type}')
                send_func(CHANNEL_ID, file_id, caption=message.caption if message.caption else '')
            bot.send_message(user_id, "✅ Опубліковано в каналі.")

# запуск бота та Flask
from flask import Flask

def run_bot():
    time.sleep(2)
    bot.polling(none_stop=True)

import threading
bot_thread = threading.Thread(target=run_bot)
bot_thread.start()

app = Flask(__name__)

@app.route('/')
def index():
    return 'Bot is running'

app.run(host="0.0.0.0", port=10000)
