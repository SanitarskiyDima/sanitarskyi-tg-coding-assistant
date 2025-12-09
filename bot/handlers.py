"""Telegram bot command handlers."""

import base64
import io
import logging
from typing import Optional

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from cursor.client import CursorAPIError, CursorTimeoutError, RunStatus, cursor_client
from cursor.task_manager import TaskManager
from bot.repository_manager import (
    get_selected_repository,
    set_selected_repository,
    get_favorite_repositories,
    add_favorite_repository,
    remove_favorite_repository,
    is_favorite_repository,
)
from bot.agent_manager import (
    get_last_agent_id,
    set_last_agent_id,
)

logger = logging.getLogger(__name__)


async def send_status_update(message: types.Message, text: str) -> None:
    """
    Send status update message to user.
    Handles errors gracefully to not break main flow.

    Args:
        message: Telegram message object
        text: Status text to send
    """
    try:
        await message.reply(text)
    except Exception as e:
        logger.warning(f"Failed to send status update: {e}")


async def handle_plan(message: types.Message, task_manager: TaskManager, is_group_chat: bool = False) -> None:
    """
    Handle /plan command.

    Args:
        message: Telegram message
        task_manager: TaskManager instance
        is_group_chat: Whether this is a group chat
    """
    # In group chats, only allow ask mode
    if is_group_chat:
        await message.reply(
            "❌ У групових чатах доступний тільки режим `/ask` для отримання відповідей на питання.\n\n"
            "Використайте `/ask <ваше питання>` або тегніть бота з питанням."
        )
        return
    
    text = message.text or ""
    # Remove /plan command prefix
    task_text = text.replace("/plan", "").strip()

    if not task_text:
        await message.reply(
            "Будь ласка, вкажіть задачу після команди /plan.\n"
            "Приклад: /plan Створити REST API для управління користувачами"
        )
        return

    # Send typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")
    await send_status_update(message, "🔄 Створюю агента...")

    # Get selected repository for user
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        # Create status callback for progress updates
        async def status_callback(elapsed: float, status: RunStatus) -> None:
            if elapsed >= 10:
                status_text = {
                    RunStatus.RUNNING: "⏳ Агент працює над завданням...",
                    RunStatus.CREATING: "🔄 Агент створюється...",
                    RunStatus.EXPIRED: "⚠️ Агент застарів...",
                }.get(status, "⏳ Агент обробляє ваш запит...")
                await send_status_update(message, f"{status_text} (прошло {int(elapsed)}с)")

        await send_status_update(message, "⏳ Агент працює над завданням...")
        agent_id, result = await task_manager.run_plan(
            task_text, 
            repository_url=selected_repo,
            status_callback=status_callback
        )
        # Save agent ID for follow-up support
        set_last_agent_id(message.from_user.id, agent_id)
        await message.reply(result, parse_mode="Markdown")
    except CursorTimeoutError:
        await message.reply(
            "⏱ Операція зайняла занадто багато часу. "
            "Спробуйте спростити задачу або повторити спробу пізніше."
        )
    except CursorAPIError as e:
        # Remove markdown formatting to avoid Telegram parsing errors
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при зверненні до Cursor API:\n\n{error_msg}\n\n"
            "Перевірте правильність API ключа та спробуйте ще раз.",
            parse_mode=None  # Disable markdown to avoid parsing errors
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_plan")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}\n\n"
            "Спробуйте ще раз або зверніться до адміністратора."
        )


async def handle_ask(message: types.Message, task_manager: TaskManager, is_group_chat: bool = False) -> None:
    """
    Handle /ask command.

    Args:
        message: Telegram message
        task_manager: TaskManager instance
        is_group_chat: Whether this is a group chat
    """
    text = message.text or ""
    # Remove /ask command prefix
    task_text = text.replace("/ask", "").strip()

    if not task_text:
        await message.reply(
            "Будь ласка, вкажіть задачу після команди /ask.\n"
            "Приклад: /ask Як створити мікросервіс на Python?"
        )
        return

    # Send typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")
    await send_status_update(message, "🔄 Створюю агента...")

    # Get selected repository for user
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        # Create status callback for progress updates
        async def status_callback(elapsed: float, status: RunStatus) -> None:
            if elapsed >= 10:
                status_text = {
                    RunStatus.RUNNING: "⏳ Агент працює над завданням...",
                    RunStatus.CREATING: "🔄 Агент створюється...",
                    RunStatus.EXPIRED: "⚠️ Агент застарів...",
                }.get(status, "⏳ Агент обробляє ваш запит...")
                await send_status_update(message, f"{status_text} (прошло {int(elapsed)}с)")

        await send_status_update(message, "⏳ Агент працює над завданням...")
        agent_id, result = await task_manager.run_ask(
            task_text,
            repository_url=selected_repo,
            status_callback=status_callback,
            is_non_technical=is_group_chat  # In groups, use non-technical mode
        )
        # Save agent ID for follow-up support
        set_last_agent_id(message.from_user.id, agent_id)
        await message.reply(result, parse_mode="Markdown")
    except CursorTimeoutError:
        await message.reply(
            "⏱ Операція зайняла занадто багато часу. "
            "Спробуйте спростити задачу або повторити спробу пізніше."
        )
    except CursorAPIError as e:
        # Remove markdown formatting to avoid Telegram parsing errors
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при зверненні до Cursor API:\n\n{error_msg}\n\n"
            "Перевірте правильність API ключа та спробуйте ще раз.",
            parse_mode=None  # Disable markdown to avoid parsing errors
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_ask")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}\n\n"
            "Спробуйте ще раз або зверніться до адміністратора."
        )


async def handle_solve(message: types.Message, task_manager: TaskManager, is_group_chat: bool = False) -> None:
    """
    Handle /solve command - generate code solution for a task.

    Args:
        message: Telegram message
        task_manager: TaskManager instance
        is_group_chat: Whether this is a group chat
    """
    # In group chats, only allow ask mode
    if is_group_chat:
        await message.reply(
            "❌ У групових чатах доступний тільки режим `/ask` для отримання відповідей на питання.\n\n"
            "Використайте `/ask <ваше питання>` або тегніть бота з питанням."
        )
        return
    
    text = message.text or ""
    # Remove /solve command prefix
    task_text = text.replace("/solve", "").strip()

    if not task_text:
        await message.reply(
            "Будь ласка, вкажіть задачу після команди /solve.\n"
            "Приклад: /solve Реалізувати функцію сортування масиву"
        )
        return

    # Send typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")
    await send_status_update(message, "🔄 Створюю агента...")

    # Get selected repository for user
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        # Create status callback for progress updates
        async def status_callback(elapsed: float, status: RunStatus) -> None:
            if elapsed >= 10:
                status_text = {
                    RunStatus.RUNNING: "⏳ Агент працює над завданням...",
                    RunStatus.CREATING: "🔄 Агент створюється...",
                    RunStatus.EXPIRED: "⚠️ Агент застарів...",
                }.get(status, "⏳ Агент обробляє ваш запит...")
                await send_status_update(message, f"{status_text} (прошло {int(elapsed)}с)")

        await send_status_update(message, "⏳ Агент працює над завданням...")
        agent_id, result = await task_manager.run_solve(
            task_text,
            repository_url=selected_repo,
            status_callback=status_callback
        )
        # Save agent ID for follow-up support
        set_last_agent_id(message.from_user.id, agent_id)
        await message.reply(result, parse_mode="Markdown")
    except CursorTimeoutError:
        await message.reply(
            "⏱ Операція зайняла занадто багато часу. "
            "Спробуйте спростити задачу або повторити спробу пізніше."
        )
    except CursorAPIError as e:
        # Remove markdown formatting to avoid Telegram parsing errors
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при зверненні до Cursor API:\n\n{error_msg}\n\n"
            "Перевірте правильність API ключа та спробуйте ще раз.",
            parse_mode=None  # Disable markdown to avoid parsing errors
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_solve")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}\n\n"
            "Спробуйте ще раз або зверніться до адміністратора."
        )


async def handle_start(message: types.Message) -> None:
    """
    Handle /start command.

    Args:
        message: Telegram message
    """
    welcome_text = (
        "👋 Привіт! Я бот для роботи з Cursor Cloud Agent API.\n\n"
        "**Доступні команди:**\n"
        "• `/repos` - показати список репозиторіїв\n"
        "• `/favrepos` - показати тільки улюблені репозиторії\n"
        "• `/setrepo <номер>` - вибрати репозиторій\n"
        "• `/plan <задача>` - отримати покроковий план рішення\n"
        "• `/ask <задача>` - отримати уточнюючі питання\n"
        "• `/solve <задача>` - згенерувати код для вирішення задачі\n"
        "• `/agents` - показати список активних агентів та їх історію\n\n"
        "**Приклади:**\n"
        "• `/repos` - подивитися доступні репозиторії\n"
        "• `/favrepos` - швидко вибрати з улюблених\n"
        "• `/setrepo 1` - вибрати перший репозиторій\n"
        "• `/plan Створити REST API на FastAPI`\n"
        "• `/ask Як оптимізувати SQL запити?`\n"
        "• `/agents` - переглянути активних агентів та продовжити роботу\n\n"
        "**Як працювати з агентами:**\n"
        "1. Створіть агента через `/plan` або `/ask`\n"
        "2. Перегляньте список через `/agents`\n"
        "3. Виберіть агента для перегляду історії\n"
        "4. Відправте текстове повідомлення або фото для follow-up"
    )
    await message.reply(welcome_text, parse_mode="Markdown")


async def handle_group_mention(message: types.Message, task_manager: TaskManager) -> None:
    """
    Handle bot mentions in group chats (when user tags the bot with a question).

    Args:
        message: Telegram message
        task_manager: TaskManager instance
    """
    text = message.text or ""
    
    # Remove bot mention from text
    # Bot mentions can be in format @botname or @botname question
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                # Remove the mention part
                mention_text = text[entity.offset:entity.offset + entity.length]
                text = text.replace(mention_text, "").strip()
    
    # Also try to remove @botname if present
    bot_username = (await message.bot.get_me()).username
    if bot_username:
        text = text.replace(f"@{bot_username}", "").strip()
    
    if not text:
        await message.reply(
            "👋 Привіт! Тегніть мене з питанням про проект.\n\n"
            "**Приклад:**\n"
            f"@{bot_username} Як працює автентифікація користувачів?\n"
            f"@{bot_username} Що робить функція X?\n\n"
            "Або використайте команду `/ask <ваше питання>`"
        )
        return

    # Send typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")
    await send_status_update(message, "🔄 Створюю агента...")

    # Get selected repository for user (use default if not set)
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        # Create status callback for progress updates
        async def status_callback(elapsed: float, status: RunStatus) -> None:
            if elapsed >= 10:
                status_text = {
                    RunStatus.RUNNING: "⏳ Агент працює над завданням...",
                    RunStatus.CREATING: "🔄 Агент створюється...",
                    RunStatus.EXPIRED: "⚠️ Агент застарів...",
                }.get(status, "⏳ Агент обробляє ваш запит...")
                await send_status_update(message, f"{status_text} (прошло {int(elapsed)}с)")

        await send_status_update(message, "⏳ Агент працює над завданням...")
        # Use non-technical mode for group chats
        agent_id, result = await task_manager.run_ask(
            text,
            repository_url=selected_repo,
            status_callback=status_callback,
            is_non_technical=True  # Always use non-technical mode in groups
        )
        # Save agent ID for follow-up support
        set_last_agent_id(message.from_user.id, agent_id)
        await message.reply(result, parse_mode="Markdown")
    except CursorTimeoutError:
        await message.reply(
            "⏱ Операція зайняла занадто багато часу. "
            "Спробуйте спростити питання або повторити спробу пізніше."
        )
    except CursorAPIError as e:
        # Remove markdown formatting to avoid Telegram parsing errors
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при зверненні до Cursor API:\n\n{error_msg}\n\n"
            "Спробуйте ще раз пізніше.",
            parse_mode=None  # Disable markdown to avoid parsing errors
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_group_mention")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}\n\n"
            "Спробуйте ще раз пізніше."
        )


async def handle_followup(message: types.Message) -> None:
    """
    Handle follow-up text messages and photos (not commands) as responses to agent questions.

    Args:
        message: Telegram message
    """
    # Get last agent ID for this user
    agent_id = get_last_agent_id(message.from_user.id)
    if not agent_id:
        await message.reply(
            "❌ Не знайдено активного агента.\n\n"
            "Варіанти:\n"
            "• Використайте `/plan` або `/ask` для створення нового агента\n"
            "• Використайте `/agents` для вибору існуючого агента",
            parse_mode="Markdown"
        )
        return

    # Send typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Prepare follow-up text
    text = message.text or ""
    followup_text = text.strip()

    # Handle photo messages
    if message.photo:
        try:
            await send_status_update(message, "📸 Обробляю фото...")
            # Get the largest photo
            photo = message.photo[-1]
            
            # Get file info and download photo to BytesIO
            file = await message.bot.get_file(photo.file_id)
            photo_buffer = io.BytesIO()
            await message.bot.download_file(file.file_path, destination=photo_buffer)
            photo_bytes = photo_buffer.getvalue()
            photo_buffer.close()
            
            # Convert to base64
            photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
            
            # Add photo info to follow-up text
            photo_info = f"\n\n[Користувач надіслав фото: {photo.width}x{photo.height}px, розмір файлу: {len(photo_bytes)} байт]"
            # Include full base64 for Cursor API to process
            if followup_text:
                followup_text = f"{followup_text}{photo_info}\n\n[Фото в base64 (data:image/jpeg;base64):\n{photo_base64}]"
            else:
                followup_text = f"Користувач надіслав фото.{photo_info}\n\n[Фото в base64 (data:image/jpeg;base64):\n{photo_base64}]"
            
            await send_status_update(message, "📸 Фото оброблено, відправляю агенту...")
            logger.info(f"Processing photo follow-up: {photo.width}x{photo.height}, {len(photo_bytes)} bytes")
        except Exception as e:
            logger.exception("Error processing photo")
            followup_text = f"{followup_text}\n\n[Помилка при обробці фото: {str(e)}]" if followup_text else f"Користувач надіслав фото, але сталася помилка при обробці: {str(e)}"

    if not followup_text.strip():
        await message.reply(
            "⚠️ Повідомлення порожнє. Будь ласка, надішліть текст або фото з описом."
        )
        return

    try:
        # Check agent status first to know if it's already finished
        initial_status = await cursor_client.get_agent_status(agent_id)
        initial_run_status = initial_status.status
        
        # Add follow-up to the agent
        await cursor_client.add_followup(agent_id, followup_text)
        await send_status_update(message, "✅ Повідомлення відправлено агенту")
        
        # Create status callback for progress updates
        async def status_callback(elapsed: float, status: RunStatus) -> None:
            if elapsed >= 10:
                status_text = {
                    RunStatus.RUNNING: "⏳ Агент обробляє ваш запит...",
                    RunStatus.CREATING: "🔄 Агент створюється...",
                    RunStatus.EXPIRED: "⚠️ Агент застарів...",
                }.get(status, "⏳ Агент працює...")
                await send_status_update(message, f"{status_text} (прошло {int(elapsed)}с)")
        
        # After follow-up, agent status changes to RUNNING (if it was FINISHED)
        # Wait for agent to complete with new response
        await send_status_update(message, "⏳ Очікую відповідь від агента...")
        
        # Pass initial status to detect transition from FINISHED to RUNNING
        completed_run = await cursor_client.wait_agent_completion(
            agent_id, 
            initial_status=initial_run_status,
            status_callback=status_callback
        )
        
        if completed_run.output:
            await message.reply(completed_run.output, parse_mode="Markdown")
        else:
            # Try to get conversation to see latest response
            try:
                messages = await cursor_client.get_agent_conversation(agent_id)
                assistant_messages = [
                    msg.get("text", "") 
                    for msg in messages 
                    if msg.get("type") == "assistant_message"
                ]
                if assistant_messages:
                    latest_response = assistant_messages[-1]
                    await message.reply(latest_response, parse_mode="Markdown")
                else:
                    await message.reply("✅ Повідомлення відправлено. Агент обробляє ваш запит...")
            except Exception as e:
                logger.warning(f"Failed to get conversation after follow-up: {e}")
                await message.reply("✅ Повідомлення відправлено. Агент обробляє ваш запит...")
    except CursorTimeoutError:
        await message.reply(
            "⏱ Операція зайняла занадто багато часу. "
            "Спробуйте спростити відповідь або повторити спробу пізніше."
        )
    except CursorAPIError as e:
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при додаванні follow-up:\n\n{error_msg}",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_followup")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}",
            parse_mode=None,
        )


async def handle_agents(message: types.Message) -> None:
    """
    Handle /agents command - list active agents.

    Args:
        message: Telegram message
    """
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        agents = await cursor_client.list_agents(limit=10)
        
        if not agents:
            await message.reply(
                "📋 **Список агентів:**\n\n"
                "Активних агентів не знайдено.\n\n"
                "Використайте /plan або /ask для створення нового агента."
            )
            return

        # Filter agents by status - show RUNNING and FINISHED
        active_agents = [
            agent for agent in agents 
            if agent.get("status") in ["CREATING", "RUNNING", "FINISHED"]
        ]

        if not active_agents:
            await message.reply(
                "📋 **Список агентів:**\n\n"
                "Активних агентів не знайдено.\n\n"
                "Використайте /plan або /ask для створення нового агента."
            )
            return

        agent_list = "📋 **Активні агенти:**\n\n"
        keyboard_buttons = []

        for idx, agent in enumerate(active_agents[:10], 1):
            agent_id = agent.get("id", "unknown")
            name = agent.get("name", "Без назви")
            status = agent.get("status", "UNKNOWN")
            
            # Map status to emoji
            status_emoji = {
                "CREATING": "🔄",
                "RUNNING": "⚙️",
                "FINISHED": "✅",
            }.get(status, "❓")
            
            # Format status in Ukrainian
            status_ua = {
                "CREATING": "створюється",
                "RUNNING": "працює",
                "FINISHED": "завершено",
            }.get(status, status.lower())
            
            short_id = agent_id[:12] + "..." if len(agent_id) > 12 else agent_id
            agent_list += f"{idx}. {status_emoji} **{name}**\n"
            agent_list += f"   Статус: {status_ua}\n"
            agent_list += f"   ID: `{short_id}`\n\n"

            # Create inline button for each agent
            button_text = f"{status_emoji} {name[:30]}"
            keyboard_buttons.append(
                [InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_agent_{idx}"
                )]
            )

        agent_list += "**Натисніть на агента для вибору та перегляду історії:**\n\n"
        agent_list += "При виборі агента ви побачите історію розмови та зможете продовжити роботу з ним."

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Store agents list for callback handler
        if not hasattr(handle_agents, '_agents_cache'):
            handle_agents._agents_cache = {}
        handle_agents._agents_cache[message.from_user.id] = active_agents[:10]

        await message.reply(agent_list, parse_mode="Markdown", reply_markup=keyboard)
    except CursorAPIError as e:
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при отриманні списку агентів:\n\n{error_msg}",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_agents")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}",
            parse_mode=None,
        )


async def handle_agent_callback(callback: CallbackQuery) -> None:
    """
    Handle agent selection callback from inline button.

    Args:
        callback: Callback query from inline keyboard
    """
    # Answer callback immediately to prevent timeout
    # If callback is already expired, ignore the error
    try:
        await callback.answer()
    except Exception:
        # Callback might be expired, but continue processing anyway
        logger.warning("Failed to answer callback query (might be expired), continuing anyway")

    # Extract agent number from callback_data (format: "select_agent_1")
    try:
        agent_number_str = callback.data.replace("select_agent_", "")
        agent_number = int(agent_number_str)
    except (ValueError, IndexError):
        await callback.message.reply("❌ Помилка: невірний формат даних.")
        return

    # Get cached agents list
    if not hasattr(handle_agents, '_agents_cache'):
        await callback.message.reply("❌ Список агентів не знайдено. Використайте /agents для оновлення.")
        return

    agents = handle_agents._agents_cache.get(callback.from_user.id)
    if not agents:
        await callback.message.reply("❌ Список агентів не знайдено. Використайте /agents для оновлення.")
        return

    if agent_number < 1 or agent_number > len(agents):
        await callback.message.reply(
            f"❌ Невірний номер. Доступно агентів: {len(agents)}\n\n"
            "Використайте /agents для перегляду списку."
        )
        return

    selected_agent = agents[agent_number - 1]
    agent_id = selected_agent.get("id")
    name = selected_agent.get("name", "Без назви")
    status = selected_agent.get("status", "UNKNOWN")

    # Set as last agent for follow-up
    set_last_agent_id(callback.from_user.id, agent_id)

    status_ua = {
        "CREATING": "створюється",
        "RUNNING": "працює",
        "FINISHED": "завершено",
    }.get(status, status.lower())

    # Get conversation history
    try:
        await callback.message.bot.send_chat_action(callback.message.chat.id, "typing")
        messages = await cursor_client.get_agent_conversation(agent_id)
        
        # Format conversation history
        history_text = f"✅ **Вибрано агента:**\n\n"
        history_text += f"**{name}**\n"
        history_text += f"Статус: {status_ua}\n"
        history_text += f"ID: `{agent_id}`\n\n"
        
        if messages:
            history_text += "📜 **Історія розмови:**\n\n"
            
            # Limit to last 10 messages to avoid too long messages
            recent_messages = messages[-10:] if len(messages) > 10 else messages
            
            for msg in recent_messages:
                msg_type = msg.get("type", "unknown")
                msg_text = msg.get("text", "")
                
                if msg_type == "user_message":
                    history_text += f"👤 **Ви:**\n{msg_text}\n\n"
                elif msg_type == "assistant_message":
                    # Truncate long messages
                    if len(msg_text) > 500:
                        msg_text = msg_text[:500] + "..."
                    history_text += f"🤖 **Агент:**\n{msg_text}\n\n"
            
            if len(messages) > 10:
                history_text += f"\n_... (показано останні 10 з {len(messages)} повідомлень)_\n"
        else:
            history_text += "📜 Історія розмови порожня.\n"
        
        history_text += "\n💬 Тепер ви можете відправляти текстові повідомлення або фото для follow-up до цього агента."
        
        await callback.message.reply(history_text, parse_mode="Markdown")
    except CursorAPIError as e:
        # If conversation fails, still show agent info
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await callback.message.reply(
            f"✅ Вибрано агента:\n\n"
            f"**{name}**\n"
            f"Статус: {status_ua}\n"
            f"ID: `{agent_id}`\n\n"
            f"⚠️ Не вдалося завантажити історію: {error_msg}\n\n"
            f"Тепер ви можете відправляти текстові повідомлення або фото для follow-up до цього агента.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Error getting conversation history")
        await callback.message.reply(
            f"✅ Вибрано агента:\n\n"
            f"**{name}**\n"
            f"Статус: {status_ua}\n"
            f"ID: `{agent_id}`\n\n"
            f"⚠️ Помилка при завантаженні історії: {str(e)}\n\n"
            f"Тепер ви можете відправляти текстові повідомлення або фото для follow-up до цього агента.",
            parse_mode="Markdown"
        )


async def handle_help(message: types.Message) -> None:
    """
    Handle /help command.

    Args:
        message: Telegram message
    """
    help_text = (
        "📖 **Довідка по командах:**\n\n"
        "**Репозиторії:**\n"
        "`/repos` - показати список доступних репозиторіїв (улюблені першими)\n"
        "`/favrepos` - показати тільки улюблені репозиторії для швидкого вибору\n"
        "`/setrepo <номер>` - вибрати репозиторій для роботи\n\n"
        "**Улюблені репозиторії:**\n"
        "Після вибору репозиторію через `/repos` або `/setrepo` ви можете додати його до улюблених.\n"
        "Улюблені репозиторії відображаються першими у списку `/repos` з маркером ⭐.\n"
        "Використайте `/favrepos` для швидкого вибору з улюблених без прокрутки всього списку.\n\n"
        "**Робота з агентами:**\n"
        "`/plan <текст задачі>`\n"
        "Створює агента та отримує покроковий план рішення.\n\n"
        "`/ask <текст>`\n"
        "Створює агента та отримує уточнюючі питання від Cursor.\n\n"
        "`/solve <текст>`\n"
        "Створює агента для генерації коду.\n\n"
        "`/agents`\n"
        "Показує список активних агентів. При виборі агента відображається історія розмови.\n"
        "Дозволяє продовжити роботу з існуючим агентом замість створення нового.\n\n"
        "**Покроковий алгоритм роботи:**\n"
        "1. Викличте `/repos`, щоб перевірити або змінити репозиторій (за потреби).\n"
        "2. Створіть агента через `/plan <задача>` або `/ask <задача>`.\n"
        "3. За потреби перегляньте всіх агентів через `/agents` та виберіть потрібного.\n"
        "4. Після створення або вибору агента відправляйте звичайні текстові повідомлення або фото (без `/`),\n"
        "   щоб додавати follow-up інструкції.\n"
        "5. Читайте відповіді агента та за потреби уточнюйте деталі новими повідомленнями або фото.\n\n"
        "**Відправка фото:**\n"
        "Ви можете відправляти фото агентам як follow-up повідомлення. Фото буде конвертовано та передано агенту.\n"
        "Можна додати текст до фото - він буде включений у повідомлення.\n\n"
        "**Примітка:** Команди `/plan`, `/ask`, `/solve` вимагають вказання тексту задачі."
    )
    await message.reply(help_text, parse_mode="Markdown")


async def handle_repos(message: types.Message) -> None:
    """
    Handle /repos command - show available repositories with clickable buttons.
    Shows favorites first, then all repositories.

    Args:
        message: Telegram message
    """
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        repos = await cursor_client.get_available_repositories()
        if not repos:
            await message.reply(
                "❌ Не знайдено доступних репозиторіїв.\n\n"
                "Перевірте налаштування Cursor GitHub App."
            )
            return

        selected_repo = get_selected_repository(message.from_user.id)
        favorite_repos = get_favorite_repositories(message.from_user.id)

        # Separate favorites and other repos
        favorite_list = []
        other_list = []
        
        for repo in repos:
            repo_url = repo.get("repository", "")
            if repo_url in favorite_repos:
                favorite_list.append(repo)
            else:
                other_list.append(repo)

        repo_list = "📂 **Доступні репозиторії:**\n\n"
        keyboard_buttons = []

        # Show favorites first
        if favorite_list:
            repo_list += "⭐ **Улюблені репозиторії:**\n\n"
            for repo in favorite_list:
                owner = repo.get("owner", "unknown")
                name = repo.get("name", "unknown")
                repo_url = repo.get("repository", "")
                marker = "✅" if repo_url == selected_repo else "⭐"
                display_name = f"{owner}/{name}"
                
                # Find index in original repos list
                repo_idx = repos.index(repo) + 1
                
                # Create inline button for each repository
                button_text = f"{marker} {display_name}"
                keyboard_buttons.append(
                    [InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"select_repo_{repo_idx}"
                    )]
                )
            
            if other_list:
                repo_list += "\n📋 **Інші репозиторії:**\n\n"

        # Show other repositories
        for repo in other_list:
            owner = repo.get("owner", "unknown")
            name = repo.get("name", "unknown")
            repo_url = repo.get("repository", "")
            marker = "✅" if repo_url == selected_repo else ""
            display_name = f"{owner}/{name}"
            
            # Find index in original repos list
            repo_idx = repos.index(repo) + 1
            
            # Create inline button for each repository
            button_text = f"{marker} {display_name}".strip()
            keyboard_buttons.append(
                [InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_repo_{repo_idx}"
                )]
            )

        repo_list += "\n"

        if selected_repo:
            repo_list += f"**Поточний репозиторій:**\n`{selected_repo}`\n\n"
        else:
            repo_list += "⚠️ Репозиторій не вибрано. Натисніть на репозиторій вище.\n\n"
        
        repo_list += "💡 Натисніть на репозиторій для вибору або використайте кнопки ⭐/➖ для додавання/видалення з улюблених."

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.reply(repo_list, parse_mode="Markdown", reply_markup=keyboard)
    except CursorAPIError as e:
        # Rate limit errors already have user-friendly messages
        if e.status_code == 429:
            error_msg = str(e)
        else:
            error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при отриманні списку репозиторіїв:\n\n{error_msg}",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_repos")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}",
            parse_mode=None,
        )


async def handle_setrepo(message: types.Message) -> None:
    """
    Handle /setrepo command - set repository for work.

    Args:
        message: Telegram message
    """
    text = message.text or ""
    parts = text.replace("/setrepo", "").strip().split()
    
    if not parts or not parts[0].isdigit():
        await message.reply(
            "Будь ласка, вкажіть номер репозиторію або використайте `/repos` для вибору через кнопки.\n\n"
            "**Приклад:**\n"
            "1. Подивіться список: `/repos`\n"
            "2. Натисніть на потрібний репозиторій або введіть: `/setrepo 1`"
        )
        return

    repo_number = int(parts[0])
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        repos = await cursor_client.get_available_repositories()
        if not repos:
            await message.reply("❌ Не знайдено доступних репозиторіїв.")
            return

        if repo_number < 1 or repo_number > len(repos):
            await message.reply(
                f"❌ Невірний номер. Доступно репозиторіїв: {len(repos)}\n\n"
                "Використайте `/repos` для перегляду списку."
            )
            return

        selected_repo = repos[repo_number - 1]
        await _set_repository_for_user(message.from_user.id, selected_repo, message)
    except CursorAPIError as e:
        error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при отриманні списку репозиторіїв:\n\n{error_msg}",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_setrepo")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}",
            parse_mode=None,
        )


async def handle_repo_callback(callback: CallbackQuery) -> None:
    """
    Handle repository selection callback from inline button.
    Also handles favorite toggle actions.

    Args:
        callback: Callback query from inline button
    """
    # Answer callback immediately to prevent timeout
    # If callback is already expired, ignore the error
    try:
        await callback.answer()
    except Exception:
        # Callback might be expired, but continue processing anyway
        logger.warning("Failed to answer callback query (might be expired), continuing anyway")

    # Check if it's a favorite toggle action
    if callback.data.startswith("fav_repo_"):
        # Toggle favorite
        try:
            repo_number = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.message.reply("❌ Помилка: невірний формат даних.")
            return

        await callback.message.bot.send_chat_action(callback.message.chat.id, "typing")

        try:
            repos = await cursor_client.get_available_repositories()
            if not repos or repo_number < 1 or repo_number > len(repos):
                await callback.message.reply("❌ Невірний номер репозиторію.")
                return

            selected_repo = repos[repo_number - 1]
            repo_url = selected_repo.get("repository", "")
            owner = selected_repo.get("owner", "unknown")
            name = selected_repo.get("name", "unknown")

            if is_favorite_repository(callback.from_user.id, repo_url):
                remove_favorite_repository(callback.from_user.id, repo_url)
                await callback.message.reply(
                    f"➖ Репозиторій [{owner}/{name}]({repo_url}) видалено з улюблених.",
                    parse_mode="Markdown"
                )
            else:
                add_favorite_repository(callback.from_user.id, repo_url)
                await callback.message.reply(
                    f"⭐ Репозиторій [{owner}/{name}]({repo_url}) додано до улюблених.",
                    parse_mode="Markdown"
                )
            
            # Refresh the repos list
            await handle_repos(callback.message)
        except Exception as e:
            logger.exception("Error toggling favorite")
            await callback.message.reply(f"❌ Помилка: {str(e)}")
        return

    # Original repository selection logic
    try:
        repo_number = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.message.reply("❌ Помилка: невірний формат даних.")
        return

    await callback.message.bot.send_chat_action(callback.message.chat.id, "typing")

    try:
        repos = await cursor_client.get_available_repositories()
        if not repos:
            await callback.message.reply("❌ Не знайдено доступних репозиторіїв.")
            return

        if repo_number < 1 or repo_number > len(repos):
            await callback.message.reply(
                f"❌ Невірний номер репозиторію."
            )
            return

        selected_repo = repos[repo_number - 1]
        repo_url = selected_repo.get("repository", "")
        owner = selected_repo.get("owner", "unknown")
        name = selected_repo.get("name", "unknown")
        
        # Set repository
        await _set_repository_for_user(
            callback.from_user.id, selected_repo, callback.message
        )
        
        # Show favorite toggle button
        is_fav = is_favorite_repository(callback.from_user.id, repo_url)
        fav_button_text = "➖ Видалити з улюблених" if is_fav else "⭐ Додати до улюблених"
        fav_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=fav_button_text,
                callback_data=f"fav_repo_{repo_number}"
            )
        ]])
        
        await callback.message.reply(
            f"💡 Використайте кнопку нижче для управління улюбленими:",
            reply_markup=fav_keyboard
        )
    except CursorAPIError as e:
        # Rate limit errors already have user-friendly messages
        if e.status_code == 429:
            error_msg = str(e)
        else:
            error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await callback.message.reply(
            f"❌ Помилка при виборі репозиторію:\n\n{error_msg}",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_repo_callback")
        await callback.message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}",
            parse_mode=None,
        )


async def _set_repository_for_user(
    user_id: int, repo: dict, message: types.Message
) -> None:
    """
    Set repository for user and send confirmation.

    Args:
        user_id: Telegram user ID
        repo: Repository dictionary
        message: Message object for reply
    """
    repo_url = repo.get("repository")
    owner = repo.get("owner")
    name = repo.get("name")

    if repo_url:
        set_selected_repository(user_id, repo_url)
        await message.reply(
            f"✅ Репозиторій вибрано:\n\n"
            f"[{owner}/{name}]({repo_url})\n\n"
            f"Тепер всі команди будуть використовувати цей репозиторій.",
            parse_mode="Markdown",
        )
    else:
        await message.reply("❌ Помилка: репозиторій не містить URL.")


async def handle_favrepos(message: types.Message) -> None:
    """
    Handle /favrepos command - show only favorite repositories for quick selection.

    Args:
        message: Telegram message
    """
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        repos = await cursor_client.get_available_repositories()
        if not repos:
            await message.reply(
                "❌ Не знайдено доступних репозиторіїв.\n\n"
                "Перевірте налаштування Cursor GitHub App."
            )
            return

        selected_repo = get_selected_repository(message.from_user.id)
        favorite_repos = get_favorite_repositories(message.from_user.id)

        if not favorite_repos:
            await message.reply(
                "⭐ **Улюблені репозиторії:**\n\n"
                "У вас поки немає улюблених репозиторіїв.\n\n"
                "**Як додати репозиторій до улюблених:**\n"
                "1. Використайте `/repos` для перегляду всіх репозиторіїв\n"
                "2. Виберіть репозиторій\n"
                "3. Натисніть кнопку \"⭐ Додати до улюблених\" після вибору"
            )
            return

        # Filter only favorite repositories
        favorite_list = [repo for repo in repos if repo.get("repository", "") in favorite_repos]

        repo_list = "⭐ **Улюблені репозиторії:**\n\n"
        repo_list += "Натисніть на репозиторій для вибору:\n\n"
        keyboard_buttons = []

        for repo in favorite_list:
            owner = repo.get("owner", "unknown")
            name = repo.get("name", "unknown")
            repo_url = repo.get("repository", "")
            marker = "✅" if repo_url == selected_repo else "⭐"
            display_name = f"{owner}/{name}"
            
            # Find index in original repos list
            repo_idx = repos.index(repo) + 1
            
            # Create inline button for each repository
            button_text = f"{marker} {display_name}"
            keyboard_buttons.append(
                [InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_repo_{repo_idx}"
                )]
            )

        repo_list += "\n"

        if selected_repo:
            repo_list += f"**Поточний репозиторій:**\n`{selected_repo}`\n\n"
        else:
            repo_list += "⚠️ Репозиторій не вибрано. Натисніть на репозиторій вище.\n\n"
        
        repo_list += "💡 Після вибору репозиторію ви зможете керувати улюбленими через кнопки."

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.reply(repo_list, parse_mode="Markdown", reply_markup=keyboard)
    except CursorAPIError as e:
        # Rate limit errors already have user-friendly messages
        if e.status_code == 429:
            error_msg = str(e)
        else:
            error_msg = str(e).replace("**", "").replace("*", "").replace("`", "")
        await message.reply(
            f"❌ Помилка при отриманні списку репозиторіїв:\n\n{error_msg}",
            parse_mode=None,
        )
    except Exception as e:
        logger.exception("Unexpected error in handle_favrepos")
        await message.reply(
            f"❌ Сталася неочікувана помилка:\n{str(e)}",
            parse_mode=None,
        )

