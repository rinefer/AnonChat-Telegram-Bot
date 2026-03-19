LEVEL_CONFIG = {
    'base_xp': 1000,
    'xp_multiplier': 2.0,
    'max_level': 50
}

LEVEL_REWARDS = {
    5:  "Exclusive profile color",
    10: "Gold profile frame",
    15: "Priority in search",
    20: "Animated profile icon",
    25: "Special profile status",
    30: "Exclusive conversation topics",
    35: "Unique achievements",
    40: "Personal chat assistant",
    45: "Legendary status",
    50: "Master of Chat title"
}

XP_REWARDS = {
    'chat_started':   50,
    'chat_per_minute': 2,
    'like_given':     25,
    'like_received':  35,
    'message_100':    10,
    'achievement':   100,
    'daily_login':    20
}

# Вычисляет необходимое количество XP для достижения указанного уровня
def xp_for_level(level):
    if level == 1:
        return LEVEL_CONFIG['base_xp']
    return int(LEVEL_CONFIG['base_xp'] * (LEVEL_CONFIG['xp_multiplier'] ** (level - 1)) + level * 500)

# Добавляет XP пользователю, повышает уровень если накоплено достаточно; возвращает (количество_уровней, новый_уровень)
def add_xp(session, user_id, xp_amount):
    from database.models import UserStats
    stats = session.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not stats:
        stats = UserStats(user_id=user_id)
        session.add(stats)

    stats.xp += xp_amount
    levels_gained = 0
    max_level = LEVEL_CONFIG['max_level']

    while stats.level < max_level and stats.xp >= xp_for_level(stats.level):
        stats.xp -= xp_for_level(stats.level)
        stats.level += 1
        levels_gained += 1

    session.commit()
    return levels_gained, stats.level

# Возвращает прогресс текущего уровня: (текущий_xp, нужно_xp, процент)
def get_level_progress(stats):
    needed = xp_for_level(stats.level)
    progress = (stats.xp / needed * 100) if needed else 100
    return stats.xp, needed, progress

# Возвращает полный информационный словарь об уровне пользователя
def get_level_info(stats):
    current_xp, xp_needed, progress = get_level_progress(stats)
    xp_remaining = xp_needed - current_xp
    days_to_level = max(1, xp_remaining // 100)
    total_xp = sum(xp_for_level(lvl) for lvl in range(1, stats.level)) + current_xp

    return {
        'current_level': stats.level,
        'current_xp': current_xp,
        'xp_needed': xp_needed,
        'progress': progress,
        'xp_remaining': xp_remaining,
        'days_to_level': days_to_level,
        'total_xp': total_xp
    }
