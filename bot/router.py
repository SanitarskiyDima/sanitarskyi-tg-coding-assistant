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
        
        # Log all messages/callbacks - THIS SHOULD ALWAYS APPEAR IF MESSAGE REACHES BOT
        if isinstance(event, Message):
            chat_type = event.chat.type if hasattr(event, 'chat') else None
            chat_id = event.chat.id if hasattr(event, 'chat') else None
            entities_info = f", entities: {event.entities}" if event.entities else ""
            logger.info(
                f"📨 MIDDLEWARE: Received message from user {user.id} (@{user.username}) "
                f"in {chat_type} (chat_id: {chat_id}): {event.text[:100] if event.text else 'no text'}{entities_info}"
            )
            logger.info(f"📨 MIDDLEWARE: Handler name: {handler.__name__ if hasattr(handler, '__name__') else str(handler)}")
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
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект."
        )
        return
    await handle_plan(message, task_manager, is_group_chat=is_group_chat)


@router.message(Command("ask"))
async def cmd_ask(message: Message, data: dict) -> None:
    """Handle /ask command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use commands - regular users should use mentions
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект (наприклад: @botname ваше питання)."
        )
        return
    await handle_ask(message, task_manager, is_group_chat=is_group_chat)


@router.message(Command("solve"))
async def cmd_solve(message: Message, data: dict) -> None:
    """Handle /solve command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект."
        )
        return
    await handle_solve(message, task_manager, is_group_chat=is_group_chat)


@router.message(Command("repos"))
async def cmd_repos(message: Message, data: dict) -> None:
    """Handle /repos command."""
    is_group_chat = data.get('is_group_chat', False)
    # In groups, only owner can use this command
    if is_group_chat and message.from_user.id != settings.allowed_user_id:
        await message.reply(
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект."
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
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект."
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
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект."
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
            "❌ У групових чатах для звичайних користувачів доступні тільки упоминания бота.\n\n"
            "Тегніть бота з питанням про проект."
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
# This handler should catch all text messages in groups
# IMPORTANT: This handler must be registered AFTER command handlers but BEFORE other text handlers
@router.message(F.text & F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def handle_group_mention_message(message: Message, **kwargs) -> None:
    """Handle bot mentions in group chats."""
    logger.info(f"🔍 GROUP MENTION HANDLER CALLED! Chat: {message.chat.id}, Text: {message.text[:100]}")
    
    # Skip if it's a command (commands are handled by other handlers)
    if message.text and message.text.startswith("/"):
        logger.debug("Skipping command in group mention handler")
        return
    
    # Get bot info once
    bot_info = await message.bot.get_me()
    bot_mentioned = False
    
    logger.info(f"Checking mention in group chat {message.chat.id}. Text: {message.text[:100]}, Bot username: @{bot_info.username}")
    
    # Method 1: Check entities (most reliable for proper mentions)
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = message.text[entity.offset:entity.offset + entity.length]
                logger.debug(f"Found mention entity: '{mention_text}', bot username: @{bot_info.username}")
                # Check exact match and case-insensitive match
                if mention_text == f"@{bot_info.username}" or mention_text.lower() == f"@{bot_info.username.lower()}":
                    bot_mentioned = True
                    logger.info(f"✅ Bot mentioned via entity: {mention_text}")
                    break
    
    # Method 2: Simple text search (fallback - works even if entities are missing)
    # This is more reliable as it works even if Telegram doesn't parse entities correctly
    if not bot_mentioned and bot_info.username:
        text_lower = message.text.lower()
        bot_mention_lower = f"@{bot_info.username.lower()}"
        # Check if mention is anywhere in the text
        if bot_mention_lower in text_lower:
            bot_mentioned = True
            logger.info(f"✅ Bot mentioned via text search: @{bot_info.username}")
        # Also check without @ symbol (sometimes users forget it)
        elif bot_info.username.lower() in text_lower and message.text.startswith(bot_info.username):
            bot_mentioned = True
            logger.info(f"✅ Bot mentioned without @ symbol: {bot_info.username}")
    
    # Method 3: Check if message is a reply to bot
    if not bot_mentioned:
        if message.reply_to_message and message.reply_to_message.from_user:
            if message.reply_to_message.from_user.id == bot_info.id:
                bot_mentioned = True
                logger.info("✅ Bot mentioned via reply")
    
    if bot_mentioned:
        logger.info(f"🚀 Processing bot mention from user {message.from_user.id} (@{message.from_user.username}) in chat {message.chat.id}")
        try:
            data = kwargs.get('data', {})
            is_group_chat = data.get('is_group_chat', False)
            await handle_group_mention(message, task_manager)
        except Exception as e:
            logger.exception(f"Error processing group mention: {e}")
            await message.reply(
                f"❌ Помилка при обробці запиту: {str(e)}\n\n"
                "Спробуйте ще раз пізніше."
            )
    else:
        logger.debug(f"⏭️ Bot not mentioned in message, ignoring: {message.text[:50]}...")
    # If not mentioned, ignore the message in groups


# Handle text messages (not commands) in private chats
@router.message(F.text & ~F.text.startswith("/") & (F.chat.type == ChatType.PRIVATE))
async def handle_text_message(message: Message, **kwargs) -> None:
    """Handle text messages in private chats - check for bot mentions or follow-up."""
    # Check if bot is mentioned in private chat
    bot_info = await message.bot.get_me()
    bot_mentioned = False
    original_text = message.text
    
    # Check entities for mentions
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = message.text[entity.offset:entity.offset + entity.length]
                if mention_text == f"@{bot_info.username}" or mention_text.lower() == f"@{bot_info.username.lower()}":
                    bot_mentioned = True
                    logger.info(f"Bot mentioned in private chat: {mention_text}")
                    break
    
    # Also check text search
    if not bot_mentioned and bot_info.username:
        text_lower = message.text.lower()
        if f"@{bot_info.username.lower()}" in text_lower:
            bot_mentioned = True
            logger.info(f"Bot mentioned in private chat via text search")
    
    # If bot is mentioned, treat it as a new question (ask mode)
    if bot_mentioned:
        logger.info(f"Processing bot mention in private chat from user {message.from_user.id}")
        try:
            # Remove bot mention from text before processing
            text = original_text
            if message.entities:
                for entity in message.entities:
                    if entity.type == "mention":
                        mention_text = text[entity.offset:entity.offset + entity.length]
                        if mention_text == f"@{bot_info.username}" or mention_text.lower() == f"@{bot_info.username.lower()}":
                            text = text.replace(mention_text, "", 1).strip()
            
            # Also remove via text replacement
            if bot_info.username:
                text = text.replace(f"@{bot_info.username}", "").strip()
                text = text.replace(f"@{bot_info.username.lower()}", "").strip()
            
            # If text is empty after removing mention, ask for question
            if not text:
                await message.reply(
                    "👋 Привіт! Напишіть питання після тегу.\n\n"
                    "**Приклад:**\n"
                    f"@{bot_info.username} Як працює автентифікація користувачів?\n\n"
                    "Або використайте команду `/ask <ваше питання>`"
                )
                return
            
            # Create a modified message object with cleaned text
            # We'll pass the cleaned text directly to handle_ask
            # For now, let's modify the message text temporarily
            original_message_text = message.text
            message.text = text  # Temporarily modify
            
            data = kwargs.get('data', {})
            is_group_chat = data.get('is_group_chat', False)
            # In private chats, use normal mode (not non-technical)
            await handle_ask(message, task_manager, is_group_chat=False)
            
            # Restore original text
            message.text = original_message_text
        except Exception as e:
            logger.exception(f"Error processing mention in private chat: {e}")
            await message.reply(
                f"❌ Помилка при обробці запиту: {str(e)}\n\n"
                "Спробуйте ще раз пізніше."
            )
    else:
        # No mention, treat as follow-up to existing agent
        await handle_followup(message)


# Handle photo messages as follow-up responses
@router.message(F.photo & (F.chat.type == ChatType.PRIVATE))
async def handle_photo_message(message: Message) -> None:
    """Handle photo messages as follow-up responses to agents (private chats only)."""
    await handle_followup(message)

