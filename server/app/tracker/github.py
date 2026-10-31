"""GitHub Issues task adapter."""

import httpx


class GitHubTracker:
    """Create issues in one configured GitHub repository."""

    def __init__(self, token: str, repository: str) -> None:
        self.token = token
        self.repository = repository.strip("/")

    async def create_task(self, title: str, description: str) -> str:
        """Create a GitHub issue and return its URL."""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://api.github.com/repos/{self.repository}/issues",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"title": title, "body": description},
            )
        if response.is_error:
            raise RuntimeError(f"GitHub issue creation failed (HTTP {response.status_code}).")
        try:
            issue_url = response.json()["html_url"]
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError("GitHub returned an invalid issue response.") from error
        if not isinstance(issue_url, str) or not issue_url:
            raise RuntimeError("GitHub returned an issue without a URL.")
        return issue_url
