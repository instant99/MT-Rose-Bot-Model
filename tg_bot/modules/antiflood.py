import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, CommandHandler, run_async
from telegram.utils.helpers import mention_html

from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.sql import antiflood_sql as sql

FLOOD_GROUP = 3


@run_async
@loggable
def check_flood(bot: Bot, update: Update) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if not user:  # ignore channels
        return ""

    # ignore admins
    if is_user_admin(chat, user.id):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        chat.kick_member(user.id)
        msg.reply_text("ഫ്ലഡ് ചെയ്യുന്നോ... നിങ്ങൾക്കായി ഒരു കണ്ടം ഒരുക്കിയിട്ടുണ്ട്...  "
                       "ഒന്ന് ഓടിയിട്ട് വരൂ...")

        return "<b>{}:</b>" \
               "\n#Забанен" \
               "\n<b>Пользователь:</b> {}" \
               "\nFlooded the group.".format(html.escape(chat.title),
                                             mention_html(user.id, user.first_name))

    except BadRequest:
        msg.reply_text("Я не могу кикать людей здесь, сначала дайте мне разрешения! Я отключу antiflood.")
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#Инфо" \
               "\nУ вас нет разрешений на кик, поэтому автоматически отключен antiflood.".format(chat.title)


@run_async
@user_admin
@can_restrict
@loggable
def set_flood(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat.id, 0)
            message.reply_text("Антифлуд был выключен.")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat.id, 0)
                message.reply_text("Антифлуд был выключен.")
                return "<b>{}:</b>" \
                       "\n#Настройка Антифлуда" \
                       "\n<b>Администратор:</b> {}" \
                       "\nDisabled antiflood.".format(html.escape(chat.title), mention_html(user.id, user.first_name))

            elif amount < 3:
                message.reply_text("Antiflood должен быть либо 0 (отключен), либо число больше 3 (включен)!")
                return ""

            else:
                sql.set_flood(chat.id, amount)
                message.reply_text("Антифлуд был установлен на {}".format(amount))
                return "<b>{}:</b>" \
                       "\n#Настройка Антифлуда" \
                       "\n<b>Администратор:</b> {}" \
                       "\nУстановил защиту от флуда <code>{}</code>.".format(html.escape(chat.title),
                                                                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text("Неизвестный аргумент - используйте число, 'off', или 'no'.")

    return ""


@run_async
def flood(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    limit = sql.get_flood_limit(chat.id)
    if limit == 0:
        update.effective_message.reply_text("В настоящее время я не применяю контроль над флудом!")
    else:
        update.effective_message.reply_text(
            "В настоящее время я баню пользователей, если они отправляют более {} последовательных сообщений.".format(limit))


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "В настоящее время я не применяю контроль над флудом!."
    else:
        return "Антифлуд настроен на `{}` сообщение.".format(limit)


__help__ = """
 - /flood: Получить текущие настройки антифлуда.

*Admin only:*
 - /setflood <число/'no'/'off'>:  Включить или выключить антифлуд защиту.
"""

__mod_name__ = "AntiFlood"

FLOOD_BAN_HANDLER = MessageHandler(Filters.all & ~Filters.status_update & Filters.group, check_flood)
SET_FLOOD_HANDLER = CommandHandler("setflood", set_flood, pass_args=True, filters=Filters.group)
FLOOD_HANDLER = CommandHandler("flood", flood, filters=Filters.group)

dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(SET_FLOOD_HANDLER)
dispatcher.add_handler(FLOOD_HANDLER)

