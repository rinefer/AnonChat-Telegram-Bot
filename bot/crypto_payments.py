import requests
import sqlite3
import json
import configparser
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / 'config_files' / 'config.ini'
DB_PATH = 'subscriptions.db'

SUBSCRIPTION_PLANS = {
    'monthly': {'price_usd': 0.1,   'duration_days': 30,  'name': 'Monthly subscription'},
    '3months': {'price_usd': 24.99, 'duration_days': 90,  'name': '3-month subscription'},
    'yearly':  {'price_usd': 79.99, 'duration_days': 365, 'name': 'Yearly subscription'},
}


class CryptoPaymentManager:
    def __init__(self, api_token, bot):
        self.api_token = api_token
        self.bot = bot
        self.base_url = "https://pay.crypt.bot/api"
        self.subscription_plans = SUBSCRIPTION_PLANS
        self._init_database()

    # Создаёт таблицу подписок в БД если она не существует
    def _init_database(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                plan_type TEXT,
                start_date TEXT,
                expiry_date TEXT,
                is_active INTEGER DEFAULT 1,
                invoice_id INTEGER
            )
        ''')
        conn.commit()
        conn.close()

    # Выполняет HTTP-запрос к CryptoBot API; возвращает result или None при ошибке
    def _request(self, method, endpoint, data=None):
        url = f"{self.base_url}/{endpoint}"
        headers = {"Crypto-Pay-API-Token": self.api_token, "Content-Type": "application/json"}
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, params=data)
            else:
                resp = requests.post(url, headers=headers, json=data)
            result = resp.json()
            return result.get('result') if result.get('ok') else None
        except Exception as e:
            print(f"API request error: {e}")
            return None

    # Создаёт счёт на оплату для указанного пользователя и тарифа; возвращает данные счёта или None
    def create_invoice(self, user_id, plan_type):
        plan = self.subscription_plans.get(plan_type)
        if not plan:
            return None

        result = self._request("POST", "createInvoice", {
            "asset": "USDT",
            "amount": str(plan['price_usd']),
            "description": f"VIP subscription: {plan['name']}",
            "hidden_message": f"user_id:{user_id}",
            "paid_btn_name": "openBot",
            "paid_btn_url": "https://t.me/shiftschatsbot",
            "payload": json.dumps({"type": "subscription", "user_id": user_id, "plan_type": plan_type}),
            "allow_comments": False,
            "expires_in": 3600
        })

        if result:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                'INSERT OR REPLACE INTO subscriptions (user_id, invoice_id, plan_type, is_active) VALUES (?, ?, ?, 0)',
                (user_id, result['invoice_id'], plan_type)
            )
            conn.commit()
            conn.close()

        return result

    # Проверяет статус оплаты счёта по его ID; возвращает строку статуса или None
    def check_payment_status(self, invoice_id):
        result = self._request("GET", "getInvoices", {"invoice_ids": invoice_id})
        if result and len(result) > 0:
            return result[0].get('status')
        return None

    # Активирует подписку пользователю: записывает в БД и добавляет в VIP-конфиг
    def activate_subscription(self, user_id, plan_type, invoice_id=None):
        plan = self.subscription_plans.get(plan_type)
        if not plan:
            return False

        expiry = datetime.now() + timedelta(days=plan['duration_days'])
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            'INSERT OR REPLACE INTO subscriptions '
            '(user_id, plan_type, start_date, expiry_date, is_active, invoice_id) VALUES (?, ?, ?, ?, 1, ?)',
            (user_id, plan_type, datetime.now().isoformat(), expiry.isoformat(), invoice_id)
        )
        conn.commit()
        conn.close()
        self._update_vip_config(user_id, True)
        return True

    # Обновляет список VIP-пользователей в конфигурационном файле
    def _update_vip_config(self, user_id, is_vip):
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_PATH)
            raw = config['VIP'].get('vip_users', '')
            vip_list = [int(x.strip()) for x in raw.split(',') if x.strip()]

            if is_vip and user_id not in vip_list:
                vip_list.append(user_id)
            elif not is_vip and user_id in vip_list:
                vip_list.remove(user_id)

            config['VIP']['vip_users'] = ','.join(map(str, vip_list))
            with open(CONFIG_PATH, 'w') as f:
                config.write(f)
            return True
        except Exception as e:
            print(f"Config update error: {e}")
            return False

    # Проверяет активность подписки; деактивирует и уведомляет пользователя если истекла
    def check_subscription(self, user_id):
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            'SELECT plan_type, expiry_date FROM subscriptions WHERE user_id = ? AND is_active = 1',
            (user_id,)
        ).fetchone()

        if not row:
            conn.close()
            return {'active': False}

        plan_type, expiry_str = row
        expiry = datetime.fromisoformat(expiry_str)

        if datetime.now() < expiry:
            conn.close()
            return {
                'active': True,
                'plan_type': plan_type,
                'expiry_date': expiry,
                'days_left': (expiry - datetime.now()).days
            }

        conn.execute('UPDATE subscriptions SET is_active = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        self._update_vip_config(user_id, False)

        try:
            self.bot.send_message(
                user_id,
                "Your VIP subscription has expired.\n"
                "Access to VIP features has been disabled.\n"
                "Use /subscribe to renew.",
                parse_mode='HTML'
            )
        except Exception:
            pass

        return {'active': False}

    # Создаёт Inline-клавиатуру с доступными тарифами подписки
    def get_subscription_plans_keyboard(self):
        from telebot import types
        markup = types.InlineKeyboardMarkup(row_width=1)
        for plan_type, info in self.subscription_plans.items():
            markup.add(types.InlineKeyboardButton(
                f"{info['name']} - ${info['price_usd']}",
                callback_data=f"subscribe_{plan_type}"
            ))
        markup.add(types.InlineKeyboardButton("Back", callback_data="subscription_back"))
        return markup

    # Обрабатывает входящий вебхук от CryptoBot; активирует подписку при успешной оплате
    def process_webhook(self, update):
        try:
            invoice = update.get('invoice')
            if invoice and invoice.get('status') == 'paid':
                payload = json.loads(invoice.get('payload', '{}'))
                if payload.get('type') == 'subscription':
                    user_id = payload['user_id']
                    plan_type = payload['plan_type']
                    invoice_id = invoice.get('invoice_id')
                    self.activate_subscription(user_id, plan_type, invoice_id)
                    try:
                        self.bot.send_message(
                            user_id,
                            "Payment confirmed! VIP subscription activated.\n\n"
                            "Features now available:\n"
                            "- Gender filter search\n"
                            "- Connection priority\n"
                            "- Faster matching\n"
                            "- Extended statistics\n\n"
                            "Use /vip to manage your settings.",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        print(f"Notification error: {e}")
                    return True
        except Exception as e:
            print(f"Webhook error: {e}")
        return False


# Инициализирует и возвращает экземпляр CryptoPaymentManager на основе конфига
def init_crypto_payment(bot):
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    api_token = config['CryptoBot']['api_token']
    return CryptoPaymentManager(api_token, bot)
