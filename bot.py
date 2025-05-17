import os
import time
import telebot
from telebot import types
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ['BOT_TOKEN']
CHANNEL_ID = -1002612055353
CHANNEL_USERNAME = "CtrlTap"  # без @
ADMIN_ID = 470240474

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

waiting_for_message = {}
pending_messages = {}
first_users = set()  # Зберігає ID перших підписників
FIRST_USERS_FILE = "first_users.txt"

# === Функції ===

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Помилка перевірки підписки: {e}")
        return False

def save_first_user(user_id):
    if user_id not in first_users:
        first_users.add(user_id)
        with open(FIRST_USERS_FILE, "a") as file:
            file.write(str(user_id) + "\n")

def load_first_users():
    if os.path.exists(FIRST_USERS_FILE):
        with open(FIRST_USERS_FILE, "r") as file:
            for line in file:
                user_id = line.strip()
                if user_id.isdigit():
                    first_users.add(int(user_id))

load_first_users()

# === Команди ===

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("✉️ Написати повідомлення")
    markup.row("🔍 Стати першим")
    markup.row("☕ Донат", "ℹ️ Про мене")
    markup.row("📄 Допомога", "❌ Вийти")
    bot.send_message(
        message.chat.id,
        "👋 Вітаю! Скористайся кнопками або надішли мені своє повідомлення, і я передам його адміну!",
        reply_markup=markup
    )

@bot.message_handler(commands=['first'])
def show_first_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    if not first_users:
        bot.send_message(message.chat.id, "Список перших пiдписникiв порожнiй.")
    else:
        users = "\n".join([str(uid) for uid in sorted(first_users)])
        bot.send_message(message.chat.id, f"Список перших пiдписникiв:\n{users}")

# === Обробка кнопок ===

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text_buttons(message):
    text = message.text
    user_id = message.chat.id

    if text == "☕ Донат":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Перейти", url="https://send.monobank.ua/jar/7F8qg5rR9c"))
        bot.send_message(message.chat.id, "Дякуємо за підтримку!", reply_markup=markup)

    elif text == "ℹ️ Про мене":
        bot.send_message(message.chat.id, "📊 Ctrl.Tap — канал новин, спорту, технологій та геймінгу. Ми публікуємо тільки найцікавіше!")

    elif text == "📄 Допомога":
        bot.send_message(message.chat.id, "🤔 Просто напиши нам повідомлення, а ми передамо його адміну. Він вирішить, чи опублікувати його в каналі.")

    elif text == "✉️ Написати повідомлення":
        bot.send_message(message.chat.id, "Напиши сюди своє повідомлення та натисни кнопку нижче! Я передам його адміну.")

    elif text == "🔍 Стати першим":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Я підписався", callback_data="check_sub"))
        markup.add(types.InlineKeyboardButton("🔗 Перейти до каналу", url=f"https://t.me/{CHANNEL_USERNAME}"))
        bot.send_message(message.chat.id, "Підпишись на канал та натисни кнопку нижче для перевірки:", reply_markup=markup)

    elif text == "❌ Вийти":
        bot.send_message(message.chat.id, "Ви вийшли з меню. Напишіть /start, щоб почати знову.", reply_markup=types.ReplyKeyboardRemove())

    else:
        handle_user_message(message)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription(call):
    user_id = call.from_user.id
    if is_subscribed(user_id):
        if user_id not in first_users:
            save_first_user(user_id)
            bot.send_message(user_id, "🎉 Ви стали одним із перших підписників!")
        else:
            bot.send_message(user_id, "🔁 Ви вже в списку перших підписників.")
    else:
        bot.send_message(user_id, "❗ Щоб стати першим, потрібно бути підписаним на канал!")

# === Обробка повідомлень від користувачів ===

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice'])
def handle_user_message(message):
    user_id = message.chat.id
    waiting_for_message[user_id] = message

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Надіслати", callback_data="submit"),
        types.InlineKeyboardButton("❌ Скасувати", callback_data="cancel")
    )
    bot.send_message(user_id, "Підтвердити надсилання повідомлення?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "submit":
        msg = waiting_for_message.get(user_id)
        if not msg:
            bot.answer_callback_query(call.id, "Немає повідомлення")
            return

        name = msg.from_user.first_name or ""
        username = msg.from_user.username or ""
        pending_messages[msg.message_id] = (msg, user_id)

        caption = f"📨 Повідомлення від {name} (@{username} | ID: {user_id})"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Опублікувати", callback_data=f"approve:{msg.message_id}"),
            types.InlineKeyboardButton("❌ Видалити", callback_data=f"decline:{msg.message_id}"),
            types.InlineKeyboardButton("✉️ Відповісти", callback_data=f"reply:{msg.message_id}")
        )

        if msg.content_type == "text":
            bot.send_message(ADMIN_ID, f"{caption}\n\n{msg.text}", reply_markup=markup)
        else:
            bot.copy_message(ADMIN_ID, msg.chat.id, msg.message_id, caption=caption, reply_markup=markup)

        bot.send_message(user_id, "✅ Повідомлення надіслано на перевірку.")
        waiting_for_message.pop(user_id)

    elif data == "cancel":
        bot.send_message(user_id, "❌ Надсилання скасовано.")
        waiting_for_message.pop(user_id, None)

    elif data.startswith("approve:"):
        msg_id = int(data.split(":")[1])
        msg, original_user = pending_messages.get(msg_id, (None, None))
        if msg:
            bot.copy_message(CHANNEL_ID, msg.chat.id, msg.message_id)
            bot.send_message(original_user, "✅ Ваше повідомлення опубліковано.")
            pending_messages.pop(msg_id, None)
        else:
            bot.answer_callback_query(call.id, "Повідомлення не знайдено.")

    elif data.startswith("decline:"):
        msg_id = int(data.split(":")[1])
        msg, original_user = pending_messages.get(msg_id, (None, None))
        if msg:
            bot.send_message(original_user, "❌ Ваше повідомлення відхилено.")
            pending_messages.pop(msg_id, None)
        else:
            bot.answer_callback_query(call.id, "Повідомлення не знайдено.")

    elif data.startswith("reply:"):
        msg_id = int(data.split(":")[1])
        msg, original_user = pending_messages.get(msg_id, (None, None))
        if msg:
            bot.send_message(user_id, "✉️ Напишіть відповідь користувачу:")
            bot.register_next_step_handler_by_chat_id(user_id, lambda m: reply_to_user(m, original_user))
            pending_messages.pop(msg_id, None)
        else:
            bot.answer_callback_query(call.id, "Повідомлення не знайдено.")

def reply_to_user(message, user_id):
    bot.send_message(user_id, f"📢 Відповідь від адміністратора:\n\n{message.text}")
    bot.send_message(ADMIN_ID, "✅ Відповідь надіслана.")

@app.route('/', methods=['GET'])
def index():
    return "✅ Бот працює", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook"
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
