"""Small polite HTTP client: retries, backoff, on-disk cache. Standard library only."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "pssd-atlas/0.1 (research evidence mapper)"


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status
        self.body = body


class Client:
    def __init__(self, cache_dir: Path | None = None, cache_ttl: float = 7 * 86400,
                 min_interval: float = 0.4, retries: int = 4):
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl
        self.min_interval = min_interval
        self.retries = retries
        self._last = 0.0
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".txt")

    def get(self, url: str, params: dict | None = None, *, post: bool = False,
            ok_statuses: tuple[int, ...] = ()) -> str:
        """Fetch text. `ok_statuses` are non-200 codes returned (as body) rather than raised."""
        query = urllib.parse.urlencode(params or {}, quote_via=urllib.parse.quote)
        key = f"{url}?{query}"
        path = self._cache_path(key)
        if path and path.exists() and time.time() - path.stat().st_mtime < self.cache_ttl:
            return path.read_text(encoding="utf-8")

        last_err: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            if post:
                req = urllib.request.Request(url, data=query.encode(), method="POST")
            else:
                req = urllib.request.Request(f"{url}?{query}" if query else url)
            req.add_header("User-Agent", USER_AGENT)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                if path:
                    path.write_text(text, encoding="utf-8")
                return text
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code in ok_statuses:
                    if path:
                        path.write_text(body, encoding="utf-8")
                    return body
                last_err = HttpError(e.code, url, body)
                if e.code not in (429, 500, 502, 503, 504):
                    raise last_err from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
            time.sleep(min(30, 2 ** attempt))
        raise last_err  # type: ignore[misc]

    def get_json(self, url: str, params: dict | None = None, **kw) -> dict:
        return json.loads(self.get(url, params, **kw))
