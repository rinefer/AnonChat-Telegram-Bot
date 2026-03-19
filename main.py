import sqlite3
import time
import threading
import schedule
from datetime import datetime

from bot.shared import bot as tg_bot
from bot.crypto_payments import init_crypto_payment

import bot.handlers.admin   # noqa: F401 — команды администратора
import bot.handlers.chat    # noqa: F401 — /profile, /interests, /translate
import bot.handlers.vip     # noqa: F401 — /vip, /subscribe, платежи
import bot.handlers.start   # noqa: F401 — последним: relay перехватывает всё остальное

from database.dataEngine import session, recovery_data
from utils.interests import initialize_interests
import bot.handlers.vip as vip_module


# Проверяет все истёкшие подписки и деактивирует их; уведомляет пользователей
def check_expired_subscriptions():
    crypto = vip_module.crypto_payment
    if not crypto:
        return
    conn = sqlite3.connect('subscriptions.db')
    rows = conn.execute(
        'SELECT user_id FROM subscriptions WHERE expiry_date < ? AND is_active = 1',
        (datetime.now().isoformat(),)
    ).fetchall()
    for (user_id,) in rows:
        conn.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ?', (user_id,))
        crypto._update_vip_config(user_id, False)
        try:
            tg_bot.send_message(user_id,
                "Your VIP subscription has expired.\n"
                "Use /subscribe to renew.")
        except Exception:
            pass
    conn.commit()
    conn.close()


# Запускает планировщик проверки подписок каждый час в отдельном потоке
def run_scheduler():
    schedule.every(1).hours.do(check_expired_subscriptions)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    print('Bot starting...')

    crypto = init_crypto_payment(tg_bot)
    vip_module.crypto_payment = crypto

    with session() as s:
        initialize_interests(s)

    recovery_data()

    threading.Thread(target=run_scheduler, daemon=True).start()

    print('Bot is running.')
    tg_bot.polling(none_stop=True)
