from telebot import types
from deep_translator import GoogleTranslator
from bot.shared import (
    bot, is_allowed, touch, profile_photo_path, level_status, progress_bar, user_rank
)
from database.dataEngine import session
from database.models import User, Interest
from utils.interests import INTERESTS_LIST, get_interests_keyboard, parse_interest_from_text
from bot.shared import user_interests_selection

SUPPORTED_LANGS = {
    'en': 'English', 'ru': 'Russian', 'kk': 'Kazakh',  'uk': 'Ukrainian',
    'es': 'Spanish', 'fr': 'French',  'de': 'German',  'it': 'Italian',
    'pt': 'Portuguese', 'zh': 'Chinese', 'ja': 'Japanese', 'ar': 'Arabic',
    'be': 'Belarusian', 'uz': 'Uzbek', 'hy': 'Armenian', 'az': 'Azerbaijani',
    'sk': 'Slovak', 'cs': 'Czech', 'sl': 'Slovenian', 'pl': 'Polish',
    'lt': 'Lithuanian', 'lv': 'Latvian', 'et': 'Estonian',
}


@bot.message_handler(commands=['profile'])
def cmd_profile(message):
    if not is_allowed(message.chat.id): return
    touch(message.chat.id)
    user_id = message.chat.id

    with session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        if not u:
            bot.send_message(user_id, "Profile not found.")
            return
        exp   = u.experience or 0
        lvl   = u.level or 1
        gend  = u.gender or 'not set'
        uname = u.username
        like  = u.like

    rank = user_rank(user_id)
    text = (
        f"Your profile\n\n"
        f"Username: @{uname}\n"
        f"Status: {level_status(lvl)}\n"
        f"Gender: {gend}\n"
        f"Like: {'yes' if like else 'no'}\n"
        f"Experience: {exp}\n"
        f"Level: {lvl}\n"
        f"Rank: #{rank}\n\n"
        f"Progress to next level:\n"
        f"{progress_bar(exp, lvl)}"
    )
    try:
        with open(profile_photo_path(lvl), 'rb') as photo:
            bot.send_photo(user_id, photo, caption=text)
    except FileNotFoundError:
        bot.send_message(user_id, text)


@bot.message_handler(commands=['interests'])
def cmd_interests(message):
    user_id = message.chat.id
    if not is_allowed(user_id): return
    touch(user_id)

    with session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        current = [i.id for i in u.interests] if u else []

    user_interests_selection[user_id] = current.copy()
    bot.send_message(user_id,
        "Choose your interests:\n\n"
        "Tap an interest to select/deselect it.\n"
        "Press 'Done' when finished.",
        reply_markup=get_interests_keyboard(current)
    )


# Обрабатывает нажатие на кнопку интереса в клавиатуре
@bot.message_handler(func=lambda m: any(i['name'] in (m.text or '') for i in INTERESTS_LIST))
def handle_interest_button(message):
    user_id = message.chat.id
    if user_id not in user_interests_selection:
        return
    iid = parse_interest_from_text(message.text)
    if iid:
        sel = user_interests_selection[user_id]
        if iid in sel: sel.remove(iid)
        else:          sel.append(iid)
        bot.send_message(user_id, "Choose interests:", reply_markup=get_interests_keyboard(sel))


# Завершает выбор интересов и сохраняет их в БД
@bot.message_handler(func=lambda m: m.text == 'Done')
def finish_interests(message):
    user_id = message.chat.id
    if user_id not in user_interests_selection:
        bot.send_message(user_id, "Start with /interests first.")
        return
    selected = user_interests_selection.pop(user_id)

    with session() as s:
        u = s.query(User).filter(User.id == user_id).first()
        if u:
            u.interests = []
            for iid in selected:
                interest = s.query(Interest).filter(Interest.id == iid).first()
                if interest:
                    u.interests.append(interest)

    menu = types.ReplyKeyboardRemove()
    if selected:
        names = [i['name'] for i in INTERESTS_LIST if i['id'] in selected]
        bot.send_message(user_id,
            "Interests saved:\n\n" + "\n".join(f"- {n}" for n in names) +
            "\n\nWe will now look for partners with similar interests!",
            reply_markup=menu)
    else:
        bot.send_message(user_id,
            "No interests selected. Use /interests to configure later.",
            reply_markup=menu)


@bot.message_handler(commands=['translate'])
def cmd_translate(message):
    if not is_allowed(message.chat.id, 'command'): return
    touch(message.chat.id, 'command')
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        langs = ', '.join(SUPPORTED_LANGS.keys())
        bot.send_message(message.chat.id,
            f"Usage: /translate <lang> <text>\n"
            f"Example: /translate en Hello\n\n"
            f"Supported languages: {langs}")
        return
    lang = parts[1].lower()
    if lang not in SUPPORTED_LANGS:
        bot.send_message(message.chat.id, f"Unsupported language. Use: {', '.join(SUPPORTED_LANGS.keys())}")
        return
    try:
        result = GoogleTranslator(source='auto', target=lang).translate(parts[2])
        bot.send_message(message.chat.id, f"Original: {parts[2]}\n{SUPPORTED_LANGS[lang]}: {result}")
    except Exception as e:
        bot.send_message(message.chat.id, "Translation error. Please try again.")
        print(f"Translation error: {e}")
