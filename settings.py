"""Application settings and configuration."""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        """Initialize settings and validate required variables."""
        self.cursor_api_key: str = self._get_required_env("CURSOR_API_KEY")
        self.telegram_token: str = self._get_required_env("TELEGRAM_TOKEN")
        self.api_base: str = os.getenv("API_BASE", "https://api.cursor.com/v0")
        # Repository URL for Cursor API (required)
        self.repository_url: str = os.getenv(
            "CURSOR_REPOSITORY_URL", "https://github.com/microsoft/vscode"
        )
        # Allowed user ID (default: 215985701 for @dmytro_s_s)
        allowed_user_id = os.getenv("ALLOWED_USER_ID", "215985701")
        self.allowed_user_id: int = int(allowed_user_id)

    @staticmethod
    def _get_required_env(key: str) -> str:
        """
        Get required environment variable.

        Args:
            key: Environment variable name

        Returns:
            Environment variable value

        Raises:
            ValueError: If environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Required environment variable {key} is not set. "
                f"Please check your .env file or environment variables."
            )
        return value


# Global settings instance
settings = Settings()

