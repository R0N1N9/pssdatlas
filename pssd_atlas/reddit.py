"""Reddit posts via the official API (application-only OAuth).

Needs a Reddit "script" app: set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.
Authors are deliberately not read from the response, so usernames never reach disk.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os

from .http import Client, HttpError

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"


class MissingCredentials(RuntimeError):
    pass


def token(client: Client) -> str:
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not secret:
        raise MissingCredentials("set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (see README)")
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    try:
        data = json.loads(client.get(TOKEN_URL, {"grant_type": "client_credentials"}, post=True,
                                     headers={"Authorization": f"Basic {basic}"}))
    except HttpError as e:
        if e.status == 401:
            raise RuntimeError("Reddit rejected the client ID or secret") from None
        if e.status == 403:
            raise RuntimeError("Reddit blocked this network (it refuses many cloud and VPN addresses); "
                               "run the update from a home connection") from None
        raise
    if "access_token" not in data:
        raise RuntimeError(f"Reddit refused the credentials: {data.get('error', data)}")
    return data["access_token"]


def _post(d: dict) -> dict:
    return {
        "id": f"reddit:{d['id']}",
        "source": "reddit",
        "community": f"r/{d.get('subreddit', '')}",
        "url": "https://www.reddit.com" + d.get("permalink", ""),
        "date": dt.datetime.fromtimestamp(d.get("created_utc", 0), dt.timezone.utc).date().isoformat(),
        "title": d.get("title", ""),
        "text": d.get("selftext", "") or "",
        "replies": d.get("num_comments", 0),
    }


def _listing(client: Client, tok: str, path: str, params: dict, max_pages: int) -> list[dict]:
    out, after = [], None
    for _ in range(max_pages):
        q = {**params, "limit": 100, "raw_json": 1}
        if after:
            q["after"] = after
        data = json.loads(client.get(f"{API}{path}", q, headers={"Authorization": f"Bearer {tok}"}))
        children = data.get("data", {}).get("children", [])
        out.extend(_post(c["data"]) for c in children if c.get("kind") == "t3")
        after = data.get("data", {}).get("after")
        if not after or not children:
            break
    return out


def collect(client: Client, cfg: dict, log=lambda m: None, max_pages: int = 10) -> list[dict]:
    """Newest submissions from each configured subreddit, plus the configured searches."""
    tok = token(client)
    pool: dict[str, dict] = {}
    for sub in cfg.get("subreddits", []):
        posts = _listing(client, tok, f"/r/{sub}/new", {}, max_pages)
        log(f"- reddit r/{sub} newest: {len(posts)} posts")
        pool.update((p["id"], p) for p in posts)
    for s in cfg.get("search", []):
        posts = _listing(client, tok, f"/r/{s['subreddit']}/search",
                         {"q": s["q"], "restrict_sr": 1, "sort": "new", "type": "link"}, max_pages)
        log(f"- reddit r/{s['subreddit']} search [{s['q'][:40]}]: {len(posts)} posts")
        pool.update((p["id"], p) for p in posts)
    return list(pool.values())
