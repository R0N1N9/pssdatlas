"""Disproportionality analysis on FDA adverse-event reports (openFDA).

For each drug x reaction pair we build the classic 2x2 table

                    reaction    no reaction
    drug               a            b
    all other drugs    c            d

and report the reporting odds ratio (ROR) and proportional reporting ratio (PRR)
with 95% confidence intervals. The background is restricted to reports whose
drugs openFDA could map to a generic name, so numerator and denominator are
drawn from the same population.
"""

from __future__ import annotations

import json
import math

from .http import Client

BASE = "https://api.fda.gov/drug/event.json"
DRUG_FIELD = "patient.drug.openfda.generic_name"
REACTION_FIELD = "patient.reaction.reactionmeddrapt.exact"
BACKGROUND = f"_exists_:{DRUG_FIELD}"


def disproportionality(a: int, drug_total: int, reaction_total: int, n: int) -> dict:
    """ROR and PRR with 95% CIs from marginal counts. Returns None stats when undefined."""
    b = drug_total - a
    c = reaction_total - a
    d = n - a - b - c
    out = {"a": a, "b": b, "c": c, "d": d, "ror": None, "ror_lo": None, "ror_hi": None,
           "prr": None, "prr_lo": None, "prr_hi": None, "signal": False}
    if min(a, b, c, d) <= 0:
        return out
    ror = (a / b) / (c / d)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    prr = (a / (a + b)) / (c / (c + d))
    se_prr = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    out.update(
        ror=ror, ror_lo=math.exp(math.log(ror) - 1.96 * se), ror_hi=math.exp(math.log(ror) + 1.96 * se),
        prr=prr, prr_lo=math.exp(math.log(prr) - 1.96 * se_prr), prr_hi=math.exp(math.log(prr) + 1.96 * se_prr),
    )
    # Conventional screening threshold: at least 3 cases and lower CI bound above 1.
    out["signal"] = a >= 3 and out["ror_lo"] > 1
    return out


def _reaction_clause(terms: list[str]) -> str:
    return "(" + " OR ".join(f'{REACTION_FIELD}:"{t}"' for t in terms) + ")"


def _drug_clause(name: str) -> str:
    return f'{DRUG_FIELD}:"{name}"'


def count(client: Client, search: str) -> int:
    """Number of reports matching an openFDA search expression (0 when none match)."""
    body = client.get(BASE, {"search": search, "limit": 1}, ok_statuses=(404,))
    data = json.loads(body)
    if "error" in data:
        if data["error"].get("code") == "NOT_FOUND":
            return 0
        raise RuntimeError(f"openFDA error for {search!r}: {data['error']}")
    return data["meta"]["results"]["total"]


def analyse(client: Client, drugs: list[dict], reactions: list[str], composite: list[str],
            progress=lambda msg: None) -> dict:
    n = count(client, BACKGROUND)
    groups = {"ANY SEXUAL DYSFUNCTION (composite)": composite, **{r: [r] for r in reactions}}
    reaction_totals = {}
    for label, terms in groups.items():
        reaction_totals[label] = count(client, f"{BACKGROUND} AND {_reaction_clause(terms)}")
    rows = []
    for drug in drugs:
        name = drug["name"]
        progress(f"  openFDA: {name}")
        drug_total = count(client, _drug_clause(name))
        for label, terms in groups.items():
            a = count(client, f"{_drug_clause(name)} AND {_reaction_clause(terms)}") if drug_total else 0
            rows.append({"drug": name, "drug_class": drug.get("class", ""), "control": bool(drug.get("control")),
                         "reaction": label, "composite": len(terms) > 1, "drug_total": drug_total,
                         "reaction_total": reaction_totals[label],
                         **disproportionality(a, drug_total, reaction_totals[label], n)})
    return {"n_reports": n, "reactions": list(groups), "composite_terms": composite, "rows": rows}
