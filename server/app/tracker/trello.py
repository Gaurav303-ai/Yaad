"""Trello card adapter."""

import httpx


class TrelloTracker:
    """Create cards in one configured Trello list."""

    def __init__(self, api_key: str, token: str, list_id: str) -> None:
        self.api_key = api_key
        self.token = token
        self.list_id = list_id

    async def create_task(self, title: str, description: str) -> str:
        """Create a Trello card and return its URL."""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.trello.com/1/cards",
                params={
                    "key": self.api_key,
                    "token": self.token,
                    "idList": self.list_id,
                    "name": title,
                    "desc": description,
                },
            )
        if response.is_error:
            raise RuntimeError(f"Trello task creation failed (HTTP {response.status_code}).")
        try:
            card = response.json()
            card_url = card["url"]
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError("Trello returned an invalid task response.") from error
        if not isinstance(card_url, str) or not card_url:
            raise RuntimeError("Trello returned a task without a URL.")
        return card_url
