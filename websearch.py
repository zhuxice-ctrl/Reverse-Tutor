from __future__ import annotations

import json
import os
from typing import NamedTuple, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WebHit(NamedTuple):
    title: str
    url: str
    snippet: str
    provider: str


class WebSearchProvider(Protocol):
    def search(self, query: str, *, top_k: int = 3) -> list[WebHit]: ...


class NullWebSearchProvider:
    """Default: web search disabled, returns nothing."""

    def search(self, query: str, *, top_k: int = 3) -> list[WebHit]:
        return []


class MockWebSearchProvider:
    """Deterministic provider for tests."""

    def __init__(self, hits: list[WebHit] | None = None):
        self._hits = hits or []

    def search(self, query: str, *, top_k: int = 3) -> list[WebHit]:
        return list(self._hits)[: max(0, int(top_k or 0))]


class HttpWebSearchProvider:
    """Real provider stub. Requires WEB_SEARCH_API_KEY and WEB_SEARCH_ENDPOINT."""

    def __init__(self, api_key: str, endpoint: str = ""):
        self.api_key = api_key
        self.endpoint = endpoint or os.getenv("WEB_SEARCH_ENDPOINT", "")

    def search(self, query: str, *, top_k: int = 3) -> list[WebHit]:
        if not self.api_key or not self.endpoint or not (query or "").strip():
            return []
        try:
            separator = "&" if "?" in self.endpoint else "?"
            url = f"{self.endpoint}{separator}{urlencode({'q': query, 'top_k': int(top_k or 3)})}"
            req = Request(url, headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"})
            with urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        rows = []
        if isinstance(payload, dict):
            for key in ("hits", "results", "items"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
        elif isinstance(payload, list):
            rows = payload

        hits: list[WebHit] = []
        for row in rows[: max(0, int(top_k or 0))]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or row.get("name") or "").strip()
            url = str(row.get("url") or row.get("link") or "").strip()
            snippet = str(row.get("snippet") or row.get("summary") or row.get("content") or "").strip()
            if not (title or url or snippet):
                continue
            hits.append(WebHit(title=title or url or "Untitled", url=url, snippet=snippet, provider="http"))
        return hits


def get_web_search_provider() -> WebSearchProvider:
    provider = (os.getenv("WEB_SEARCH_PROVIDER", "") or "").strip().lower()
    if provider in {"", "null"}:
        return NullWebSearchProvider()
    if provider == "mock":
        return MockWebSearchProvider()
    if provider == "http":
        api_key = os.getenv("WEB_SEARCH_API_KEY", "")
        if not api_key:
            return NullWebSearchProvider()
        return HttpWebSearchProvider(api_key)
    return NullWebSearchProvider()
