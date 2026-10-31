"""Common task tracker interface."""

from typing import Protocol


class Tracker(Protocol):
    """Minimal tracker interface; implementations create tasks only."""

    async def create_task(self, title: str, description: str) -> str:
        """Create a task and return its external identifier."""
        ...
