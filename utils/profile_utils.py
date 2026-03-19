import math

# Строит текстовый прогресс-бар заданной длины на основе процента прогресса
def create_progress_bar(progress, length=20):
    filled = math.floor(progress * length / 100)
    return "x" * filled + "." * (length - filled)

# Форматирует большое число XP в читаемый вид (K, M)
def format_xp(xp):
    if xp >= 1_000_000:
        return f"{xp / 1_000_000:.1f}M"
    if xp >= 1_000:
        return f"{xp / 1_000:.1f}K"
    return str(xp)

# Возвращает звание игрока по его уровню
def get_rank_title(level):
    ranks = [
        (1,  5,  "Novice"),
        (6,  10, "Apprentice"),
        (11, 15, "Experienced"),
        (16, 20, "Expert"),
        (21, 25, "Master"),
        (26, 30, "Guru"),
        (31, 35, "Legend"),
        (36, 40, "Myth"),
        (41, 45, "Deity"),
        (46, 50, "Creator"),
    ]
    for lo, hi, title in ranks:
        if lo <= level <= hi:
            return title
    return "Traveler"

# Возвращает символ статуса пользователя по его числовому коду
def get_status_symbol(status):
    return {0: "[free]", 1: "[chat]", 2: "[wait]", 3: "[off]"}.get(status, "[?]")
