# Системные сообщения бота

m_is_not_free_users = (
    'Sorry, no free users at the moment. '
    'We will connect you as soon as another user appears!'
)

m_is_connect = (
    "Connected!\n"
    "You are now chatting with an anonymous user.\n"
    "Say hello!\n\n"
    "If you enjoy the chat, press Like.\n"
    "With mutual interest you will learn each other's username."
)

m_play_again = 'Would you like to chat with someone else?'

m_is_not_user_name = 'Sorry, you need a Telegram username to use this bot.'

m_good_bye = 'Goodbye, hope to see you again!'

m_disconnect_user = 'Your chat partner has disconnected.'

m_failed = 'Something went wrong!'

m_like = 'Good choice!'

m_dislike_user = 'Chat ended.'

m_dislike_user_to = 'Your partner ended the chat.'

m_send_some_messages = 'You cannot forward your own messages.'

m_has_not_dialog = 'You are not in a chat.'

dislike_str = 'Dislike'
like_str    = 'Like'

m_interests_help = (
    "Interests system\n\n"
    "Choose your hobbies and we will find partners with similar interests!\n\n"
    "Use /interests to configure your preferences."
)

m_no_interests = (
    "No interests set.\n\n"
    "Set your preferences first using /interests."
)

m_interests_saved = "Your interests have been saved!"

m_interests_selection = (
    "Choose your interests:\n\n"
    "Tap an interest to select or deselect it.\n"
    "Press 'Done' when finished."
)

m_no_interests_selected = "No interests selected. Use /interests later to configure them."

# Сообщение о взаимном лайке — принимает username партнера
def m_all_like(username):
    return f"You liked each other!\nPartner login: {username}\nGood luck and enjoy chatting!"

# Сообщение об общих интересах — принимает список строк
def m_common_interests(interests_list):
    if not interests_list:
        return "No common interests found."
    return "Common interests:\n" + "\n".join(interests_list)
