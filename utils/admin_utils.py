import configparser
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

CONFIG_PATH = Path(__file__).parent.parent / 'config_files' / 'config.ini'
DB_PATH = 'subscriptions.db'

# Читает и возвращает текущий список VIP-пользователей из конфига
def _read_vip_list(config):
    raw = config['VIP'].get('vip_users', '')
    return [int(x.strip()) for x in raw.split(',') if x.strip()]

# Записывает обновлённый список VIP-пользователей в конфиг
def _write_vip_list(config, vip_list):
    config['VIP']['vip_users'] = ','.join(map(str, vip_list))
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)

# Добавляет пользователя в VIP: обновляет конфиг и активирует подписку в БД
def add_vip(user_id, days=30):
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        vip_list = _read_vip_list(config)
        if user_id not in vip_list:
            vip_list.append(user_id)
            _write_vip_list(config, vip_list)

        expiry = datetime.now() + timedelta(days=days)
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT OR REPLACE INTO subscriptions '
            '(user_id, plan_type, start_date, expiry_date, is_active, invoice_id) '
            'VALUES (?, ?, ?, ?, 1, "manual")',
            (user_id, 'manual', datetime.now().isoformat(), expiry.isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding VIP: {e}")
        return False

# Удаляет пользователя из VIP: обновляет конфиг и деактивирует подписку в БД
def remove_vip(user_id):
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        vip_list = _read_vip_list(config)
        if user_id in vip_list:
            vip_list.remove(user_id)
            _write_vip_list(config, vip_list)

        conn = sqlite3.connect(DB_PATH)
        conn.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error removing VIP: {e}")
        return False

# Возвращает словарь со статусом VIP пользователя из конфига и БД
def get_vip_status(user_id):
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        in_config = user_id in _read_vip_list(config)

        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            'SELECT plan_type, expiry_date, is_active FROM subscriptions WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        conn.close()

        db_info = {}
        in_db = False
        if row:
            plan_type, expiry_str, is_active = row
            in_db = bool(is_active)
            if in_db:
                expiry = datetime.fromisoformat(expiry_str)
                db_info = {
                    'plan_type': plan_type,
                    'expiry_date': expiry,
                    'days_left': max(0, (expiry - datetime.now()).days)
                }

        return {
            'user_id': user_id,
            'in_config': in_config,
            'in_db': in_db,
            'db_info': db_info,
            'synchronized': in_config == in_db
        }
    except Exception as e:
        print(f"Error getting VIP status: {e}")
        return None
