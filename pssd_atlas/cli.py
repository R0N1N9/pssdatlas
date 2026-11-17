"""Command-line interface: fetch sources, tag records, write data + report."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

from . import classify, config, europepmc, faers, pubmed, report, trials
from .http import Client

SCOPE_RANK = {"core": 0, "related": 1, "adjacent": 2}
SOURCES = ("pubmed", "preprints", "trials", "faers")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _merge(pool: dict, recs: list[dict], scope: str, query_id: str) -> None:
    for r in recs:
        cur = pool.get(r["id"])
        if cur is None:
            pool[r["id"]] = {**r, "scope": scope, "queries": [query_id]}
        else:
            if query_id not in cur["queries"]:
                cur["queries"].append(query_id)
            if SCOPE_RANK[scope] < SCOPE_RANK[cur["scope"]]:
                cur["scope"] = scope


def _norm_title(t: str) -> str:
    return "".join(ch for ch in t.lower() if ch.isalnum())


def cmd_update(args) -> int:
    cfg = config.load(args.config)
    data = Path(args.data)
    today = dt.date.today().isoformat()
    client = Client(cache_dir=None if args.no_cache else Path(args.cache), cache_ttl=args.cache_days * 86400)
    skip = set(args.skip or [])
    meta = _read(data / "meta.json", {})
    status = meta.setdefault("sources", {})
    failures = []

    def run(name, fn):
        """Run one source; on failure keep the previous snapshot for that source."""
        if name in skip:
            _log(f"- {name}: skipped")
            return None
        try:
            result = fn()
            status[name] = {"updated": today, "ok": True}
            return result
        except Exception as e:  # noqa: BLE001 - one flaky API must not lose the others
            _log(f"! {name} failed, keeping previous data: {e}")
            status[name] = {**status.get(name, {}), "ok": False, "error": str(e)[:300], "failed": today}
            failures.append(name)
            return None

    old_papers = {p["id"]: p for p in _read(data / "papers.json", [])}

    def get_pubmed():
        pool: dict = {}
        for q in cfg.queries:
            if not q["pubmed"]:
                continue
            ids = pubmed.search(client, q["pubmed"])
            _log(f"- pubmed [{q['id']}]: {len(ids)} records")
            _merge(pool, pubmed.fetch(client, ids), q["scope"], q["id"])
        return pool

    def get_preprints():
        pool: dict = {}
        for q in cfg.queries:
            if not q["europepmc"]:
                continue
            recs = europepmc.search_preprints(client, q["europepmc"])
            _log(f"- preprints [{q['id']}]: {len(recs)} records")
            _merge(pool, recs, q["scope"], q["id"])
        return pool

    pm = run("pubmed", get_pubmed)
    pp = run("preprints", get_preprints)
    if pm is None:
        pm = {k: v for k, v in old_papers.items() if v["source"] == "pubmed"}
    if pp is None:
        pp = {k: v for k, v in old_papers.items() if v["source"] == "preprint"}
    # Drop preprints that have since been published and indexed in PubMed.
    seen_dois = {p["doi"].lower() for p in pm.values() if p.get("doi")}
    seen_titles = {_norm_title(p["title"]) for p in pm.values()}
    pp = {k: v for k, v in pp.items()
          if v.get("doi", "").lower() not in seen_dois and _norm_title(v["title"]) not in seen_titles}

    papers = []
    for rec in {**pm, **pp}.values():
        rec["first_seen"] = old_papers.get(rec["id"], {}).get("first_seen", today)
        papers.append(classify.classify_paper(rec, cfg))
    papers.sort(key=lambda r: (-(r["year"] or 0), r["id"]))

    old_trials = {t["id"]: t for t in _read(data / "trials.json", [])}

    def get_trials():
        pool: dict = {}
        for term in cfg.trial_terms:
            found = trials.search(client, term)
            kept = 0
            for t in found:
                scope = classify.trial_scope(t, cfg)
                if scope and t["id"] not in pool:
                    pool[t["id"]] = {**t, "scope": scope}
                    kept += 1
            _log(f"- trials [{term}]: {len(found)} hits, {kept} new relevant")
        return pool

    tr = run("trials", get_trials)
    if tr is None:
        tr = old_trials
    trial_list = []
    for t in tr.values():
        t["first_seen"] = old_trials.get(t["id"], {}).get("first_seen", today)
        trial_list.append(classify.classify_trial(t, cfg))
    trial_list.sort(key=lambda t: (SCOPE_RANK[t["scope"]], t["id"]))

    def get_faers():
        _log("- openFDA adverse-event grid (a few minutes on first run)")
        return faers.analyse(client, cfg.faers_drugs, cfg.faers_reactions, cfg.faers_composite, progress=_log)

    fa = run("faers", get_faers)
    if fa is None:
        fa = _read(data / "faers.json", {"rows": [], "reactions": [], "n_reports": 0, "composite_terms": []})

    new_papers = [p for p in papers if p["id"] not in old_papers]
    new_trials = [t for t in trial_list if t["id"] not in old_trials]
    meta.update(generated=today, version=1)
    _write(data / "papers.json", papers)
    _write(data / "trials.json", trial_list)
    _write(data / "faers.json", fa)
    _write(data / "meta.json", meta)
    write_csv(data, papers, trial_list, fa)
    report.build(cfg, data, Path(args.report))

    _log(f"\n{len(papers)} papers, {len(trial_list)} trials, {len(fa['rows'])} drug-reaction pairs")
    if old_papers or old_trials:
        _log(f"New since last update: {len(new_papers)} papers, {len(new_trials)} trials")
        for p in new_papers[:30]:
            _log(f"  + [{p['year']}] {p['title'][:110]}  {p['url']}")
        for t in new_trials[:30]:
            _log(f"  + [trial] {t['brief_title'][:110]}  {t['url']}")
    _log(f"Report: {args.report}")
    return 1 if failures else 0


def write_csv(data: Path, papers, trial_list, fa) -> None:
    def dump(name, rows, cols):
        with (data / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow(["; ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else v)
                            for v in (r.get(c) for c in cols)])

    dump("papers.csv", papers, ["id", "source", "scope", "year", "study_type", "title", "journal", "authors", "doi",
                                "url", "hypotheses", "interventions", "drugs", "first_seen"])
    dump("trials.csv", trial_list, ["id", "scope", "status", "phases", "study_type", "enrollment", "start",
                                    "completion", "brief_title", "conditions", "interventions",
                                    "intervention_tags", "sponsor", "has_results", "url", "first_seen"])
    dump("faers.csv", fa["rows"], ["drug", "drug_class", "control", "reaction", "a", "b", "c", "d", "drug_total",
                                   "reaction_total", "ror", "ror_lo", "ror_hi", "prr", "prr_lo", "prr_hi", "signal"])


def cmd_report(args) -> int:
    report.build(config.load(args.config), Path(args.data), Path(args.report))
    _log(f"Report: {args.report}")
    return 0


def cmd_new(args) -> int:
    data = Path(args.data)
    since = args.since
    papers = [p for p in _read(data / "papers.json", []) if p["first_seen"] >= since]
    tl = [t for t in _read(data / "trials.json", []) if t["first_seen"] >= since]
    print(f"First seen on or after {since}: {len(papers)} papers, {len(tl)} trials\n")
    for p in papers:
        print(f"[{p['scope']}/{p['study_type']}] {p['year']} {p['title']}\n    {p['url']}")
    for t in tl:
        print(f"[{t['scope']}/trial/{t['status']}] {t['brief_title']}\n    {t['url']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pssd-atlas", description=__doc__)
    ap.add_argument("--config", type=Path, default=None, help="alternative config.toml")
    ap.add_argument("--data", default="data", help="data directory (default: data)")
    ap.add_argument("--report", default="docs/index.html", help="report path (default: docs/index.html)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("update", help="fetch all sources, re-tag, rebuild the report")
    up.add_argument("--skip", nargs="*", choices=SOURCES, help="sources to leave untouched")
    up.add_argument("--cache", default=".cache", help="HTTP cache directory")
    up.add_argument("--cache-days", type=float, default=1.0, help="reuse cached responses younger than this")
    up.add_argument("--no-cache", action="store_true")
    up.set_defaults(fn=cmd_update)

    rp = sub.add_parser("report", help="rebuild the HTML report from existing data")
    rp.set_defaults(fn=cmd_report)

    nw = sub.add_parser("new", help="list records first seen since a date")
    nw.add_argument("--since", required=True, metavar="YYYY-MM-DD")
    nw.set_defaults(fn=cmd_new)

    args = ap.parse_args(argv)
    return args.fn(args)
