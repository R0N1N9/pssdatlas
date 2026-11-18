#!/usr/bin/env python3
"""Re-analysis of rat drug-treatment-and-withdrawal brain RNA-seq (Giatti et al.).

REQUIRES numpy, pandas, scipy and openpyxl (not stdlib; the rest of pssd_atlas
is stdlib-only, this script is a stand-alone analysis).  Run it with -I and
never from inside the download directory:

    python3 -I reanalysis.py --download DATA_DIR        # fetch supplements
    python3 -I reanalysis.py --data DATA_DIR --out results

Data (NOT in GEO; journal supplementary tables, treated here as untrusted
spreadsheets that are only parsed, never executed):

  paroxetine   Giatti et al., Mol Neurobiol 2025, PMID 39495228,
               doi:10.1007/s12035-024-04592-9.  Male rats, paroxetine daily
               for 2 weeks (T0) and 1 month after withdrawal (T1);
               hypothalamus and nucleus accumbens; 4 treated vs 4 controls in
               each tissue x timepoint (separate animals at each timepoint).
  finasteride  Giatti et al., J Endocrinol Invest 2024, PMID 38493246,
               doi:10.1007/s40618-024-02345-y.  Same design; hypothalamus and
               hippocampus.  Run as a secondary, clearly labelled analysis.

Each supplementary table holds, for one tissue x timepoint, the authors'
DESeq2 results plus DESeq2-size-factor-normalised counts for the 8 samples.
We do NOT have raw counts, so DESeq2 cannot be re-run; instead we:

  1. take log2(normalised count + 1), keep genes with mean normalised count
     >= 10 and a non-zero value in at least 4 of 8 samples;
  2. test treated vs control with (a) a limma-trend style moderated t-test
     (empirical-Bayes shrinkage of gene variances towards a mean-dependent
     prior; implemented below after Smyth 2004 / Law 2014) and (b) a plain
     Welch t-test as an assumption-light sensitivity check;
  3. Benjamini-Hochberg FDR within each contrast;
  4. carry the authors' own DESeq2 p / padj alongside for comparison;
  5. ask whether end-of-treatment changes persist, reverse or newly appear
     after withdrawal, including an exact label-permutation check of the
     T0-vs-T1 effect correlation (35 possible 4-vs-4 splits);
  6. extract a candidate gene panel.

Limits: n = 4 per group; separate control groups and sequencing runs per
timepoint (so only within-timepoint contrasts are valid); bulk tissue; one sex;
normalised rather than raw counts.
"""
from __future__ import annotations

import argparse
import itertools
import math
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import special, stats

USER_AGENT = "pssd-atlas/0.1 (research evidence mapper)"
SPRINGER = "https://static-content.springer.com/esm/art%3A{doi}/MediaObjects/{stem}_MOESM{i}_ESM.xlsx"

# file number -> (tissue, timepoint).  The paroxetine tables do not name the
# tissue; it was identified from marker genes (checked again at run time) and
# from the number of DEGs matching the abstract.  The finasteride tables are
# described in the open-access paper (Suppl. Tables 1-2 hypothalamus, 3-4
# hippocampus) and table 1 says "HYP" in its sheet name.
DATASETS = {
    "paroxetine": {
        "dir": "giatti2025_paroxetine_supp",
        "doi": "10.1007%2Fs12035-024-04592-9", "stem": "12035_2024_4592",
        "files": {1: ("hypothalamus", "T0"), 2: ("hypothalamus", "T1"),
                  3: ("nucleus_accumbens", "T0"), 5: ("nucleus_accumbens", "T1")},
        "treated_words": ("par",),
    },
    "finasteride": {
        "dir": "giatti2024_finasteride_supp",
        "doi": "10.1007%2Fs40618-024-02345-y", "stem": "40618_2024_2345",
        "files": {1: ("hypothalamus", "T0"), 2: ("hypothalamus", "T1"),
                  3: ("hippocampus", "T0"), 4: ("hippocampus", "T1")},
        "treated_words": ("fina",),
    },
}
MARKERS = {  # tissue -> (genes expected high, genes expected low)
    "hypothalamus": (["OXT", "PMCH", "AVP"], []),
    "nucleus_accumbens": (["DRD1", "PPP1R1B", "PENK"], ["OXT", "PMCH"]),
    "hippocampus": (["PROX1", "NEUROD6"], ["OXT", "PMCH"]),
}

# Candidate panel: human symbol -> regex over upper-cased rat symbols.
PANEL = [
    ("sodium/sensory channels", {
        "SCN9A": r"SCN9A", "SCN10A": r"SCN10A", "SCN11A": r"SCN11A", "TRPV1": r"TRPV1",
        "TRPM8": r"TRPM8", "TRPA1": r"TRPA1", "PIEZO2": r"PIEZO2", "ASIC3": r"ASIC3|ACCN3"}),
    ("serotonin", {
        "SLC6A4": r"SLC6A4", "HTR1A": r"HTR1A", "HTR1B": r"HTR1B", "HTR2A": r"HTR2A",
        "HTR2C": r"HTR2C", "HTR3A": r"HTR3A", "HTR7": r"HTR7", "TPH2": r"TPH2"}),
    ("dopamine", {
        "DRD1": r"DRD1A?", "DRD2": r"DRD2", "DRD3": r"DRD3", "TH": r"TH", "SLC6A3": r"SLC6A3"}),
    ("neurosteroid/steroid", {
        "SRD5A1": r"SRD5A1", "SRD5A2": r"SRD5A2",
        "AKR1C family (3alpha-HSD)": r"AKR1C\d+[A-Z]?\d*",
        "HSD3B family": r"HSD3B\d*", "TSPO": r"TSPO", "STAR": r"STAR", "CYP11A1": r"CYP11A1",
        "GABRD": r"GABRD", "GABRA4": r"GABRA4"}),
    ("hormonal", {
        "AR": r"AR", "ESR1": r"ESR1", "ESR2": r"ESR2", "PRL": r"PRL", "PRLR": r"PRLR"}),
    ("other", {
        "NOS1": r"NOS1", "PDE5A": r"PDE5A", "OXT": r"OXT", "OXTR": r"OXTR", "MC4R": r"MC4R",
        "SIGMAR1": r"SIGMAR1", "ADRA2A": r"ADRA2A", "HRH1": r"HRH1", "BDNF": r"BDNF"}),
]


# ---------------------------------------------------------------- statistics
def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    out = np.full(p.shape, np.nan)
    ok = np.isfinite(p)
    n = ok.sum()
    if n == 0:
        return out
    order = np.argsort(p[ok])
    ranked = p[ok][order] * n / np.arange(1, n + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(n)
    q[order] = np.minimum(ranked, 1.0)
    out[ok] = q
    return out


def trigamma_inverse(x: np.ndarray) -> np.ndarray:
    """Newton iteration from limma::trigammaInverse."""
    x = np.asarray(x, float)
    y = 0.5 + 1.0 / x
    for _ in range(50):
        tri = special.polygamma(1, y)
        dif = tri * (1 - tri / x) / special.polygamma(2, y)
        y = y + dif
        if np.max(-dif / y) < 1e-8:
            break
    return y


def moderated_t(x: np.ndarray, treated: np.ndarray):
    """limma-trend style two-group test on a genes x samples log-expression matrix.

    Returns log2FC, moderated t, p, plus the prior d.f. (shared by all genes).
    The prior variance is a smooth function of mean log-expression (cubic
    polynomial fitted to log residual variance); the prior d.f. comes from
    Smyth's moment estimator on the residuals around that trend.
    """
    a, b = x[:, treated], x[:, ~treated]
    n1, n0 = a.shape[1], b.shape[1]
    df = n1 + n0 - 2
    lfc = a.mean(1) - b.mean(1)
    s2 = (a.var(1, ddof=1) * (n1 - 1) + b.var(1, ddof=1) * (n0 - 1)) / df
    s2 = np.maximum(s2, 1e-8)
    amean = x.mean(1)
    z = np.log(s2)
    e = z - special.digamma(df / 2) + math.log(df / 2)  # unbiased for log prior var
    # centre/scale the covariate so the cubic fit is well conditioned
    u = (amean - amean.mean()) / amean.std()
    coef = np.polyfit(u, e, 3)
    trend = np.polyval(coef, u)
    resid_var = np.mean((e - trend) ** 2) * len(e) / (len(e) - 4)
    excess = resid_var - special.polygamma(1, df / 2)
    if excess > 0:
        d0 = float(2 * trigamma_inverse(np.array([excess]))[0])
        s02 = np.exp(trend + special.digamma(d0 / 2) - math.log(d0 / 2))
        s2_post = (d0 * s02 + df * s2) / (d0 + df)
        df_tot = d0 + df
    else:  # no extra-gene variability: prior d.f. infinite
        d0 = float("inf")
        s2_post = np.exp(trend)
        df_tot = float("inf")
    se = np.sqrt(s2_post * (1 / n1 + 1 / n0))
    t = lfc / se
    p = 2 * stats.t.sf(np.abs(t), df_tot) if np.isfinite(df_tot) else 2 * stats.norm.sf(np.abs(t))
    return lfc, t, p, d0, np.sqrt(s2), np.sqrt(s2_post)


def all_splits(n: int, k: int):
    """All distinct unordered k-vs-(n-k) splits for n == 2k (first sample fixed)."""
    for comb in itertools.combinations(range(1, n), k - 1):
        mask = np.zeros(n, bool)
        mask[[0, *comb]] = True
        yield mask


# ---------------------------------------------------------------- data loading
def load_table(path: Path, treated_words) -> tuple[pd.DataFrame, list[str], np.ndarray, str]:
    df = pd.read_excel(path, sheet_name=0)
    df = df.rename(columns={df.columns[0]: "gene"})
    df["gene"] = df["gene"].astype(str).str.strip().str.upper()
    stat_cols = ["baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj", "padj_NoNA"]
    missing = [c for c in stat_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"{path.name}: expected DESeq2 columns missing: {missing}")
    samples = [c for c in df.columns if c not in stat_cols and c != "gene"]
    if len(samples) != 8:
        raise SystemExit(f"{path.name}: expected 8 sample columns, found {len(samples)}")
    df = df.drop_duplicates("gene").reset_index(drop=True)
    low = [s.lower() for s in samples]
    is_ctrl = np.array([("ctrl" in s) or ("control" in s) for s in low])
    is_trt = np.array([any(w in s for w in treated_words) for s in low])
    if is_ctrl.sum() == 4 and is_trt.sum() == 4 and not (is_ctrl & is_trt).any():
        treated, how = is_trt, "sample labels"
    else:
        # Unlabelled plate-order names (A..H): the other tables from the same lab
        # put controls in A-D and treated in E-H.  Verified below against the sign
        # of the published log2FoldChange; abort if it does not hold.
        order = np.argsort(samples)
        treated = np.zeros(8, bool)
        treated[order[4:]] = True
        how = "INFERRED (plate order A-D control, E-H treated; checked against published log2FC)"
    x = np.log2(df[samples].to_numpy(float) + 1)
    # Check the assignment against the authors' own results: among genes they
    # report at p < 0.05 (baseMean > 50), our treated-minus-control difference
    # must have the same sign as their log2FoldChange.
    ok = (df["baseMean"].to_numpy() > 50) & (df["pvalue"].to_numpy() < 0.05)
    obs = x[ok][:, treated].mean(1) - x[ok][:, ~treated].mean(1)
    r = float((np.sign(obs) == np.sign(df.loc[ok, "log2FoldChange"])).mean())
    if not r > 0.95:
        raise SystemExit(f"{path.name}: group assignment does not reproduce the sign of the "
                         f"published log2FC (agreement {r:.2f}); refusing to guess")
    return df, samples, treated, f"{how}; sign agreement with published log2FC (their p<0.05 genes, n={int(ok.sum())}) = {r:.3f}"


def analyse_contrast(df, samples, treated):
    counts = df[samples].to_numpy(float)
    keep = (counts.mean(1) >= 10) & ((counts > 0).sum(1) >= 4)
    d = df.loc[keep].reset_index(drop=True)
    x = np.log2(d[samples].to_numpy(float) + 1)
    lfc, t, p, d0, sd, sd_post = moderated_t(x, treated)
    wt, wp = stats.ttest_ind(x[:, treated], x[:, ~treated], axis=1, equal_var=False)
    res = pd.DataFrame({
        "gene": d["gene"],
        "mean_norm_count": counts[keep].mean(1),
        "mean_log2_control": x[:, ~treated].mean(1),
        "mean_log2_treated": x[:, treated].mean(1),
        "log2FC": lfc,
        "pooled_sd_log2": sd,
        "hedges_g": lfc / sd * (1 - 3 / (4 * (len(samples) - 2) - 1)),
        "mod_t": t, "mod_p": p, "mod_fdr": bh(p),
        "welch_t": wt, "welch_p": wp, "welch_fdr": bh(wp),
        "deseq2_log2FC_published": d["log2FoldChange"],
        "deseq2_p_published": d["pvalue"],
        "deseq2_padj_published": d["padj"],
    })
    return res, x, d0, int(keep.sum()), len(df)


def min_detectable_lfc(sd: float, n: int, alpha: float, power: float = 0.8) -> float:
    """Smallest |log2FC| a two-sided two-sample t-test (n per group) detects."""
    df = 2 * n - 2
    crit = stats.t.isf(alpha / 2, df)
    lo, hi = 0.0, 50.0
    for _ in range(60):
        mid = (lo + hi) / 2
        pw = stats.nct.sf(crit, df, mid) + stats.nct.cdf(-crit, df, mid)
        lo, hi = (mid, hi) if pw < power else (lo, mid)
    return hi * sd * math.sqrt(2 / n)


# ---------------------------------------------------------------- persistence
def persistence(t0, t1, x1, treated1, genes1, label):
    m = t0.merge(t1, on="gene", suffixes=("_T0", "_T1"))
    rows, summary = [], {}

    def classify(sub, src):
        cats = []
        for _, r in sub.iterrows():
            same = np.sign(r.log2FC_T0) == np.sign(r.log2FC_T1)
            if r.mod_fdr_T1 < 0.10 and same:
                c = "persists (T1 FDR<0.10, same direction)"
            elif r.mod_p_T1 < 0.05 and same:
                c = "nominally persists (T1 raw p<0.05, same direction)"
            elif r.mod_p_T1 < 0.05 and not same:
                c = "reversed (T1 raw p<0.05, opposite direction)"
            else:
                c = "not detectable at T1 (raw p>=0.05)"
            cats.append(c)
            rows.append({"contrast_set": label, "selected_by": src, "gene": r.gene, "category": c,
                         "log2FC_T0": r.log2FC_T0, "mod_p_T0": r.mod_p_T0, "mod_fdr_T0": r.mod_fdr_T0,
                         "deseq2_padj_T0": r.deseq2_padj_published_T0,
                         "log2FC_T1": r.log2FC_T1, "mod_p_T1": r.mod_p_T1, "mod_fdr_T1": r.mod_fdr_T1,
                         "deseq2_padj_T1": r.deseq2_padj_published_T1})
        return pd.Series(cats, dtype=object).value_counts().to_dict()

    sets = {
        "T0 DEGs, moderated-t FDR<0.10": m[m.mod_fdr_T0 < 0.10],
        "T0 DEGs, published DESeq2 padj<0.10": m[m.deseq2_padj_published_T0 < 0.10],
    }
    for name, sub in sets.items():
        summary[name] = {"n_T0_DEGs_also_measured_at_T1": len(sub), **classify(sub, name)}
        if len(sub) >= 5:
            summary[name]["spearman_log2FC_T0_vs_T1"] = float(stats.spearmanr(sub.log2FC_T0, sub.log2FC_T1)[0])
            summary[name]["fraction_same_direction"] = float(
                (np.sign(sub.log2FC_T0) == np.sign(sub.log2FC_T1)).mean())

    new = m[((m.mod_fdr_T1 < 0.10) | (m.deseq2_padj_published_T1 < 0.10))]
    for _, r in new.iterrows():
        if r.mod_p_T0 >= 0.05:
            c = "new at T1 (T0 raw p>=0.05)"
        elif np.sign(r.log2FC_T0) == np.sign(r.log2FC_T1):
            c = "at T1 and nominally at T0, same direction"
        else:
            c = "at T1 and nominally at T0, opposite direction"
        rows.append({"contrast_set": label, "selected_by": "T1 DEGs (moderated-t FDR<0.10 or published padj<0.10)",
                     "gene": r.gene, "category": c,
                     "log2FC_T0": r.log2FC_T0, "mod_p_T0": r.mod_p_T0, "mod_fdr_T0": r.mod_fdr_T0,
                     "deseq2_padj_T0": r.deseq2_padj_published_T0,
                     "log2FC_T1": r.log2FC_T1, "mod_p_T1": r.mod_p_T1, "mod_fdr_T1": r.mod_fdr_T1,
                     "deseq2_padj_T1": r.deseq2_padj_published_T1})
    summary["n_T1_DEGs (moderated FDR<0.10 or published padj<0.10)"] = len(new)

    # Genome-wide: do the top T0 genes keep their direction at T1 more than chance?
    # Exact permutation over the 35 distinct 4-vs-4 relabellings of the T1 samples
    # (the T0 and T1 animals and controls are independent, so no shared-control artefact).
    perm = {}
    idx1 = {g: i for i, g in enumerate(genes1)}
    for top in (100, 500):
        sel = m.nsmallest(top, "mod_p_T0")
        rows_i = np.array([idx1[g] for g in sel.gene])
        xs = x1[rows_i]
        l0 = sel.log2FC_T0.to_numpy()
        vals, true_val = [], None
        for mask in all_splits(8, 4):
            lf = xs[:, mask].mean(1) - xs[:, ~mask].mean(1)
            r = stats.spearmanr(l0, lf)[0]
            is_true = np.array_equal(mask, treated1) or np.array_equal(~mask, treated1)
            if is_true:
                true_val = r if np.array_equal(mask, treated1) else -r
            vals.append(abs(r))
        vals = np.array(vals)
        perm[f"top{top}_T0_genes"] = {
            "spearman_T0_vs_T1_log2FC": float(true_val),
            "rank_of_|rho|_among_35_relabellings (1 = most extreme)": int((vals >= abs(true_val) - 1e-12).sum()),
            "permutation_p_two_sided": float((vals >= abs(true_val) - 1e-12).mean()),
            "median_|rho|_under_relabelling": float(np.median(vals)),
        }
    # Diagnostic: is the T0 drug signature aligned with the main axis of
    # animal-to-animal variation WITHIN groups at T1 (PC1 of group-centred data)?
    # If so, the "signature" lies along a direction in which samples differ anyway
    # (dissection / cell-type composition), which makes chance or confounded
    # concordance between timepoints easy to produce.
    xc = x1.copy()
    xc[:, treated1] -= xc[:, treated1].mean(1, keepdims=True)
    xc[:, ~treated1] -= xc[:, ~treated1].mean(1, keepdims=True)
    u, sv, _ = np.linalg.svd(xc, full_matrices=False)
    pc1 = pd.Series(u[:, 0], index=genes1)
    common = m.gene.to_numpy()
    summary["within_group_PC1_at_T1 | variance_fraction"] = float(sv[0] ** 2 / (sv ** 2).sum())
    summary["within_group_PC1_at_T1 | |spearman| with T0 log2FC (all genes)"] = float(
        abs(stats.spearmanr(pc1.loc[common].to_numpy(), m.log2FC_T0.to_numpy())[0]))
    summary["within_group_PC1_at_T1 | |spearman| with T1 log2FC (all genes)"] = float(
        abs(stats.spearmanr(pc1.loc[common].to_numpy(), m.log2FC_T1.to_numpy())[0]))
    summary["genome_wide_all_genes_spearman_T0_vs_T1"] = float(stats.spearmanr(m.log2FC_T0, m.log2FC_T1)[0])
    summary["permutation"] = perm
    return rows, summary


def panel_table(results: dict, drug: str) -> pd.DataFrame:
    out = []
    for (tissue, tp), res in results.items():
        genes = res["all_genes"]  # every gene in the supplementary table, pre-filter
        tested = res["table"].set_index("gene")
        for group, members in PANEL:
            for human, pattern in members.items():
                rx = re.compile(f"^(?:{pattern})$")
                hits = sorted(g for g in genes.index if rx.match(g))
                if not hits:
                    out.append({"drug": drug, "tissue": tissue, "timepoint": tp, "panel_group": group,
                                "human_symbol": human, "rat_symbol": "", "status": "absent from supplementary table"})
                    continue
                for g in hits:
                    row = {"drug": drug, "tissue": tissue, "timepoint": tp, "panel_group": group,
                           "human_symbol": human, "rat_symbol": g}
                    if g in tested.index:
                        r = tested.loc[g]
                        row.update(status="tested", mean_norm_count=r.mean_norm_count, log2FC=r.log2FC,
                                   hedges_g=r.hedges_g, mod_p=r.mod_p, mod_fdr=r.mod_fdr,
                                   welch_p=r.welch_p, welch_fdr=r.welch_fdr,
                                   deseq2_log2FC_published=r.deseq2_log2FC_published,
                                   deseq2_p_published=r.deseq2_p_published,
                                   deseq2_padj_published=r.deseq2_padj_published)
                    else:
                        row.update(status="below expression filter (mean normalised count < 10)",
                                   mean_norm_count=float(genes.loc[g, "baseMean"]),
                                   deseq2_log2FC_published=genes.loc[g, "log2FoldChange"],
                                   deseq2_p_published=genes.loc[g, "pvalue"],
                                   deseq2_padj_published=genes.loc[g, "padj"])
                    out.append(row)
    df = pd.DataFrame(out)
    # BH across the tested panel genes only, within each tissue x timepoint
    df["panel_only_fdr"] = np.nan
    for _, idx in df[df.status == "tested"].groupby(["tissue", "timepoint"]).groups.items():
        df.loc[idx, "panel_only_fdr"] = bh(df.loc[idx, "mod_p"].to_numpy())
    return df


# ---------------------------------------------------------------- driver
def download(dest: Path):
    for name, cfg in DATASETS.items():
        d = dest / cfg["dir"]
        d.mkdir(parents=True, exist_ok=True)
        for i in cfg["files"]:
            url = SPRINGER.format(doi=cfg["doi"], stem=cfg["stem"], i=i)
            target = d / f"MOESM{i}.xlsx"
            if target.exists():
                continue
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                target.write_bytes(resp.read())
            print(f"downloaded {target}", file=sys.stderr)


def sig(x):
    return float(f"{x:.4g}") if isinstance(x, (float, np.floating)) and np.isfinite(x) else x


def run(name: str, data: Path, out: Path, lines: list[str]):
    cfg = DATASETS[name]
    results, summary_rows, persist_rows = {}, [], []
    for i, (tissue, tp) in cfg["files"].items():
        path = data / cfg["dir"] / f"MOESM{i}.xlsx"
        df, samples, treated, how = load_table(path, cfg["treated_words"])
        bm = df.set_index("gene")["baseMean"]
        high, low = MARKERS[tissue]
        marker_ok = all(bm.get(g, 0) > 200 for g in high) and all(bm.get(g, 0) < 200 for g in low)
        res, x, d0, n_tested, n_all = analyse_contrast(df, samples, treated)
        results[(tissue, tp)] = {"table": res, "x": x, "treated": treated,
                                 "all_genes": df.set_index("gene")}
        med_sd = float(np.median(res.pooled_sd_log2))
        row = {
            "drug": name, "tissue": tissue, "timepoint": tp,
            "contrast": f"{name} vs control at {'end of treatment' if tp == 'T0' else '1 month after withdrawal'}",
            "n_control": int((~treated).sum()), "n_treated": int(treated.sum()),
            "group_assignment": how,
            "tissue_marker_check": "pass" if marker_ok else "FAIL",
            "genes_in_supplement": n_all, "genes_tested": n_tested,
            "mod_fdr<0.05": int((res.mod_fdr < 0.05).sum()), "mod_fdr<0.10": int((res.mod_fdr < 0.10).sum()),
            "welch_fdr<0.05": int((res.welch_fdr < 0.05).sum()), "welch_fdr<0.10": int((res.welch_fdr < 0.10).sum()),
            "published_deseq2_padj<0.05": int((df.padj < 0.05).sum()),
            "published_deseq2_padj<0.10": int((df.padj < 0.10).sum()),
            "mod_raw_p<0.001": int((res.mod_p < 0.001).sum()),
            "expected_raw_p<0.001_under_null": round(n_tested * 0.001, 1),
            "min_mod_fdr": float(res.mod_fdr.min()), "min_welch_fdr": float(res.welch_fdr.min()),
            "prior_df_moderation": round(d0, 2),
            "median_gene_sd_log2": round(med_sd, 3),
            "min_log2FC_80pct_power_alpha0.05": round(min_detectable_lfc(med_sd, 4, 0.05), 2),
            "min_log2FC_80pct_power_alpha1e-5": round(min_detectable_lfc(med_sd, 4, 1e-5), 2),
        }
        summary_rows.append(row)
        top = res[(res.mod_p < 0.01) | (res.welch_p < 0.01) | (res.deseq2_padj_published < 0.10)]
        top = top.sort_values("mod_p").map(sig)
        top.to_csv(out / f"{name}_{tissue}_{tp}_top_genes.csv", index=False)
        lines.append(f"[{name}] {tissue} {tp}: n={row['n_control']}+{row['n_treated']}, tested {n_tested}, "
                     f"moderated FDR<0.05: {row['mod_fdr<0.05']}, <0.10: {row['mod_fdr<0.10']}; "
                     f"Welch FDR<0.10: {row['welch_fdr<0.10']}; published padj<0.10: {row['published_deseq2_padj<0.10']}; "
                     f"markers {row['tissue_marker_check']}; groups: {how}")

    psum = []
    for tissue in dict.fromkeys(t for t, _ in cfg["files"].values()):
        r0, r1 = results[(tissue, "T0")], results[(tissue, "T1")]
        rows, summ = persistence(r0["table"], r1["table"], r1["x"], r1["treated"],
                                 list(r1["table"].gene), f"{name}:{tissue}")
        persist_rows.extend(rows)
        flat = {"drug": name, "tissue": tissue}
        for k, v in summ.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    if isinstance(v2, dict):
                        for k3, v3 in v2.items():
                            flat[f"{k} | {k2} | {k3}"] = v3
                    else:
                        flat[f"{k} | {k2}"] = v2
            else:
                flat[k] = v
        psum.append(flat)
        lines.append(f"[{name}] {tissue} persistence: " + "; ".join(f"{k}={sig(v)}" for k, v in flat.items()
                                                                     if k not in ("drug", "tissue")))
    panel = panel_table(results, name)
    return (pd.DataFrame(summary_rows), pd.DataFrame(persist_rows), pd.DataFrame(psum), panel)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--download", type=Path, help="fetch the supplementary tables into this directory and exit")
    ap.add_argument("--data", type=Path, help="directory holding the downloaded dataset sub-directories")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results")
    ap.add_argument("--only", choices=list(DATASETS), help="analyse one dataset only")
    args = ap.parse_args()
    if args.download:
        download(args.download)
        return 0
    if not args.data:
        ap.error("--data is required (or use --download)")
    args.out.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    parts = [run(n, args.data, args.out, lines) for n in DATASETS if args.only in (None, n)]
    pd.concat([p[0] for p in parts]).to_csv(args.out / "contrast_summary.csv", index=False)
    pd.concat([p[1] for p in parts]).map(sig).to_csv(args.out / "persistence_genes.csv", index=False)
    pd.concat([p[2] for p in parts]).map(sig).to_csv(args.out / "persistence_summary.csv", index=False)
    pd.concat([p[3] for p in parts]).map(sig).to_csv(args.out / "candidate_panel.csv", index=False)
    (args.out / "run_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
