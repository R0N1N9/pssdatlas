"""Build the self-contained HTML report."""

from __future__ import annotations

import json
from pathlib import Path

from . import classify
from .config import Config

TEMPLATE = Path(__file__).with_name("template.html")


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def payload(cfg: Config, data: Path) -> dict:
    return {
        "meta": _read(data / "meta.json", {}),
        "papers": _read(data / "papers.json", []),
        "trials": _read(data / "trials.json", []),
        "faers": _read(data / "faers.json", {"rows": [], "reactions": [], "n_reports": 0}),
        "targets": _read(data / "targets.json", {"targets": [], "binding": {}}),
        "drugClasses": {d["name"]: d.get("class", "") for d in cfg.faers_drugs},
        "community": _read(data / "community.json", []),
        "partitions": [{"id": p.id, "label": p.label, "description": p.description, "drugs": sorted(p.drugs),
                        "everything": p.everything} for p in cfg.partitions],
        "symptoms": [{"id": s.id, "label": s.label} for s in cfg.symptoms],
        "communityInterventions": [{"id": i.id, "label": i.label} for i in cfg.community_interventions],
        "studyTypes": [{"id": i, "label": l} for i, l in classify.STUDY_TYPES],
        "humanPrimary": sorted(classify.HUMAN_PRIMARY),
        "hypotheses": [{"id": h.id, "label": h.label, "kind": h.kind, "description": h.description}
                       for h in cfg.hypotheses],
        "interventions": [{"id": i.id, "label": i.label} for i in cfg.interventions],
        "queries": [{"id": q["id"], "scope": q["scope"], "label": q["label"]} for q in cfg.queries],
    }


def build(cfg: Config, data: Path, out: Path) -> None:
    blob = json.dumps(payload(cfg, data), ensure_ascii=False, separators=(",", ":"))
    # Keep the embedded JSON from terminating the <script> element or opening a comment.
    blob = blob.replace("</", "<\\/").replace("<!--", "<\\!--")
    app = TEMPLATE.with_name("app.js").read_text(encoding="utf-8")
    # Replace the script first so text inside the data can never be mistaken for the placeholder.
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__APP__*/", app).replace("/*__DATA__*/null", blob)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
