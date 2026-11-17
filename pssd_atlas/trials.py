"""Registered clinical studies via the ClinicalTrials.gov v2 API."""

from __future__ import annotations

from .http import Client

BASE = "https://clinicaltrials.gov/api/v2/studies"


def _parse(study: dict) -> dict:
    p = study.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status = p.get("statusModule", {})
    design = p.get("designModule", {})
    nct = ident.get("nctId", "")
    return {
        "id": nct,
        "title": ident.get("officialTitle") or ident.get("briefTitle", ""),
        "brief_title": ident.get("briefTitle", ""),
        "status": status.get("overallStatus", ""),
        "phases": design.get("phases", []),
        "study_type": design.get("studyType", ""),
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "start": (status.get("startDateStruct") or {}).get("date", ""),
        "completion": (status.get("completionDateStruct") or {}).get("date", ""),
        "conditions": (p.get("conditionsModule") or {}).get("conditions", []),
        "interventions": [i.get("name", "") for i in (p.get("armsInterventionsModule") or {}).get("interventions", [])],
        "sponsor": ((p.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name", ""),
        "summary": (p.get("descriptionModule") or {}).get("briefSummary", ""),
        "has_results": bool(study.get("hasResults")),
        "url": f"https://clinicaltrials.gov/study/{nct}",
    }


def search(client: Client, term: str, max_records: int = 1000) -> list[dict]:
    out, token = [], None
    while len(out) < max_records:
        params = {"query.term": term, "pageSize": 100}
        if token:
            params["pageToken"] = token
        data = client.get_json(BASE, params)
        out.extend(_parse(s) for s in data.get("studies", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return out
