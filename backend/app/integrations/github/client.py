import logging
import os
import time
from typing import Optional, Dict, Any, List
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """
    GitHub App API client.
    Supports GitHub App JWT authentication, installation access tokens,
    or personal access token fallback for reconciliation and live queries.
    Section 2 of Specification.
    """

    def __init__(self):
        self.base_url = settings.GITHUB_API_BASE_URL.rstrip("/")
        self._installation_token: Optional[str] = None
        self._token_expires_at: float = 0

    def is_configured(self) -> bool:
        """Returns True if either GitHub App credentials or Personal API Token is configured."""
        if settings.GITHUB_API_TOKEN:
            return True
        if settings.GITHUB_APP_ID and (settings.GITHUB_APP_PRIVATE_KEY or settings.GITHUB_APP_PRIVATE_KEY_PATH):
            return True
        return False

    def get_integration_status(self) -> Dict[str, Any]:
        """Provides status details for GitHub App integration."""
        configured = self.is_configured()
        auth_type = (
            "personal_token" if settings.GITHUB_API_TOKEN else ("github_app" if settings.GITHUB_APP_ID else "none")
        )

        return {
            "configured": configured,
            "auth_type": auth_type,
            "app_id": settings.GITHUB_APP_ID,
            "installation_id": settings.GITHUB_APP_INSTALLATION_ID,
            "webhook_configured": bool(
                settings.GITHUB_WEBHOOK_SECRET and settings.GITHUB_WEBHOOK_SECRET != "test-github-webhook-secret"
            ),
            "status": "CONFIGURED" if configured else "PENDING_SETUP",
        }

    def _generate_app_jwt(self) -> Optional[str]:
        """Generates a GitHub App JWT using RS256."""
        if not settings.GITHUB_APP_ID:
            return None

        private_key = settings.GITHUB_APP_PRIVATE_KEY
        if (
            not private_key
            and settings.GITHUB_APP_PRIVATE_KEY_PATH
            and os.path.exists(settings.GITHUB_APP_PRIVATE_KEY_PATH)
        ):
            with open(settings.GITHUB_APP_PRIVATE_KEY_PATH, "r", encoding="utf-8") as f:
                private_key = f.read()

        if not private_key:
            return None

        try:
            import jwt  # PyJWT or python-jose

            now = int(time.time())
            payload = {"iat": now - 60, "exp": now + (10 * 60), "iss": settings.GITHUB_APP_ID}
            return jwt.encode(payload, private_key, algorithm="RS256")
        except Exception as e:
            logger.error(f"Failed to generate GitHub App JWT: {e}")
            return None

    async def _get_auth_header(self) -> Dict[str, str]:
        """Resolves Authorization headers safely."""
        if settings.GITHUB_API_TOKEN:
            return {
                "Authorization": f"Bearer {settings.GITHUB_API_TOKEN}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

        jwt_token = self._generate_app_jwt()
        if jwt_token:
            if settings.GITHUB_APP_INSTALLATION_ID:
                # Exchange JWT for installation access token
                if not self._installation_token or time.time() >= self._token_expires_at - 60:
                    token_url = f"{self.base_url}/app/installations/{settings.GITHUB_APP_INSTALLATION_ID}/access_tokens"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.post(
                            token_url,
                            headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
                        )
                        if res.status_code == 201:
                            data = res.json()
                            self._installation_token = data.get("token")
                            self._token_expires_at = time.time() + 3500

                if self._installation_token:
                    return {
                        "Authorization": f"Bearer {self._installation_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    }

            return {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

        return {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    async def get_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetches repository metadata from GitHub API."""
        if not self.is_configured():
            logger.debug("GitHub client not configured, skipping remote API call")
            return None

        headers = await self._get_auth_header()
        url = f"{self.base_url}/repos/{owner}/{repo}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"GitHub API returned {res.status_code} for {owner}/{repo}")
                return None
        except Exception as e:
            logger.error(f"Error calling GitHub API for repository {owner}/{repo}: {e}")
            return None

    async def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Optional[Dict[str, Any]]:
        """Fetches workflow run metadata for reconciliation."""
        if not self.is_configured():
            return None

        headers = await self._get_auth_header()
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.json()
                return None
        except Exception as e:
            logger.error(f"Error calling GitHub API for workflow run {run_id}: {e}")
            return None


github_client = GitHubClient()
