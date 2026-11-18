#!/usr/bin/env python3
"""Catalogue GEO series relevant to persistent post-drug sexual dysfunction.

Standard library only.  Queries NCBI E-utilities (db=gds, series entries) for
each drug of interest, pulls the document summaries, classifies every series
with keyword rules (drug, tissue relevance, washout/withdrawal design, early
life exposure) and writes:

    geo_datasets.json    every record with its classification
    GEO_CATALOGUE.md     ranked shortlist, counts, and a statement of gaps

Usage:
    python3 geo_search.py [--cache DIR] [--out DIR] [--top N]

--cache DIR  keeps the raw E-utilities responses so a re-run does not hit
             NCBI again (delete the directory to refresh).
Hand-checked notes for individual accessions live in geo_manual_notes.json
next to this script; they are merged into the outputs (and can override the
keyword classification) but never add an accession the API did not return.

The keyword rules are deliberately simple and over-inclusive.  They read only
the title, summary and sample titles that GEO returns, so "washout: none" means
"no washout wording found", not "verified absent".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
USER_AGENT = "pssd-atlas/0.1 (research evidence mapper)"
MIN_INTERVAL = 0.40  # seconds between requests (< 3 requests / second)
HERE = Path(__file__).resolve().parent
MAX_TITLES_STORED = 40  # per series, to keep geo_datasets.json small

# drug -> (class, search synonyms)
DRUGS = {
    "fluoxetine": ("SSRI", ["fluoxetine", "prozac"]),
    "paroxetine": ("SSRI", ["paroxetine"]),
    "sertraline": ("SSRI", ["sertraline"]),
    "citalopram": ("SSRI", ["citalopram"]),
    "escitalopram": ("SSRI", ["escitalopram"]),
    "venlafaxine": ("SNRI", ["venlafaxine"]),
    "duloxetine": ("SNRI", ["duloxetine"]),
    "olanzapine": ("antipsychotic", ["olanzapine"]),
    "quetiapine": ("antipsychotic", ["quetiapine"]),
    "risperidone": ("antipsychotic", ["risperidone"]),
    "aripiprazole": ("antipsychotic", ["aripiprazole"]),
    "haloperidol": ("antipsychotic", ["haloperidol"]),
    "clozapine": ("antipsychotic", ["clozapine"]),
    "mirtazapine": ("mirtazapine", ["mirtazapine"]),
    "finasteride": ("5ARI", ["finasteride"]),
    "dutasteride": ("5ARI", ["dutasteride"]),
    "isotretinoin": ("retinoid", ["isotretinoin", "13-cis retinoic acid",
                                  "13-cis-retinoic acid", "accutane"]),
}
# Class-level queries that catch series not naming a single drug in indexed text.
EXTRA_QUERIES = {
    "class:SSRI": '"SSRI" OR "selective serotonin reuptake inhibitor" OR "serotonin reuptake inhibitors"',
    "class:antidepressant-withdrawal": '(antidepressant OR antidepressants) AND (withdrawal OR discontinuation OR washout)',
    "class:antipsychotic-withdrawal": '(antipsychotic OR antipsychotics OR neuroleptic) AND (withdrawal OR discontinuation OR washout)',
}

_last_request = [0.0]


def fetch(endpoint: str, params: dict, cache: Path | None) -> bytes:
    query = urllib.parse.urlencode(params)
    key = hashlib.sha256((endpoint + "?" + query).encode()).hexdigest()[:24]
    if cache is not None:
        hit = cache / f"{endpoint.split('.')[0]}_{key}.json"
        if hit.exists():
            return hit.read_bytes()
    for attempt in range(5):
        wait = MIN_INTERVAL - (time.monotonic() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()
        req = urllib.request.Request(EUTILS + endpoint, data=query.encode(),
                                     headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read()
            json.loads(body)  # validate before caching
            break
        except Exception as exc:  # network / 429 / malformed JSON
            if attempt == 4:
                raise
            print(f"  retry {attempt + 1} after error: {exc}", file=sys.stderr)
            time.sleep(2 + 2 * attempt)
    if cache is not None:
        hit.write_bytes(body)
    return body


def esearch(term: str, cache: Path | None) -> list[str]:
    ids, start = [], 0
    while True:
        data = json.loads(fetch("esearch.fcgi", {
            "db": "gds", "term": term, "retmode": "json",
            "retmax": 500, "retstart": start}, cache))["esearchresult"]
        ids.extend(data.get("idlist", []))
        start += 500
        if start >= int(data.get("count", 0)):
            return ids


def esummary(ids: list[str], cache: Path | None) -> dict:
    out = {}
    for i in range(0, len(ids), 200):
        data = json.loads(fetch("esummary.fcgi", {
            "db": "gds", "id": ",".join(ids[i:i + 200]), "retmode": "json"},
            cache))["result"]
        for uid in data.get("uids", []):
            out[uid] = data[uid]
    return out


# --------------------------------------------------------------------------
# classification rules
# --------------------------------------------------------------------------
def rx(*words: str) -> re.Pattern:
    return re.compile("|".join(words), re.I)


TISSUE_RULES = [  # first match wins; ordered by relevance
    ("sensory_spinal_genital", 5, rx(
        r"dorsal root gangli", r"\bDRGs?\b", r"sensory neuron", r"nocicept",
        r"trigeminal gangli", r"spinal cord", r"\bpenis\b", r"\bpenile\b",
        r"corpus cavernos", r"corpora cavernos", r"clitor", r"\bgenital",
        r"pelvic gangli", r"pudendal", r"\bvagina", r"foreskin",
        r"peripheral nerve", r"sciatic nerve")),
    ("hypothalamus_accumbens", 4, rx(
        r"hypothalam", r"nucleus accumbens", r"\bNAc\b", r"ventral striatum",
        r"preoptic", r"ventral tegmental")),
    ("brain_other", 3, rx(
        r"hippocamp", r"dentate gyrus", r"prefrontal", r"\bcortex\b",
        r"cortical", r"striat", r"amygdal", r"raphe", r"\bbrain\b",
        r"cerebell", r"habenula", r"cingulate", r"forebrain", r"midbrain",
        r"astrocyt", r"microglia", r"oligodendro", r"caudate", r"putamen")),
    ("reproductive_endocrine", 3, rx(
        r"prostate", r"prostatic", r"\btestis\b", r"\btestes\b", r"testicular",
        r"epididym", r"seminal vesicle", r"\bovar(y|ies|ian)\b", r"uter(us|ine)",
        r"placenta", r"pituitary", r"adrenal", r"leydig", r"sertoli")),
    ("ipsc_neuron", 2, rx(
        r"iPSC", r"induced pluripotent", r"\bhPSC", r"organoid",
        r"neural progenitor", r"neuronal culture", r"primary neuron",
        r"cultured neurons?", r"SH-SY5Y", r"neuroblastoma", r"\bneurons?\b",
        r"neural stem")),
    ("blood_immune", 1, rx(
        r"\bblood\b", r"PBMC", r"lymphoblastoid", r"\bLCLs?\b", r"leukocyte",
        r"lymphocyte", r"monocyte", r"macrophage", r"platelet")),
    ("skin_hair", 1, rx(
        r"\bskin\b", r"sebocyte", r"sebaceous", r"\bacne\b", r"hair follicle",
        r"dermal papilla", r"keratinocyte", r"scalp")),
]

WASHOUT_STRONG = rx(
    r"withdraw", r"wash[- ]?out", r"discontinu", r"cessation",
    r"drug[- ]free", r"post[- ]treatment", r"after (the )?(end|cessation|termination) of",
    r"treatment[- ]free", r"abstinen", r"recovery period", r"off[- ]drug",
    r"after stopping", r"suspension of (the )?treatment", r"post[- ]finasteride",
    r"post[- ]SSRI", r"\bPSSD\b", r"\bPFS\b")
WASHOUT_WEAK = rx(
    r"persist", r"long[- ]lasting", r"enduring", r"long[- ]term (effect|consequence|change)",
    r"lasting (effect|change)", r"irreversib", r"reversib", r"weeks? after",
    r"days? after (the )?(last|final)", r"months? after")
EARLY_LIFE = rx(
    r"perinatal", r"prenatal", r"neonatal", r"postnatal", r"in utero",
    r"gestation", r"maternal", r"early[- ]life", r"adolescen", r"juvenile",
    r"developmental exposure", r"during pregnancy", r"lactation", r"offspring",
    r"embryo", r"\bfetal\b", r"\bfoetal\b", r"larva")
ADULT_READOUT = rx(r"adult", r"later life", r"long[- ]term", r"persist", r"lasting")
CANCER = rx(r"cancer", r"carcinoma", r"tumou?r", r"leukemi", r"leukaemi",
            r"glioma", r"glioblastoma", r"lymphoma", r"melanoma", r"\bLNCaP\b",
            r"neuroblastoma", r"metasta")
DREADD = rx(r"DREADD", r"clozapine[- ]N[- ]oxide", r"\bCNO\b", r"chemogenetic",
            r"hM3Dq", r"hM4Di")
CLOZAPINE_REAL = re.compile(r"clozapine(?![- ]N[- ]oxide)", re.I)
SEXUAL = rx(r"sexual", r"libido", r"erectile", r"\bPSSD\b",
            r"post[- ]finasteride", r"\bPFS\b", r"copulat", r"anorgasm")


def platform_type(gdstype: str) -> str:
    t = (gdstype or "").lower()
    kinds = []
    if "high throughput sequencing" in t:
        if "expression" in t:
            kinds.append("RNA-seq")
        if "methylation" in t:
            kinds.append("methylation-seq")
        if "genome binding" in t or "occupancy" in t:
            kinds.append("ChIP/ATAC-seq")
        if "non-coding" in t:
            kinds.append("ncRNA-seq")
        if not kinds:
            kinds.append("sequencing-other")
    if "by array" in t:
        if "expression" in t:
            kinds.append("expression array")
        if "methylation" in t:
            kinds.append("methylation array")
        if "non-coding" in t:
            kinds.append("ncRNA array")
        if not any("array" in k for k in kinds):
            kinds.append("array-other")
    if "rt-pcr" in t:
        kinds.append("RT-PCR")
    return "; ".join(dict.fromkeys(kinds)) or (gdstype or "unknown")


def classify(rec: dict) -> dict:
    core = f"{rec['title']} . {rec['summary']}"
    text = core + " . " + " | ".join(rec["sample_titles"])

    drugs_text = []
    for drug, (_, syns) in DRUGS.items():
        for s in syns:
            pat = re.escape(s).replace(r"\ ", r"[- ]").replace(r"\-", r"[- ]")
            if drug == "clozapine":
                found = bool(CLOZAPINE_REAL.search(text))
            else:
                found = bool(re.search(pat, text, re.I))
            if found:
                drugs_text.append(drug)
                break
    drug_named = bool(drugs_text)
    drugs = drugs_text or sorted(q for q in rec["matched_queries"] if q in DRUGS)
    classes = sorted({DRUGS[d][0] for d in drugs})
    dreadd_only = bool(DREADD.search(text)) and "clozapine" not in drugs_text and \
        set(q for q in rec["matched_queries"] if q in DRUGS) <= {"clozapine"}

    tissue, tissue_score, tissue_hit = "other_or_unclear", 0, ""
    for name, score, pat in TISSUE_RULES:
        m = pat.search(text)
        if m:
            tissue, tissue_score, tissue_hit = name, score, m.group(0)
            break

    strong = sorted({m.group(0).lower() for m in WASHOUT_STRONG.finditer(text)})
    weak = sorted({m.group(0).lower() for m in WASHOUT_WEAK.finditer(text)})
    early = sorted({m.group(0).lower() for m in EARLY_LIFE.finditer(text)})
    early_adult = bool(early) and bool(ADULT_READOUT.search(text))
    if strong:
        washout = "washout_keyword"
    elif early_adult:
        washout = "early_life_exposure_adult_readout"
    elif early:
        washout = "early_life_exposure"
    elif weak:
        washout = "persistence_wording_only"
    else:
        washout = "none_found"

    cancer = bool(CANCER.search(core))
    sexual = bool(SEXUAL.search(text))

    score = tissue_score
    score += {"washout_keyword": 6, "early_life_exposure_adult_readout": 3,
              "early_life_exposure": 2, "persistence_wording_only": 1,
              "none_found": 0}[washout]
    score += 2 if drug_named else -3
    score += 2 if sexual else 0
    score -= 3 if cancer else 0
    score -= 6 if dreadd_only else 0
    score += 1 if rec["n_samples"] >= 12 else 0
    if rec["organism"] and not re.search(
            r"Homo sapiens|Mus musculus|Rattus|Macaca", rec["organism"]):
        score -= 1  # fish, worms, etc.: weaker translational relevance

    return {
        "drugs": drugs, "drug_classes": classes, "drug_named_in_text": drug_named,
        "dreadd_ligand_only": dreadd_only,
        "tissue_category": tissue, "tissue_score": tissue_score,
        "tissue_keyword": tissue_hit,
        "washout_class": washout, "washout_keywords": strong,
        "persistence_keywords": weak, "early_life_keywords": early,
        "cancer_context": cancer, "sexual_function_wording": sexual,
        "relevance_score": score,
    }


def build_record(doc: dict, queries: set[str]) -> dict:
    samples = doc.get("samples") or []
    supp = doc.get("suppfile", "") or ""
    return {
        "accession": doc.get("accession", ""),
        "title": doc.get("title", ""),
        "organism": doc.get("taxon", ""),
        "n_samples": int(doc.get("n_samples") or 0),
        "gds_type": doc.get("gdstype", ""),
        "platform_type": platform_type(doc.get("gdstype", "")),
        "platforms": ["GPL" + p for p in (doc.get("gpl", "") or "").split(";") if p],
        "summary": doc.get("summary", ""),
        "pubmed_ids": [str(p) for p in doc.get("pubmedids", [])],
        "release_date": doc.get("pdat", ""),
        "supplementary_file_types": supp,
        "ftp_link": doc.get("ftplink", ""),
        "sample_titles": [s.get("title", "") for s in samples],
        "matched_queries": sorted(queries),
    }


def md_escape(s: str) -> str:
    return s.replace("|", "/").replace("\n", " ").strip()


def write_markdown(records, notes, path: Path, top: int, queries_run: dict):
    relevant = [r for r in records if r["drug_named_in_text"] and not r["dreadd_ligand_only"]]
    L = []
    A = L.append
    A("# GEO catalogue: transcriptomic / epigenomic datasets on drugs linked to persistent sexual dysfunction\n")
    A(f"Generated by `analysis/geo_search.py` on {time.strftime('%Y-%m-%d')} from NCBI GEO DataSets "
      "(E-utilities, `db=gds`, series entries only). Full machine-readable list: `geo_datasets.json`.\n")
    A("**How to read this.** Classification is by keyword rules over the title, summary and sample "
      "titles that GEO returns. It is over-inclusive and has not been checked against the papers, "
      "except for the entries carrying a *hand-check* note (those were read by eye: GEO summary and, "
      "where stated, the sample table). A dataset being listed here does not mean it shows anything "
      "about persistent sexual dysfunction; almost none were designed to.\n")
    A("## Counts\n")
    A(f"- Series returned by all queries (deduplicated): **{len(records)}**")
    A(f"- Series where a target drug is actually named in title/summary/sample titles, excluding "
      f"DREADD-ligand (clozapine-N-oxide) hits: **{len(relevant)}**")
    A(f"- Dropped from the counts below: {sum(r['dreadd_ligand_only'] for r in records)} chemogenetics "
      f"series (clozapine-N-oxide), {sum((not r['drug_named_in_text']) and not r['dreadd_ligand_only'] for r in records)} "
      "series where the drug name was matched only in fields the summary API does not return.\n")
    A("### By drug (a series can count under several drugs)\n")
    A("| Drug | Class | Series | ...with washout keyword | ...early-life exposure |")
    A("|---|---|---:|---:|---:|")
    for drug, (cls, _) in DRUGS.items():
        rs = [r for r in relevant if drug in r["drugs"]]
        A(f"| {drug} | {cls} | {len(rs)} | {sum(r['washout_class'] == 'washout_keyword' for r in rs)} | "
          f"{sum(r['washout_class'].startswith('early_life') for r in rs)} |")
    A("\n### By tissue category\n")
    A("| Tissue category (keyword rule, first match wins) | Series | ...with washout keyword |")
    A("|---|---:|---:|")
    order = [t[0] for t in TISSUE_RULES] + ["other_or_unclear"]
    for t in order:
        rs = [r for r in relevant if r["tissue_category"] == t]
        A(f"| {t} | {len(rs)} | {sum(r['washout_class'] == 'washout_keyword' for r in rs)} |")
    A("\n### Drug class x tissue category\n")
    classes = ["SSRI", "SNRI", "antipsychotic", "mirtazapine", "5ARI", "retinoid"]
    A("| Tissue | " + " | ".join(classes) + " |")
    A("|---|" + "---:|" * len(classes))
    for t in order:
        row = [str(sum(1 for r in relevant if r["tissue_category"] == t and c in r["drug_classes"]))
               for c in classes]
        A(f"| {t} | " + " | ".join(row) + " |")
    A("\n### By washout class and platform\n")
    for label, key in (("Washout class", "washout_class"), ("Platform type", "platform_type"),
                       ("Organism", "organism")):
        c = Counter(r[key] for r in relevant)
        A(f"- **{label}:** " + "; ".join(f"{k or 'unknown'} {v}" for k, v in c.most_common(12)))
    A("")

    # ---- shortlist ----
    def rank_key(r):
        n = notes.get(r["accession"], {})
        return (-(n.get("priority", 0)), -r["relevance_score"], r["accession"])
    ranked = sorted(relevant, key=rank_key)
    ranked = [r for r in ranked if not notes.get(r["accession"], {}).get("exclude")]
    A(f"## Ranked shortlist (top {top})\n")
    A("Ranking = hand-check priority first (where a note exists), then the keyword relevance score "
      "(tissue relevance + washout/early-life design + drug named + sexual-function wording - cancer context).\n")
    A("| # | Accession | Drug(s) | Organism | Tissue (rule) | n | Platform | Washout class | Why it is here |")
    A("|---:|---|---|---|---|---:|---|---|---|")
    for i, r in enumerate(ranked[:top], 1):
        n = notes.get(r["accession"], {})
        why = n.get("note") or (
            f"keyword-only: tissue '{r['tissue_keyword']}'; washout words {r['washout_keywords'] or r['early_life_keywords'] or '-'}")
        if n.get("note"):
            why = "*hand-check:* " + why
        pm = (" PMID " + ",".join(r["pubmed_ids"])) if r["pubmed_ids"] else " (no PMID linked)"
        A(f"| {i} | [{r['accession']}](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={r['accession']}) | "
          f"{', '.join(r['drugs'])} | {md_escape(r['organism'])} | {r['tissue_category']} | {r['n_samples']} | "
          f"{r['platform_type']} | {r['washout_class']} | {md_escape(r['title'])[:110]}. {md_escape(why)}{pm} |")
    A("")
    excluded = [r for r in relevant if notes.get(r["accession"], {}).get("exclude")]
    if excluded:
        A("### High keyword score but excluded after hand-check\n")
        for r in sorted(excluded, key=lambda r: r["accession"]):
            A(f"- **{r['accession']}** ({', '.join(r['drugs'])}): {md_escape(notes[r['accession']].get('note', ''))}")
        A("")

    # ---- gaps ----
    A("## What is missing\n")
    def has(pred):
        return sorted((r for r in relevant if pred(r)), key=lambda r: r["accession"])
    sens = has(lambda r: r["tissue_category"] == "sensory_spinal_genital")
    A(f"- **Sensory ganglia / spinal cord / genital tissue:** {len(sens)} series hit a sensory/spinal/genital "
      "keyword anywhere in their text: " + (", ".join(f"{r['accession']} ({'/'.join(r['drugs'])})" for r in sens) or "none") +
      ". See the hand-check notes and the gap statement below for which of these truly profile such tissue after drug exposure.")
    for cls in ("antipsychotic", "mirtazapine", "5ARI", "retinoid", "SNRI", "SSRI"):
        rs = has(lambda r, c=cls: c in r["drug_classes"] and r["washout_class"] == "washout_keyword")
        A(f"- **{cls} with a washout keyword:** {len(rs)} series" +
          (": " + ", ".join(r["accession"] for r in rs[:30]) + (" ..." if len(rs) > 30 else "") if rs else "."))
    A("")
    gap = notes.get("_gap_statement")
    if gap:
        A("### Hand-checked gap statement\n")
        for line in gap:
            A(f"- {line}")
        A("")
    A("## Queries run\n")
    A("| Query | Term sent to esearch (db=gds) | Series returned |")
    A("|---|---|---:|")
    for q, (term, n) in queries_run.items():
        A(f"| {q} | `{md_escape(term)}` | {n} |")
    A("")
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)

    uid_queries: dict[str, set[str]] = {}
    queries_run = {}
    terms = {d: " OR ".join(f'"{s}"[All Fields]' for s in syns) for d, (_, syns) in DRUGS.items()}
    terms.update(EXTRA_QUERIES)
    for name, expr in terms.items():
        term = f"({expr}) AND gse[Entry Type]"
        ids = esearch(term, args.cache)
        queries_run[name] = (term, len(ids))
        print(f"{name:35s} {len(ids):5d} series", file=sys.stderr)
        for uid in ids:
            uid_queries.setdefault(uid, set()).add(name)

    docs = esummary(sorted(uid_queries, key=int), args.cache)
    records = []
    for uid, doc in docs.items():
        if doc.get("entrytype") != "GSE":
            continue
        rec = build_record(doc, uid_queries.get(uid, set()))
        rec.update(classify(rec))  # classification reads every sample title
        rec["n_sample_titles_listed"] = len(rec["sample_titles"])
        rec["sample_titles"] = rec["sample_titles"][:MAX_TITLES_STORED]
        records.append(rec)

    notes_path = HERE / "geo_manual_notes.json"
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}
    known = {r["accession"] for r in records}
    for acc in [k for k in notes if not k.startswith("_") and k not in known]:
        print(f"warning: manual note for {acc} ignored (not returned by the API)", file=sys.stderr)
        del notes[acc]
    for r in records:
        n = notes.get(r["accession"])
        if n:
            r["manual_check"] = n
    records.sort(key=lambda r: (-r["relevance_score"], r["accession"]))

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "geo_datasets.json").write_text(json.dumps({
        "generated": time.strftime("%Y-%m-%d"),
        "source": "NCBI GEO DataSets via E-utilities (db=gds, gse[Entry Type])",
        "queries": {k: {"term": t, "n_series": n} for k, (t, n) in queries_run.items()},
        "n_records": len(records),
        "records": records,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    write_markdown(records, notes, args.out / "GEO_CATALOGUE.md", args.top, queries_run)
    print(f"wrote {len(records)} records", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
