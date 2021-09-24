import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram import ParseMode
from telegram.error import BadRequest
from telegram.ext import CommandHandler, Filters, RegexHandler
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import escape_markdown, mention_html

from tg_bot import dispatcher
import tg_bot.modules.sql.setlink_sql as sql
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import bot_admin, can_promote, user_admin, can_pin
from tg_bot.modules.helper_funcs.extraction import extract_user
from tg_bot.modules.helper_funcs.string_handling import markdown_parser
from tg_bot.modules.log_channel import loggable


@run_async
@bot_admin
@can_promote
@user_admin
@loggable
def promote(bot: Bot, update: Update, args: List[str]) -> str:
    chat_id = update.effective_chat.id
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("Похоже, вы не ссылаетесь на пользователя.")
        return ""

    user_member = chat.get_member(user_id)
    if user_member.status == 'administrator' or user_member.status == 'creator':
        message.reply_text("Как я должен повышать кого-то, кто уже является администратором?")
        return ""

    if user_id == bot.id:
        message.reply_text("Я не могу повысить себя! Попросите администратора сделать это за меня.")
        return ""

    # set same perms as bot - bot can't assign higher perms than itself!
    bot_member = chat.get_member(bot.id)

    bot.promoteChatMember(chat_id, user_id,
                          can_change_info=bot_member.can_change_info,
                          can_post_messages=bot_member.can_post_messages,
                          can_edit_messages=bot_member.can_edit_messages,
                          can_delete_messages=bot_member.can_delete_messages,
                          # can_invite_users=bot_member.can_invite_users,
                          can_restrict_members=bot_member.can_restrict_members,
                          can_pin_messages=bot_member.can_pin_messages,
                          can_promote_members=bot_member.can_promote_members)

    message.reply_text("Успешно повышен!")
    return "<b>{}:</b>" \
           "\n#Повышен" \
           "\n<b>Админ:</b> {}" \
           "\n<b>Пользователь:</b> {}".format(html.escape(chat.title),
                                      mention_html(user.id, user.first_name),
                                      mention_html(user_member.user.id, user_member.user.first_name))


@run_async
@bot_admin
@can_promote
@user_admin
@loggable
def demote(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]

    user_id = extract_user(message, args)
    if not user_id:
        message.reply_text("Похоже, вы не ссылаетесь на пользователя.")
        return ""

    user_member = chat.get_member(user_id)
    if user_member.status == 'creator':
        message.reply_text("Этот человек СОЗДАЛ чат, как бы я понизил их в должности?")
        return ""

    if not user_member.status == 'administrator':
        message.reply_text("Не могу понизить того, кто не был повышен!")
        return ""

    if user_id == bot.id:
        message.reply_text("Я не могу понизить себя в должности! Попросите администратора сделать это за меня.")
        return ""

    try:
        bot.promoteChatMember(int(chat.id), int(user_id),
                              can_change_info=False,
                              can_post_messages=False,
                              can_edit_messages=False,
                              can_delete_messages=False,
                              can_invite_users=False,
                              can_restrict_members=False,
                              can_pin_messages=False,
                              can_promote_members=False)
        message.reply_text("Успешно понижен!")
        return "<b>{}:</b>" \
               "\n#Понижен" \
               "\n<b>Админ:</b> {}" \
               "\n<b>Пользователь:</b> {}".format(html.escape(chat.title),
                                          mention_html(user.id, user.first_name),
                                          mention_html(user_member.user.id, user_member.user.first_name))

    except BadRequest:
        message.reply_text("Не удалось понизить в должности. Возможно, я не администратор, или статус администратора был назначен другим "
                           "пользователем, поэтому я не могу действовать в соответствии с ними!")
        return ""


@run_async
@bot_admin
@can_pin
@user_admin
@loggable
def pin(bot: Bot, update: Update, args: List[str]) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]

    is_group = chat.type != "private" and chat.type != "channel"

    prev_message = update.effective_message.reply_to_message

    is_silent = True
    if len(args) >= 1:
        is_silent = not (args[0].lower() == 'notify' or args[0].lower() == 'loud' or args[0].lower() == 'violent')

    if prev_message and is_group:
        try:
            bot.pinChatMessage(chat.id, prev_message.message_id, disable_notification=is_silent)
        except BadRequest as excp:
            if excp.message == "Chat_not_modified":
                pass
            else:
                raise
        return "<b>{}:</b>" \
               "\n#Закреплен" \
               "\n<b>Админ:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name))

    return ""


@run_async
@bot_admin
@can_pin
@user_admin
@loggable
def unpin(bot: Bot, update: Update) -> str:
    chat = update.effective_chat
    user = update.effective_user  # type: Optional[User]

    try:
        bot.unpinChatMessage(chat.id)
    except BadRequest as excp:
        if excp.message == "Chat_not_modified":
            pass
        else:
            raise

    return "<b>{}:</b>" \
           "\n#Откреплен" \
           "\n<b>Админ:</b> {}".format(html.escape(chat.title),
                                       mention_html(user.id, user.first_name))

@run_async
@bot_admin
@user_admin
def invite(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message #type: Optional[Messages]
    
    if chat.username:
        update.effective_message.reply_text("@{}".format(chat.username))
    elif chat.type == chat.SUPERGROUP or chat.type == chat.CHANNEL:
        bot_member = chat.get_member(bot.id)
        if bot_member.can_invite_users:
            invitelink = bot.exportChatInviteLink(chat.id)
            linktext = "Успешно сгенерирована новая ссылка для *{}:*".format(chat.title)
            link = "`{}`".format(invitelink)
            message.reply_text(linktext, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            message.reply_text(link, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        else:
            message.reply_text("У меня нет доступа к ссылке приглашения, Попробуйте изменить мои права!")
    else:
        message.reply_text("Я могу дать вам только пригласить ссылки для супергрупп и каналов, извините!")

@run_async
def link_public(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message #type: Optional[Messages]
    chat_id = update.effective_chat.id
    invitelink = sql.get_link(chat_id)
    
    if chat.type == chat.SUPERGROUP or chat.type == chat.CHANNEL:
        if invitelink:
            message.reply_text("Ссылка на *{}*:\n`{}`".format(chat.title, invitelink), parse_mode=ParseMode.MARKDOWN)
        else:
            message.reply_text("Администраторы *{}* не установили ссылку."
                               " \nСсылку можно установить, выполнив следующие действия: `/setlink` и получите ссылку чата "
                               "using /invitelink, paste the link after `/setlink` append.".format(chat.title), parse_mode=ParseMode.MARKDOWN)
    else:
        message.reply_text("Я могу только сохранять ссылки для супергрупп и каналов, извините!")

@run_async
@user_admin
def set_link(bot: Bot, update: Update):
    chat_id = update.effective_chat.id
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    raw_text = msg.text
    args = raw_text.split(None, 1)  # use python's maxsplit to separate cmd and args
    
    if len(args) == 2:
        links_text = args[1]

        sql.set_link(chat_id, links_text)
        msg.reply_text("Ссылка установлена для {}!\nПолучить ссылку можно с помощью #link".format((chat.title)))


@run_async
@user_admin
def clear_link(bot: Bot, update: Update):
    chat_id = update.effective_chat.id
    sql.set_link(chat_id, "")
    update.effective_message.reply_text("Ссылка успешно очищена!")


@run_async
def adminlist(bot: Bot, update: Update):
    administrators = update.effective_chat.get_administrators()
    text = "Админ в *{}*:".format(update.effective_chat.title or "этот чате")
    for admin in administrators:
        user = admin.user
        name = "[{}](tg://user?id={})".format(user.first_name + (user.last_name or ""), user.id)
        if user.username:
            name = escape_markdown("@" + user.username)
        text += "\n - {}".format(name)

    update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

def __stats__():
    return "{} chats have links set.".format(sql.num_chats())

def __chat_settings__(chat_id, user_id):
    return "Вы *админ*: `{}`".format(
        dispatcher.bot.get_chat_member(chat_id, user_id).status in ("administrator", "creator"))


__help__ = """
Лень повышать или понижать кого-то для администраторов? Хотите увидеть основную информацию о чате? \
Все, что касается чата, например списки администраторов, закрепление или захват ссылки приглашения, может быть \
легко делается с помощью бота.

 - /adminlist: список администраторов и участников в чате
 - /staff: то же, что и /adminlist
 - /link: получить ссылку на группу для этого чата.
 - #link: то же, что и /link

*Только для администраторов:*
 - /pin: Безшумно закрепить отвеченое сообщение - добавьте аргумент 'loud' или 'notify' чтобы уведомить пользователей о закреплении.
 - /unpin: Открепить текущее закрепренное сообщение.
 - /invitelink: Получить ссылку-приглашение.
 - /setlink <ссылка: установите ссылку на группу для этого чата.
 - /clearlink: очистите ссылку на группу для этого чата.
 - /promote: Повысить пользователя.
 - /demote: Понизить пользователя
 
"""

__mod_name__ = "Admin"

PIN_HANDLER = CommandHandler("pin", pin, pass_args=True, filters=Filters.group)
UNPIN_HANDLER = CommandHandler("unpin", unpin, filters=Filters.group)
LINK_HANDLER = DisableAbleCommandHandler("link", link_public)
SET_LINK_HANDLER = CommandHandler("setlink", set_link, filters=Filters.group)
RESET_LINK_HANDLER = CommandHandler("clearlink", clear_link, filters=Filters.group)
HASH_LINK_HANDLER = RegexHandler("#link", link_public)
INVITE_HANDLER = CommandHandler("invitelink", invite, filters=Filters.group)
PROMOTE_HANDLER = CommandHandler("promote", promote, pass_args=True, filters=Filters.group)
DEMOTE_HANDLER = CommandHandler("demote", demote, pass_args=True, filters=Filters.group)
ADMINLIST_HANDLER = DisableAbleCommandHandler(["adminlist", "staff"], adminlist, filters=Filters.group)

dispatcher.add_handler(PIN_HANDLER)
dispatcher.add_handler(UNPIN_HANDLER)
dispatcher.add_handler(INVITE_HANDLER)
dispatcher.add_handler(LINK_HANDLER)
dispatcher.add_handler(SET_LINK_HANDLER)
dispatcher.add_handler(RESET_LINK_HANDLER)
dispatcher.add_handler(HASH_LINK_HANDLER)
dispatcher.add_handler(PROMOTE_HANDLER)
dispatcher.add_handler(DEMOTE_HANDLER)
dispatcher.add_handler(ADMINLIST_HANDLER)
