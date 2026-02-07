"""
Утилиты для cross-bot коммуникации.

Обрабатывает уведомления между ботом поддержки и основным ботом.
"""

import structlog
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import SupportTicket, SupportMessage, User


logger = structlog.get_logger()


async def notify_admins_about_ticket(
    ticket: SupportTicket,
    user: User,
    bot: Bot,
) -> None:
    """
    Уведомить всех администраторов о новом тикете.

    Args:
        ticket: Созданный тикет
        user: Пользователь, создавший тикет
        bot: Экземпляр бота поддержки
    """
    from support_bot.config import support_settings

    category_names = {
        "payment": "💳 Оплата",
        "technical": "🔧 Техническая проблема",
        "other": "❓ Другое",
    }

    # Получаем первое сообщение (описание проблемы)
    description = ""
    if ticket.messages:
        description = ticket.messages[0].text
        # Ограничиваем длину описания
        if len(description) > 300:
            description = description[:300] + "..."

    text = f"""🆕 <b>Новое обращение в поддержку!</b>

━━━━━━━━━━━━━━━━━━━━━

<b>Тикет:</b> #{ticket.id}
<b>Категория:</b> {category_names.get(ticket.category, ticket.category)}
<b>Пользователь:</b> @{user.username or 'без имени'}
<b>ID:</b> <code>{user.telegram_id}</code>
<b>Баланс:</b> {user.balance} генераций

<b>Описание:</b>
{description}

━━━━━━━━━━━━━━━━━━━━━

👇 Ответить можно через админ-панель основного бота"""

    # Создаём клавиатуру с ссылкой на тикет в админ-панели
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 Открыть в админ-панели",
            url=f"https://t.me/{support_settings.main_bot_username}?start=admin_ticket_{ticket.id}",
        ),
    )

    keyboard = builder.as_markup()

    # Отправляем всем админам (через основного бота, если доступен)
    for admin_id in support_settings.admin_ids:
        try:
            # Пытаемся отправить уведомление
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "failed_to_notify_admin_about_ticket",
                admin_id=admin_id,
                ticket_id=ticket.id,
                error=str(e),
            )

    logger.info(
        "admins_notified_about_ticket",
        ticket_id=ticket.id,
        admins_count=len(support_settings.admin_ids),
    )


async def notify_admins_about_new_user_message(
    ticket_id: int,
    user: User,
    message_text: str,
    bot: Bot,
) -> None:
    """
    Уведомить админов о новом сообщении пользователя в существующем тикете.

    Отправляет компактное уведомление (не полный тикет).

    Args:
        ticket_id: ID тикета
        user: Пользователь, отправивший сообщение
        message_text: Текст нового сообщения
        bot: Экземпляр бота поддержки
    """
    from support_bot.config import support_settings

    # Ограничиваем длину превью
    preview = message_text[:300] + "..." if len(message_text) > 300 else message_text

    text = f"""💬 <b>Новое сообщение в тикете #{ticket_id}</b>

👤 <b>Пользователь:</b> @{user.username or 'без имени'} (<code>{user.telegram_id}</code>)

<b>Сообщение:</b>
{preview}

━━━━━━━━━━━━━━━━━━━━━

👇 Ответить можно через админ-панель основного бота"""

    builder = InlineKeyboardBuilder()
    if support_settings.main_bot_username:
        builder.row(
            InlineKeyboardButton(
                text="📋 Открыть в админ-панели",
                url=f"https://t.me/{support_settings.main_bot_username}?start=admin_ticket_{ticket_id}",
            ),
        )

    keyboard = builder.as_markup()

    for admin_id in support_settings.admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "failed_to_notify_admin_about_user_message",
                admin_id=admin_id,
                ticket_id=ticket_id,
                error=str(e),
            )

    logger.info(
        "admins_notified_about_user_message",
        ticket_id=ticket_id,
    )


async def notify_user_about_admin_reply(
    message: SupportMessage,
    user: User,
    bot: Bot,
) -> None:
    """
    Уведомить пользователя об ответе администратора.

    Args:
        message: Сообщение администратора
        user: Пользователь для уведомления
        bot: Экземпляр бота поддержки
    """
    from support_bot.config import support_settings

    text = f"""💬 <b>Новое сообщение в обращении #{message.ticket_id}</b>

👨‍💻 <b>Поддержка:</b>
{message.text}

━━━━━━━━━━━━━━━━━━━━━

💡 Ответить можно в этом боте."""

    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML",
        )

        logger.info(
            "user_notified_about_admin_reply",
            ticket_id=message.ticket_id,
            user_id=user.id,
        )
    except Exception as e:
        logger.error(
            "failed_to_notify_user_about_reply",
            error=str(e),
            user_id=user.id,
        )


async def notify_user_about_new_message(
    ticket_id: int,
    user: User,
    admin_name: str,
    bot: Bot,
) -> None:
    """
    Уведомить пользователя о новом сообщении от админа.

    Упрощённая версия для случаев, когда нужно просто уведомить
    о наличии нового сообщения без полного текста.

    Args:
        ticket_id: ID тикета
        user: Пользователь для уведомления
        admin_name: Имя администратора
        bot: Экземпляр бота поддержки
    """
    text = f"""💬 <b>Новое сообщение в обращении #{ticket_id}</b>

👨‍💻 <b>{admin_name}</b> ответил на ваше обращение.

━━━━━━━━━━━━━━━━━━━━━

💡 Открой тикет, чтобы прочитать сообщение и ответить."""

    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            parse_mode="HTML",
        )

        logger.info(
            "user_notified_about_new_message",
            ticket_id=ticket_id,
            user_id=user.id,
        )
    except Exception as e:
        logger.error(
            "failed_to_notify_user_about_new_message",
            error=str(e),
            user_id=user.id,
        )
