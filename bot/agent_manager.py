"""Agent ID manager for storing last active agent per user."""

from typing import Optional

# In-memory storage for last active agent ID (per user)
# In future could be extended to use database or file storage
_last_agent_ids: dict[int, str] = {}


def get_last_agent_id(user_id: int) -> Optional[str]:
    """
    Get last active agent ID for user.

    Args:
        user_id: Telegram user ID

    Returns:
        Last agent ID or None
    """
    return _last_agent_ids.get(user_id)


def set_last_agent_id(user_id: int, agent_id: str) -> None:
    """
    Set last active agent ID for user.

    Args:
        user_id: Telegram user ID
        agent_id: Agent ID to set
    """
    _last_agent_ids[user_id] = agent_id


def clear_last_agent_id(user_id: int) -> None:
    """
    Clear last active agent ID for user.

    Args:
        user_id: Telegram user ID
    """
    _last_agent_ids.pop(user_id, None)

