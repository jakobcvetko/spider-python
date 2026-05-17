"""Cached Telegram bot metadata (username from getMe)."""

_bot_username: str | None = None


def get_bot_username() -> str | None:
    return _bot_username


def set_bot_username(username: str) -> None:
    global _bot_username
    _bot_username = username.lstrip("@")
