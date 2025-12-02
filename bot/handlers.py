"""Telegram bot command handlers."""

import logging
from typing import Optional

from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from cursor.client import CursorAPIError, CursorTimeoutError, cursor_client
from cursor.task_manager import TaskManager
from bot.repository_manager import (
    get_selected_repository,
    set_selected_repository,
)
from bot.agent_manager import (
    get_last_agent_id,
    set_last_agent_id,
)

logger = logging.getLogger(__name__)


async def handle_plan(message: types.Message, task_manager: TaskManager) -> None:
    """
    Handle /plan command.

    Args:
        message: Telegram message
        task_manager: TaskManager instance
    """
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

    # Get selected repository for user
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        agent_id, result = await task_manager.run_plan(task_text, repository_url=selected_repo)
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


async def handle_ask(message: types.Message, task_manager: TaskManager) -> None:
    """
    Handle /ask command.

    Args:
        message: Telegram message
        task_manager: TaskManager instance
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

    # Get selected repository for user
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        agent_id, result = await task_manager.run_ask(task_text, repository_url=selected_repo)
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


async def handle_solve(message: types.Message, task_manager: TaskManager) -> None:
    """
    Handle /solve command - generate code solution for a task.

    Args:
        message: Telegram message
        task_manager: TaskManager instance
    """
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

    # Get selected repository for user
    selected_repo = get_selected_repository(message.from_user.id)

    try:
        agent_id, result = await task_manager.run_solve(
            task_text, repository_url=selected_repo
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
        "• `/setrepo <номер>` - вибрати репозиторій\n"
        "• `/plan <задача>` - отримати покроковий план рішення\n"
        "• `/ask <задача>` - отримати уточнюючі питання\n"
        "• `/solve <задача>` - згенерувати код для вирішення задачі\n"
        "• `/agents` - показати список активних агентів та їх історію\n\n"
        "**Приклади:**\n"
        "• `/repos` - подивитися доступні репозиторії\n"
        "• `/setrepo 1` - вибрати перший репозиторій\n"
        "• `/plan Створити REST API на FastAPI`\n"
        "• `/ask Як оптимізувати SQL запити?`\n"
        "• `/agents` - переглянути активних агентів та продовжити роботу\n\n"
        "**Як працювати з агентами:**\n"
        "1. Створіть агента через `/plan` або `/ask`\n"
        "2. Перегляньте список через `/agents`\n"
        "3. Виберіть агента для перегляду історії\n"
        "4. Відправте текстове повідомлення для follow-up"
    )
    await message.reply(welcome_text, parse_mode="Markdown")


async def handle_followup(message: types.Message) -> None:
    """
    Handle follow-up text messages (not commands) as responses to agent questions.

    Args:
        message: Telegram message
    """
    text = message.text or ""
    if not text.strip():
        return

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

    try:
        # Check agent status first to know if it's already finished
        initial_status = await cursor_client.get_agent_status(agent_id)
        initial_run_status = initial_status.status
        
        # Add follow-up to the agent
        await cursor_client.add_followup(agent_id, text)
        
        # After follow-up, agent status changes to RUNNING (if it was FINISHED)
        # Wait for agent to complete with new response
        await message.reply("⏳ Відправляю ваше повідомлення агенту. Очікую відповідь...")
        
        # Pass initial status to detect transition from FINISHED to RUNNING
        completed_run = await cursor_client.wait_agent_completion(
            agent_id, 
            initial_status=initial_run_status
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
    await callback.answer()

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
        
        history_text += "\n💬 Тепер ви можете відправляти текстові повідомлення для follow-up до цього агента."
        
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
            f"Тепер ви можете відправляти текстові повідомлення для follow-up до цього агента.",
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
            f"Тепер ви можете відправляти текстові повідомлення для follow-up до цього агента.",
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
        "`/repos` - показати список доступних репозиторіїв\n"
        "`/setrepo <номер>` - вибрати репозиторій для роботи\n\n"
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
        "4. Після створення або вибору агента відправляйте звичайні текстові повідомлення (без `/`),\n"
        "   щоб додавати follow-up інструкції.\n"
        "5. Читайте відповіді агента та за потреби уточнюйте деталі новими повідомленнями.\n\n"
        "**Примітка:** Команди `/plan`, `/ask`, `/solve` вимагають вказання тексту задачі."
    )
    await message.reply(help_text, parse_mode="Markdown")


async def handle_repos(message: types.Message) -> None:
    """
    Handle /repos command - show available repositories with clickable buttons.

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

        repo_list = "📂 **Доступні репозиторії:**\n\n"
        repo_list += "Натисніть на репозиторій для вибору:\n\n"
        keyboard_buttons = []

        for idx, repo in enumerate(repos, 1):
            owner = repo.get("owner", "unknown")
            name = repo.get("name", "unknown")
            repo_url = repo.get("repository", "")
            marker = "✅" if repo_url == selected_repo else ""
            display_name = f"{owner}/{name}"
            
            # Create inline button for each repository
            button_text = f"{marker} {display_name}".strip()
            keyboard_buttons.append(
                [InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"select_repo_{idx}"
                )]
            )

        repo_list += "\n"

        if selected_repo:
            repo_list += f"**Поточний репозиторій:**\n`{selected_repo}`"
        else:
            repo_list += "⚠️ Репозиторій не вибрано. Натисніть на репозиторій вище."

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

    Args:
        callback: Callback query from inline button
    """
    await callback.answer()

    # Extract repository number from callback_data (format: "select_repo_1")
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
        await _set_repository_for_user(
            callback.from_user.id, selected_repo, callback.message
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

