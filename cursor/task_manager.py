"""Task manager for executing Cursor API operations."""

import logging
from typing import Awaitable, Callable, Optional

from cursor.client import CursorClient, CursorAPIError, CursorTimeoutError, RunStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """Manager for executing Cursor tasks with high-level methods."""

    def __init__(self, client: CursorClient) -> None:
        """
        Initialize task manager.

        Args:
            client: CursorClient instance
        """
        self.client = client

    async def run_plan(
        self, 
        text: str, 
        repository_url: str = None,
        status_callback: Optional[Callable[[float, RunStatus], Awaitable[None]]] = None
    ) -> tuple[str, str]:
        """
        Create a task and run it with 'plan' action.

        Args:
            text: Task description
            repository_url: Optional repository URL (if None, will be auto-selected)
            status_callback: Optional callback function(elapsed_seconds, status) for status updates

        Returns:
            Formatted plan text

        Raises:
            CursorAPIError: If API request fails
            CursorTimeoutError: If operation times out
        """
        logger.info(f"Running plan for text: {text[:100]}...")

        try:
            # Create task (agent) with plan action - the agent starts working immediately
            task = await self.client.create_task(
                text=text, repository_url=repository_url, action="plan"
            )

            # Wait for agent to complete
            completed_run = await self.client.wait_agent_completion(
                task.id, 
                status_callback=status_callback
            )

            if not completed_run.output:
                return task.id, "План не був згенерований. Спробуйте ще раз."

            return task.id, self._format_plan(completed_run.output)
        except (CursorAPIError, CursorTimeoutError) as e:
            logger.error(f"Error in run_plan: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in run_plan: {str(e)}")
            raise CursorAPIError(f"Неочікувана помилка: {str(e)}") from e

    async def run_ask(
        self, 
        text: str, 
        repository_url: str = None,
        status_callback: Optional[Callable[[float, RunStatus], Awaitable[None]]] = None,
        is_non_technical: bool = False,
        reuse_agent_id: Optional[str] = None
    ) -> tuple[str, str]:
        """
        Create a task and run it with 'ask' action.
        Optionally reuses existing agent if provided and still active.

        Args:
            text: Task description
            repository_url: Optional repository URL (if None, will be auto-selected)
            status_callback: Optional callback function(elapsed_seconds, status) for status updates
            is_non_technical: If True, add prompt for non-technical users (testers, managers)
            reuse_agent_id: Optional existing agent ID to reuse instead of creating new one

        Returns:
            Formatted answer text

        Raises:
            CursorAPIError: If API request fails
            CursorTimeoutError: If operation times out
        """
        logger.info(f"Running ask for text: {text[:100]}... (non-technical: {is_non_technical}, reuse_agent: {reuse_agent_id})")

        try:
            # Add non-technical prompt prefix if needed
            prompt_text = text
            if is_non_technical:
                non_tech_prefix = (
                    "Важливо: Відповідай як не технічному спеціалісту. "
                    "Користувач - тестувальник або менеджер проекту. "
                    "Використовуй просту мову, уникай технічного жаргону, "
                    "пояснюй терміни якщо використовуєш їх. "
                    "Фокусуйся на практичних аспектах та бізнес-логіці, а не на деталях реалізації. "
                    "Твоя мета - відповісти на питання користувача та надати корисну інформацію про проект, "
                    "а не задавати уточнюючі питання. Будь корисним джерелом документації. "
                    "Обмеж свою відповідь до 2000 символів.\n\n"
                )
                prompt_text = f"{non_tech_prefix}Питання: {text}"
            else:
                # For technical mode, also add "Питання:" prefix for clarity
                prompt_text = f"Питання: {text}"

            # Check if we can reuse existing agent (only for group chats)
            if reuse_agent_id:
                try:
                    agent_status = await self.client.get_agent_status(reuse_agent_id)
                    # Reuse agent if it's not expired and not failed
                    if agent_status.status not in (RunStatus.EXPIRED, RunStatus.FAILED):
                        logger.info(f"Reusing existing agent {reuse_agent_id} (status: {agent_status.status})")
                        
                        # Get conversation BEFORE follow-up to track new messages
                        assistant_count_before = 0
                        try:
                            messages_before = await self.client.get_agent_conversation(reuse_agent_id)
                            assistant_count_before = len([
                                msg for msg in messages_before 
                                if msg.get("type") == "assistant_message"
                            ])
                            logger.info(
                                f"🔍 [REUSE_DEBUG] Before follow-up: {assistant_count_before} assistant messages. "
                                f"Last message preview: {messages_before[-1].get('text', '')[:100] if messages_before else 'N/A'}..."
                            )
                        except Exception as e:
                            logger.warning(f"Failed to get conversation before follow-up in reuse: {e}")
                        
                        # Add follow-up to existing agent
                        await self.client.add_followup(reuse_agent_id, prompt_text)
                        
                        # Wait for agent to complete, passing count_before to track new messages
                        completed_run = await self.client.wait_agent_completion(
                            reuse_agent_id,
                            initial_status=agent_status.status,
                            status_callback=status_callback,
                            assistant_messages_count_before=assistant_count_before
                        )
                        
                        if not completed_run.output:
                            return reuse_agent_id, "Відповідь не була згенерована. Спробуйте ще раз."
                        
                        return reuse_agent_id, self._format_answer(completed_run.output)
                    else:
                        logger.info(f"Agent {reuse_agent_id} is {agent_status.status}, creating new agent")
                except CursorAPIError as e:
                    # If agent not found or error, create new one
                    logger.warning(f"Cannot reuse agent {reuse_agent_id}: {e}, creating new agent")

            # Create new task (agent) with ask action - the agent starts working immediately
            task = await self.client.create_task(
                text=prompt_text, repository_url=repository_url, action="ask"
            )

            # Wait for agent to complete
            completed_run = await self.client.wait_agent_completion(
                task.id,
                status_callback=status_callback
            )

            if not completed_run.output:
                return task.id, "Відповідь не була згенерована. Спробуйте ще раз."

            return task.id, self._format_answer(completed_run.output)
        except (CursorAPIError, CursorTimeoutError) as e:
            logger.error(f"Error in run_ask: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in run_ask: {str(e)}")
            raise CursorAPIError(f"Неочікувана помилка: {str(e)}") from e

    async def run_solve(
        self, 
        text: str, 
        repository_url: str = None,
        status_callback: Optional[Callable[[float, RunStatus], Awaitable[None]]] = None
    ) -> tuple[str, str]:
        """
        Create a task and run it with 'code_generate' action.

        Args:
            text: Task description
            repository_url: Optional repository URL (if None, will be auto-selected)
            status_callback: Optional callback function(elapsed_seconds, status) for status updates

        Returns:
            Tuple of (agent_id, formatted generated code text)

        Raises:
            CursorAPIError: If API request fails
            CursorTimeoutError: If operation times out
        """
        logger.info(f"Running solve for text: {text[:100]}...")

        try:
            # Create task (agent) with code_generate action - the agent starts working immediately
            task = await self.client.create_task(
                text=text, repository_url=repository_url, action="code_generate"
            )

            # Wait for agent to complete
            completed_run = await self.client.wait_agent_completion(
                task.id,
                status_callback=status_callback
            )

            if not completed_run.output:
                base_text = (
                    "Код не був згенерований. Спробуйте ще раз або спростіть опис задачі."
                )
            else:
                code_text = completed_run.output
                # Add header if not present
                if not code_text.strip().startswith("💻"):
                    code_text = f"💻 **Згенерований код / рішення:**\n\n{code_text}"
                base_text = code_text

            # Add note about bumping minor version
            suffix = (
                "\n\n🔁 Після внесення змін не забудь оновити мінорну версію проєкту "
                "(наприклад, з `0.0.1` до `0.0.2`)."
            )

            return task.id, base_text + suffix
        except (CursorAPIError, CursorTimeoutError) as e:
            logger.error(f"Error in run_solve: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in run_solve: {str(e)}")
            raise CursorAPIError(f"Неочікувана помилка: {str(e)}") from e

    @staticmethod
    def _extract_title(text: str, max_length: int = 50) -> str:
        """
        Extract a title from text.

        Args:
            text: Full text
            max_length: Maximum title length

        Returns:
            Extracted title
        """
        if not text:
            return "Untitled Task"

        # Take first line or first max_length characters
        lines = text.strip().split("\n")
        title = lines[0].strip()

        if len(title) > max_length:
            title = title[:max_length].rsplit(" ", 1)[0] + "..."

        return title or "Untitled Task"

    @staticmethod
    def _format_plan(plan_text: str) -> str:
        """
        Format plan text for Telegram.

        Args:
            plan_text: Raw plan text

        Returns:
            Formatted plan text
        """
        # Add header if not present
        if not plan_text.strip().startswith("📋"):
            plan_text = f"📋 **План рішення:**\n\n{plan_text}"

        # Always add note about bumping minor version
        suffix = (
            "\n\n🔁 Після внесення змін онови мінорну версію проєкту "
            "(наприклад, з `0.0.1` до `0.0.2`)."
        )
        return plan_text + suffix

    @staticmethod
    def _format_answer(answer_text: str) -> str:
        """
        Format answer text for Telegram.
        Truncates to Telegram message limit (4096 characters).

        Args:
            answer_text: Raw answer text

        Returns:
            Formatted answer text (truncated if needed)
        """
        # Telegram message limit is 4096 characters
        # Leave some margin for formatting and truncation notice
        MAX_LENGTH = 4000
        
        # Add header if not present
        header = "💡 **Відповідь:**\n\n"
        if answer_text.strip().startswith("💡") or answer_text.strip().startswith("📖"):
            header = ""
            formatted_text = answer_text
        else:
            formatted_text = f"{header}{answer_text}"
        
        # Truncate if too long
        if len(formatted_text) > MAX_LENGTH:
            # Calculate available space for text (after header and truncation notice)
            truncation_notice = "\n\n_... (відповідь обрізана через обмеження Telegram)_"
            available_length = MAX_LENGTH - len(header) - len(truncation_notice)
            
            # Truncate the original text, trying to cut at paragraph boundary
            truncated_text = answer_text[:available_length]
            
            # Try to cut at last paragraph (double newline) or last newline
            if '\n\n' in truncated_text:
                truncated_text = truncated_text.rsplit('\n\n', 1)[0]
            elif '\n' in truncated_text:
                truncated_text = truncated_text.rsplit('\n', 1)[0]
            else:
                # If no newlines, cut at last space to avoid breaking words
                truncated_text = truncated_text.rsplit(' ', 1)[0]
            
            if header:
                formatted_text = f"{header}{truncated_text}{truncation_notice}"
            else:
                formatted_text = f"{truncated_text}{truncation_notice}"
            
            logger.info(f"Answer truncated from {len(answer_text)} to {len(formatted_text)} characters")
        
        return formatted_text

