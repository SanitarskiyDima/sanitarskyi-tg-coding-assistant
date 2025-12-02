"""Telegram bot router configuration."""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, F, Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers import (
    handle_agent_callback,
    handle_agents,
    handle_ask,
    handle_favrepos,
    handle_followup,
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
            logger.info(
                f"Received message from user {user.id} (@{user.username}): "
                f"{event.text[:100] if event.text else 'no text'}"
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                f"Received callback from user {user.id} (@{user.username}): "
                f"{event.data}"
            )
        
        # Check if user is allowed
        if user.id != settings.allowed_user_id:
            if isinstance(event, Message):
                await event.reply("Тільки мій власник @dmytro_s_s може керувати мною")
            elif isinstance(event, CallbackQuery):
                await event.answer("Тільки мій власник @dmytro_s_s може керувати мною", show_alert=True)
            return
        
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
async def cmd_plan(message: Message) -> None:
    """Handle /plan command."""
    await handle_plan(message, task_manager)


@router.message(Command("ask"))
async def cmd_ask(message: Message) -> None:
    """Handle /ask command."""
    await handle_ask(message, task_manager)


@router.message(Command("solve"))
async def cmd_solve(message: Message) -> None:
    """Handle /solve command."""
    await handle_solve(message, task_manager)


@router.message(Command("repos"))
async def cmd_repos(message: Message) -> None:
    """Handle /repos command."""
    await handle_repos(message)


@router.message(Command("favrepos"))
async def cmd_favrepos(message: Message) -> None:
    """Handle /favrepos command."""
    await handle_favrepos(message)


@router.message(Command("setrepo"))
async def cmd_setrepo(message: Message) -> None:
    """Handle /setrepo command."""
    await handle_setrepo(message)


@router.message(Command("agents"))
async def cmd_agents(message: Message) -> None:
    """Handle /agents command."""
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


# Handle text messages (not commands) as follow-up responses
@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message) -> None:
    """Handle text messages as follow-up responses to agents."""
    await handle_followup(message)


# Handle photo messages as follow-up responses
@router.message(F.photo)
async def handle_photo_message(message: Message) -> None:
    """Handle photo messages as follow-up responses to agents."""
    await handle_followup(message)

