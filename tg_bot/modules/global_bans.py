import html
from io import BytesIO
from typing import Optional, List

from telegram import Message, Update, Bot, User, Chat, ParseMode, InlineKeyboardMarkup
from telegram.error import BadRequest, TelegramError
from telegram.ext import run_async, CommandHandler, MessageHandler, Filters
from telegram.utils.helpers import mention_html

import tg_bot.modules.sql.global_bans_sql as sql
from tg_bot import dispatcher, OWNER_ID, SUDO_USERS, SUPPORT_USERS, STRICT_GBAN
from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_admin
from tg_bot.modules.helper_funcs.extraction import extract_user, extract_user_and_text
from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.misc import send_to_list
from tg_bot.modules.sql.users_sql import get_all_chats

GBAN_ENFORCE_GROUP = 6

GBAN_ERRORS = {
    "Пользователь является администратором чата",
    "Чат не найден",
    "Недостаточно прав для ограничения/неограниченного участника чата",
    "Пользователь_не_участник",
    "Неверный_идентификатор_ИД",
    "Групповой чат деактивирован",
    "Нужно быть приглашенным пользователем, чтобы выбить его из базовой группы",
    "Требуется_админ_чата",
    "Только создатель базовой группы может пинать администраторов группы",
    "Приватный_канал",
    "Нет в чате",
    "Пользователь не найден"
}

UNGBAN_ERRORS = {
    "Пользователь является администратором чата",
    "Чат не найден",
    "Недостаточно прав для ограничения/неограниченного участника чата",
    "Пользователь_не_участник",
    "Метод доступен только для супергрупповых и канальных чатов",
    "Нет в чате",
    "Приватный_канал",
    "Chat_admin_required",
    "Требуется_админ_чата",
    "Пользователь не найден"
}


@run_async
def gban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Кажется, вы не обращаетесь к пользователю.")
        return

    if int(user_id) in SUDO_USERS:
        message.reply_text("Я шпионю своим маленьким глазом... война пользователей sudo! Почему вы, ребята, навечиваетесь друг на друга?")
        return

    if int(user_id) in SUPPORT_USERS:
        message.reply_text("ООХ, кто-то пытается выдать gban пользователя службы поддержки! *grabs popcorn*")
        return

    if user_id == bot.id:
        message.reply_text("-_- Так забавно, давайте забаним себя, почему бы и нет? Хорошая попытка.")
        return

    try:
        user_chat = bot.get_chat(user_id)
    except BadRequest as excp:
        message.reply_text(excp.message)
        return

    if user_chat.type != 'private':
        message.reply_text("Это не пользователь!")
        return

    if sql.is_user_gbanned(user_id):
        if not reason:
            message.reply_text("Этот пользователь уже gbanned; Я бы изменил причину, но вы не дали мне ни одной...")
            return

        old_reason = sql.update_gban_reason(user_id, user_chat.username or user_chat.first_name, reason)
        if old_reason:

            banner = update.effective_user  # type: Optional[User]
            send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                     "<b>Emendation of Global Ban</b>" \
                     "\n#GBAN" \
                     "\n<b>Статус:</b> <code>Amended</code>" \
                     "\n<b>Администратор:</b> {}" \
                     "\n<b>Пользователь:</b> {}" \
                     "\n<b>ID:</b> <code>{}</code>" \
                     "\n<b>Предыдущая Причина:</b> {}" \
                     "\n<b>Измененная Причина:</b> {}".format(mention_html(banner.id, banner.first_name),
                                              mention_html(user_chat.id, user_chat.first_name or "Deleted Account"),
                                                           user_chat.id, old_reason, reason),
                    html=True)

            message.reply_text("Этот пользователь уже зарегистрирован по следующей причине:\n"
                               "<code>{}</code>\n"
                               "Я пошел и обновил его с вашей новой причиной!".format(html.escape(old_reason)),
                               parse_mode=ParseMode.HTML)
        else:
            banner = update.effective_user  # type: Optional[User]
            send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                     "<b>Emendation of Global Ban</b>" \
                     "\n#GBAN" \
                     "\n<b>Статус:</b> <code>New reason</code>" \
                     "\n<b>Администратор:</b> {}" \
                     "\n<b>Пользователь:</b> {}" \
                     "\n<b>ID:</b> <code>{}</code>" \
                     "\n<b>Новая причина:</b> {}".format(mention_html(banner.id, banner.first_name or "Deleted Account"),
                                              mention_html(user_chat.id, user_chat.first_name),
                                                           user_chat.id, reason),
                    html=True)
            message.reply_text("Этот пользователь уже получил gban, но не имел причин для установки; Я пошел и обновил его!")

        return

    starting = "Инициирован глобальный запрет на: \nПользователь: {}\nПричина: {}".format(mention_html(user_chat.id, user_chat.first_name or "Удаленный аккаунт"), reason)
    keyboard = []
    message.reply_text(starting, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    banner = update.effective_user  # type: Optional[User]
    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                 "<b>Глобальный бан</b>" \
                 "\n#GBAN" \
                 "\n<b>Статус:</b> <code>Enforcing</code>" \
                 "\n<b>Администратор:</b> {}" \
                 "\n<b>Пользователь:</b> {}" \
                 "\n<b>ID:</b> <code>{}</code>" \
                 "\n<b>Причина:</b> {}".format(mention_html(banner.id, banner.first_name),
                                              mention_html(user_chat.id, user_chat.first_name or "Удаленный аккаунт"),  
                                                           user_chat.id, reason or "Причина не указана"), 
                html=True)

    sql.gban_user(user_id, user_chat.username or user_chat.first_name, reason)

    chats = get_all_chats()
    for chat in chats:
        chat_id = chat.chat_id

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            bot.kick_chat_member(chat_id, user_id)
        except BadRequest as excp:
            if excp.message in GBAN_ERRORS:
                pass
            else:
                message.reply_text("Не удалось выдать gban из-за: {}".format(excp.message))
                send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "Не удалось выдать gban из-за: {}".format(excp.message))
                sql.ungban_user(user_id)
                return
        except TelegramError:
            pass

    gban_complete="{} успешно выполнен gbanned :)\nПричина: {}".format(mention_html(user_chat.id, user_chat.first_name or "Удаленный аккаунт"), reason)
    keyboard = []
    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                   "{} успешно выполнен gbanned :)".format(mention_html(user_chat.id, user_chat.first_name or "Удаленный аккаунт")),
                   html=True)
    message.reply_text(gban_complete, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@run_async
def ungban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("Кажется, вы не обращаетесь к пользователю.")
        return

    user_chat = bot.get_chat(user_id)
    if user_chat.type != 'private':
        message.reply_text("Это не пользователь!")
        return

    if not sql.is_user_gbanned(user_id):
        message.reply_text("Этот пользователь не является gbanned!")
        return

    banner = update.effective_user  # type: Optional[User]

    message.reply_text("I'll give {} a second chance, globally.".format(user_chat.first_name))

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS,
                 "<b>Разбан на Глобальный бан</b>" \
                 "\n#UNGBAN" \
                 "\n<b>Статус:</b> <code>Ceased</code>" \
                 "\n<b>Администратор:</b> {}" \
                 "\n<b>Пользователь:</b> {}" \
                 "\n<b>ID:</b> <code>{}</code>".format(mention_html(banner.id, banner.first_name),
                                                       mention_html(user_chat.id, user_chat.first_name or "Удаленный аккаунт"), 
                                                                    user_chat.id),
                html=True)

    chats = get_all_chats()
    for chat in chats:
        chat_id = chat.chat_id

        # Check if this group has disabled gbans
        if not sql.does_chat_gban(chat_id):
            continue

        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status == 'kicked':
                bot.unban_chat_member(chat_id, user_id)

        except BadRequest as excp:
            if excp.message in UNGBAN_ERRORS:
                pass
            else:
                message.reply_text("Не удалось отменить gban из-за: {}".format(excp.message))
                bot.send_message(OWNER_ID, "Не удалось отменить gban из-за: {}".format(excp.message))
                return
        except TelegramError:
            pass

    sql.ungban_user(user_id)

    send_to_list(bot, SUDO_USERS + SUPPORT_USERS, "un-gban завершено!")

    message.reply_text("Человек был un-gbanned.")


@run_async
def gbanlist(bot: Bot, update: Update):
    banned_users = sql.get_gban_list()

    if not banned_users:
        update.effective_message.reply_text("Нет пользователей gbanned! Ты добрее, чем я ожидал...")
        return

    banfile = 'К черту этих парней.\n'
    for user in banned_users:
        banfile += "[x] {} - {}\n".format(user["name"], user["user_id"])
        if user["reason"]:
            banfile += "Причина: {}\n".format(user["reason"])

    with BytesIO(str.encode(banfile)) as output:
        output.name = "gbanlist.txt"
        update.effective_message.reply_document(document=output, filename="gbanlist.txt",
                                                caption="Вот список пользователей, которые в настоящее время находятся в списке gbanned.")


def check_and_ban(update, user_id, should_message=True):
    if sql.is_user_gbanned(user_id):
        update.effective_chat.kick_member(user_id)
        if should_message:
            update.effective_message.reply_text("Это плохой человек, его здесь быть не должно!")


@run_async
def enforce_gban(bot: Bot, update: Update):
    # Not using @restrict handler to avoid spamming - just ignore if cant gban.
    if sql.does_chat_gban(update.effective_chat.id) and update.effective_chat.get_member(bot.id).can_restrict_members:
        user = update.effective_user  # type: Optional[User]
        chat = update.effective_chat  # type: Optional[Chat]
        msg = update.effective_message  # type: Optional[Message]

        if user and not is_user_admin(chat, user.id):
            check_and_ban(update, user.id)

        if msg.new_chat_members:
            new_members = update.effective_message.new_chat_members
            for mem in new_members:
                check_and_ban(update, mem.id)

        if msg.reply_to_message:
            user = msg.reply_to_message.from_user  # type: Optional[User]
            if user and not is_user_admin(chat, user.id):
                check_and_ban(update, user.id, should_message=False)


@run_async
@user_admin
def gbanstat(bot: Bot, update: Update, args: List[str]):
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_gbans(update.effective_chat.id)
            update.effective_message.reply_text("Я включил gbans в этой группе. Это поможет защитить вас "
                                                "от спамеров, сомнительных персонажей и самых больших троллей.")
        elif args[0].lower() in ["off", "no"]:
            sql.disable_gbans(update.effective_chat.id)
            update.effective_message.reply_text("Я отключил gbans в этой группе. GBans не повлияет на ваших пользователей "
                                                "больше. Вы будете менее защищены от любых троллей и спамеров "
                                                "хотя!")
    else:
        update.effective_message.reply_text("Приведите несколько аргументов для выбора параметра! on/off, yes/no!\n\n"
                                            "Текущая настройка: {}\n"
                                            "Если значение true, любые gbans, которые произойдут, также произойдут в вашей группе.. "
                                            "Когда False, они этого не сделают, оставив вас на возможной милости "
                                            "spammers.".format(sql.does_chat_gban(update.effective_chat.id)))


def __stats__():
    return "{} gbanned users.".format(sql.num_gbanned_users())


def __user_info__(user_id):
    is_gbanned = sql.is_user_gbanned(user_id)

    text = "Глобально запрещено: <b>{}</b>"
    if is_gbanned:
        text = text.format("Yes")
        user = sql.get_gbanned_user(user_id)
        if user.reason:
            text += "\nReason: {}".format(html.escape(user.reason))
    else:
        text = text.format("No")
    return text


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    return "This chat is enforcing *gbans*: `{}`.".format(sql.does_chat_gban(chat_id))


__help__ = """
*Только для администраторов:*
 - /gbanstat <on/off/yes/no>: Отключит действие глобальных запретов на вашу группу или вернет ваши текущие настройки.

Gbans, также известные как глобальные запреты, используются владельцами ботов для блокировки спамеров во всех группах. Это помогает защитить \
вы и ваши группы, удаляя спам-флудеры как можно быстрее. Их можно отключить для группы, позвонив по телефону \
/gbanstat
"""

__mod_name__ = "Global Bans"

GBAN_HANDLER = CommandHandler("gban", gban, pass_args=True,
                              filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
UNGBAN_HANDLER = CommandHandler("ungban", ungban, pass_args=True,
                                filters=CustomFilters.sudo_filter | CustomFilters.support_filter)
GBAN_LIST = CommandHandler("gbanlist", gbanlist,
                           filters=CustomFilters.sudo_filter | CustomFilters.support_filter)

GBAN_STATUS = CommandHandler("gbanstat", gbanstat, pass_args=True, filters=Filters.group)

GBAN_ENFORCER = MessageHandler(Filters.all & Filters.group, enforce_gban)

dispatcher.add_handler(GBAN_HANDLER)
dispatcher.add_handler(UNGBAN_HANDLER)
dispatcher.add_handler(GBAN_LIST)
dispatcher.add_handler(GBAN_STATUS)

if STRICT_GBAN:  # enforce GBANS if this is set
    dispatcher.add_handler(GBAN_ENFORCER, GBAN_ENFORCE_GROUP)
