"""Turn patient posts into anonymous, structured tags.

Keyword-based and deliberately conservative. The post text itself is never
written to the published data: only tags, a date and a link back to the post.
"""

from __future__ import annotations

import re

from .config import Config

OUTCOMES = ("better", "none", "worse", "mixed", "mentioned")

_SENT = re.compile(r"(?<=[.!?\n])\s+")
_NONE = re.compile(r"(no|zero|without any|didn'?t (have|notice|see) any) (real |noticeable |lasting )?(effect|change|difference|improvement|benefit)s?"
                   r"|(did|does|do|has|have)(n'?t| not) (really )?(help|work|do anything|done anything|improve)\w*"
                   r"|did nothing|does nothing|no help|useless|not help(ing|ed)?", re.I)
_WORSE = re.compile(r"\bworse\b|worsen|crash(ed|es)?\b|set ?back|regret|ruined|damag", re.I)
_BETTER = re.compile(r"\bhelp(ed|s|ing|ful)?\b|improv|\bbetter\b|recover|\bcured?\b|\bwindows?\b|\bwork(ed|s|ing)\b"
                     r"|came back|return(ed|ing)\b|restor|benefit", re.I)
_RECOVERY = re.compile(r"\b(recovered|recovery|remission|cured|back to normal|healed)\b", re.I)


def _outcome(sentences: list[str]) -> str:
    seen = set()
    for s in sentences:
        if _NONE.search(s):
            seen.add("none")
            s = _NONE.sub(" ", s)          # so "didn't help" is not also read as "help"
        if _WORSE.search(s):
            seen.add("worse")
        if _BETTER.search(s):
            seen.add("better")
    if not seen:
        return "mentioned"
    if "better" in seen and "worse" in seen:
        return "mixed"
    for o in ("better", "worse", "none"):
        if o in seen:
            return o
    return "mentioned"


def extract(post: dict, cfg: Config) -> dict:
    """Structured, text-free record for one post."""
    text = f"{post.get('title', '')}. {post.get('text', '')}"
    sentences = [s for s in _SENT.split(text) if s.strip()]
    drugs = [t.id for t in cfg.drug_tagger if t.regex.search(text)]
    treatments = []
    for t in [*cfg.interventions, *cfg.community_interventions]:
        hits = [s for s in sentences if t.regex.search(s)]
        if hits:
            treatments.append({"id": t.id, "outcome": _outcome(hits)})
    # Blog articles are published under their titles; forum and Reddit posts stay untitled.
    extra = {"title": post.get("title", "")} if post["source"] == "blog" else {}
    return {
        **extra,
        "id": post["id"], "source": post["source"], "community": post.get("community", ""),
        "url": post["url"], "date": post.get("date", ""), "replies": post.get("replies", 0),
        "drugs": drugs,
        "partitions": cfg.partitions_for(drugs, text, paper=False),
        "symptoms": [t.id for t in cfg.symptoms if t.regex.search(text)],
        "treatments": treatments,
        "recovery": bool(_RECOVERY.search(text)),
    }
