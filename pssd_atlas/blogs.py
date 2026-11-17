"""Blog and advocacy-site articles, via each site's own WordPress search API or RSS feed.

Only sites whose robots rules permit it are configured, and each site's crawl
delay is honoured.
"""

from __future__ import annotations

import email.utils
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from .http import Client

_RELEVANT = re.compile(r"post-?SSRI|\bPSSD\b|(persistent|enduring|permanent|lasting) sexual|sexual (dysfunction|side effects?)"
                       r"|genital (numb|an(a)?esthesia)", re.I)


def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s or "")
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def relevant(title: str, text: str) -> bool:
    """Site search matches any mention; keep articles that are substantially about the topic."""
    return bool(_RELEVANT.search(title)) or len(_RELEVANT.findall(text)) >= 3


def _record(name: str, host: str, key: str, url: str, date: str, title: str, text: str) -> dict:
    return {"id": f"blog:{host}:{key}", "source": "blog", "community": name, "url": url, "date": date,
            "title": strip_html(title), "text": strip_html(text), "replies": 0}


def wordpress(client: Client, name: str, base: str, terms: list[str], max_pages: int = 5) -> list[dict]:
    host, out = urllib.parse.urlparse(base).netloc, {}
    for term in terms:
        for page in range(1, max_pages + 1):
            body = client.get(f"{base}/wp-json/wp/v2/posts",
                              {"search": term, "per_page": 100, "page": page, "_fields": "id,date,link,title,content"},
                              ok_statuses=(400,))  # WordPress answers 400 past the last page
            items = json.loads(body)
            if not isinstance(items, list) or not items:
                break
            for it in items:
                r = _record(name, host, str(it["id"]), it["link"], it["date"][:10],
                            it["title"]["rendered"], it["content"]["rendered"])
                if relevant(r["title"], r["text"]):
                    out[r["id"]] = r
            if len(items) < 100:
                break
    return list(out.values())


def rss(client: Client, name: str, url: str) -> list[dict]:
    host, out = urllib.parse.urlparse(url).netloc, []
    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    for item in ET.fromstring(client.get(url)).iter("item"):
        link = (item.findtext("link") or "").strip()
        try:
            date = email.utils.parsedate_to_datetime(item.findtext("pubDate") or "").date().isoformat()
        except (TypeError, ValueError):
            date = ""
        body = item.findtext("content:encoded", namespaces=ns) or item.findtext("description") or ""
        if link:
            out.append(_record(name, host, urllib.parse.urlparse(link).path.strip("/"), link, date,
                               item.findtext("title") or "", body))
    return out


def collect(blogs: list[dict], log=lambda m: None) -> list[dict]:
    out = []
    for b in blogs:
        client = Client(min_interval=float(b.get("delay", 2)))
        try:
            got = (wordpress(client, b["name"], b["url"], b.get("search", ["PSSD"])) if b["kind"] == "wordpress"
                   else rss(client, b["name"], b["url"]))
            log(f"- blog {b['name']}: {len(got)} articles")
            out.extend(got)
        except Exception as e:  # noqa: BLE001 - one site being down must not lose the others
            log(f"! blog {b['name']} failed: {e}")
    return out
