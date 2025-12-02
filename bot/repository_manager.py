"""Repository selection manager for storing selected repository."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# File path for storing favorites
# Use /mnt/data on fly.io (volume mount), otherwise use current directory
_DATA_DIR = Path("/mnt/data") if Path("/mnt/data").exists() else Path(".")
_FAVORITES_FILE = _DATA_DIR / "favorites.json"

# In-memory storage for selected repository (per user)
# In future could be extended to use database or file storage
_selected_repositories: dict[int, str] = {}
# Storage for favorite repositories (per user)
_favorite_repositories: dict[int, set[str]] = {}


def _load_favorites() -> None:
    """Load favorite repositories from file."""
    global _favorite_repositories
    # Ensure data directory exists
    _FAVORITES_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not _FAVORITES_FILE.exists():
        logger.info(f"Favorites file does not exist at {_FAVORITES_FILE}, starting with empty favorites")
        _favorite_repositories = {}
        return

    try:
        with open(_FAVORITES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Convert list values back to sets
            _favorite_repositories = {
                int(user_id): set(repos) for user_id, repos in data.items()
            }
        logger.info(f"Loaded {sum(len(repos) for repos in _favorite_repositories.values())} favorites from {_FAVORITES_FILE}")
    except (json.JSONDecodeError, ValueError, IOError) as e:
        logger.warning(f"Failed to load favorites from file {_FAVORITES_FILE}: {e}. Starting with empty favorites.")
        _favorite_repositories = {}


def _save_favorites() -> None:
    """Save favorite repositories to file."""
    try:
        # Ensure data directory exists
        _FAVORITES_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert sets to lists for JSON serialization
        data = {
            str(user_id): list(repos) for user_id, repos in _favorite_repositories.items()
        }
        with open(_FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved favorites to {_FAVORITES_FILE}")
    except IOError as e:
        logger.error(f"Failed to save favorites to file {_FAVORITES_FILE}: {e}")


# Load favorites on module import
_load_favorites()


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


def get_favorite_repositories(user_id: int) -> set[str]:
    """
    Get favorite repositories for user.

    Args:
        user_id: Telegram user ID

    Returns:
        Set of favorite repository URLs
    """
    return _favorite_repositories.get(user_id, set())


def add_favorite_repository(user_id: int, repository_url: str) -> None:
    """
    Add repository to favorites for user.

    Args:
        user_id: Telegram user ID
        repository_url: Repository URL to add
    """
    if user_id not in _favorite_repositories:
        _favorite_repositories[user_id] = set()
    _favorite_repositories[user_id].add(repository_url)
    _save_favorites()


def remove_favorite_repository(user_id: int, repository_url: str) -> None:
    """
    Remove repository from favorites for user.

    Args:
        user_id: Telegram user ID
        repository_url: Repository URL to remove
    """
    if user_id in _favorite_repositories:
        _favorite_repositories[user_id].discard(repository_url)
        # Remove user entry if no favorites left
        if not _favorite_repositories[user_id]:
            _favorite_repositories.pop(user_id, None)
        _save_favorites()


def is_favorite_repository(user_id: int, repository_url: str) -> bool:
    """
    Check if repository is in favorites for user.

    Args:
        user_id: Telegram user ID
        repository_url: Repository URL to check

    Returns:
        True if repository is favorite, False otherwise
    """
    return repository_url in _favorite_repositories.get(user_id, set())

