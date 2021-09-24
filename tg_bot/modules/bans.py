import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import run_async, CommandHandler, Filters
from telegram.utils.helpers import mention_html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery

from tg_bot import dispatcher, BAN_STICKER, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_ban_protected, can_restrict, \
    is_user_admin, is_user_in_chat, is_bot_admin
from tg_bot.modules.helper_funcs.extraction import extract_user_and_text
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.helper_funcs.filters import CustomFilters

RBAN_ERRORS = {
    "Пользователь является администратором чата",
    "Чат не найден",
    "Недостаточно прав для ограничения/неограниченного участника чата",
    "Пользователь_не_участник",
    "Peer_id_invalid",
    "Групповой чат деактивирован",
    "Нужно быть приглашенным пользователем, чтобы выбить его из базовой группы",
    "Требуется_админ_чата",
    "Только создатель базовой группы может пинать администраторов группы",
    "Channel_private",
    "Нет в чате"
}

RUNBAN_ERRORS = {
    "Пользователь является администратором чата",
    "Чат не найден",
    "Недостаточно прав для ограничения/неограниченного участника чата",
    "User_not_participant",
    "Peer_id_invalid",
    "Групповой чат был деактивирован",
    "Нужно быть приглашенным пользователем, чтобы выбить его из базовой группы",
    "Требуется_админ_чата",
    "Только создатель базовой группы может пинать администраторов группы",
    "Приватный_канал",
    "Нет в чате"
}



@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Кажется, вы не обращаетесь к пользователю..")
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Пользователь не найден":
            message.reply_text("Я не могу найти этого пользователя")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Мне так жаль, что я не могу забанить админа...")
        return ""

    if user_id == bot.id:
        message.reply_text("Я не собираюсь банить себя, ты с ума сошел?")
        return ""

    log = "<b>{}:</b>" \
          "\n#Забанен" \
          "\n<b>Администратор:</b> {}" \
          "\n<b>Пользователь:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Причина:</b> {}".format(reason)

    try:
        chat.kick_member(user_id)
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = []
        reply = "{} ന് ബണ്ണ് കൊടുത്തു വിട്ടിട്ടുണ്ട് !".format(mention_html(member.user.id, member.user.first_name))
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return log

    except BadRequest as excp:
        if excp.message == "Ответ на сообщение не найден":
            chat_id = update.effective_chat.id
            message = update.effective_message
            # Do not reply
            reply = "{} ന് ബണ്ണ് കൊടുത്തു വിട്ടിട്ടുണ്ട് !".format(mention_html(member.user.id, member.user.first_name))
            bot.send_message(chat_id, reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
#           message.reply_text('Забанен!', quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ОШИБКА блокировки пользователя %s в чате %s (%s) по причине %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Черт, я не могу запретить этого пользователя.")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def temp_ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Кажется, вы не обращаетесь к пользователю.")
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Пользователь не найден":
            message.reply_text("Я не могу найти этого пользователя")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Мне так жаль, что я не могу забанить админа...")
        return ""

    if user_id == bot.id:
        message.reply_text("Я не собираюсь банить себя, ты с ума сошел?")
        return ""

    if not reason:
        message.reply_text("Вы не указали время, чтобы забанить этого пользователя!")
        return ""

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    if len(split_reason) > 1:
        reason = split_reason[1]
    else:
        reason = ""

    bantime = extract_time(message, time_val)

    if not bantime:
        return ""

    log = "<b>{}:</b>" \
          "\n#Временный бан" \
          "\n<b>Администратор:</b> {}" \
          "\n<b>Пользователь:</b> {}" \
          "\n<b>Time:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name), time_val)
    if reason:
        log += "\n<b>Причина:</b> {}".format(reason)

    try:
        chat.kick_member(user_id, until_date=bantime)
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Забанен! Пользователь забанен на {}.".format(time_val))
        return log

    except BadRequest as excp:
        if excp.message == "Ответ на сообщение не найден":
            # Do not reply
            message.reply_text("Забанен! Пользователь забанен на {}.".format(time_val), quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ОШИБКА блокировки пользователя %s в чате %s (%s) по причине %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Черт, я не могу запретить этого пользователя.")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def kick(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Пользователь не найден":
            message.reply_text("Я не могу найти этого пользователя")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id):
        message.reply_text("Я действительно хотел бы пинать админов...")
        return ""

    if user_id == bot.id:
        message.reply_text("Да, я не собираюсь этого делать")
        return ""

    res = chat.unban_member(user_id)  # unban on current user = kick
    if res:
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Kicked!")
        log = "<b>{}:</b>" \
              "\n#KICKED" \
              "\n<b>Администратор:</b> {}" \
              "\n<b>Пользователь:</b> {}".format(html.escape(chat.title),
                                         mention_html(user.id, user.first_name),
                                         mention_html(member.user.id, member.user.first_name))
        if reason:
            log += "\n<b>Причина:</b> {}".format(reason)

        return log

    else:
        message.reply_text("Черт, я не могу кикнуть этого пользователя.")

    return ""


@run_async
@bot_admin
@can_restrict
def kickme(bot: Bot, update: Update):
    user_id = update.effective_message.from_user.id
    if is_user_admin(update.effective_chat, user_id):
        update.effective_message.reply_text("Жаль, что я не могу... но вы администратор.")
        return

    res = update.effective_chat.unban_member(user_id)  # unban on current user = kick
    if res:
        update.effective_message.reply_text("Нет проблем.")
    else:
        update.effective_message.reply_text("Да? Не могу :/")


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def unban(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Пользователь не найден":
            message.reply_text("Я не могу найти этого пользователя")
            return ""
        else:
            raise

    if user_id == bot.id:
        message.reply_text("Как бы я разблокировал себя, если бы меня здесь не было...?")
        return ""

    if is_user_in_chat(chat, user_id):
        message.reply_text("Почему вы пытаетесь разблокировать кого-то, кто уже находится в чате?")
        return ""

    chat.unban_member(user_id)
    message.reply_text("Да, этот пользователь может присоединиться!")

    log = "<b>{}:</b>" \
          "\n#UNBANNED" \
          "\n<b>Администратор:</b> {}" \
          "\n<b>Пользователь:</b> {}".format(html.escape(chat.title),
                                     mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Причина:</b> {}".format(reason)

    return log


@run_async
@bot_admin
def rban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message

    if not args:
        message.reply_text("Кажется, вы не обращаетесь к чату/пользователю.")
        return

    user_id, chat_id = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Кажется, вы не обращаетесь к пользователю.")
        return
    elif not chat_id:
        message.reply_text("Кажется, вы не обращаетесь к чату.")
        return

    try:
        chat = bot.get_chat(chat_id.split()[0])
    except BadRequest as excp:
        if excp.message == "Чат не найден":
            message.reply_text("Чат не найден! Убедитесь, что вы ввели действительный идентификатор чата, и я являюсь частью этого чата.")
            return
        else:
            raise

    if chat.type == 'private':
        message.reply_text("Извините, но это приватный чат!")
        return

    if not is_bot_admin(chat, bot.id) or not chat.get_member(bot.id).can_restrict_members:
        message.reply_text("Я не могу ограничивать людей там! Убедитесь, что я администратор и могу забанить пользователей.")
        return

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Пользователь не найден":
            message.reply_text("Я не могу найти этого пользователя")
            return
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Мне так жаль, что я не могу забанить админа...")
        return

    if user_id == bot.id:
        message.reply_text("Я не собираюсь банить себя, ты с ума сошел?")
        return

    try:
        chat.kick_member(user_id)
        message.reply_text("Забанен!")
    except BadRequest as excp:
        if excp.message == "Ответ на сообщение не найден":
            # Do not reply
            message.reply_text('Забанен!', quote=False)
        elif excp.message in RBAN_ERRORS:
            message.reply_text(excp.message)
        else:
            LOGGER.warning(update)
            LOGGER.exception("ОШИБКА блокировки пользователя %s в чате %s (%s) благодаря %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Черт, я не могу запретить этого пользователя.")

@run_async
@bot_admin
def runban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message

    if not args:
        message.reply_text("Кажется, вы не обращаетесь к чату/пользователю.")
        return

    user_id, chat_id = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Кажется, вы не обращаетесь к пользователю.")
        return
    elif not chat_id:
        message.reply_text("Кажется, вы не обращаетесь к чату.")
        return

    try:
        chat = bot.get_chat(chat_id.split()[0])
    except BadRequest as excp:
        if excp.message == "Чат не найден":
            message.reply_text("Чат не найден! Убедитесь, что вы ввели действительный идентификатор чата, и я являюсь частью этого чата.")
            return
        else:
            raise

    if chat.type == 'private':
        message.reply_text("Извините, но это приватный чат!")
        return

    if not is_bot_admin(chat, bot.id) or not chat.get_member(bot.id).can_restrict_members:
        message.reply_text("Я не могу без ограничений людей там! Убедитесь, что я администратор и могу разблокить пользователей.")
        return

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "Пользователь не найден":
            message.reply_text("Я не могу найти этого пользователя здесь")
            return
        else:
            raise
            
    if is_user_in_chat(chat, user_id):
        message.reply_text("Почему вы пытаетесь удаленно разблокировать кого-то, кто уже находится в этом чате?")
        return

    if user_id == bot.id:
        message.reply_text("Я не собираюсь РАЗБАНИВАТЬ себя, я здесь администратор!")
        return

    try:
        chat.unban_member(user_id)
        message.reply_text("Да, этот пользователь может присоединиться к этому чату!")
    except BadRequest as excp:
        if excp.message == "Ответ на сообщение не найден":
            # Do not reply
            message.reply_text('Разбанен!', quote=False)
        elif excp.message in RUNBAN_ERRORS:
            message.reply_text(excp.message)
        else:
            LOGGER.warning(update)
            LOGGER.exception("ОШИБКА разбана пользователя %s в чате %s (%s) по причине %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Черт возьми, я не могу разбанить этого пользователя.")


__help__ = """
 - /kickme: Удаляет пользователя написавшего это из группы. 

*Только администраторам*
 - /ban <ник>: Забанить пользователя. (вручную, или с помощью ответа)
 - /tban <ник> (m/h/d): Забанить пользователя на X время. (вручную, или с помощью ответа). m = минуты, h = часы  d = days.
 - /unban <ник> Разбанить пользователя. (вручную, или с помощью ответа)
 - /kick <ник>:  Удалить пользователя из группы, (вручную, или с помощью ответа)
"""s

__mod_name__ = "Bans"

BAN_HANDLER = CommandHandler("ban", ban, pass_args=True, filters=Filters.group)
TEMPBAN_HANDLER = CommandHandler(["tban", "tempban"], temp_ban, pass_args=True, filters=Filters.group)
KICK_HANDLER = CommandHandler("kick", kick, pass_args=True, filters=Filters.group)
UNBAN_HANDLER = CommandHandler("unban", unban, pass_args=True, filters=Filters.group)
KICKME_HANDLER = DisableAbleCommandHandler("kickme", kickme, filters=Filters.group)
RBAN_HANDLER = CommandHandler("rban", rban, pass_args=True, filters=CustomFilters.sudo_filter)
RUNBAN_HANDLER = CommandHandler("runban", runban, pass_args=True, filters=CustomFilters.sudo_filter)

dispatcher.add_handler(BAN_HANDLER)
dispatcher.add_handler(TEMPBAN_HANDLER)
dispatcher.add_handler(KICK_HANDLER)
dispatcher.add_handler(UNBAN_HANDLER)
dispatcher.add_handler(KICKME_HANDLER)
dispatcher.add_handler(RBAN_HANDLER)
dispatcher.add_handler(RUNBAN_HANDLER)
