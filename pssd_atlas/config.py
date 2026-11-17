"""Load and validate the TOML configuration."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")
SCOPES = ("core", "related", "adjacent")


@dataclass
class Tagger:
    id: str
    label: str
    patterns: list[str]
    kind: str = ""
    description: str = ""
    regex: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        self.regex = re.compile("|".join(f"(?:{p})" for p in self.patterns), re.IGNORECASE)


@dataclass
class Config:
    queries: list[dict]
    trial_terms: list[str]
    trial_relevance: dict[str, re.Pattern]
    hypotheses: list[Tagger]
    interventions: list[Tagger]
    faers_reactions: list[str]
    faers_composite: list[str]
    faers_drugs: list[dict]

    @property
    def drug_tagger(self) -> list[Tagger]:
        return [Tagger(d["name"], d["name"].capitalize(), [rf"\b{re.escape(d['name'])}\b"])
                for d in self.faers_drugs if not d.get("control")]


def _clean(term: str) -> str:
    return " ".join(term.split())


def load(path: Path | None = None) -> Config:
    raw = tomllib.loads((path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    queries = []
    for q in raw["query"]:
        if q["scope"] not in SCOPES:
            raise ValueError(f"query {q['id']}: scope must be one of {SCOPES}")
        queries.append({**q, "pubmed": _clean(q.get("pubmed", "")), "europepmc": _clean(q.get("europepmc", ""))})
    trials = raw.get("trials", {})
    relevance = {scope: re.compile("|".join(f"(?:{p})" for p in pats), re.IGNORECASE | re.DOTALL)
                 for scope, pats in trials.get("relevance", {}).items()}
    faers = raw.get("faers", {})
    return Config(
        queries=queries,
        trial_terms=trials.get("terms", []),
        trial_relevance=relevance,
        hypotheses=[Tagger(h["id"], h["label"], h["patterns"], h.get("kind", "mechanism"), h.get("description", ""))
                    for h in raw.get("hypothesis", [])],
        interventions=[Tagger(i["id"], i["label"], i["patterns"]) for i in raw.get("intervention", [])],
        faers_reactions=faers.get("reactions", []),
        faers_composite=faers.get("composite", []),
        faers_drugs=faers.get("drug", []),
    )
