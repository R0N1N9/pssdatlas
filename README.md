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
| Reddit, blogs, advocacy sites | Patient posts and articles, reduced to tags and links |

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

### Live updating from the report

```bash
python -m pssd_atlas serve
```

Then open http://127.0.0.1:8765. The **Update data** button in the report
re-fetches papers, preprints and trials (under a minute, with an option to
refresh the FDA data too) and reloads the page. Opened as a plain file, the
report is a snapshot and the button explains how to start the server.

### Three views

A selector at the top of the report switches every section between **all
psychiatric medication**, **SSRIs and SNRIs**, and **antipsychotics and
mirtazapine**. A record belongs to a view when it names one of that group's
drugs (generic or brand name). The groups are defined under `[[partition]]`
in the config.

### Patient reports and community sources

| Source | How | Status |
|---|---|---|
| Reddit | Official API | Needs your own free API app, and a home connection: Reddit refuses many cloud and VPN addresses |
| RxISK, David Healy, Mad in America | Each site's WordPress search API | Works out of the box |
| PSSD Network, PSSD Canada | RSS feeds (most recent items only) | Works out of the box |
| pssdforum.org, survivingantidepressants.org | Not crawled: both block automated access | Use `import` for pages you saved yourself |

For Reddit, create a "script" app at https://www.reddit.com/prefs/apps and set:

```bash
export REDDIT_CLIENT_ID=your-client-id
```

```bash
export REDDIT_CLIENT_SECRET=your-client-secret
```

To add a forum thread you saved from your own browser:

```bash
python -m pssd_atlas import thread.html --source "PSSD Forum" --url https://example.org/thread --date 2025-03-01
```

Each patient post is reduced to tags (drugs, symptoms, treatments and a rough
reading of how each went) plus a link. Usernames are never collected. Post text
is kept only in `data_raw/`, which is git-ignored, so that tags can be
re-derived when the config changes. Blog articles keep their titles.

Outcome tags come from nearby words ("didn't help", "made it worse"), not from
understanding the post, and are frequently wrong. Posts are self-selected.
Treat this section as a source of leads, not evidence.

The report also has a light/dark toggle, and the paper explorer sorts by
publication date (newest or oldest first).

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
