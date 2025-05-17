import os
import time
import telebot
from telebot import types
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ['BOT_TOKEN']
CHANNEL_ID = -1002612055353  # заміни, якщо потрібно
ADMIN_ID = 470240474         # заміни, якщо потрібно

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

waiting_for_message = {}
pending_messages = {}

# === ОБРОБНИКИ TELEGRAM ===

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Надішли своє повідомлення, щоб я передав його адміну!")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice'])
def handle_user_message(message):
    user_id = message.chat.id
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "🔧 Ви адміністратор. Для вас доступні інші функції.")
        return

    waiting_for_message[user_id] = message

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Надіслати", callback_data="submit"))
    markup.add(types.InlineKeyboardButton("❌ Скасувати", callback_data="cancel"))

    bot.send_message(user_id, "Підтвердити надсилання повідомлення?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["submit", "cancel", "approve", "decline", "reply"])
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

    elif data.startswith("approve:") or data.startswith("decline:") or data.startswith("reply:"):
        parts = data.split(":")
        action = parts[0]
        msg_id = int(parts[1])
        msg, original_user = pending_messages.get(msg_id, (None, None))

        if not msg:
            bot.answer_callback_query(call.id, "Повідомлення не знайдено.")
            return

        if action == "approve":
            bot.copy_message(CHANNEL_ID, msg.chat.id, msg.message_id)
            bot.send_message(original_user, "✅ Ваше повідомлення опубліковано.")
        elif action == "decline":
            bot.send_message(original_user, "❌ Ваше повідомлення відхилено.")
        elif action == "reply":
            bot.send_message(user_id, "✉️ Напишіть відповідь користувачу:")
            bot.register_next_step_handler_by_chat_id(user_id, lambda m: reply_to_user(m, original_user))

        pending_messages.pop(msg_id, None)

def reply_to_user(message, user_id):
    bot.send_message(user_id, f"📢 Відповідь від адміністратора:\n\n{message.text}")
    bot.send_message(ADMIN_ID, "✅ Відповідь надіслана.")

# === FLASK WEBHOOK ===

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

# === ГОЛОВНИЙ ЗАПУСК ===

if __name__ == "__main__":
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook"
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=webhook_url)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
