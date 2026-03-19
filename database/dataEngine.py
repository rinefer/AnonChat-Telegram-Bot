import random
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.models import User, Contact, UserStats, Base, Interest

# --- Глобальное состояние ---
free_users = {}
communications = {}
vip_search_settings = {}

MATCHING_PROBABILITIES = {
    'male':   {'male': 0.3, 'female': 0.7},
    'female': {'female': 0.3, 'male': 0.7},
    None:     {'male': 0.5, 'female': 0.5}
}

# --- Инициализация базы данных ---
engine = create_engine('sqlite:///anon_chat.db', echo=False)
Base.metadata.create_all(engine)
_Session = sessionmaker(bind=engine)

# Контекстный менеджер для автоматического закрытия сессии
@contextmanager
def session():
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

# Добавляет недостающие колонки experience и level в таблицу users
def update_database():
    with session() as s:
        result = s.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result]
        if 'experience' not in columns:
            s.execute(text("ALTER TABLE users ADD COLUMN experience INTEGER DEFAULT 0"))
        if 'level' not in columns:
            s.execute(text("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1"))

update_database()

# Возвращает количество свободных (ожидающих) пользователей
def get_free_users_count():
    return len(free_users)

# Добавляет или обновляет пользователя в БД и в очередь поиска
def add_user(chat, gender=None, interests=None):
    user_id = chat.id
    username = chat.username or 'anon'

    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(id=user_id, username=username, like=False, status=0,
                        gender=gender, experience=0, level=1)
            s.add(user)
        else:
            user.status = 0
            user.username = username
            if gender:
                user.gender = gender

        if interests is not None:
            user.interests = []
            for iid in interests:
                interest = s.query(Interest).filter(Interest.id == iid).first()
                if interest:
                    user.interests.append(interest)

    free_users[user_id] = {
        'UserName': username,
        'like': False,
        'gender': gender,
        'interests': interests or []
    }

# Возвращает список ID интересов пользователя из БД
def get_user_interests(user_id):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        return [i.id for i in user.interests] if user else []

# Ищет собеседника с максимальным числом общих интересов с учётом пола
def find_match_by_interests(user_id):
    if user_id not in free_users:
        return None

    user_interests = set(free_users[user_id].get('interests', []))
    user_gender = free_users[user_id]['gender']
    best_match, best_score = None, 0

    for other_id, other_data in free_users.items():
        if other_id == user_id:
            continue
        common = user_interests & set(other_data.get('interests', []))
        prob = MATCHING_PROBABILITIES.get(user_gender, {}).get(other_data['gender'], 0.5)
        score = len(common) * prob
        if score > best_score:
            best_score, best_match = score, other_id

    return best_match if best_score >= 1 else None

# Возвращает список названий общих интересов двух пользователей
def get_common_interests(user1_id, user2_id):
    with session() as s:
        u1 = s.query(User).filter(User.id == user1_id).first()
        u2 = s.query(User).filter(User.id == user2_id).first()
        if not u1 or not u2:
            return []
        ids1 = {i.id for i in u1.interests}
        ids2 = {i.id for i in u2.interests}
        common = ids1 & ids2
        result = []
        for iid in common:
            interest = s.query(Interest).filter(Interest.id == iid).first()
            if interest:
                result.append(f"{interest.emoji} {interest.name}")
        return result

# Помечает пользователя как неактивного и удаляет из очереди поиска
def delete_user_from_db(user_id):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if user:
            user.status = 3
    free_users.pop(user_id, None)

# Возвращает пол пользователя из БД
def get_user_gender(user_id):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        return user.gender if user else None

# Ищет случайного собеседника с учётом вероятностей по полу
def find_match_for_user(user_id):
    if user_id not in free_users:
        return None

    user_gender = free_users[user_id]['gender']
    potential = [
        other_id for other_id, other_data in free_users.items()
        if other_id != user_id and random.random() < MATCHING_PROBABILITIES.get(
            user_gender, {}).get(other_data['gender'], 0.5)
    ]
    return random.choice(potential) if potential else None

# Создаёт активный диалог между двумя пользователями
def add_communications(user_id, user_to_id):
    communications[user_id] = {'UserTo': user_to_id, 'UserName': free_users[user_id]['UserName'], 'like': False}
    communications[user_to_id] = {'UserTo': user_id, 'UserName': free_users[user_to_id]['UserName'], 'like': False}

    with session() as s:
        for uid in (user_id, user_to_id):
            u = s.query(User).filter(User.id == uid).first()
            if u:
                u.status = 1
        free_users.pop(user_id, None)
        free_users.pop(user_to_id, None)

# Удаляет информацию о диалоге пользователя
def delete_info(user_id):
    communications.pop(user_id, None)
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if user:
            user.status = 0
            user.like = False

# Ставит лайк от пользователя и начисляет опыт
def update_user_like(user_id):
    if user_id not in communications:
        return
    communications[user_id]['like'] = True
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if user:
            user.like = True
            user.experience = (user.experience or 0) + 10
            user.level = user.experience // 100 + 1

# Восстанавливает состояние из БД при перезапуске
def recovery_data():
    with session() as s:
        for user in s.query(User).filter(User.status.in_([0, 1])).all():
            user.status = 0
            free_users[user.id] = {
                'UserName': user.username,
                'like': user.like,
                'gender': user.gender,
                'interests': []
            }

# Добавляет опыт пользователю и пересчитывает уровень
def add_experience(user_id, amount):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.experience = max(0, (user.experience or 0) + amount)
        user.level = user.experience // 100 + 1
        return True

# Устанавливает точное значение опыта пользователю
def set_experience(user_id, experience):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.experience = max(0, experience)
        user.level = user.experience // 100 + 1
        return True

# Принудительно задаёт уровень пользователю
def set_level(user_id, level):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.level = max(1, level)
        return True

# Возвращает словарь с основными данными пользователя
def get_user_stats(user_id):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return {
            'id': user.id, 'username': user.username,
            'gender': user.gender, 'status': user.status,
            'like': user.like,
            'experience': user.experience or 0,
            'level': user.level or 1
        }

# Возвращает всех пользователей из БД
def get_all_users():
    with session() as s:
        return s.query(User).all()

# Возвращает пользователей с указанным полом
def get_users_by_gender(gender):
    with session() as s:
        return s.query(User).filter(User.gender == gender).all()

# Возвращает пользователей с указанным статусом
def get_users_by_status(status):
    with session() as s:
        return s.query(User).filter(User.status == status).all()

# Возвращает топ-N пользователей по очкам опыта
def get_top_users_by_experience(limit=10):
    with session() as s:
        return s.query(User).order_by(User.experience.desc()).limit(limit).all()

# Возвращает объект пользователя по его Telegram ID
def get_user_by_id(user_id):
    with session() as s:
        return s.query(User).filter(User.id == user_id).first()

# Обновляет пол пользователя в БД
def update_user_gender(user_id, gender):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.gender = gender
        return True

# Сбрасывает лайки, опыт и уровень пользователя до начальных значений
def reset_user_stats(user_id):
    with session() as s:
        user = s.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.like = False
        user.experience = 0
        user.level = 1
        return True

# Возвращает общее количество пользователей в БД
def get_total_users_count():
    with session() as s:
        return s.query(User).count()

# Возвращает количество онлайн-пользователей (статус 0, 1 или 2)
def get_online_users_count():
    with session() as s:
        return s.query(User).filter(User.status.in_([0, 1, 2])).count()

# Возвращает словарь с количеством пользователей по полу
def get_user_count_by_gender():
    with session() as s:
        return {
            'male': s.query(User).filter(User.gender == 'male').count(),
            'female': s.query(User).filter(User.gender == 'female').count(),
            'unknown': s.query(User).filter(User.gender == None).count()
        }

# Возвращает настройку фильтра поиска VIP-пользователя (any/male/female)
def get_vip_search_setting(user_id):
    return vip_search_settings.get(user_id, 'any')

# Сохраняет настройку фильтра поиска для VIP-пользователя
def set_vip_search_setting(user_id, gender):
    vip_search_settings[user_id] = gender

# Фильтрует список потенциальных собеседников по VIP-настройке пола
def filter_users_by_vip_setting(user_id, potential_matches):
    setting = get_vip_search_setting(user_id)
    if setting == 'any':
        return potential_matches
    return [mid for mid in potential_matches
            if free_users.get(mid, {}).get('gender') == setting]
