"""Main entry point for Telegram bot."""

import asyncio
import logging
import signal
import sys
from signal import SIGINT, SIGTERM
from types import FrameType
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.router import router
from cursor.client import cursor_client
from settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main function to start the bot."""
    logger.info("Starting Telegram bot...")

    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # Register router
    dp.include_router(router)

    # Register commands in Telegram
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Почати роботу з ботом"),
            BotCommand(command="help", description="Показати довідку"),
            BotCommand(command="repos", description="Показати список репозиторіїв"),
            BotCommand(command="setrepo", description="Вибрати репозиторій для роботи"),
            BotCommand(command="plan", description="Отримати план рішення задачі"),
            BotCommand(command="ask", description="Отримати уточнюючі питання"),
            BotCommand(command="solve", description="Згенерувати код для задачі"),
            BotCommand(command="agents", description="Показати список активних агентів"),
        ]
    )

    logger.info("Bot initialized. Starting polling...")

    try:
        # Start polling
        await dp.start_polling(bot, handle_as_tasks=False)
    except Exception as e:
        logger.exception("Error during polling")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down...")
        await cursor_client.close()
        await bot.session.close()
        logger.info("Bot stopped")


def signal_handler(sig: int, frame: Any) -> None:
    """Handle shutdown signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(SIGINT, signal_handler)
    signal.signal(SIGTERM, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception("Fatal error")
        sys.exit(1)

