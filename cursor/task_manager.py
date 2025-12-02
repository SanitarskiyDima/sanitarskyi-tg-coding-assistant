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
        status_callback: Optional[Callable[[float, RunStatus], Awaitable[None]]] = None
    ) -> tuple[str, str]:
        """
        Create a task and run it with 'ask' action.

        Args:
            text: Task description
            repository_url: Optional repository URL (if None, will be auto-selected)
            status_callback: Optional callback function(elapsed_seconds, status) for status updates

        Returns:
            Formatted questions text

        Raises:
            CursorAPIError: If API request fails
            CursorTimeoutError: If operation times out
        """
        logger.info(f"Running ask for text: {text[:100]}...")

        try:
            # Create task (agent) with ask action - the agent starts working immediately
            task = await self.client.create_task(
                text=text, repository_url=repository_url, action="ask"
            )

            # Wait for agent to complete
            completed_run = await self.client.wait_agent_completion(
                task.id,
                status_callback=status_callback
            )

            if not completed_run.output:
                return task.id, "Питання не були згенеровані. Спробуйте ще раз."

            return task.id, self._format_questions(completed_run.output)
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
    def _format_questions(questions_text: str) -> str:
        """
        Format questions text for Telegram.

        Args:
            questions_text: Raw questions text

        Returns:
            Formatted questions text
        """
        # Add header if not present
        if not questions_text.strip().startswith("❓"):
            return f"❓ **Уточнюючі питання:**\n\n{questions_text}"
        return questions_text

