import sqlite3
from bot.shared import bot, is_allowed, touch, vip_keyboard, is_vip
from database.dataEngine import get_vip_search_setting, set_vip_search_setting

# Глобальная ссылка на объект оплаты — инициализируется в main.py
crypto_payment = None

GENDER_LABEL = {'any': 'Any gender', 'male': 'Guys only', 'female': 'Girls only'}


@bot.message_handler(commands=['vip'])
def cmd_vip(message):
    user_id = message.chat.id
    if not is_vip(user_id, crypto_payment):
        bot.send_message(user_id, "This feature is available for VIP users only. Use /subscribe.")
        return
    if not is_allowed(user_id): return
    touch(user_id)

    setting = get_vip_search_setting(user_id)
    text = (
        f"VIP Panel\n\n"
        f"Current search setting: {GENDER_LABEL.get(setting, 'Any')}\n\n"
        f"Available features:\n"
        f"- Gender filter search\n"
        f"- Connection priority\n"
        f"- Faster matching\n\n"
        f"Use the buttons below to manage settings:"
    )
    try:
        with open('vip_panel.jpg', 'rb') as photo:
            bot.send_photo(user_id, photo, caption=text, reply_markup=vip_keyboard())
    except FileNotFoundError:
        bot.send_message(user_id, text, reply_markup=vip_keyboard())


@bot.message_handler(commands=['subscribe'])
def cmd_subscribe(message):
    user_id = message.chat.id
    if not is_allowed(user_id): return
    touch(user_id)

    info = crypto_payment.check_subscription(user_id)
    if info['active']:
        plan_type = info['plan_type']
        plan_name = crypto_payment.subscription_plans.get(plan_type, {}).get('name', plan_type.capitalize())
        bot.send_message(user_id,
            f"You have an active subscription!\n\n"
            f"Plan: {plan_name}\nDays left: {info['days_left']}\n\n"
            f"You can select a new plan below to extend:",
            reply_markup=crypto_payment.get_subscription_plans_keyboard()
        )
    else:
        bot.send_message(user_id,
            "VIP Subscription\n\n"
            "Benefits:\n"
            "- Gender filter search\n"
            "- Connection priority\n"
            "- Faster matching\n"
            "- Extended statistics\n\n"
            "Choose a plan:",
            reply_markup=crypto_payment.get_subscription_plans_keyboard()
        )


@bot.message_handler(commands=['mysubscription'])
def cmd_mysubscription(message):
    user_id = message.chat.id
    if not is_allowed(user_id): return
    touch(user_id)
    info = crypto_payment.check_subscription(user_id)
    if info['active']:
        plan_type = info['plan_type']
        plan_name = crypto_payment.subscription_plans.get(plan_type, {}).get('name', plan_type.capitalize())
        expiry    = info['expiry_date'].strftime("%d.%m.%Y %H:%M")
        bot.send_message(user_id,
            f"Subscription info:\n\nPlan: {plan_name}\nActive: yes\n"
            f"Expires: {expiry}\nDays left: {info['days_left']}\n\n"
            f"To renew use /subscribe")
    else:
        bot.send_message(user_id,
            "No active subscription.\n\n"
            "Use /subscribe to get VIP access.")


@bot.message_handler(commands=['vip_any', 'vip_male', 'vip_female'])
def cmd_quick_vip(message):
    user_id = message.chat.id
    if not is_vip(user_id, crypto_payment):
        bot.send_message(user_id, "VIP only.")
        return
    cmd = message.text.split()[0]
    search_type = {'vip_any': 'any', '/vip_any': 'any',
                   'vip_male': 'male', '/vip_male': 'male',
                   'vip_female': 'female', '/vip_female': 'female'}.get(cmd, 'any')
    set_vip_search_setting(user_id, search_type)
    bot.send_message(user_id,
        f"VIP setting updated.\nNow searching: {GENDER_LABEL.get(search_type)}\n\nUse /vip for full panel.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('vip_search_'))
def cb_vip_search(call):
    user_id = call.message.chat.id
    if not is_vip(user_id, crypto_payment):
        bot.answer_callback_query(call.id, "Access denied.")
        return
    search_type = call.data.split('_')[2]
    set_vip_search_setting(user_id, search_type)
    label = GENDER_LABEL.get(search_type, 'Any')
    text = (
        f"VIP Panel\n\nSetting updated!\n"
        f"Now searching: {label}\n\n"
        f"Use the buttons to change:"
    )
    # Пробуем edit_message_caption (если сообщение с фото),
    # затем edit_message_text (если текстовое).
    # В обоих случаях игнорируем "message is not modified".
    edited = False
    try:
        bot.edit_message_caption(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  caption=text, reply_markup=vip_keyboard())
        edited = True
    except Exception:
        pass
    if not edited:
        try:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                   message_id=call.message.message_id,
                                   text=text, reply_markup=vip_keyboard())
        except Exception:
            pass
    bot.answer_callback_query(call.id, f"Saved: {label}")


@bot.callback_query_handler(func=lambda call: call.data == 'vip_info')
def cb_vip_info(call):
    if not is_vip(call.message.chat.id, crypto_payment):
        bot.answer_callback_query(call.id, "Access denied.")
        return
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,
        "VIP Features:\n\n"
        "Gender filter search:\n"
        "  - Any gender: default search\n"
        "  - Guys only: search male users\n"
        "  - Girls only: search female users\n\n"
        "Other benefits:\n"
        "  - Priority in match queue\n"
        "  - Faster connection\n"
        "  - Extended statistics"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('subscribe_'))
def cb_subscribe(call):
    user_id   = call.message.chat.id
    plan_type = call.data.split('_')[1]
    if plan_type not in crypto_payment.subscription_plans:
        bot.answer_callback_query(call.id, "Invalid plan.")
        return
    plan    = crypto_payment.subscription_plans[plan_type]
    invoice = crypto_payment.create_invoice(user_id, plan_type)
    if not invoice:
        bot.answer_callback_query(call.id, "Error creating invoice.")
        return
    pay_url    = invoice.get('pay_url')
    invoice_id = invoice.get('invoice_id')
    if not pay_url:
        bot.answer_callback_query(call.id, "Error getting payment link.")
        return

    from telebot import types as tbtypes
    markup = tbtypes.InlineKeyboardMarkup()
    markup.add(tbtypes.InlineKeyboardButton("Pay", url=pay_url))
    markup.add(tbtypes.InlineKeyboardButton("Check payment", callback_data=f"check_payment_{invoice_id}"))
    markup.add(tbtypes.InlineKeyboardButton("Back", callback_data="subscription_back"))

    text = (
        f"Payment\n\nPlan: {plan['name']}\n"
        f"Price: ${plan['price_usd']}\nDuration: {plan['duration_days']} days\n\n"
        f"Pay via link:\n{pay_url}\n\n"
        f"Subscription activates within 1-2 minutes after payment."
    )
    try:
        bot.edit_message_text(chat_id=call.message.chat.id,
                               message_id=call.message.message_id,
                               text=text, reply_markup=markup)
    except Exception:
        bot.send_message(user_id, text, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment_'))
def cb_check_payment(call):
    user_id = call.message.chat.id
    try:
        invoice_id = int(call.data.split('_')[2])
    except (IndexError, ValueError):
        bot.answer_callback_query(call.id, "Error.")
        return

    status = crypto_payment.check_payment_status(invoice_id)
    if status == 'paid':
        conn = sqlite3.connect('subscriptions.db')
        row  = conn.execute('SELECT plan_type FROM subscriptions WHERE invoice_id = ?', (invoice_id,)).fetchone()
        conn.close()
        plan_type = row[0] if row else 'monthly'
        if crypto_payment.activate_subscription(user_id, plan_type, invoice_id):
            bot.answer_callback_query(call.id, "Payment confirmed! Subscription activated.")
            msg = ("Payment confirmed! VIP subscription activated.\n\n"
                   "Features unlocked:\n- Gender filter search\n- Priority matching\n"
                   "- Faster search\n- Extended statistics\n\nUse /vip to manage settings.")
            try:
                bot.edit_message_text(chat_id=call.message.chat.id,
                                       message_id=call.message.message_id, text=msg)
            except Exception:
                bot.send_message(user_id, msg)
        else:
            bot.answer_callback_query(call.id, "Activation error.")
    elif status == 'active':
        bot.answer_callback_query(call.id, "Invoice awaiting payment.")
    else:
        bot.answer_callback_query(call.id, "Payment not found.")


@bot.callback_query_handler(func=lambda call: call.data == 'subscription_back')
def cb_subscription_back(call):
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "VIP Subscription\n\n"
                "Benefits:\n- Gender filter search\n- Connection priority\n"
                "- Faster matching\n- Extended statistics\n\nChoose a plan:"
            ),
            reply_markup=crypto_payment.get_subscription_plans_keyboard()
        )
    except Exception:
        # Сообщение уже содержит тот же текст — игнорируем
        pass
    bot.answer_callback_query(call.id)
