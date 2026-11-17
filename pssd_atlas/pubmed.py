"""PubMed via NCBI E-utilities."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .http import Client

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search(client: Client, term: str, retmax: int = 5000) -> list[str]:
    data = client.get_json(f"{BASE}/esearch.fcgi",
                           {"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax})
    return data["esearchresult"].get("idlist", [])


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


_MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def _date(el) -> str:
    """ISO date from a PubMed date element, as precise as the record allows ('2019', '2019-03', '2019-03-07')."""
    if el is None:
        return ""
    year, month, day = (_text(el.find(k)) for k in ("Year", "Month", "Day"))
    if not year:
        medline = _text(el.find("MedlineDate"))  # e.g. "2019 Jan-Feb", "2004 Winter"
        m = re.search(r"((?:19|20)\d\d)(?:\s+([A-Za-z]{3}))?", medline)
        if not m:
            return ""
        year, month = m.group(1), m.group(2) or ""
    mm = int(month) if month.isdigit() else _MONTHS.get(month[:3].lower())
    if not mm:
        return year
    return f"{year}-{mm:02d}-{int(day):02d}" if day.isdigit() else f"{year}-{mm:02d}"


def parse(xml_text: str) -> list[dict]:
    out = []
    for art in ET.fromstring(xml_text).iter("PubmedArticle"):
        cit = art.find("MedlineCitation")
        a = cit.find("Article")
        pmid = _text(cit.find("PMID"))
        parts = []
        for ab in a.findall("Abstract/AbstractText"):
            label = ab.get("Label")
            body = _text(ab)
            parts.append(f"{label}: {body}" if label else body)
        # First publication: the earlier of the electronic date and the journal-issue date.
        dates = [d for d in (_date(a.find("ArticleDate")), _date(a.find("Journal/JournalIssue/PubDate"))) if d]
        date = min(dates, key=lambda d: (d + "-99-99")[:10]) if dates else ""
        authors = []
        for au in a.findall("AuthorList/Author"):
            name = " ".join(x for x in (_text(au.find("LastName")), _text(au.find("Initials"))) if x)
            authors.append(name or _text(au.find("CollectiveName")))
        doi = ""
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = _text(aid)
        out.append({
            "id": f"PMID:{pmid}",
            "source": "pubmed",
            "title": _text(a.find("ArticleTitle")),
            "abstract": " ".join(parts),
            "date": date,
            "year": int(date[:4]) if date else None,
            "journal": _text(a.find("Journal/ISOAbbreviation")) or _text(a.find("Journal/Title")),
            "authors": [x for x in authors if x],
            "doi": doi,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "pub_types": [_text(p) for p in a.findall("PublicationTypeList/PublicationType")],
            "mesh": [_text(m) for m in cit.findall("MeshHeadingList/MeshHeading/DescriptorName")],
        })
    return out


def fetch(client: Client, pmids: list[str], batch: int = 150) -> list[dict]:
    records = []
    for i in range(0, len(pmids), batch):
        xml_text = client.get(f"{BASE}/efetch.fcgi",
                              {"db": "pubmed", "id": ",".join(pmids[i:i + batch]), "retmode": "xml"}, post=True)
        records.extend(parse(xml_text))
    return records
