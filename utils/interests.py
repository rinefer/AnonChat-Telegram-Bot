INTERESTS_LIST = [
    {"id": 1,  "name": "Roleplay",      "emoji": ""},
    {"id": 2,  "name": "Memes",         "emoji": ""},
    {"id": 3,  "name": "Loneliness",    "emoji": ""},
    {"id": 4,  "name": "Flirt",         "emoji": ""},
    {"id": 5,  "name": "Games",         "emoji": ""},
    {"id": 6,  "name": "Music",         "emoji": ""},
    {"id": 7,  "name": "Travel",        "emoji": ""},
    {"id": 8,  "name": "Anime",         "emoji": ""},
    {"id": 9,  "name": "Movies",        "emoji": ""},
    {"id": 10, "name": "Pets",          "emoji": ""},
    {"id": 11, "name": "Books",         "emoji": ""},
    {"id": 12, "name": "Sports",        "emoji": ""},
    {"id": 13, "name": "Programming",   "emoji": ""},
    {"id": 14, "name": "Art",           "emoji": ""},
    {"id": 15, "name": "Cooking",       "emoji": ""},
]

# Создаёт записи интересов в БД если их ещё нет
def initialize_interests(session):
    from database.models import Interest
    for data in INTERESTS_LIST:
        if not session.query(Interest).filter(Interest.id == data['id']).first():
            session.add(Interest(id=data['id'], name=data['name'], emoji=data['emoji']))
    session.commit()

# Создаёт клавиатуру выбора интересов; помечает уже выбранные галочкой
def get_interests_keyboard(selected_interests=None):
    from telebot import types
    selected_interests = selected_interests or []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = []
    for interest in INTERESTS_LIST:
        prefix = "[x] " if interest['id'] in selected_interests else ""
        buttons.append(f"{prefix}{interest['name']}")
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.add(*row)
    markup.add("Done")
    return markup

# Извлекает ID интереса из текста нажатой кнопки; возвращает None если не найден
def parse_interest_from_text(text):
    for interest in INTERESTS_LIST:
        if interest['name'] in text:
            return interest['id']
    return None
