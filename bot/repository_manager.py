"""Repository selection manager for storing selected repository."""

from typing import Optional

# In-memory storage for selected repository (per user)
# In future could be extended to use database or file storage
_selected_repositories: dict[int, str] = {}


def get_selected_repository(user_id: int) -> Optional[str]:
    """
    Get selected repository for user.

    Args:
        user_id: Telegram user ID

    Returns:
        Selected repository URL or None
    """
    return _selected_repositories.get(user_id)


def set_selected_repository(user_id: int, repository_url: str) -> None:
    """
    Set selected repository for user.

    Args:
        user_id: Telegram user ID
        repository_url: Repository URL to set
    """
    _selected_repositories[user_id] = repository_url


def clear_selected_repository(user_id: int) -> None:
    """
    Clear selected repository for user.

    Args:
        user_id: Telegram user ID
    """
    _selected_repositories.pop(user_id, None)

