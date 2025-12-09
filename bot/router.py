"""Telegram bot router configuration."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, F, Router, types
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers import (
    handle_agent_callback,
    handle_agents,
    handle_ask,
    handle_favrepos,
    handle_followup,
    handle_group_mention,
    handle_help,
    handle_plan,
    handle_repo_callback,
    handle_repos,
    handle_setrepo,
    handle_solve,
    handle_start,
)
from cursor.task_manager import TaskManager
from cursor.client import cursor_client
from settings import settings

logger = logging.getLogger(__name__)

# Create router
router = Router()

# Initialize task manager
task_manager = TaskManager(cursor_client)


class UserAccessMiddleware(BaseMiddleware):
    """Middleware to check if user is allowed to use the bot."""

    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        """
        Check user access before handling.

        Args:
            handler: Message or callback handler
            event: Message or CallbackQuery event
            data: Handler data
        """
        user = event.from_user
        
        # Log all messages/callbacks
        if isinstance(event, Message):
            chat_type = event.chat.type if hasattr(event, 'chat') else None
            logger.info(
                f"Received message from user {user.id} (@{user.username}) "
                f"in {chat_type}: {event.text[:100] if event.text else 'no text'}"
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                f"Received callback from user {user.id} (@{user.username}): "
                f"{event.data}"
            )
        
        # For group chats, allow all users (they can only use ask mode)
        # For private chats, only allow the owner
        if isinstance(event, Message):
            chat_type = event.chat.type
            is_group = chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)
            
            if is_group:
                # In groups, allow all users - they will be restricted to ask mode only
                # Store chat type in data for handlers
                data['is_group_chat'] = True
                return await handler(event, data)
            else:
                # In private chats, only allow owner
                if user.id != settings.allowed_user_id:
                    await event.reply("Тільки мій власник @dmytro_s_s може керувати мною")
                    return
                data['is_group_chat'] = False
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            # For callbacks, check if it's from a group
            if hasattr(event, 'message') and event.message:
                chat_type = event.message.chat.type
                is_group = chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)
                
                if is_group:
                    # In groups, allow all users for callbacks
                    data['is_group_chat'] = True
                    return await handler(event, data)
                else:
                    # In private chats, only allow owner
                    if user.id != settings.allowed_user_id:
                        await event.answer("Тільки мій власник @dmytro_s_s може керувати мною", show_alert=True)
                        return
                    data['is_group_chat'] = False
                    return await handler(event, data)
            else:
                # No message context, apply private chat rules
                if user.id != settings.allowed_user_id:
                    await event.answer("Тільки мій власник @dmytro_s_s може керувати мною", show_alert=True)
                    return
                data['is_group_chat'] = False
                return await handler(event, data)
        
        return await handler(event, data)


# Register middleware (order matters - access check first)
router.message.middleware(UserAccessMiddleware())
router.callback_query.middleware(UserAccessMiddleware())


# Register command handlers
@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Handle /start command."""
    await handle_start(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command."""
    await handle_help(message)


@router.message(Command("plan"))
async def cmd_plan(message: Message, data: dict) -> None:
    """Handle /plan command."""
    is_group_chat = data.get('is_group_chat', False)
    await handle_plan(message, task_manager, is_group_chat=is_group_chat)


@router.message(Command("ask"))
async def cmd_ask(message: Message, data: dict) -> None:
    """Handle /ask command."""
    is_group_chat = data.get('is_group_chat', False)
    await handle_ask(message, task_manager, is_group_chat=is_group_chat)


@router.message(Command("solve"))
async def cmd_solve(message: Message, data: dict) -> None:
    """Handle /solve command."""
    is_group_chat = data.get('is_group_chat', False)
    await handle_solve(message, task_manager, is_group_chat=is_group_chat)


@router.message(Command("repos"))
async def cmd_repos(message: Message, data: dict) -> None:
    """Handle /repos command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах доступний тільки режим `/ask` для отримання відповідей на питання.\n\n"
            "Використайте `/ask <ваше питання>` або тегніть бота з питанням."
        )
        return
    await handle_repos(message)


@router.message(Command("favrepos"))
async def cmd_favrepos(message: Message, data: dict) -> None:
    """Handle /favrepos command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах доступний тільки режим `/ask` для отримання відповідей на питання.\n\n"
            "Використайте `/ask <ваше питання>` або тегніть бота з питанням."
        )
        return
    await handle_favrepos(message)


@router.message(Command("setrepo"))
async def cmd_setrepo(message: Message, data: dict) -> None:
    """Handle /setrepo command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах доступний тільки режим `/ask` для отримання відповідей на питання.\n\n"
            "Використайте `/ask <ваше питання>` або тегніть бота з питанням."
        )
        return
    await handle_setrepo(message)


@router.message(Command("agents"))
async def cmd_agents(message: Message, data: dict) -> None:
    """Handle /agents command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах доступний тільки режим `/ask` для отримання відповідей на питання.\n\n"
            "Використайте `/ask <ваше питання>` або тегніть бота з питанням."
        )
        return
    await handle_agents(message)


@router.callback_query(F.data.startswith("select_repo_"))
async def callback_repo_selection(callback: CallbackQuery) -> None:
    """Handle repository selection callback."""
    await handle_repo_callback(callback)


@router.callback_query(F.data.startswith("fav_repo_"))
async def callback_fav_toggle(callback: CallbackQuery) -> None:
    """Handle favorite repository toggle callback."""
    await handle_repo_callback(callback)


@router.callback_query(F.data.startswith("select_agent_"))
async def callback_agent_selection(callback: CallbackQuery) -> None:
    """Handle agent selection callback."""
    await handle_agent_callback(callback)


# Handle bot mentions in group chats
@router.message(F.text & (F.chat.type == ChatType.GROUP | F.chat.type == ChatType.SUPERGROUP))
async def handle_group_mention_message(message: Message, data: dict) -> None:
    """Handle bot mentions in group chats."""
    # Skip if it's a command
    if message.text and message.text.startswith("/"):
        return
    
    # Check if message mentions the bot
    bot_info = await message.bot.get_me()
    bot_mentioned = False
    
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = message.text[entity.offset:entity.offset + entity.length]
                if mention_text == f"@{bot_info.username}":
                    bot_mentioned = True
                    break
    
    # Also check if text contains @botname (case insensitive)
    if not bot_mentioned and bot_info.username:
        text_lower = message.text.lower()
        if f"@{bot_info.username.lower()}" in text_lower:
            bot_mentioned = True
    
    if bot_mentioned:
        is_group_chat = data.get('is_group_chat', False)
        await handle_group_mention(message, task_manager)
    # If not mentioned, ignore the message in groups


# Handle text messages (not commands) as follow-up responses
@router.message(F.text & ~F.text.startswith("/") & (F.chat.type == ChatType.PRIVATE))
async def handle_text_message(message: Message) -> None:
    """Handle text messages as follow-up responses to agents (private chats only)."""
    await handle_followup(message)


# Handle photo messages as follow-up responses
@router.message(F.photo & (F.chat.type == ChatType.PRIVATE))
async def handle_photo_message(message: Message) -> None:
    """Handle photo messages as follow-up responses to agents (private chats only)."""
    await handle_followup(message)

