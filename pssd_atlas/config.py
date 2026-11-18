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
class Partition:
    id: str
    label: str
    description: str
    drugs: set[str]                    # generic names, resolved from classes + explicit drugs
    terms: re.Pattern | None           # matched against any text
    paper_terms: re.Pattern | None     # matched against papers and trials only

    @property
    def everything(self) -> bool:
        return not self.drugs and not self.terms and not self.paper_terms

    def contains(self, drugs: list[str], text: str, paper: bool) -> bool:
        if self.everything or self.drugs.intersection(drugs):
            return True
        if self.terms and self.terms.search(text):
            return True
        return bool(paper and self.paper_terms and self.paper_terms.search(text))


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
    partitions: list[Partition] = field(default_factory=list)
    symptoms: list[Tagger] = field(default_factory=list)
    community_interventions: list[Tagger] = field(default_factory=list)
    reddit: dict = field(default_factory=dict)
    blogs: list[dict] = field(default_factory=list)
    targets: list[dict] = field(default_factory=list)

    @property
    def drug_tagger(self) -> list[Tagger]:
        """Generic and brand names map to the generic name."""
        return [Tagger(d["name"], d["name"].capitalize(),
                       [rf"\b{re.escape(n)}\b" for n in [d["name"], *d.get("aliases", [])]])
                for d in self.faers_drugs if not d.get("control")]

    def partitions_for(self, drugs: list[str], text: str, paper: bool) -> list[str]:
        return [p.id for p in self.partitions if p.contains(drugs, text, paper)]


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
    alt = lambda pats: re.compile("|".join(f"(?:{p})" for p in pats), re.IGNORECASE) if pats else None
    partitions = []
    for p in raw.get("partition", []):
        drugs = {d["name"] for d in faers.get("drug", []) if d.get("class") in p.get("classes", [])} | set(p.get("drugs", []))
        partitions.append(Partition(p["id"], p["label"], p.get("description", ""), drugs,
                                    alt(p.get("terms")), alt(p.get("paper_terms"))))
    com = raw.get("community", {})
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
        partitions=partitions,
        symptoms=[Tagger(x["id"], x["label"], x["patterns"]) for x in com.get("symptom", [])],
        community_interventions=[Tagger(x["id"], x["label"], x["patterns"]) for x in com.get("intervention", [])],
        reddit=com.get("reddit", {}),
        blogs=com.get("blog", []),
        targets=raw.get("target", []),
    )
