"""Read a forum thread page that someone saved from their own browser.

Splits the page into individual posts for the two common forum engines
(phpBB and Invision Community), so each person's account is tagged separately.
Falls back to treating the page as one piece of text. Author names are never read.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_VOID = {"br", "img", "hr", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
_SAVED_FROM = re.compile(r"<!--\s*saved from url=\(\d+\)(\S+)\s*-->")


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.url = self.title = ""
        self.posts: list[dict] = []
        self._stack: list[str] = []
        self._post_depth = None        # stack depth at which the current post body opened
        self._skip_depth = None        # inside a quote / script / signature within a post
        self._buf: list[str] = []
        self._last_time = ""
        self._in_title = False
        self._all: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "link" and a.get("rel") == "canonical" and a.get("href"):
            self.url = a["href"]
        if tag == "meta" and a.get("property") == "og:url" and a.get("content") and not self.url:
            self.url = a["content"]
        if tag == "time" and a.get("datetime"):
            self._last_time = a["datetime"][:10]
        if tag == "title":
            self._in_title = True
        if tag in _VOID:
            return
        self._stack.append(tag)
        if self._post_depth is None:
            # phpBB: <div class="content"> inside the post body; Invision: data-role="commentContent"
            if a.get("data-role") == "commentContent" or (tag == "div" and cls == ["content"]):
                self._post_depth, self._buf = len(self._stack), []
        elif self._skip_depth is None and (tag in ("blockquote", "script", "style") or "signature" in cls):
            self._skip_depth = len(self._stack)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in _VOID or tag not in self._stack:
            return
        while self._stack:
            depth = len(self._stack)
            top = self._stack.pop()
            if self._skip_depth == depth:
                self._skip_depth = None
            if self._post_depth == depth:
                text = " ".join(" ".join(self._buf).split())
                if len(text) > 40:
                    self.posts.append({"date": self._last_time, "text": text})
                self._post_depth = None
            if top == tag:
                break

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._stack and self._stack[-1] in ("script", "style"):
            return
        self._all.append(data)
        if self._post_depth is not None and self._skip_depth is None:
            self._buf.append(data)


def parse(html_text: str) -> dict:
    """{'url', 'title', 'posts': [{'date', 'text'}]}; one whole-page post when no forum structure is found."""
    p = _Page()
    p.feed(html_text)
    m = _SAVED_FROM.search(html_text[:2000])
    url = p.url or (m.group(1) if m else "")
    posts = p.posts or [{"date": p._last_time, "text": " ".join(" ".join(p._all).split())}]
    return {"url": url, "title": " ".join(p.title.split()), "posts": posts, "split": bool(p.posts)}
