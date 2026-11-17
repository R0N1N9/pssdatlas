"""Preprints via Europe PMC (medRxiv, bioRxiv, Research Square, PsyArXiv, ...)."""

from __future__ import annotations

import re

from .http import Client

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _strip_tags(s: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", s or "").split())


def search_preprints(client: Client, term: str, max_records: int = 500) -> list[dict]:
    out, cursor = [], "*"
    while len(out) < max_records:
        data = client.get_json(BASE, {"query": f"({term}) AND SRC:PPR", "format": "json",
                                      "resultType": "core", "pageSize": 100, "cursorMark": cursor})
        results = data.get("resultList", {}).get("result", [])
        for r in results:
            date = r.get("firstPublicationDate") or str(r.get("pubYear") or "")
            out.append({
                "id": f"PPR:{r['id']}",
                "source": "preprint",
                "title": _strip_tags(r.get("title", "")),
                "abstract": _strip_tags(r.get("abstractText", "")),
                "date": date,
                "year": int(date[:4]) if date[:4].isdigit() else None,
                "journal": (r.get("bookOrReportDetails") or {}).get("publisher", "") or "Preprint",
                "authors": [a.strip() for a in (r.get("authorString") or "").rstrip(".").split(",") if a.strip()],
                "doi": r.get("doi", ""),
                "url": f"https://europepmc.org/article/PPR/{r['id']}",
                "pub_types": ["Preprint"],
                "mesh": [],
            })
        nxt = data.get("nextCursorMark")
        if not results or not nxt or nxt == cursor:
            break
        cursor = nxt
    return out
