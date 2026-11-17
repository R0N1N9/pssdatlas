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
        year = _text(a.find("Journal/JournalIssue/PubDate/Year"))
        if not year:
            m = re.search(r"(19|20)\d\d", _text(a.find("Journal/JournalIssue/PubDate/MedlineDate")))
            year = m.group(0) if m else _text(a.find("ArticleDate/Year"))
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
            "year": int(year) if year.isdigit() else None,
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
