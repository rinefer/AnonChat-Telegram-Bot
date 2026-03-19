import time
import configparser
from pathlib import Path
from telebot import types

# Читаем конфиг
config = configparser.ConfigParser()
config.read(Path(__file__).parent.parent / 'config_files' / 'config.ini')

import telebot
bot = telebot.TeleBot(config['Telegram']['access_token'])

ADMIN_ID   = int(config['Telegram']['admin_id'])
VIP_USERS  = [int(x.strip()) for x in config['VIP']['vip_users'].split(',') if x.strip()]

# Временные состояния (in-memory)
user_last_request      = {}   # {user_id: {type: timestamp}}
user_interests_selection = {} # {user_id: [interest_id, ...]}

COOLDOWNS = {'command': 5, 'message': 2}

# Проверяет, прошло ли достаточно времени с последнего запроса пользователя
def is_allowed(user_id, kind='command'):
    last = user_last_request.get(user_id, {}).get(kind, 0)
    return time.time() - last >= COOLDOWNS.get(kind, 2)

# Обновляет время последнего запроса пользователя
def touch(user_id, kind='command'):
    user_last_request.setdefault(user_id, {})[kind] = time.time()

# Возвращает Inline-клавиатуру с кнопкой «Новый чат»
def inline_menu():
    menu = types.InlineKeyboardMarkup()
    menu.add(types.InlineKeyboardButton(text='New chat', callback_data='NewChat'))
    return menu

# Возвращает Reply-клавиатуру с кнопками Like / Dislike
def chat_markup():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
    markup.add('Like')
    markup.add('Dislike')
    return markup

# Возвращает Reply-клавиатуру для выбора пола
def gender_keyboard():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('Guy', 'Girl')
    return markup

# Возвращает путь к фото профиля в зависимости от уровня
def profile_photo_path(level):
    thresholds = [50, 40, 30, 20, 10, 5]
    for t in thresholds:
        if level >= t:
            return f'profile_photos/level_{t}.jpg'
    return 'profile_photos/level_1.jpg'

# Возвращает статус-звание по уровню
def level_status(level):
    statuses = [
        (50, 'Grand Master'), (45, 'Celestial'), (40, 'Divine'),
        (35, 'Mythical'),     (30, 'Legendary'), (25, 'Diamond'),
        (20, 'Superstar'),    (15, 'Chat King'),  (10, 'Champion'),
        (9,  'Pro'),          (8,  'Expert'),     (7,  'Master'),
        (6,  'Advanced'),     (5,  'Trainee'),    (4,  'Experienced'),
        (3,  'Active'),       (2,  'Beginner'),   (1,  'Newcomer'),
    ]
    for threshold, title in statuses:
        if level >= threshold:
            return title
    return 'Newcomer'

# Строит текстовый прогресс-бар (10 блоков) для профиля
def progress_bar(experience, level):
    current = experience - (level - 1) * 100
    pct = min(100, int((current / 100) * 100))
    filled = pct // 10
    bar = '[' + 'x' * filled + '.' * (10 - filled) + ']'
    return f"{bar} {pct}%\n{current}/100 exp"

# Возвращает место пользователя в рейтинге по опыту
def user_rank(user_id):
    from database.dataEngine import session
    from database.models import User
    try:
        with session() as s:
            u = s.query(User).filter(User.id == user_id).first()
            if not u:
                return 'N/A'
            return s.query(User).filter(User.experience > u.experience).count() + 1
    except Exception:
        return 'N/A'

# Проверяет, является ли пользователь VIP (активная подписка)
def is_vip(user_id, crypto_payment):
    info = crypto_payment.check_subscription(user_id)
    if info['active']:
        return True
    if user_id in VIP_USERS:
        crypto_payment._update_vip_config(user_id, False)
        if user_id in VIP_USERS:
            VIP_USERS.remove(user_id)
    return False

# Возвращает Inline-клавиатуру для VIP-настроек поиска
def vip_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Any gender",    callback_data="vip_search_any"),
        types.InlineKeyboardButton("Guys only",     callback_data="vip_search_male"),
        types.InlineKeyboardButton("Girls only",    callback_data="vip_search_female"),
        types.InlineKeyboardButton("Info",          callback_data="vip_info"),
    )
    return markup
