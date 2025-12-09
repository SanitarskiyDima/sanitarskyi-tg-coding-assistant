"""HTTP client for Cursor Cloud Agent API."""

import asyncio
import base64
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx

from cursor.schemas import (
    CreateRunRequest,
    CreateTaskRequest,
    RunResponse,
    RunStatus,
    TaskResponse,
)
from settings import settings as app_settings

logger = logging.getLogger(__name__)


class CursorClientError(Exception):
    """Base exception for Cursor client errors."""

    pass


class CursorAPIError(CursorClientError):
    """Exception raised when Cursor API returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        """
        Initialize API error.

        Args:
            message: Error message
            status_code: HTTP status code if available
        """
        super().__init__(message)
        self.status_code = status_code


class CursorTimeoutError(CursorClientError):
    """Exception raised when operation times out."""

    pass


class CursorClient:
    """Client for interacting with Cursor Cloud Agent API."""

    def __init__(self, api_key: str, base_url: str) -> None:
        """
        Initialize Cursor client.

        Args:
            api_key: Cursor API key
            base_url: Base URL for Cursor API
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        # Cursor API uses Basic Auth: -u API_KEY:
        auth_string = base64.b64encode(f"{api_key}:".encode()).decode()
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )
        # Cache for repositories (TTL: 60 seconds to respect rate limit of 1 req/min)
        self._repositories_cache: Optional[List[Dict[str, str]]] = None
        self._repositories_cache_time: float = 0.0
        self._repositories_cache_ttl: float = 60.0  # 60 seconds
        logger.info(f"Initialized CursorClient with base URL: {self.base_url}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_available_repositories(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """
        Get list of available repositories with caching.

        Args:
            use_cache: Whether to use cached data if available (default: True)

        Returns:
            List of repository dictionaries with owner, name, and repository URL

        Raises:
            CursorAPIError: If API request fails and no cached data available
        """
        current_time = time.time()
        
        # Check if we have valid cached data
        if use_cache and self._repositories_cache is not None:
            cache_age = current_time - self._repositories_cache_time
            if cache_age < self._repositories_cache_ttl:
                logger.debug(f"Using cached repositories (age: {cache_age:.1f}s)")
                return self._repositories_cache
        
        logger.debug("Fetching available repositories from API")
        try:
            response = await self.client.get("/repositories")
            response.raise_for_status()
            data = response.json()
            repositories = data.get("repositories", [])
            logger.info(f"Found {len(repositories)} available repositories")
            
            # Update cache
            self._repositories_cache = repositories
            self._repositories_cache_time = current_time
            
            return repositories
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            error_data = {}
            try:
                error_data = json.loads(error_text)
            except (json.JSONDecodeError, ValueError):
                pass
            
            # Check if it's a rate limit error
            if e.response.status_code == 429 or (
                "rate limit" in error_text.lower() or 
                error_data.get("error") == "Rate limit exceeded"
            ):
                # Try to use cached data if available
                if use_cache and self._repositories_cache is not None:
                    cache_age = current_time - self._repositories_cache_time
                    logger.warning(
                        f"Rate limit exceeded, using cached repositories "
                        f"(age: {cache_age:.1f}s, limit: {self._repositories_cache_ttl}s)"
                    )
                    return self._repositories_cache
                
                # No cache available, return user-friendly error
                error_msg = (
                    "⏱ Перевищено ліміт запитів до API.\n\n"
                    "API Cursor дозволяє лише 1 запит на хвилину для цього endpoint.\n\n"
                    "Спробуйте:\n"
                    "- Зачекати хвилину та повторити запит\n"
                    "- Використати вже вибраний репозиторій\n"
                    "- Звернутися до hi@cursor.com для збільшення ліміту"
                )
                logger.error(f"Rate limit exceeded: {error_text}")
                raise CursorAPIError(error_msg, status_code=429) from e
            
            error_msg = f"Не вдалося отримати список репозиторіїв: {error_text}"
            logger.error(error_msg)
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            # Try to use cached data if available
            if use_cache and self._repositories_cache is not None:
                cache_age = current_time - self._repositories_cache_time
                logger.warning(
                    f"Network error, using cached repositories "
                    f"(age: {cache_age:.1f}s)"
                )
                return self._repositories_cache
            
            error_msg = self._format_network_error(e, f"{self.base_url}/repositories")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e

    async def list_agents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List all cloud agents for the authenticated user.

        Args:
            limit: Number of agents to return (default: 20, max: 100)

        Returns:
            List of agent dictionaries

        Raises:
            CursorAPIError: If API request fails
        """
        logger.debug(f"Fetching list of agents (limit: {limit})")
        try:
            response = await self.client.get("/agents", params={"limit": min(limit, 100)})
            response.raise_for_status()
            data = response.json()
            agents = data.get("agents", [])
            logger.info(f"Found {len(agents)} agents")
            return agents
        except httpx.HTTPStatusError as e:
            error_msg = f"Не вдалося отримати список агентів: {e.response.text}"
            logger.error(error_msg)
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = self._format_network_error(e, f"{self.base_url}/agents")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e

    def _format_network_error(self, error: httpx.RequestError, endpoint: str) -> str:
        """
        Format network error message in Ukrainian.

        Args:
            error: Request error
            endpoint: API endpoint that failed

        Returns:
            Formatted error message
        """
        error_str = str(error)
        if "nodename nor servname provided" in error_str or "Could not resolve host" in error_str:
            return (
                "Не вдалося підключитися до Cursor API.\n\n"
                "Перевірте:\n"
                "- Правильність API_BASE в налаштуваннях (поточне значення: {})\n"
                "- Наявність інтернет-з'єднання\n"
                "- Доступність API сервера\n\n"
                "Endpoint: {}"
            ).format(self.base_url, endpoint)
        else:
            return "Помилка мережі: {}\n\nEndpoint: {}".format(error_str, endpoint)

    async def create_task(
        self, text: str, repository_url: str = None, action: str = None, model: str = None
    ) -> TaskResponse:
        """
        Create a new agent task in Cursor.

        Args:
            text: Task description/prompt text
            repository_url: Repository URL (required by API)
            action: Action type (plan, ask, code_generate)
            model: AI model to use (e.g., "gemini-3-pro", "claude-4-sonnet"). 
                   If None, uses default from settings.

        Returns:
            TaskResponse with created task information

        Raises:
            CursorAPIError: If API request fails
            httpx.RequestError: If network error occurs
        """
        if not repository_url:
            # Try to use default repository from settings first, then first available
            try:
                repos = await self.get_available_repositories()
                default_repo_url = app_settings.repository_url
                
                logger.info(f"Looking for default repository: {default_repo_url}")
                logger.debug(f"Available repositories: {[repo.get('repository') for repo in repos]}")
                
                if repos and len(repos) > 0:
                    # Check if default repository from settings is in the available list
                    # Support both full URL format (https://github.com/owner/repo) and short format (owner/repo)
                    default_repo_found = False
                    
                    # Normalize default repo URL for comparison
                    # Extract owner/repo from full URL if needed, or use as-is if already in owner/repo format
                    default_repo_normalized = default_repo_url
                    if default_repo_url.startswith("http"):
                        # Extract owner/repo from full URL
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(default_repo_url)
                            path_parts = parsed.path.strip("/").split("/")
                            if len(path_parts) >= 2:
                                default_repo_normalized = f"{path_parts[0]}/{path_parts[1]}"
                        except Exception:
                            pass
                    elif "/" in default_repo_url and not default_repo_url.startswith("http"):
                        # Already in owner/repo format, use as-is
                        default_repo_normalized = default_repo_url
                    
                    logger.debug(f"Normalized default repo: {default_repo_normalized}")
                    
                    for repo in repos:
                        repo_url = repo.get("repository", "")
                        owner = repo.get("owner", "")
                        name = repo.get("name", "")
                        
                        # Extract owner/repo from repo_url if it's a full URL
                        repo_normalized = f"{owner}/{name}" if owner and name else ""
                        if repo_url.startswith("http"):
                            try:
                                from urllib.parse import urlparse
                                parsed = urlparse(repo_url)
                                path_parts = parsed.path.strip("/").split("/")
                                if len(path_parts) >= 2:
                                    repo_normalized = f"{path_parts[0]}/{path_parts[1]}"
                            except Exception:
                                pass
                        
                        logger.debug(f"Comparing repo: {repo_url} (normalized: {repo_normalized}) with default: {default_repo_url} (normalized: {default_repo_normalized})")
                        
                        # Try multiple comparison methods
                        repo_match = False
                        match_reason = ""
                        
                        # 1. Exact match of full URLs
                        if repo_url == default_repo_url:
                            repo_match = True
                            match_reason = "exact URL match"
                        # 2. Match normalized owner/repo format (most reliable)
                        elif repo_normalized and default_repo_normalized and repo_normalized.lower() == default_repo_normalized.lower():
                            repo_match = True
                            match_reason = f"normalized match ({repo_normalized} == {default_repo_normalized})"
                        # 3. Match if default_repo_url is in repo_url (for partial matches)
                        elif default_repo_url in repo_url or repo_url in default_repo_url:
                            repo_match = True
                            match_reason = "partial URL match"
                        # 4. Match if normalized default is in repo URL
                        elif default_repo_normalized and default_repo_normalized.lower() in repo_url.lower():
                            repo_match = True
                            match_reason = f"normalized in URL ({default_repo_normalized} in {repo_url})"
                        
                        if repo_match:
                            repository_url = repo_url
                            default_repo_found = True
                            logger.info(
                                f"✅ Found and using default repository: {repository_url} "
                                f"(matched default: {default_repo_url}, reason: {match_reason})"
                            )
                            break
                    
                    # If default not found, try to find by name (e.g., "nour-jobs")
                    if not default_repo_found:
                        # Try to extract repo name from default URL and find by name
                        repo_name_to_find = None
                        if default_repo_normalized and "/" in default_repo_normalized:
                            repo_name_to_find = default_repo_normalized.split("/")[-1]
                        
                        if repo_name_to_find:
                            logger.info(f"Trying to find repository by name: {repo_name_to_find}")
                            for repo in repos:
                                repo_url = repo.get("repository", "")
                                name = repo.get("name", "")
                                
                                # Check if repo name matches (case-insensitive)
                                if name and name.lower() == repo_name_to_find.lower():
                                    repository_url = repo_url
                                    default_repo_found = True
                                    logger.info(
                                        f"✅ Found repository by name: {repository_url} "
                                        f"(name: {name}, searched for: {repo_name_to_find})"
                                    )
                                    break
                                # Also check if name is in URL
                                elif repo_name_to_find.lower() in repo_url.lower():
                                    repository_url = repo_url
                                    default_repo_found = True
                                    logger.info(
                                        f"✅ Found repository by name in URL: {repository_url} "
                                        f"(searched for: {repo_name_to_find})"
                                    )
                                    break
                        
                        # If still not found, use first available
                        if not default_repo_found:
                            repository_url = repos[0]["repository"]
                            logger.warning(
                                f"⚠️ Default repository '{default_repo_url}' not found in available repos. "
                                f"Available repos: {[r.get('repository') for r in repos[:5]]}... "
                                f"Using first available: {repository_url}\n"
                                f"💡 Tip: Set CURSOR_REPOSITORY_URL in .env file to use a specific default repository."
                            )
                else:
                    # No repositories available, use default from settings
                    repository_url = default_repo_url
                    logger.warning(
                        f"No repositories available, using default from settings: {repository_url}"
                    )
            except Exception as e:
                logger.warning(f"Failed to get repositories, using default from settings: {e}")
                repository_url = app_settings.repository_url

        # Build prompt text - include action if specified
        prompt_text = text
        if action:
            # Prepend action instruction to the prompt
            action_map = {
                "plan": "Створи план рішення для наступної задачі:",
                "ask": "Відповідай на питання користувача про проект. Будь корисним джерелом документації та інформації. Обмеж свою відповідь до 2000 символів:",
                "code_generate": "Створи код для наступної задачі:",
            }
            action_prefix = action_map.get(action, "")
            if action_prefix:
                prompt_text = f"{action_prefix}\n\n{text}"
        
        # Use provided model or default from settings
        model_to_use = model or app_settings.default_model
        
        # Build source with repository and branch
        source_data = {"repository": repository_url}
        if app_settings.default_branch:
            source_data["ref"] = app_settings.default_branch
        
        request_data = CreateTaskRequest(
            prompt={"text": prompt_text},
            source=source_data,
            model=model_to_use
        )
        logger.info(f"Creating agent task: {text[:50]}...")
        logger.info(f"Using model: {model_to_use}, repository: {repository_url}, branch: {app_settings.default_branch}")
        logger.debug(f"API Base URL: {self.base_url}, Endpoint: /agents")

        try:
            response = await self.client.post(
                "/agents",
                json=request_data.model_dump(),
            )
            response.raise_for_status()
            response_data = response.json()
            # API returns agent object, need to adapt to TaskResponse
            # Structure might be different, need to check actual response
            logger.info(f"Agent task created successfully")
            logger.info(f"Agent creation response: {response_data}")
            # Try to extract ID from response
            task_id = response_data.get("id") or response_data.get("agentId") or "unknown"
            return TaskResponse(
                id=task_id,
                title=text[:50],
                description=text,
            )
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            if e.response.status_code == 400 and "validate access to repository" in error_text:
                error_msg = (
                    f"Не вдалося отримати доступ до репозиторію.\n\n"
                    f"Перевірте:\n"
                    f"- Правильність CURSOR_REPOSITORY_URL в налаштуваннях\n"
                    f"- Наявність доступу до репозиторію через Cursor GitHub App\n"
                    f"- Чи встановлений Cursor GitHub App для цього репозиторію\n\n"
                    f"Поточний репозиторій: {repository_url}"
                )
            elif e.response.status_code == 404:
                error_msg = (
                    f"Endpoint не знайдено (404). "
                    f"Можливо, структура API відрізняється від очікуваної.\n\n"
                    f"Спробований URL: {self.base_url}/agents\n"
                    f"Відповідь сервера: {error_text}\n\n"
                    f"Перевірте документацію Cursor Cloud Agent API для правильних endpoints."
                )
            else:
                error_msg = f"Помилка при створенні задачі: {error_text}"
            logger.error(f"{error_msg} (Status: {e.response.status_code}, URL: {self.base_url}/agents)")
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = self._format_network_error(e, f"{self.base_url}/agents")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e

    async def get_agent_status(self, agent_id: str) -> RunResponse:
        """
        Get agent status and results.

        Args:
            agent_id: Agent ID

        Returns:
            RunResponse with agent status and output

        Raises:
            CursorAPIError: If API request fails
            httpx.RequestError: If network error occurs
        """
        try:
            response = await self.client.get(f"/agents/{agent_id}")
            response.raise_for_status()
            data = response.json()
            
            # Log full response for debugging (first few times only)
            if not hasattr(self, '_debug_logged_agents'):
                self._debug_logged_agents = set()
            if agent_id not in self._debug_logged_agents and len(self._debug_logged_agents) < 2:
                logger.info(f"Agent {agent_id} full response structure: {data}")
                self._debug_logged_agents.add(agent_id)
            
            # Parse agent response structure
            # API returns status in UPPERCASE: "CREATING", "RUNNING", "FINISHED"
            status_str = str(data.get("status", "unknown")).upper()
            
            logger.debug(f"Parsed status string: {status_str}")
            
            # Map API statuses to our RunStatus enum
            # According to docs: "CREATING", "RUNNING", "FINISHED"
            if status_str == "FINISHED":
                status = RunStatus.COMPLETED
            elif status_str in ["FAILED", "ERROR", "FAILURE"]:
                status = RunStatus.FAILED
            elif status_str == "EXPIRED":
                status = RunStatus.EXPIRED
            elif status_str == "CREATING":
                status = RunStatus.CREATING
            elif status_str == "RUNNING":
                status = RunStatus.RUNNING
            else:
                # Default to running if status is unknown
                logger.warning(f"Unknown status '{status_str}' for agent {agent_id}, defaulting to RUNNING")
                status = RunStatus.RUNNING
            
            # According to docs, when status is "FINISHED", get result from conversation
            output = None
            if status == RunStatus.COMPLETED:
                # Try to get conversation messages first (more reliable for getting actual questions/plan)
                try:
                    conv_response = await self.client.get(f"/agents/{agent_id}/conversation")
                    conv_response.raise_for_status()
                    conv_data = conv_response.json()
                    # Extract assistant messages as output
                    messages = conv_data.get("messages", [])
                    assistant_messages = [
                        msg.get("text", "") 
                        for msg in messages 
                        if msg.get("type") == "assistant_message"
                    ]
                    if assistant_messages:
                        # If there's only one message, use it
                        if len(assistant_messages) == 1:
                            output = assistant_messages[0]
                            logger.info(
                                f"🔍 [GET_STATUS_DEBUG] Got output from conversation: {len(output)} chars, "
                                f"single assistant message (preview: {output[:200]}...)"
                            )
                        else:
                            # Multiple messages - check if last one is complete or just a fragment
                            last_message = assistant_messages[-1]
                            # If last message is very short (< 100 chars), it might be just a fragment
                            # In that case, combine with previous messages
                            if len(last_message.strip()) < 100 and len(assistant_messages) > 1:
                                # Last message seems incomplete, combine all messages
                                output = "\n\n".join(assistant_messages)
                                logger.info(
                                    f"🔍 [GET_STATUS_DEBUG] Last message is short ({len(last_message)} chars), "
                                    f"combining all {len(assistant_messages)} messages. "
                                    f"Total: {len(output)} chars (preview: {output[:200]}...)"
                                )
                            else:
                                # Last message seems complete, use it
                                output = last_message
                                logger.info(
                                    f"🔍 [GET_STATUS_DEBUG] Got output from conversation: {len(output)} chars, "
                                    f"total assistant messages: {len(assistant_messages)}, "
                                    f"using last message (preview: {output[:200]}...). "
                                    f"Previous messages lengths: {[len(m) for m in assistant_messages[:-1]]}"
                                )
                except Exception as e:
                    logger.warning(f"Failed to get conversation for agent {agent_id}: {e}")
                    # Fallback to summary if conversation fails
                    output = data.get("summary")
                    if output:
                        logger.debug(f"Using summary as fallback: {len(output)} chars")
            
            # For running agents, output is None
            if status == RunStatus.RUNNING:
                output = None
            
            # Try multiple possible error fields
            error = (
                data.get("error") 
                or data.get("errorMessage")
                or data.get("error_message")
                or (data.get("data", {}).get("error") if isinstance(data.get("data"), dict) else None)
            )
            
            # Log status info periodically (every 10th request or when status changes)
            if not hasattr(self, '_agent_status_log'):
                self._agent_status_log = {}
            
            prev_status = self._agent_status_log.get(agent_id)
            if prev_status != status or (not hasattr(self, '_status_log_count') or self._status_log_count % 10 == 0):
                logger.info(
                    f"Agent {agent_id}: status={status.value}, "
                    f"has_output={bool(output)}, has_error={bool(error)}, "
                    f"raw_status='{status_str}'"
                )
                self._agent_status_log[agent_id] = status
                if not hasattr(self, '_status_log_count'):
                    self._status_log_count = 0
                self._status_log_count += 1
            
            return RunResponse(
                id=agent_id,
                status=status,
                output=output,
                error=error,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = (
                    f"Агент не знайдено (404). "
                    f"Спробований URL: {self.base_url}/agents/{agent_id}\n"
                    f"Відповідь сервера: {e.response.text}"
                )
            else:
                error_msg = f"Не вдалося отримати статус агента: {e.response.text}"
            logger.error(error_msg)
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = self._format_network_error(e, f"{self.base_url}/agents/{agent_id}")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e

    async def get_agent_conversation(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation history for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of conversation messages

        Raises:
            CursorAPIError: If API request fails
        """
        logger.debug(f"Getting conversation for agent {agent_id}")
        try:
            response = await self.client.get(f"/agents/{agent_id}/conversation")
            response.raise_for_status()
            data = response.json()
            messages = data.get("messages", [])
            logger.debug(f"Found {len(messages)} messages in conversation")
            return messages
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = (
                    f"Агент або його розмова не знайдена (404). "
                    f"Спробований URL: {self.base_url}/agents/{agent_id}/conversation\n"
                    f"Відповідь сервера: {e.response.text}"
                )
            else:
                error_msg = f"Не вдалося отримати історію розмови: {e.response.text}"
            logger.error(error_msg)
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = self._format_network_error(e, f"{self.base_url}/agents/{agent_id}/conversation")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e

    async def get_run(self, task_id: str, run_id: str) -> RunResponse:
        """
        Get run status and results.

        Args:
            task_id: Task ID
            run_id: Run ID

        Returns:
            RunResponse with current run status

        Raises:
            CursorAPIError: If API request fails
            httpx.RequestError: If network error occurs
        """
        logger.debug(f"Getting run {run_id} for task {task_id}")

        try:
            response = await self.client.get(f"/tasks/{task_id}/runs/{run_id}")
            response.raise_for_status()
            return RunResponse(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = (
                    f"Endpoint не знайдено (404). "
                    f"Спробований URL: {self.base_url}/tasks/{task_id}/runs/{run_id}\n"
                    f"Відповідь сервера: {e.response.text}"
                )
            else:
                error_msg = f"Failed to get run: {e.response.text}"
            logger.error(error_msg)
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = self._format_network_error(e, f"{self.base_url}/tasks/{task_id}/runs/{run_id}")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e

    async def wait_agent_completion(
        self,
        agent_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
        initial_status: Optional[RunStatus] = None,
        status_callback: Optional[Callable[[float, RunStatus], Awaitable[None]]] = None,
        assistant_messages_count_before: Optional[int] = None,
    ) -> RunResponse:
        """
        Wait for agent to complete by polling its status.

        Args:
            agent_id: Agent ID
            timeout: Maximum time to wait in seconds (default: 300)
            poll_interval: Interval between polls in seconds (default: 5)
            initial_status: Initial status before waiting (to detect status changes)
            status_callback: Optional callback function(elapsed_seconds, status) called periodically

        Returns:
            RunResponse with completed agent information

        Raises:
            CursorTimeoutError: If timeout is exceeded
            CursorAPIError: If agent fails or API error occurs
        """
        logger.info(
            f"Waiting for agent {agent_id} to complete (timeout: {timeout}s, "
            f"poll interval: {poll_interval}s, "
            f"assistant_messages_count_before: {assistant_messages_count_before}, "
            f"initial_status: {initial_status})"
        )

        start_time = time.time()
        last_status_update = 0.0
        status_update_interval = 10.0  # Update status every 10 seconds
        
        # If initial status was COMPLETED and we just sent a follow-up,
        # we must дочекатися, поки агент перейде в RUNNING, а вже потім — знову в COMPLETED.
        waiting_for_restart = initial_status == RunStatus.COMPLETED
        seen_running_after_finished = False
        last_completed_check_time = time.time() if waiting_for_restart else None
        completed_check_interval = 15.0  # Check for new messages if still COMPLETED after 15 seconds
        first_completed_check_done = False  # Flag to check immediately on first poll
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise CursorTimeoutError(
                    f"Агент {agent_id} не завершив роботу протягом {timeout} секунд"
                )

            agent_status = await self.get_agent_status(agent_id)
            
            # Call status callback if provided and enough time has passed
            if status_callback and elapsed - last_status_update >= status_update_interval:
                try:
                    await status_callback(elapsed, agent_status.status)
                    last_status_update = elapsed
                except Exception as e:
                    logger.warning(f"Status callback failed for agent {agent_id} with status {agent_status.status}: {e}", exc_info=True)

            # If agent was COMPLETED when we sent follow-up, we must first see it RUNNING
            # before treating new COMPLETED as a new answer.
            if waiting_for_restart:
                if agent_status.status in [RunStatus.CREATING, RunStatus.RUNNING]:
                    logger.debug(f"Agent {agent_id} started running after follow-up")
                    seen_running_after_finished = True
                    waiting_for_restart = False
                    last_completed_check_time = None
                elif agent_status.status == RunStatus.COMPLETED:
                    # Still old completed state, wait more
                    # But if it's been COMPLETED for too long, check conversation for new messages
                    should_check_conversation = False
                    if not first_completed_check_done:
                        # Check immediately on first poll if agent is still COMPLETED
                        should_check_conversation = True
                        first_completed_check_done = True
                    elif last_completed_check_time and (time.time() - last_completed_check_time) >= completed_check_interval:
                        should_check_conversation = True
                    
                    if should_check_conversation:
                        logger.info(f"🔍 [WAIT_DEBUG] Agent {agent_id} still COMPLETED after {completed_check_interval}s, checking conversation for new messages")
                        try:
                            messages = await self.get_agent_conversation(agent_id)
                            assistant_messages = [
                                msg.get("text", "") 
                                for msg in messages 
                                if msg.get("type") == "assistant_message"
                            ]
                            logger.info(
                                f"🔍 [WAIT_DEBUG] Found {len(assistant_messages)} assistant messages "
                                f"(count_before: {assistant_messages_count_before}). "
                                f"Last message preview: {assistant_messages[-1][:100] if assistant_messages else 'N/A'}..."
                            )
                            if assistant_messages:
                                # Only return if there are NEW messages (more than before follow-up)
                                if assistant_messages_count_before is not None and len(assistant_messages) > assistant_messages_count_before:
                                    # Get only new messages
                                    new_messages = assistant_messages[assistant_messages_count_before:]
                                    # Combine all new messages to get complete response
                                    if len(new_messages) == 1:
                                        latest_output = new_messages[0]
                                    else:
                                        # Multiple new messages - combine them
                                        latest_output = "\n\n".join(new_messages)
                                    logger.info(
                                        f"✅ [WAIT_DEBUG] Found {len(new_messages)} NEW message(s) in conversation for agent {agent_id} "
                                        f"(was {assistant_messages_count_before}, now {len(assistant_messages)}). "
                                        f"Combined output: {len(latest_output)} chars, preview: {latest_output[:200]}..."
                                    )
                                    return RunResponse(
                                        id=agent_id,
                                        status=RunStatus.COMPLETED,
                                        output=latest_output,
                                        error=None,
                                    )
                                elif assistant_messages_count_before is None:
                                    # If we don't know the count, use last message (fallback)
                                    latest_output = assistant_messages[-1]
                                    logger.warning(
                                        f"⚠️ [WAIT_DEBUG] No count tracking, using last message for agent {agent_id} "
                                        f"(total: {len(assistant_messages)}). Preview: {latest_output[:200]}..."
                                    )
                                    return RunResponse(
                                        id=agent_id,
                                        status=RunStatus.COMPLETED,
                                        output=latest_output,
                                        error=None,
                                    )
                                else:
                                    logger.debug(
                                        f"⏳ [WAIT_DEBUG] No new messages yet ({assistant_messages_count_before} -> {len(assistant_messages)}), "
                                        f"waiting for agent to process follow-up..."
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to check conversation while waiting for restart: {e}")
                        # Reset check time to avoid checking too frequently
                        last_completed_check_time = time.time()
                    
                    logger.debug(
                        f"Agent {agent_id} still in COMPLETED state after follow-up, "
                        f"waiting for it to start RUNNING..."
                    )
                    await asyncio.sleep(poll_interval)
                    continue

            # Normal completion handling
            if agent_status.status == RunStatus.COMPLETED:
                # If we were waiting for new completion after follow-up, get fresh conversation
                if seen_running_after_finished:
                    logger.info(f"🔍 [WAIT_DEBUG] Agent {agent_id} completed after follow-up, getting latest response")
                    # Get the latest message from conversation
                    try:
                        messages = await self.get_agent_conversation(agent_id)
                        assistant_messages = [
                            msg.get("text", "") 
                            for msg in messages 
                            if msg.get("type") == "assistant_message"
                        ]
                        logger.info(
                            f"🔍 [WAIT_DEBUG] After completion: {len(assistant_messages)} assistant messages "
                            f"(count_before: {assistant_messages_count_before}). "
                            f"Last message preview: {assistant_messages[-1][:100] if assistant_messages else 'N/A'}..."
                        )
                        if assistant_messages:
                            # Only return NEW messages (those after follow-up)
                            if assistant_messages_count_before is not None and len(assistant_messages) > assistant_messages_count_before:
                                new_messages = assistant_messages[assistant_messages_count_before:]
                                # Combine all new messages to get complete response
                                if len(new_messages) == 1:
                                    latest_output = new_messages[0]
                                else:
                                    # Multiple new messages - combine them
                                    latest_output = "\n\n".join(new_messages)
                                logger.info(
                                    f"✅ [WAIT_DEBUG] Returning NEW response after follow-up: {len(new_messages)} new message(s) "
                                    f"(was {assistant_messages_count_before}, now {len(assistant_messages)}). "
                                    f"Combined output: {len(latest_output)} chars, preview: {latest_output[:200]}..."
                                )
                                return RunResponse(
                                    id=agent_id,
                                    status=RunStatus.COMPLETED,
                                    output=latest_output,
                                    error=None,
                                )
                            else:
                                # Fallback: use last message if count tracking not available
                                latest_output = assistant_messages[-1]
                                logger.warning(
                                    f"⚠️ [WAIT_DEBUG] Using last message as fallback "
                                    f"(count tracking: {assistant_messages_count_before}, "
                                    f"total: {len(assistant_messages)}, "
                                    f"count increased: {len(assistant_messages) > assistant_messages_count_before if assistant_messages_count_before is not None else 'N/A'}). "
                                    f"Message preview: {latest_output[:200]}..."
                                )
                                return RunResponse(
                                    id=agent_id,
                                    status=RunStatus.COMPLETED,
                                    output=latest_output,
                                    error=None,
                                )
                    except Exception as e:
                        logger.warning(f"Failed to get conversation after follow-up: {e}")
                        # Fall back to summary if available
                        if agent_status.output:
                            return agent_status
                
                logger.info(f"Agent {agent_id} completed successfully")
                return agent_status
            elif agent_status.status == RunStatus.FAILED:
                error_msg = agent_status.error or "Агент завершився з помилкою"
                logger.error(f"Agent {agent_id} failed: {error_msg}")
                raise CursorAPIError(f"Агент завершився з помилкою: {error_msg}")
            elif agent_status.status == RunStatus.EXPIRED:
                error_msg = "Агент застарів і більше не може обробляти запити. Створіть нового агента."
                logger.warning(f"Agent {agent_id} expired")
                raise CursorAPIError(error_msg)

            # Status is still running, wait before next poll
            logger.debug(f"Agent {agent_id} still running, waiting {poll_interval}s...")
            await asyncio.sleep(poll_interval)

    async def add_followup(self, agent_id: str, text: str) -> None:
        """
        Add a follow-up instruction to an existing agent.

        Args:
            agent_id: Agent ID
            text: Follow-up instruction text

        Raises:
            CursorAPIError: If API request fails
            httpx.RequestError: If network error occurs
        """
        logger.info(f"Adding follow-up to agent {agent_id}: {text[:50]}...")

        try:
            response = await self.client.post(
                f"/agents/{agent_id}/followup",
                json={"prompt": {"text": text}},
            )
            response.raise_for_status()
            logger.info(f"Follow-up added successfully to agent {agent_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                error_msg = (
                    f"Агент не знайдено (404). "
                    f"Спробований URL: {self.base_url}/agents/{agent_id}/followup\n"
                    f"Відповідь сервера: {e.response.text}"
                )
            elif e.response.status_code == 409:
                # 409 Conflict usually means agent is expired/deleted
                try:
                    error_data = e.response.json()
                    if "deleted" in error_data.get("error", "").lower():
                        error_msg = "Агент застарів або був видалений і більше не може обробляти запити. Створіть нового агента через /plan, /ask або /solve."
                    else:
                        error_msg = f"Не вдалося додати follow-up: {error_data.get('error', e.response.text)}"
                except:
                    error_msg = f"Агент застарів або був видалений. Створіть нового агента через /plan, /ask або /solve."
            else:
                error_msg = f"Не вдалося додати follow-up: {e.response.text}"
            logger.error(error_msg)
            raise CursorAPIError(error_msg, status_code=e.response.status_code) from e
        except httpx.RequestError as e:
            error_msg = self._format_network_error(e, f"{self.base_url}/agents/{agent_id}/followup")
            logger.error(error_msg)
            raise CursorAPIError(error_msg) from e


# Global client instance
cursor_client = CursorClient(app_settings.cursor_api_key, app_settings.api_base)

