"""
handlers/start.py — базовые обработчики: /start, /stop, /project,
выбор пола, передача сообщений между собеседниками, лайк/дизлайк.
"""
from telebot import types
from bot.shared import bot, is_allowed, touch, inline_menu, chat_markup, gender_keyboard
from database.dataEngine import (
    session, free_users, communications,
    add_user, delete_user_from_db, delete_info, update_user_like,
    get_common_interests, find_match_by_interests, find_match_for_user,
    add_communications, get_free_users_count, get_vip_search_setting
)
from database.models import User
from utils.interests import INTERESTS_LIST, get_interests_keyboard, parse_interest_from_text
from bot.Messages import (
    m_is_not_user_name, m_good_bye, m_disconnect_user, m_failed,
    m_like, m_dislike_user, m_dislike_user_to, m_all_like,
    m_play_again, m_send_some_messages, m_has_not_dialog
)

WELCOME = (
    "Hello, {username}!\n\n"
    "You are in an anonymous chat.\n"
    "Press the button below to find a chat partner.\n"
    "Press Like if you enjoy the conversation.\n"
    "With mutual interest you will see each other's username.\n\n"
    "To exit, press /stop."
)

# Проверяет, указан ли пол у пользователя в БД
def _has_gender(user_id):
    with session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        return bool(u and u.gender)

# Отправляет приветственное фото с меню
def _send_welcome(user_id, username):
    text = WELCOME.format(username=f"@{username}" if username else "anonymous")
    try:
        with open('w.jpg', 'rb') as photo:
            bot.send_photo(chat_id=user_id, photo=photo, caption=text, reply_markup=inline_menu())
    except FileNotFoundError:
        bot.send_message(user_id, text, reply_markup=inline_menu())


@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.chat.id
    if not is_allowed(user_id): return
    touch(user_id)
    if not message.chat.username:
        bot.send_message(user_id, m_is_not_user_name)
        return
    if not _has_gender(user_id):
        msg = bot.send_message(user_id, "Welcome! Please choose your gender:", reply_markup=gender_keyboard())
        bot.register_next_step_handler(msg, _process_gender)
        return
    _send_welcome(user_id, message.chat.username)


# Обрабатывает ответ пользователя при выборе пола
def _process_gender(message):
    user_id = message.chat.id
    gender_map = {'Guy': 'male', 'Girl': 'female'}
    gender = gender_map.get(message.text)
    if not gender:
        msg = bot.send_message(user_id, "Please use the buttons below:", reply_markup=gender_keyboard())
        bot.register_next_step_handler(msg, _process_gender)
        return
    with session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        if u:
            u.gender = gender
        else:
            s.add(User(id=user_id, username=message.chat.username or 'anon',
                       like=False, status=0, gender=gender, experience=0, level=1))
    add_user(chat=message.chat, gender=gender)
    bot.send_message(user_id, "Gender saved.", reply_markup=types.ReplyKeyboardRemove())
    _send_welcome(user_id, message.chat.username)


@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    if not is_allowed(message.chat.id): return
    touch(message.chat.id)
    user_id = message.chat.id
    menu = types.ReplyKeyboardRemove()
    if user_id in communications:
        partner_id = communications[user_id]['UserTo']
        bot.send_message(partner_id, m_disconnect_user, reply_markup=menu)
        delete_info(partner_id)
    delete_user_from_db(user_id)
    bot.send_message(user_id, m_good_bye, reply_markup=menu)


@bot.message_handler(commands=['project'])
def cmd_project(message):
    if not is_allowed(message.chat.id): return
    touch(message.chat.id)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Blog", url="https://t.me/+2imH_DObPjplMWI0"),
        types.InlineKeyboardButton("News", url="https://t.me/offFaodal")
    )
    bot.send_message(message.chat.id, "Our projects:", reply_markup=markup)


# Обрабатывает нажатие Like / Dislike во время диалога
@bot.message_handler(func=lambda m: m.text in ('Like', 'Dislike'))
def handle_like_dislike(message):
    if not is_allowed(message.chat.id): return
    touch(message.chat.id)
    user_id = message.chat.id
    if user_id not in communications:
        bot.send_message(user_id, m_failed, reply_markup=types.ReplyKeyboardRemove())
        return
    partner_id = communications[user_id]['UserTo']
    if message.text == 'Dislike':
        bot.send_message(user_id,   m_dislike_user,    reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(partner_id, m_dislike_user_to, reply_markup=types.ReplyKeyboardRemove())
        delete_info(partner_id)
        bot.send_message(user_id,   m_play_again, reply_markup=inline_menu())
        bot.send_message(partner_id, m_play_again, reply_markup=inline_menu())
    else:
        bot.send_message(user_id, m_like, reply_markup=types.ReplyKeyboardRemove())
        update_user_like(user_id)
        if communications[user_id]['like'] and communications[partner_id]['like']:
            bot.send_message(user_id,   m_all_like(communications[user_id]['UserName']))
            bot.send_message(partner_id, m_all_like(communications[partner_id]['UserName']))
            delete_info(partner_id)
            bot.send_message(user_id,   m_play_again, reply_markup=inline_menu())
            bot.send_message(partner_id, m_play_again, reply_markup=inline_menu())


# Пересылает сообщения, стикеры, фото, аудио, видео, войс между собеседниками.
# ВАЖНО: команды (начинаются с /) и служебные кнопки ('Done') пропускаем молча —
# их обрабатывают собственные обработчики зарегистрированные раньше.
@bot.message_handler(content_types=['text', 'sticker', 'video', 'photo', 'audio', 'voice'])
def relay(message):
    user_id = message.chat.id
    ct = message.content_type
    text = message.text or ''

    # Команды и служебные кнопки — пропускаем, их поймут свои обработчики
    if ct == 'text' and (text.startswith('/') or text in ('Like', 'Dislike', 'Done')):
        return

    # Пользователь не в диалоге — сообщаем об этом только для обычного текста
    if user_id not in communications:
        if ct == 'text':
            bot.send_message(user_id, m_has_not_dialog)
        return

    partner_id = communications[user_id]['UserTo']

    if ct == 'sticker':
        bot.send_sticker(partner_id, message.sticker.file_id)
    elif ct == 'photo':
        bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
    elif ct == 'audio':
        bot.send_audio(partner_id, message.audio.file_id, caption=message.caption)
    elif ct == 'video':
        bot.send_video(partner_id, message.video.file_id, caption=message.caption)
    elif ct == 'voice':
        bot.send_voice(partner_id, message.voice.file_id)
    elif ct == 'text':
        if message.reply_to_message is None:
            bot.send_message(partner_id, text)
        elif message.from_user.id != message.reply_to_message.from_user.id:
            bot.send_message(partner_id, text,
                             reply_to_message_id=message.reply_to_message.message_id - 1)
        else:
            bot.send_message(user_id, m_send_some_messages)


# Обрабатывает нажатие кнопки «New chat» — ищет собеседника
@bot.callback_query_handler(func=lambda call: call.data == 'NewChat')
def handle_new_chat(call):
    user_id = call.message.chat.id

    def _ack(text):
        try: bot.answer_callback_query(call.id, text)
        except Exception: pass

    if not is_allowed(user_id):
        _ack("Please wait 5 seconds...")
        return
    touch(user_id)
    _ack("Searching...")

    if user_id in communications:
        bot.send_message(user_id, "You are already in a chat.")
        return
    if not call.message.chat.username:
        bot.send_message(user_id, m_is_not_user_name)
        return

    with session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        user_interests = [i.id for i in u.interests] if u else []
        user_gender    = u.gender if u else None

    add_user(chat=call.message.chat, interests=user_interests)

    if get_free_users_count() == 0:
        bot.send_message(user_id, "You are first in the queue. Waiting for another user...")
        return

    partner_id = find_match_by_interests(user_id) if user_interests else None
    if partner_id is None:
        partner_id = find_match_for_user(user_id)

    if partner_id is None or partner_id == user_id:
        bot.send_message(user_id, "No suitable partners found. Try again in a few seconds!")
        return

    if partner_id not in free_users or partner_id in communications:
        bot.send_message(user_id, "Partner status changed. Please try again.")
        return

    common = get_common_interests(user_id, partner_id)
    partner_gender = free_users[partner_id]['gender']

    add_communications(user_id, partner_id)
    keyboard = chat_markup()

    connect_msg = (
        "Connection established!\n\n"
        f"Partner gender: {partner_gender or 'not specified'}\n"
        f"Common interests: {len(common)}\n"
    )
    if common:
        connect_msg += "\n".join(f"  - {i}" for i in common) + "\n"
    connect_msg += "\nSay hello! Press Like or Dislike when ready."

    bot.send_message(user_id,    connect_msg, reply_markup=keyboard)
    bot.send_message(partner_id, connect_msg, reply_markup=keyboard)
    _ack("Connected!")
