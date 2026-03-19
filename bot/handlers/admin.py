"""
handlers/admin.py — все административные команды.

ВАЖНО: все данные из объектов User извлекаются в примитивы (int/str)
ВНУТРИ блока with session(), чтобы избежать DetachedInstanceError.
"""
import sqlite3
import time
from telebot import types
from sqlalchemy import func
from bot.shared import bot, is_allowed, touch, ADMIN_ID, VIP_USERS
from database.dataEngine import session, MATCHING_PROBABILITIES
from database.models import User
from utils.admin_utils import add_vip, remove_vip, get_vip_status

def admin_only(fn):
    def wrapper(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "Access denied.")
            return
        fn(message)
    return wrapper

def _notify(user_id, text):
    try:
        bot.send_message(user_id, text)
    except Exception:
        pass


@bot.message_handler(commands=['adminhelp'])
@admin_only
def cmd_adminhelp(message):
    bot.send_message(message.chat.id,
        "Admin commands:\n\n"
        "/advert — broadcast to all users\n"
        "/setgender user_id male|female\n"
        "/getgender user_id\n"
        "/getuser user_id\n"
        "/findbygender male|female|null\n"
        "/setexp user_id value\n"
        "/addexp user_id amount\n"
        "/setlevel user_id level\n"
        "/setprob mm mf ff fm — probabilities (sum to 100)\n"
        "/vip_add user_id [days]\n"
        "/vip_list\n"
        "/vip_manual add/remove/status/list\n"
        "/stats\n"
        "/users [page] [gender] [status]\n"
    )


@bot.message_handler(commands=['advert'])
@admin_only
def cmd_advert(message):
    if not is_allowed(message.from_user.id): return
    touch(message.from_user.id)
    msg = bot.send_message(message.chat.id, "Enter broadcast text:")
    bot.register_next_step_handler(msg, _process_ad)

def _process_ad(message):
    with session() as s:
        user_ids = [u.id for u in s.query(User).all()]
    sent = 0
    text = message.text
    for uid in user_ids:
        try:
            bot.send_message(uid, f"Announcement:\n\n{text}")
            sent += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"Broadcast failed for {uid}: {e}")
    bot.send_message(message.chat.id, f"Sent to {sent}/{len(user_ids)} users.")


@bot.message_handler(commands=['setgender'])
@admin_only
def cmd_setgender(message):
    parts = message.text.split()
    if len(parts) != 3 or parts[2] not in ('male', 'female'):
        bot.send_message(message.chat.id, "Usage: /setgender user_id male|female")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "user_id must be a number.")
        return
    new_gender = parts[2]
    with session() as s:
        u = s.query(User).filter(User.id == uid).first()
        if not u:
            bot.send_message(message.chat.id, f"User {uid} not found.")
            return
        old_gender = u.gender
        u.gender = new_gender
    bot.send_message(message.chat.id, f"Gender changed: {old_gender} -> {new_gender}")
    _notify(uid, f"Admin changed your gender to: {new_gender}")


@bot.message_handler(commands=['getgender'])
@admin_only
def cmd_getgender(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Usage: /getgender user_id")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "user_id must be a number.")
        return
    with session() as s:
        u = s.query(User).filter(User.id == uid).first()
        if not u:
            bot.send_message(message.chat.id, f"User {uid} not found.")
            return
        username = u.username
        gender   = u.gender or 'not set'
        status   = u.status
        like     = u.like
    bot.send_message(message.chat.id,
        f"User {uid}\nUsername: @{username}\nGender: {gender}\n"
        f"Status: {status}\nLike: {like}")


@bot.message_handler(commands=['getuser'])
@admin_only
def cmd_getuser(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Usage: /getuser user_id")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "user_id must be a number.")
        return
    with session() as s:
        u = s.query(User).filter(User.id == uid).first()
        if not u:
            bot.send_message(message.chat.id, f"User {uid} not found.")
            return
        username = u.username
        gender   = u.gender or 'not set'
        status   = u.status
        like     = u.like
        exp      = u.experience or 0
        lvl      = u.level or 1
    bot.send_message(message.chat.id,
        f"ID: {uid}\nUsername: @{username}\nGender: {gender}\n"
        f"Status: {status}\nLike: {like}\n"
        f"Experience: {exp}\nLevel: {lvl}")


@bot.message_handler(commands=['findbygender'])
@admin_only
def cmd_findbygender(message):
    parts = message.text.split()
    if len(parts) != 2 or parts[1] not in ('male', 'female', 'null'):
        bot.send_message(message.chat.id, "Usage: /findbygender male|female|null")
        return
    gender = None if parts[1] == 'null' else parts[1]
    with session() as s:
        rows = [(u.id, u.username or 'anon') for u in s.query(User).filter(User.gender == gender).all()]
    if not rows:
        bot.send_message(message.chat.id, "No users found.")
        return
    lines = [f"{i+1}. ID:{uid} @{uname}" for i, (uid, uname) in enumerate(rows[:50])]
    extra = f"\n...and {len(rows)-50} more" if len(rows) > 50 else ""
    bot.send_message(message.chat.id, f"Users ({len(rows)}):\n\n" + "\n".join(lines) + extra)


@bot.message_handler(commands=['setexp'])
@admin_only
def cmd_setexp(message):
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "Usage: /setexp user_id value")
        return
    try:
        uid, exp = int(parts[1]), int(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, "user_id and value must be numbers.")
        return
    with session() as s:
        u = s.query(User).filter(User.id == uid).first()
        if not u:
            bot.send_message(message.chat.id, f"User {uid} not found.")
            return
        old = u.experience
        u.experience = exp
        u.level = exp // 100 + 1
    bot.send_message(message.chat.id, f"Experience: {old} -> {exp}")
    _notify(uid, f"Admin changed your experience: {old} -> {exp}")


@bot.message_handler(commands=['addexp'])
@admin_only
def cmd_addexp(message):
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "Usage: /addexp user_id amount")
        return
    try:
        uid, delta = int(parts[1]), int(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, "user_id and amount must be numbers.")
        return
    with session() as s:
        u = s.query(User).filter(User.id == uid).first()
        if not u:
            bot.send_message(message.chat.id, f"User {uid} not found.")
            return
        old = u.experience or 0
        u.experience = max(0, old + delta)
        u.level = u.experience // 100 + 1
        new = u.experience
    bot.send_message(message.chat.id, f"Experience: {old} -> {new} ({'+' if delta >= 0 else ''}{delta})")
    _notify(uid, f"Admin changed your experience: {old} -> {new}")


@bot.message_handler(commands=['setlevel'])
@admin_only
def cmd_setlevel(message):
    parts = message.text.split()
    try:
        uid, lvl = int(parts[1]), int(parts[2])
        if lvl < 1:
            raise ValueError
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "Usage: /setlevel user_id level\nLevel must be >= 1.")
        return
    with session() as s:
        u = s.query(User).filter(User.id == uid).first()
        if not u:
            bot.send_message(message.chat.id, f"User {uid} not found.")
            return
        old = u.level
        u.level = lvl
    bot.send_message(message.chat.id, f"Level: {old} -> {lvl}")
    _notify(uid, f"Admin changed your level: {old} -> {lvl}")


@bot.message_handler(commands=['setprob'])
@admin_only
def cmd_setprob(message):
    parts = message.text.split()
    if len(parts) != 5:
        bot.send_message(message.chat.id,
            "Usage: /setprob male_male male_female female_female female_male\n"
            "Example: /setprob 30 70 30 70")
        return
    try:
        mm, mf, ff, fm = [int(x) / 100 for x in parts[1:]]
    except ValueError:
        bot.send_message(message.chat.id, "All values must be integers.")
        return
    if abs(mm + mf - 1) > 0.01 or abs(ff + fm - 1) > 0.01:
        bot.send_message(message.chat.id, "Each pair must sum to 100%.")
        return
    MATCHING_PROBABILITIES['male']['male']     = mm
    MATCHING_PROBABILITIES['male']['female']   = mf
    MATCHING_PROBABILITIES['female']['female'] = ff
    MATCHING_PROBABILITIES['female']['male']   = fm
    bot.send_message(message.chat.id,
        f"Probabilities updated:\n"
        f"male+male: {mm*100:.0f}%\nmale+female: {mf*100:.0f}%\n"
        f"female+female: {ff*100:.0f}%\nfemale+male: {fm*100:.0f}%")


@bot.message_handler(commands=['stats'])
@admin_only
def cmd_stats(message):
    with session() as s:
        total   = s.query(User).count() or 1
        male    = s.query(User).filter(User.gender == 'male').count()
        female  = s.query(User).filter(User.gender == 'female').count()
        no_g    = s.query(User).filter(User.gender == None).count()
        s0      = s.query(User).filter(User.status == 0).count()
        s1      = s.query(User).filter(User.status == 1).count()
        s2      = s.query(User).filter(User.status == 2).count()
        s3      = s.query(User).filter(User.status == 3).count()
        liked   = s.query(User).filter(User.like == True).count()
        avg_exp = round(s.query(func.avg(User.experience)).scalar() or 0, 1)
        max_exp = s.query(func.max(User.experience)).scalar() or 0
        avg_lvl = round(s.query(func.avg(User.level)).scalar() or 0, 1)
        max_lvl = s.query(func.max(User.level)).scalar() or 0
    bot.send_message(message.chat.id,
        f"Bot statistics:\n\n"
        f"Total users: {total}\n"
        f"  Male:    {male} ({male/total*100:.1f}%)\n"
        f"  Female:  {female} ({female/total*100:.1f}%)\n"
        f"  Unknown: {no_g} ({no_g/total*100:.1f}%)\n\n"
        f"Free:     {s0}\nIn chat:  {s1}\nWaiting:  {s2}\nInactive: {s3}\n\n"
        f"With likes:    {liked}\nWithout likes: {total - liked}\n\n"
        f"Avg exp: {avg_exp}  Max exp: {max_exp}\n"
        f"Avg lvl: {avg_lvl}  Max lvl: {max_lvl}\n\n"
        f"Matching probabilities:\n"
        f"  male+male:     {MATCHING_PROBABILITIES['male']['male']*100:.0f}%\n"
        f"  male+female:   {MATCHING_PROBABILITIES['male']['female']*100:.0f}%\n"
        f"  female+female: {MATCHING_PROBABILITIES['female']['female']*100:.0f}%\n"
        f"  female+male:   {MATCHING_PROBABILITIES['female']['male']*100:.0f}%"
    )


@bot.message_handler(commands=['users'])
@admin_only
def cmd_users(message):
    if not is_allowed(message.from_user.id): return
    touch(message.from_user.id)
    parts    = message.text.split()
    page     = 1
    gender   = None
    status   = None
    per_page = 15

    for p in parts[1:]:
        if p.isdigit():
            val = int(p)
            if val in (0, 1, 2, 3) and status is None:
                status = val
            else:
                page = max(1, val)
        elif p.lower() in ('male', 'female', 'null'):
            gender = None if p.lower() == 'null' else p.lower()

    with session() as s:
        q = s.query(User)
        if gender is not None:
            q = q.filter(User.gender == gender)
        if status is not None:
            q = q.filter(User.status == status)
        total = q.count()
        pages = max(1, (total + per_page - 1) // per_page)
        page  = min(page, pages)
        # Извлекаем примитивы внутри сессии — не используем объекты User снаружи
        rows = [
            (u.id, u.username or 'anon', u.gender, u.level or 1, u.experience or 0)
            for u in q.order_by(User.id).offset((page - 1) * per_page).limit(per_page).all()
        ]

    if not rows:
        bot.send_message(message.chat.id, "No users found.")
        return

    lines = [f"Users (page {page}/{pages}, total {total}):\n"]
    for i, (uid, uname, ugender, ulvl, uexp) in enumerate(rows, start=1 + (page - 1) * per_page):
        g = {'male': 'M', 'female': 'F'}.get(ugender, '?')
        lines.append(f"{i}. [{g}] ID:{uid} @{uname} lvl:{ulvl} exp:{uexp}")

    nav = []
    if page > 1:     nav.append(f"/users {page-1}")
    if page < pages: nav.append(f"/users {page+1}")
    if nav:
        lines.append("Nav: " + " | ".join(nav))

    bot.send_message(message.chat.id, "\n".join(lines))


@bot.message_handler(commands=['vip_add'])
@admin_only
def cmd_vip_add(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: /vip_add user_id [days]\nExample: /vip_add 123456789 30")
        return
    try:
        uid  = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
    except ValueError:
        bot.send_message(message.chat.id, "Usage: /vip_add user_id [days]\nExample: /vip_add 123456789 30")
        return
    if add_vip(uid, days):
        if uid not in VIP_USERS:
            VIP_USERS.append(uid)
        bot.send_message(message.chat.id, f"User {uid} added to VIP for {days} days.")
        _notify(uid, f"You have been granted VIP access for {days} days.\nUse /vip to manage settings.")
    else:
        bot.send_message(message.chat.id, "Error adding VIP.")


@bot.message_handler(commands=['vip_list'])
@admin_only
def cmd_vip_list(message):
    if not VIP_USERS:
        bot.send_message(message.chat.id, "VIP list is empty.")
        return
    lines = ["VIP users:\n"]
    for i, uid in enumerate(VIP_USERS, 1):
        st     = get_vip_status(uid)
        active = st['in_db'] if st else False
        days   = st['db_info'].get('days_left', 0) if (st and st['in_db']) else 0
        lines.append(f"{i}. ID:{uid}  {'active' if active else 'inactive'}  days left: {days}")
    bot.send_message(message.chat.id, "\n".join(lines))


@bot.message_handler(commands=['vip_manual'])
@admin_only
def cmd_vip_manual(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id,
            "Usage:\n"
            "/vip_manual add user_id [days]\n"
            "/vip_manual remove user_id\n"
            "/vip_manual status user_id\n"
            "/vip_manual list")
        return

    action = parts[1].lower()

    if action == 'list':
        cmd_vip_list(message)
        return

    if len(parts) < 3:
        bot.send_message(message.chat.id, "Specify user_id.")
        return

    try:
        uid = int(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, "user_id must be a number.")
        return

    if action == 'add':
        try:
            days = int(parts[3]) if len(parts) > 3 else 30
        except ValueError:
            days = 30
        if add_vip(uid, days):
            if uid not in VIP_USERS:
                VIP_USERS.append(uid)
            bot.send_message(message.chat.id, f"User {uid} added to VIP for {days} days.")
            _notify(uid, f"VIP access granted for {days} days.")
        else:
            bot.send_message(message.chat.id, "Error.")

    elif action == 'remove':
        if remove_vip(uid):
            if uid in VIP_USERS:
                VIP_USERS.remove(uid)
            bot.send_message(message.chat.id, f"User {uid} removed from VIP.")
            _notify(uid, "Your VIP access has been revoked.")
        else:
            bot.send_message(message.chat.id, "Error.")

    elif action == 'status':
        st = get_vip_status(uid)
        if not st:
            bot.send_message(message.chat.id, "Error fetching status.")
            return
        info = (
            f"VIP status for {uid}:\n"
            f"  In config: {st['in_config']}\n"
            f"  In DB: {st['in_db']}\n"
            f"  Synchronized: {st['synchronized']}\n"
        )
        if st['in_db'] and st['db_info']:
            d = st['db_info']
            info += (
                f"  Plan: {d['plan_type']}\n"
                f"  Expires: {d['expiry_date'].strftime('%d.%m.%Y')}\n"
                f"  Days left: {d['days_left']}"
            )
        if not st['synchronized']:
            info += "\n\nWARNING: data is out of sync!"
        bot.send_message(message.chat.id, info)

    else:
        bot.send_message(message.chat.id, "Unknown action. Use: add / remove / status / list")
