"""Tag records with study type, hypotheses, candidate treatments and implicated drugs."""

from __future__ import annotations

import re

from .config import Config

# Display order = rough strength of evidence for a causal/treatment claim.
STUDY_TYPES = [
    ("rct", "Randomised trial"),
    ("clinical_trial", "Other clinical trial"),
    ("observational", "Observational / survey"),
    ("case_report", "Case report / series"),
    ("animal", "Animal / preclinical"),
    ("systematic_review", "Systematic review"),
    ("review", "Narrative review"),
    ("commentary", "Letter / commentary"),
    ("other", "Unclassified"),
]
HUMAN_PRIMARY = {"rct", "clinical_trial", "observational", "case_report"}

_ANIMAL = re.compile(r"\b(rats?|mice|mouse|murine|rodents?|zebrafish|animal model|sprague[- ]dawley|wistar)\b", re.I)
_SYSREV = re.compile(r"systematic(ally)? review|meta-?analy|scoping review|umbrella review", re.I)
_RCT = re.compile(r"randomi[sz]ed|double[- ]blind|placebo[- ]controlled", re.I)
_CASE = re.compile(r"case (report|series|study|presentation)|\ba case of\b|report of (a|two|three|\d+) cases?|we (report|present|describe) (a|the|two|three|\d+) ", re.I)
_OBS = re.compile(r"\b(survey|cohort|cross[- ]sectional|case[- ]control|retrospective|prospective|questionnaire|"
                  r"pharmacovigilance|disproportionality|interviews?|respondents|participants (were|completed)|"
                  r"adverse event reporting|database)\b", re.I)
_TRIAL = re.compile(r"\b(open[- ]label|pilot (study|trial)|clinical trial|were treated with|treated \d+ patients)\b", re.I)
_COMMENT = re.compile(r"^(comment(ary)? on|correction|erratum|reply|response to|re:|letter)\b", re.I)
_REVIEW_BODY = re.compile(r"\b(this|the present) (review|article|paper|chapter|primer) (review|summari[sz]e|discuss|describe|provide|examine|outline|focus)"
                          r"|\bwe (review|summari[sz]e|discuss)\b|\bis reviewed\b|\bare reviewed\b|literature (was|is) reviewed", re.I)
_HUMAN_DATA = re.compile(r"\b\d+ (patients|men|women|subjects|participants|cases|individuals|outpatients)\b"
                         r"|\b(patients|subjects|men|women) (were|was) (evaluated|assessed|recruited|enrolled|interviewed|compared|examined)", re.I)
_REVIEW = re.compile(r"\b(review|overview|update|perspective|narrative)\b", re.I)


def study_type(rec: dict) -> str:
    pts = {p.lower() for p in rec.get("pub_types", [])}
    mesh = set(rec.get("mesh", []))
    title, abstract = rec.get("title", ""), rec.get("abstract", "")
    text = f"{title} {abstract}"

    if "randomized controlled trial" in pts:
        return "rct"
    if pts & {"meta-analysis", "systematic review"} or _SYSREV.search(title):
        return "systematic_review"
    if any(p.startswith("clinical trial") or p == "controlled clinical trial" for p in pts):
        return "clinical_trial"
    if "case reports" in pts:
        return "case_report"
    if ("Animals" in mesh and "Humans" not in mesh) or _ANIMAL.search(title):
        return "animal"
    if "review" in pts:
        return "review"
    if "observational study" in pts:
        return "observational"
    # No decisive publication type: fall back to the text.
    if _CASE.search(title) or (_CASE.search(abstract) and not _OBS.search(abstract)):
        return "case_report"
    if _RCT.search(title) or (_RCT.search(abstract) and re.search(r"\bwe randomi|were randomi|randomly assigned", abstract, re.I)):
        return "rct"
    if _SYSREV.search(abstract[:600]):
        return "systematic_review"
    if _ANIMAL.search(abstract) and not re.search(r"\b(patients|participants|men|women)\b", abstract, re.I):
        return "animal"
    if _OBS.search(text):
        return "observational"
    if _TRIAL.search(text):
        return "clinical_trial"
    if pts & {"letter", "editorial", "comment", "news", "published erratum"} or _COMMENT.search(title):
        return "commentary"
    if _REVIEW.search(title) or _REVIEW_BODY.search(abstract):
        return "review"
    if _HUMAN_DATA.search(abstract):
        return "observational"
    if not abstract:
        return "commentary"
    return "other"


def _tags(taggers, text: str) -> list[str]:
    return [t.id for t in taggers if t.regex.search(text)]


def classify_paper(rec: dict, cfg: Config) -> dict:
    text = f"{rec.get('title', '')} {rec.get('abstract', '')}"
    rec["study_type"] = study_type(rec)
    rec["hypotheses"] = _tags(cfg.hypotheses, text)
    rec["interventions"] = _tags(cfg.interventions, text)
    rec["drugs"] = _tags(cfg.drug_tagger, text)
    return rec


def trial_scope(trial: dict, cfg: Config) -> str | None:
    """Most direct scope whose relevance pattern matches the registry record, else None."""
    text = " ".join([trial.get("title", ""), trial.get("brief_title", ""), " ".join(trial.get("conditions", [])),
                     trial.get("summary", "")])
    for scope in ("core", "related", "adjacent"):
        rx = cfg.trial_relevance.get(scope)
        if rx and rx.search(text):
            return scope
    return None


def classify_trial(trial: dict, cfg: Config) -> dict:
    text = " ".join([trial.get("title", ""), " ".join(trial.get("interventions", [])), trial.get("summary", "")])
    trial["intervention_tags"] = _tags(cfg.interventions, text)
    return trial
