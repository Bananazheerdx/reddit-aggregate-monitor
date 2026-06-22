from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import yaml


class ConfigurationError(RuntimeError):
    """Raised when required configuration or credentials are missing."""


class RedditAPIError(RuntimeError):
    """Raised when a Reddit API request fails after retry handling."""


@dataclass(frozen=True)
class RedditClientConfig:
    api_base: str
    token_url: str
    client_id_env: str
    client_secret_env: str
    user_agent: str
    request_limit_per_subreddit: int
    requests_per_second: float
    timeout_seconds: float
    max_retries: int
    oauth_required: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RedditClientConfig":
        reddit = data.get("reddit")
        if not isinstance(reddit, dict):
            raise ConfigurationError("Missing 'reddit' configuration section.")

        oauth_required = bool(reddit.get("oauth_required", True))
        if not oauth_required:
            raise ConfigurationError(
                "OAuth must remain required. This prototype intentionally does not support unauthenticated access."
            )

        user_agent = str(
            os.getenv("REDDIT_USER_AGENT")
            or reddit.get("user_agent")
            or ""
        ).strip()
        if not user_agent or "example_user" in user_agent:
            raise ConfigurationError(
                "A descriptive reddit.user_agent is required. Replace the example username before running."
            )

        request_limit = int(reddit.get("request_limit_per_subreddit", 25))
        if request_limit < 1 or request_limit > 100:
            raise ConfigurationError("reddit.request_limit_per_subreddit must be between 1 and 100.")

        rps = float(reddit.get("requests_per_second", 0.5))
        if rps <= 0 or rps > 1.0:
            raise ConfigurationError("reddit.requests_per_second must be > 0 and <= 1.0 for this prototype.")

        timeout = float(reddit.get("timeout_seconds", 20))
        if timeout <= 0:
            raise ConfigurationError("reddit.timeout_seconds must be positive.")

        retries = int(reddit.get("max_retries", 1))
        if retries < 0 or retries > 3:
            raise ConfigurationError("reddit.max_retries must be between 0 and 3.")

        return cls(
            api_base=str(reddit.get("api_base") or "https://oauth.reddit.com").rstrip("/"),
            token_url=str(reddit.get("token_url") or "https://www.reddit.com/api/v1/access_token"),
            client_id_env=str(reddit.get("client_id_env") or "REDDIT_CLIENT_ID"),
            client_secret_env=str(reddit.get("client_secret_env") or "REDDIT_CLIENT_SECRET"),
            user_agent=user_agent,
            request_limit_per_subreddit=request_limit,
            requests_per_second=rps,
            timeout_seconds=timeout,
            max_retries=retries,
            oauth_required=True,
        )


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    if not isinstance(payload, dict):
        raise ConfigurationError("Config file must contain a YAML mapping at the top level.")

    return payload


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(
            f"Required environment variable {name!r} is missing. "
            "OAuth credentials are required; unauthenticated fallback is intentionally disabled."
        )
    return value.strip()


@dataclass
class ListingResult:
    subreddit: str
    status: str
    item_count: int
    http_status: int | None
    latency_ms: int | None
    rate_limit_used: str | None
    rate_limit_remaining: str | None
    rate_limit_reset: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subreddit": self.subreddit,
            "status": self.status,
            "listing_items_returned": self.item_count,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
            "rate_limit": {
                "used": self.rate_limit_used,
                "remaining": self.rate_limit_remaining,
                "reset": self.rate_limit_reset,
            },
            "error": self.error,
        }


class RedditOAuthClient:
    """
    Minimal OAuth-only Reddit API client.

    This client intentionally does not implement public JSON fallback, web scraping,
    posting, commenting, voting, messaging, moderation, or user-profile access.
    """

    def __init__(self, config: RedditClientConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})
        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0
        self._last_request_at: float = 0.0

    def _basic_auth_header(self, client_id: str, client_secret: str) -> str:
        raw = f"{client_id}:{client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _refresh_access_token(self) -> str:
        client_id = require_env(self.config.client_id_env)
        client_secret = require_env(self.config.client_secret_env)

        headers = {
            "Authorization": self._basic_auth_header(client_id, client_secret),
            "User-Agent": self.config.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        try:
            response = self.session.post(
                self.config.token_url,
                headers=headers,
                data=data,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RedditAPIError(f"OAuth token request failed: {exc}") from exc

        if response.status_code >= 400:
            raise RedditAPIError(
                f"OAuth token request returned HTTP {response.status_code}: {response.text[:200]}"
            )

        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RedditAPIError("OAuth token response did not include an access_token.")

        expires_in = int(payload.get("expires_in") or 3600)
        self._access_token = token
        self._access_token_expires_at = time.time() + max(60, expires_in - 60)
        return token

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at:
            return self._access_token
        return self._refresh_access_token()

    def _wait_for_rate_limit(self) -> None:
        min_interval = 1.0 / self.config.requests_per_second
        now = time.monotonic()
        wait_s = self._last_request_at + min_interval - now
        if wait_s > 0:
            time.sleep(wait_s)
        self._last_request_at = time.monotonic()

    def _headers(self) -> dict[str, str]:
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.config.user_agent,
        }

    def fetch_public_new_listing_count(self, subreddit: str) -> ListingResult:
        """
        Fetch one public listing endpoint and return aggregate request metrics only.

        The response body is not returned to callers and is not written to disk here.
        The only Reddit-derived data exposed by this method is the count of listing
        items returned for the requested subreddit.
        """
        clean_subreddit = self._validate_subreddit(subreddit)
        endpoint = f"/r/{quote(clean_subreddit)}/new"
        url = f"{self.config.api_base}{endpoint}"
        params = {"limit": self.config.request_limit_per_subreddit}

        attempts = self.config.max_retries + 1
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            self._wait_for_rate_limit()
            started = time.monotonic()

            try:
                response = self.session.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt < attempts:
                    time.sleep(min(2.0 * attempt, 5.0))
                    continue
                return ListingResult(
                    subreddit=clean_subreddit,
                    status="error",
                    item_count=0,
                    http_status=None,
                    latency_ms=None,
                    rate_limit_used=None,
                    rate_limit_remaining=None,
                    rate_limit_reset=None,
                    error=last_error,
                )

            latency_ms = int(round((time.monotonic() - started) * 1000))
            rate_limit_used = response.headers.get("x-ratelimit-used")
            rate_limit_remaining = response.headers.get("x-ratelimit-remaining")
            rate_limit_reset = response.headers.get("x-ratelimit-reset")

            if response.status_code == 429 and attempt < attempts:
                reset_s = _safe_float(rate_limit_reset)
                time.sleep(min(max(reset_s or 2.0, 1.0), 30.0))
                continue

            if response.status_code >= 400:
                return ListingResult(
                    subreddit=clean_subreddit,
                    status="error",
                    item_count=0,
                    http_status=response.status_code,
                    latency_ms=latency_ms,
                    rate_limit_used=rate_limit_used,
                    rate_limit_remaining=rate_limit_remaining,
                    rate_limit_reset=rate_limit_reset,
                    error=f"HTTP {response.status_code}",
                )

            try:
                payload = response.json()
                children = payload.get("data", {}).get("children", [])
                item_count = len(children) if isinstance(children, list) else 0
            except Exception as exc:  # noqa: BLE001 - intentionally defensive for API parsing
                return ListingResult(
                    subreddit=clean_subreddit,
                    status="error",
                    item_count=0,
                    http_status=response.status_code,
                    latency_ms=latency_ms,
                    rate_limit_used=rate_limit_used,
                    rate_limit_remaining=rate_limit_remaining,
                    rate_limit_reset=rate_limit_reset,
                    error=f"Could not parse listing response: {exc}",
                )

            return ListingResult(
                subreddit=clean_subreddit,
                status="ok",
                item_count=item_count,
                http_status=response.status_code,
                latency_ms=latency_ms,
                rate_limit_used=rate_limit_used,
                rate_limit_remaining=rate_limit_remaining,
                rate_limit_reset=rate_limit_reset,
                error=None,
            )

        return ListingResult(
            subreddit=clean_subreddit,
            status="error",
            item_count=0,
            http_status=None,
            latency_ms=None,
            rate_limit_used=None,
            rate_limit_remaining=None,
            rate_limit_reset=None,
            error=last_error or "unknown_error",
        )

    @staticmethod
    def _validate_subreddit(subreddit: str) -> str:
        value = str(subreddit or "").strip()
        if value.lower().startswith("r/"):
            value = value[2:]
        if not value:
            raise ConfigurationError("Subreddit name cannot be empty.")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
        if any(ch not in allowed for ch in value):
            raise ConfigurationError(f"Invalid subreddit name: {subreddit!r}")
        if len(value) > 50:
            raise ConfigurationError(f"Subreddit name is too long: {subreddit!r}")
        return value


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
