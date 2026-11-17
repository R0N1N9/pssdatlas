# PSSD Atlas

A living evidence map for post-SSRI sexual dysfunction (PSSD) and related
persistent post-drug syndromes.

Research on PSSD is small, scattered across psychiatry, urology, endocrinology
and pharmacology journals, and dominated by reviews that repeat the same
hypotheses. This tool pulls the whole field into one place, tags it, and shows
where the evidence is and where it is missing, so that researchers and patients
can see what has actually been tested.

It also covers enduring sexual dysfunction after non-SSRI drugs
(antipsychotics, mirtazapine, finasteride, isotretinoin), since these may share
mechanisms and are routinely left out of SSRI-only searches.

## What it does

`pssd-atlas update` fetches four public sources and builds a single
self-contained report at `docs/index.html`:

| Source | What is collected |
|---|---|
| PubMed | Every paper matching the searches in `config.toml` |
| Europe PMC | Preprints not yet indexed in PubMed |
| ClinicalTrials.gov | Registered studies, filtered for relevance |
| openFDA (FAERS) | Adverse-event report counts for a drug × reaction grid |

Each paper is tagged with:

- **scope**: `core` (persistent dysfunction after psychotropics), `related`
  (post-finasteride / post-retinoid), or `adjacent` (on-treatment dysfunction,
  where most treatment trials are)
- **study design**: randomised trial, observational, case report, animal, review, …
- **hypotheses** it discusses (neurosteroids, serotonin receptors, neuropathy,
  epigenetics, microbiome, …)
- **candidate treatments** and **drugs** it mentions

The report then shows:

- **Evidence matrix**: hypothesis × study design, click any cell to read those papers
- **Where the evidence is thin**: per hypothesis, original human data versus
  animal work versus reviews
- **Candidate treatments**: literature and trial-registry counts for each
- **Registered trials**
- **Drug-safety signals**: reporting odds ratios with 95% CIs for sexual
  adverse events, per drug, with comparator drugs
- **Paper explorer**: full-text search and filters over every record, with CSV export

The same data is written to `data/` as JSON and CSV for your own analysis.

## Usage

Python 3.11+, no dependencies.

```bash
python -m pssd_atlas update
```

Then open `docs/index.html` in a browser. The first run takes about five
minutes (the openFDA grid is ~500 rate-limited queries); responses are cached
in `.cache/` for a day.

```bash
python -m pssd_atlas update --skip faers      # literature and trials only
python -m pssd_atlas report                   # rebuild the report after editing config
python -m pssd_atlas new --since 2026-11-01   # what has appeared since a date
python -m unittest                            # tests
```

Each update prints the papers and trials that are new since the previous
snapshot, so running it weekly works as an alerting service.

## Adapting it

Everything domain-specific lives in [`pssd_atlas/config.toml`](pssd_atlas/config.toml):
search strings, the hypothesis taxonomy, the treatment list and the
pharmacovigilance grid. Adding a hypothesis is a five-line edit:

```toml
[[hypothesis]]
id = "my_idea"
kind = "mechanism"
label = "My idea"
description = "One sentence."
patterns = ['regex one', 'regex two']
```

## Limitations

- **Tagging is keyword-based.** A hypothesis tag means the title or abstract
  mentions the topic, not that the paper supports it. Study design comes from
  PubMed publication types with text fallbacks; roughly 9% of records are left
  unclassified. Treat counts as a map of where to read, not as a meta-analysis.
- **Abstracts only.** Full texts are not analysed.
- **FAERS cannot measure PSSD.** Spontaneous reports do not record whether a
  symptom persisted after stopping the drug, cannot give incidence, and are
  distorted by publicity, by the underlying illness and by under-reporting.
  Reports list every drug the patient was taking, so a co-prescribed drug
  inherits its partner's signal. Comparator drugs are imperfect (statins, for
  instance, are taken by an older, more male population).
- **ClinicalTrials.gov only.** EU CTIS, ISRCTN and other registries are not searched.

This is a research-navigation aid, not medical advice.
