# Re-analysis: do brain transcriptome changes outlast paroxetine (and finasteride) in rats?

Script: `analysis/reanalysis.py` (needs numpy, pandas, scipy, openpyxl). Tables: `analysis/results/`.
Run date 2026-11-18.

## Bottom line

- **No public GEO dataset** has an adult washout arm with usable replication for any drug of interest
  (see `GEO_CATALOGUE.md`). The best available data are **not in GEO**: per-sample normalised counts in
  the supplementary tables of two papers from the Melcangi/Giatti group.
- Primary dataset: **paroxetine, male rat hypothalamus and nucleus accumbens (NAc), end of 2 weeks'
  treatment (T0) and 1 month after withdrawal (T1), 4 treated vs 4 controls per tissue and timepoint.**
- With tests that respect the sample size (moderated t and Welch t, Benjamini-Hochberg),
  **no gene passes FDR < 0.10 in any contrast**, at T0 or T1, in either tissue. The authors' DESeq2
  analysis reports 8 / 1 (hypothalamus T0 / T1) and 255 / 7 (NAc T0 / T1) genes at padj < 0.10.
  The two analyses agree on direction and ranking; they differ in how much confidence 4 animals per group
  can buy.
- **Persistence:** in the NAc there is a weak, suggestive carry-over. The 255 genes the authors report at
  T0 keep their direction at T1 in 81% of cases (Spearman 0.54 between T0 and T1 effects; 54 are nominally
  significant in the same direction at T1 against about 6 expected by chance; 2 reverse). In an exact
  relabelling test the concordance for the top 500 T0 genes is the most extreme of the 35 possible
  splits (p = 0.029, the smallest value this design can produce); for the top 100 it is not (p = 0.20).
  Effects at T1 are roughly half the size of those at T0. **In the hypothalamus there is no carry-over
  at all.** Nothing here is strong enough to call a persistent change established.
- **Candidate panel:** no panel gene passes genome-wide FDR in any contrast. The only panel gene nominally
  changed in the same direction at both timepoints is **Gabra4 in the NAc** (log2FC -0.62, p = 0.009 at T0;
  -0.35, p = 0.023 at T1; FDR 0.41 and 0.66). Sensory-neuron channel genes are barely expressed in these
  brain regions, so this dataset cannot address genital numbness.
- **The analysis is underpowered (n = 4 per group).** A typical gene needs roughly a 1.3- to 1.6-fold change
  to be detected at an uncorrected p < 0.05 with 80% power, and roughly a 2- to 3-fold change to survive
  genome-wide correction. Absence of FDR-significant genes is therefore not evidence of absence.

## Data

| | Primary | Secondary (sister syndrome) |
|---|---|---|
| Paper | Giatti et al., *Mol Neurobiol* 2025, PMID 39495228, doi:10.1007/s12035-024-04592-9 | Giatti et al., *J Endocrinol Invest* 2024, PMID 38493246, doi:10.1007/s40618-024-02345-y |
| Drug | Paroxetine, daily for 2 weeks (dose not checked: paper is paywalled, only the abstract and supplement were read) | Finasteride 1 mg/rat/day s.c. for 20 days (read from open-access text) |
| Animals | Adult male rats | Adult male Sprague-Dawley rats |
| Tissues | Hypothalamus, nucleus accumbens | Hypothalamus, hippocampus |
| Timepoints | T0 = end of treatment; T1 = 1 month after withdrawal | T0 = 24 h after last dose; T1 = 1 month after suspension |
| Groups | 4 drug + 4 vehicle per tissue per timepoint, different animals at T0 and T1 | same |
| What is public | Supplementary Tables 1, 2, 3, 5 (xlsx): DESeq2 results plus DESeq2-normalised counts for the 8 samples of each contrast | Supplementary Tables 1-4, same layout |
| Repository deposit | None found in GEO, BioProject or SRA (searched this session). Data statement: "available within the paper and its Supplementary Information" | None found. Data statement: "available from the corresponding author on reasonable request" |

Both PMIDs were returned by PubMed in this session. The files were downloaded from the publisher's
supplementary-material links; they are not redistributed here (`reanalysis.py --download DIR` fetches them).

Two things about the paroxetine tables had to be **inferred**, and the script re-checks both at run time:

1. *Which tissue each table is.* The tables are not labelled by tissue. Tables 1-2 have very high Oxt, Pmch
   and Avp (hypothalamus); tables 3 and 5 have high Drd1, Ppp1r1b, Penk and negligible Oxt (striatum/NAc).
   The numbers of padj < 0.10 genes (8, 1, 255, 7) also match the abstract's 7, 1, 245, 6 closely but not
   exactly; the small differences are unexplained (possibly unannotated genes dropped by the authors).
2. *Which hypothalamus samples are treated.* Tables 1-2 name samples only A..H. Every labelled table from
   this group puts controls first, so A-D were taken as control and E-H as paroxetine. With that
   assignment our treated-minus-control difference has the same sign as the authors' log2FoldChange for
   100% of their p < 0.05 genes (1,034 genes at T0, 130 at T1), so the assignment is very unlikely to be wrong.

## Methods

- Input: DESeq2 size-factor-normalised counts as supplied. Raw counts are not available, so DESeq2/edgeR
  could not be re-run.
- Transform: log2(normalised count + 1). Filter: mean normalised count >= 10 and non-zero in >= 4 of 8 samples
  (13,592-15,583 genes per contrast).
- Tests, treated vs control within each tissue x timepoint:
  - **Moderated t-test, limma-trend style** (primary). Gene variances are shrunk towards a prior that
    depends on mean expression (cubic trend on log variance; prior degrees of freedom by Smyth's moment
    estimator). Written from scratch in numpy/scipy; on simulated data with known truth it recovered the
    prior d.f. (4.03 vs 4), gave 4.98% of null genes at p < 0.05, and an achieved FDR of about 12% at a
    nominal 10%.
  - **Welch t-test** as an assumption-light sensitivity check.
  - The authors' DESeq2 p and padj are carried alongside every gene for comparison.
- Multiple testing: Benjamini-Hochberg within each contrast. For the candidate panel a second, more lenient
  BH over the panel genes only is also given (`panel_only_fdr`).
- Persistence: T0 and T1 are separate contrasts with separate animals and separate control groups, so
  they can be compared without a shared-control artefact. Genes selected at T0 are classified at T1 as
  *persists* (same direction, T1 FDR < 0.10), *nominally persists* (same direction, raw p < 0.05),
  *reversed* (opposite direction, raw p < 0.05) or *not detectable*. Because no gene met our own FDR at T0,
  the gene set used is the authors' DESeq2 padj < 0.10 list. Genome-wide concordance is tested by an exact
  relabelling test: for the top 100 or 500 T0 genes, the Spearman correlation between T0 and T1 effects is
  compared with the same statistic under all 35 distinct 4-vs-4 relabellings of the T1 samples.
- T0 and T1 samples were never compared directly: they were sequenced to different depths (hypothalamus
  about 19 M vs 13 M normalised counts per sample) and are confounded with run and age.

## Results

### Samples and FDR-significant genes

<!-- summary:start -->
| Drug | Tissue | Contrast | n ctrl / treated | Genes tested | Moderated-t FDR<0.05 / <0.10 | Welch FDR<0.10 | Smallest moderated FDR | Raw p<0.001 (observed / expected by chance) | Authors' DESeq2 padj<0.05 / <0.10 | log2FC needed for 80% power at raw p<0.05 / p<1e-5 |
|---|---|---|---|---:|---|---:|---:|---|---|---|
| paroxetine | hypothalamus | end of treatment (T0) | 4 / 4 | 14456 | 0 / 0 | 0 | 0.69 | 8 / 14.5 | 6 / 8 | 0.41 / 0.96 |
| paroxetine | hypothalamus | after 1 month withdrawal (T1) | 4 / 4 | 13951 | 0 / 0 | 0 | 1.00 | 2 / 14.0 | 1 / 1 | 0.64 / 1.49 |
| paroxetine | nucleus accumbens | end of treatment (T0) | 4 / 4 | 13592 | 0 / 0 | 0 | 0.34 | 31 / 13.6 | 102 / 255 | 0.56 / 1.3 |
| paroxetine | nucleus accumbens | after 1 month withdrawal (T1) | 4 / 4 | 13645 | 0 / 0 | 0 | 0.22 | 8 / 13.6 | 5 / 7 | 0.48 / 1.12 |
| finasteride | hypothalamus | end of treatment (T0) | 4 / 4 | 14958 | 0 / 0 | 0 | 0.25 | 49 / 15.0 | 98 / 186 | 0.36 / 0.84 |
| finasteride | hypothalamus | after 1 month withdrawal (T1) | 4 / 4 | 15583 | 0 / 0 | 0 | 0.96 | 1 / 15.6 | 0 / 0 | 0.37 / 0.87 |
| finasteride | hippocampus | end of treatment (T0) | 4 / 4 | 14615 | 0 / 0 | 0 | 0.77 | 7 / 14.6 | 7 / 19 | 0.39 / 0.9 |
| finasteride | hippocampus | after 1 month withdrawal (T1) | 4 / 4 | 14721 | 0 / 0 | 0 | 0.97 | 3 / 14.7 | 0 / 0 | 0.43 / 1.01 |
<!-- summary:end -->

Reading the table: nothing passes FDR under either t-test. The NAc at T0 (31 genes at raw p < 0.001 where
about 14 are expected by chance) and the finasteride hypothalamus at T0 (49 vs 15) show an excess of small
p-values, i.e. there is real signal at end of treatment that 4 vs 4 animals cannot resolve gene by gene. At
T1 no contrast shows any excess (2-8 observed vs 14-16 expected).

Why the authors find more: DESeq2 tests each gene against a normal distribution, with dispersion shared
across genes; a t-test with these sample sizes has about 10 effective degrees of freedom and much heavier
tails. For the top NAc T0 gene (Fcer1g, log2FC +0.97) DESeq2 gives p = 1e-10, the moderated t gives
p = 4e-5 and Welch p = 8e-4. DESeq2 at n = 4 is standard practice and is not "wrong", but its calls rest
more on the model than on the eight data points, and it is known to be less robust at this sample size.
The honest summary is that the T0 NAc gene list is plausible but individually unconfirmed, and the T1 lists
(1 and 7 genes) are within what noise could produce.

### Do end-of-treatment changes persist, reverse or newly appear?

| Drug / tissue | Authors' T0 genes (padj < 0.10) measured at T1 | Same direction at T1 | Nominally persist (same direction, raw p < 0.05) | Reversed (raw p < 0.05) | Not detectable | Pass FDR at T1 | Spearman T0 vs T1 effect (these genes) | Relabelling test, top 500 T0 genes: rho, rank of 35, p | Top 100: rho, rank, p |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Paroxetine, hypothalamus | 8 | 3 (38%) | 0 | 1 | 7 | 0 | -0.02 | -0.01, 33rd, 0.94 | -0.01, 34th, 0.97 |
| Paroxetine, nucleus accumbens | 255 | 207 (81%) | 54 | 2 | 199 | 0 | 0.54 | 0.59, 1st, 0.029 | 0.46, 7th, 0.20 |
| Finasteride, hypothalamus | 183 | 166 (91%) | 26 | 0 | 157 | 0 | 0.46 | 0.55, 8th, 0.23 | 0.50, 13th, 0.37 |
| Finasteride, hippocampus | 19 | 13 (68%) | 2 | 0 | 17 | 0 | 0.41 | 0.27, 17th, 0.49 | 0.10, 28th, 0.80 |

- **Paroxetine, NAc.** The direction of the T0 signature is partly retained a month after withdrawal, with
  smaller effects. Genes that are nominally down at both timepoints include Pde10a, Grm5, Gabra4, Syt6,
  Tenm4, Foxo3, Slc24a4; nominally up at both include immune/microglia-associated genes (Ctss, Cd53, Ly86,
  Lsp1, Psme2). Two genes reverse (Zbtb20, Chi3l1). This is the only place in either dataset where the
  relabelling test reaches its floor (p = 0.029), and it does so for the top 500 genes but not the top 100,
  so it should be read as suggestive, not as a demonstrated persistent signature.
- **New at T1?** Of the authors' 7 NAc T1 genes, 6 were also measured at T0. Five of them (Lancl1, Slc24a4,
  Unc79, Zswim6, Pde10a) were already nominally changed in the same direction at T0, and the sixth
  (Slc2a10) trended the same way (T0 p = 0.10). So the T1 NAc hits look like residual T0 effects rather than
  late-emerging ones. The seventh (Lypd8, log2FC +5.6) is essentially absent in controls and low in treated
  animals; an on/off call on about 40 counts deserves no weight without replication.
- **Paroxetine, hypothalamus.** No carry-over. The one T1 gene, Chi3l1 (log2FC -0.53; moderated p = 0.0004,
  FDR 1.0; authors' padj 0.018), was unchanged at T0 (+0.05), so it would count as "newly appearing" - but
  one gene among 14,000 at this level is expected by chance. (Chi3l1 is also nominally lower in the NAc at T1,
  -0.32, p = 0.036; worth a look in any replication, nothing more.)
- **Finasteride (secondary).** Hypothalamic T0 genes mostly keep their sign at T1 (91%), but the relabelling
  test shows this degree of concordance arises in about one split in four, so it is not distinguishable from
  structured noise. No gene is called at T1 by any method, matching the authors.
- **Caveat on concordance statistics.** Within-group animal-to-animal variation in these tissues is highly
  structured: the first principal component of group-centred data carries 33-50% of the variance, and
  random relabellings of T1 typically give |rho| of 0.2-0.4 with the T0 signature. Bulk dissection of small
  nuclei is the likely cause (in the NAc tables Oxt, a hypothalamic transcript, varies by several fold
  between animals). A treated-vs-control difference in tissue composition, repeated at both timepoints,
  would look exactly like a persistent drug effect. The NAc pattern (striatal neuron genes Pde10a, Drd1,
  Drd2, Drd3 down; glial/immune genes up) is compatible with a real drug effect and with slightly different
  dissections. In favour of a real effect: the T0 signature is not aligned with the main within-group axis at
  T1 (|rho| = 0.04). It cannot be settled from these data.

### Candidate gene panel

Cells are **log2 fold change / raw p (moderated t) / genome-wide BH FDR**. "low (x)" = mean normalised count
x < 10, not tested. Full table with Hedges g, Welch p, panel-only FDR and the authors' DESeq2 values:
`results/candidate_panel.csv`. Symbols are rat symbols upper-cased as in the source tables. Slc6a4, Scn10a,
Srd5a2 and Prl are effectively not expressed in these regions; Hsd3b1/3b3 and several Akr1c members are near
zero. (Rat 3-alpha-HSD, called AKR1C9 in older papers, is to my knowledge the gene now annotated Akr1c14;
that mapping was not verified against a database in this session.)

**Paroxetine**

<!-- panel_par:start -->
| Group | Human gene | Rat symbol | hypothalamus T0 | hypothalamus T1 | nucleus_accumbens T0 | nucleus_accumbens T1 |
|---|---|---|---|---|---|---|
| sodium/sensory channels | SCN9A | SCN9A | +0.37 / 0.101 / 0.71 | +0.03 / 0.895 / 1.00 | -0.02 / 0.944 / 0.98 | +0.18 / 0.422 / 0.80 |
| sodium/sensory channels | SCN10A | SCN10A | low (9.9) | low (5.6) | low (4.2) | low (4.2) |
| sodium/sensory channels | SCN11A | SCN11A | -0.07 / 0.695 / 0.93 | +0.30 / 0.371 / 1.00 | -0.58 / 0.366 / 0.72 | +0.69 / 0.118 / 0.66 |
| sodium/sensory channels | TRPV1 | TRPV1 | -0.44 / 0.0621 / 0.69 | -0.06 / 0.817 / 1.00 | -0.20 / 0.469 / 0.78 | -0.12 / 0.654 / 0.89 |
| sodium/sensory channels | TRPM8 | TRPM8 | -0.65 / 0.0688 / 0.70 | -0.09 / 0.821 / 1.00 | low (4.2) | low (4.0) |
| sodium/sensory channels | TRPA1 | TRPA1 | -0.16 / 0.559 / 0.90 | -0.53 / 0.314 / 1.00 | low (4.4) | low (7.9) |
| sodium/sensory channels | PIEZO2 | PIEZO2 | +0.10 / 0.753 / 0.95 | -0.36 / 0.411 / 1.00 | low (8.5) | low (9.0) |
| sodium/sensory channels | ASIC3 | ASIC3 | +0.13 / 0.618 / 0.91 | -0.03 / 0.932 / 1.00 | -0.57 / 0.102 / 0.52 | -0.18 / 0.649 / 0.89 |
| serotonin | SLC6A4 | SLC6A4 | low (3.3) | low (2.0) | low (0.7) | low (0.5) |
| serotonin | HTR1A | HTR1A | -0.11 / 0.465 / 0.86 | +0.31 / 0.248 / 1.00 | -0.15 / 0.803 / 0.94 | +0.10 / 0.809 / 0.94 |
| serotonin | HTR1B | HTR1B | +0.21 / 0.192 / 0.75 | +0.33 / 0.219 / 1.00 | -0.81 / 0.0291 / 0.45 | -0.22 / 0.181 / 0.68 |
| serotonin | HTR2A | HTR2A | +0.40 / 0.00873 / 0.69 | -0.00 / 0.997 / 1.00 | -0.11 / 0.764 / 0.92 | -0.34 / 0.308 / 0.75 |
| serotonin | HTR2C | HTR2C | +0.15 / 0.248 / 0.77 | +0.03 / 0.864 / 1.00 | -0.23 / 0.364 / 0.72 | -0.24 / 0.463 / 0.82 |
| serotonin | HTR3A | HTR3A | +0.10 / 0.529 / 0.89 | -0.12 / 0.439 / 1.00 | -0.30 / 0.298 / 0.68 | +0.36 / 0.0834 / 0.66 |
| serotonin | HTR7 | HTR7 | -0.16 / 0.214 / 0.76 | -0.03 / 0.864 / 1.00 | -0.04 / 0.916 / 0.98 | +0.53 / 0.097 / 0.66 |
| serotonin | TPH2 | TPH2 | -0.00 / 0.995 / 1.00 | +0.33 / 0.366 / 1.00 | +0.04 / 0.928 / 0.98 | -0.35 / 0.263 / 0.72 |
| dopamine | DRD1 | DRD1 | -0.30 / 0.192 / 0.75 | +0.09 / 0.631 / 1.00 | -0.81 / 0.0802 / 0.50 | -0.29 / 0.0967 / 0.66 |
| dopamine | DRD2 | DRD2 | -0.05 / 0.778 / 0.95 | +0.00 / 0.993 / 1.00 | -0.88 / 0.0838 / 0.50 | -0.33 / 0.0618 / 0.66 |
| dopamine | DRD3 | DRD3 | -0.33 / 0.517 / 0.88 | low (5.4) | -1.11 / 0.0163 / 0.43 | -0.55 / 0.0681 / 0.66 |
| dopamine | TH | TH | +0.21 / 0.551 / 0.89 | -0.08 / 0.81 / 1.00 | +0.43 / 0.269 / 0.66 | -0.16 / 0.691 / 0.91 |
| dopamine | SLC6A3 | SLC6A3 | +0.79 / 0.474 / 0.87 | +0.76 / 0.471 / 1.00 | low (0.7) | low (2.3) |
| neurosteroid/steroid | SRD5A1 | SRD5A1 | +0.07 / 0.536 / 0.89 | +0.06 / 0.746 / 1.00 | -0.10 / 0.576 / 0.84 | +0.08 / 0.509 / 0.84 |
| neurosteroid/steroid | SRD5A2 | SRD5A2 | low (1.8) | low (0.8) | low (1.7) | low (1.6) |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C12 | low (2.5) | low (2.8) | low (1.2) | low (1.2) |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C13 | low (7.2) | low (5.7) | low (6.6) | low (6.3) |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C14 | +0.25 / 0.484 / 0.87 | +0.15 / 0.703 / 1.00 | +1.56 / 0.0851 / 0.50 | +0.58 / 0.119 / 0.66 |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C19 | +0.73 / 0.0186 / 0.69 | -0.82 / 0.00991 / 1.00 | +0.72 / 0.159 / 0.57 | -0.41 / 0.314 / 0.75 |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C2 | low (0.2) | not in table | low (3.9) | low (3.5) |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C3 | low (0.2) | not in table | low (0.2) | not in table |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C8 | +0.02 / 0.954 / 0.99 | -0.56 / 0.0257 / 1.00 | +0.92 / 0.0073 / 0.39 | +0.09 / 0.691 / 0.91 |
| neurosteroid/steroid | HSD3B family | HSD3B7 | -0.03 / 0.817 / 0.96 | +0.05 / 0.754 / 1.00 | -0.22 / 0.125 / 0.53 | -0.16 / 0.303 / 0.74 |
| neurosteroid/steroid | TSPO | TSPO | +0.31 / 0.101 / 0.71 | +0.11 / 0.648 / 1.00 | +0.26 / 0.588 / 0.84 | +0.48 / 0.235 / 0.71 |
| neurosteroid/steroid | STAR | STAR | -0.06 / 0.815 / 0.96 | -0.17 / 0.577 / 1.00 | -0.00 / 0.99 / 1.00 | -0.42 / 0.188 / 0.69 |
| neurosteroid/steroid | CYP11A1 | CYP11A1 | +0.58 / 0.138 / 0.73 | +0.46 / 0.421 / 1.00 | -0.37 / 0.37 / 0.73 | +0.00 / 0.997 / 1.00 |
| neurosteroid/steroid | GABRD | GABRD | -1.08 / 0.224 / 0.76 | +0.66 / 0.309 / 1.00 | -0.23 / 0.521 / 0.81 | -0.24 / 0.267 / 0.73 |
| neurosteroid/steroid | GABRA4 | GABRA4 | -0.28 / 0.447 / 0.86 | +0.06 / 0.87 / 1.00 | -0.62 / 0.00924 / 0.41 | -0.35 / 0.023 / 0.66 |
| hormonal | AR | AR | +0.49 / 0.0738 / 0.70 | +0.34 / 0.303 / 1.00 | low (9.4) | -0.42 / 0.49 / 0.83 |
| hormonal | ESR1 | ESR1 | +0.18 / 0.472 / 0.87 | +0.29 / 0.398 / 1.00 | low (6.9) | low (7.3) |
| hormonal | ESR2 | ESR2 | -0.14 / 0.602 / 0.91 | +0.37 / 0.398 / 1.00 | -0.49 / 0.223 / 0.62 | low (8.8) |
| hormonal | PRL | - | not in table | not in table | not in table | not in table |
| hormonal | PRLR | PRLR | +1.03 / 0.0679 / 0.70 | +0.29 / 0.608 / 1.00 | low (2.2) | low (1.6) |
| other | NOS1 | NOS1 | +0.14 / 0.503 / 0.88 | +0.37 / 0.231 / 1.00 | -0.47 / 0.00967 / 0.41 | -0.25 / 0.402 / 0.79 |
| other | PDE5A | PDE5A | +0.29 / 0.377 / 0.83 | +0.38 / 0.306 / 1.00 | +0.29 / 0.509 / 0.80 | -0.46 / 0.1 / 0.66 |
| other | OXT | OXT | -0.42 / 0.0557 / 0.69 | +0.06 / 0.892 / 1.00 | low (5.9) | +2.27 / 0.0912 / 0.66 |
| other | OXTR | OXTR | -0.02 / 0.901 / 0.98 | +0.21 / 0.316 / 1.00 | +0.33 / 0.433 / 0.76 | -0.24 / 0.388 / 0.78 |
| other | MC4R | MC4R | -0.31 / 0.0438 / 0.69 | -0.07 / 0.744 / 1.00 | -0.27 / 0.467 / 0.78 | +0.41 / 0.26 / 0.72 |
| other | SIGMAR1 | SIGMAR1 | -0.08 / 0.305 / 0.80 | +0.21 / 0.259 / 1.00 | +0.07 / 0.34 / 0.71 | +0.29 / 0.0171 / 0.66 |
| other | ADRA2A | ADRA2A | +0.02 / 0.829 / 0.96 | +0.06 / 0.653 / 1.00 | +0.77 / 0.12 / 0.53 | +0.03 / 0.912 / 0.98 |
| other | HRH1 | HRH1 | +0.07 / 0.546 / 0.89 | +0.03 / 0.873 / 1.00 | -0.04 / 0.834 / 0.95 | +0.31 / 0.207 / 0.70 |
| other | BDNF | BDNF | +0.01 / 0.93 / 0.99 | -0.17 / 0.321 / 1.00 | +1.45 / 0.18 / 0.59 | -0.66 / 0.456 / 0.82 |
<!-- panel_par:end -->

**Finasteride (secondary analysis)**

<!-- panel_fin:start -->
| Group | Human gene | Rat symbol | hypothalamus T0 | hypothalamus T1 | hippocampus T0 | hippocampus T1 |
|---|---|---|---|---|---|---|
| sodium/sensory channels | SCN9A | SCN9A | -0.41 / 0.00278 / 0.30 | +0.07 / 0.629 / 0.97 | -0.45 / 0.357 / 0.87 | -0.00 / 0.999 / 1.00 |
| sodium/sensory channels | SCN10A | SCN10A | low (7.7) | -0.05 / 0.869 / 0.99 | low (0.7) | low (1.4) |
| sodium/sensory channels | SCN11A | SCN11A | +0.42 / 0.22 / 0.66 | +0.20 / 0.501 / 0.97 | low (3.1) | low (5.2) |
| sodium/sensory channels | TRPV1 | TRPV1 | -0.20 / 0.302 / 0.71 | +0.40 / 0.0112 / 0.96 | +0.13 / 0.527 / 0.92 | +0.12 / 0.621 / 0.97 |
| sodium/sensory channels | TRPM8 | TRPM8 | +0.02 / 0.934 / 0.98 | -0.23 / 0.44 / 0.97 | low (2.9) | low (3.0) |
| sodium/sensory channels | TRPA1 | TRPA1 | -0.39 / 0.14 / 0.62 | -0.07 / 0.697 / 0.98 | low (6.0) | low (4.2) |
| sodium/sensory channels | PIEZO2 | PIEZO2 | -0.36 / 0.177 / 0.64 | +0.01 / 0.975 / 1.00 | -0.23 / 0.2 / 0.82 | -0.06 / 0.771 / 0.98 |
| sodium/sensory channels | ASIC3 | ASIC3 | -0.07 / 0.852 / 0.95 | +0.26 / 0.226 / 0.96 | -0.52 / 0.216 / 0.82 | -0.36 / 0.278 / 0.97 |
| serotonin | SLC6A4 | SLC6A4 | low (1.8) | low (2.7) | low (0.8) | low (0.6) |
| serotonin | HTR1A | HTR1A | -0.19 / 0.344 / 0.73 | -0.13 / 0.464 / 0.97 | +0.04 / 0.72 / 0.96 | +0.14 / 0.477 / 0.97 |
| serotonin | HTR1B | HTR1B | -0.18 / 0.0953 / 0.60 | -0.27 / 0.164 / 0.96 | -0.09 / 0.647 / 0.95 | +0.41 / 0.0761 / 0.97 |
| serotonin | HTR2A | HTR2A | +0.00 / 0.991 / 1.00 | -0.15 / 0.414 / 0.97 | -0.08 / 0.73 / 0.96 | +0.18 / 0.562 / 0.97 |
| serotonin | HTR2C | HTR2C | -0.08 / 0.48 / 0.81 | -0.06 / 0.515 / 0.97 | -0.10 / 0.614 / 0.94 | +0.15 / 0.44 / 0.97 |
| serotonin | HTR3A | HTR3A | +0.04 / 0.843 / 0.95 | -0.07 / 0.648 / 0.98 | +0.02 / 0.914 / 0.99 | -0.07 / 0.648 / 0.97 |
| serotonin | HTR7 | HTR7 | -0.05 / 0.432 / 0.78 | -0.13 / 0.148 / 0.96 | +0.05 / 0.803 / 0.97 | +0.24 / 0.17 / 0.97 |
| serotonin | TPH2 | TPH2 | -0.04 / 0.902 / 0.97 | +0.12 / 0.641 / 0.97 | -0.08 / 0.766 / 0.97 | +0.22 / 0.44 / 0.97 |
| dopamine | DRD1 | DRD1 | +0.16 / 0.393 / 0.76 | -0.21 / 0.0789 / 0.96 | +0.10 / 0.545 / 0.92 | +0.03 / 0.807 / 0.99 |
| dopamine | DRD2 | DRD2 | +0.21 / 0.124 / 0.62 | +0.02 / 0.885 / 0.99 | +0.16 / 0.412 / 0.89 | -0.06 / 0.783 / 0.98 |
| dopamine | DRD3 | DRD3 | +0.19 / 0.603 / 0.86 | -0.62 / 0.23 / 0.96 | not in table | low (0.7) |
| dopamine | TH | TH | +0.77 / 0.000426 / 0.28 | -0.08 / 0.844 / 0.99 | +0.01 / 0.985 / 1.00 | +0.00 / 0.984 / 1.00 |
| dopamine | SLC6A3 | SLC6A3 | +1.68 / 0.0103 / 0.41 | +0.65 / 0.588 / 0.97 | low (0.9) | low (0.8) |
| neurosteroid/steroid | SRD5A1 | SRD5A1 | +0.06 / 0.471 / 0.80 | -0.05 / 0.692 / 0.98 | +0.12 / 0.223 / 0.83 | +0.09 / 0.464 / 0.97 |
| neurosteroid/steroid | SRD5A2 | SRD5A2 | low (1.6) | low (3.7) | low (3.0) | low (2.5) |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C12 | low (3.4) | low (2.1) | low (2.2) | low (4.3) |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C13 | low (6.8) | +0.65 / 0.16 / 0.96 | low (9.4) | +0.26 / 0.456 / 0.97 |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C14 | -0.01 / 0.981 / 0.99 | +0.55 / 0.214 / 0.96 | +0.27 / 0.347 / 0.87 | -0.12 / 0.615 / 0.97 |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C15 | +0.18 / 0.196 / 0.65 | +0.37 / 0.11 / 0.96 | -0.06 / 0.744 / 0.96 | -0.09 / 0.675 / 0.98 |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C19 | -0.61 / 0.0169 / 0.44 | +0.31 / 0.319 / 0.96 | -0.32 / 0.233 / 0.83 | -0.29 / 0.205 / 0.97 |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C2 | low (0.4) | low (1.3) | low (0.5) | low (0.6) |
| neurosteroid/steroid | HSD3B family | HSD3B7 | +0.18 / 0.344 / 0.73 | +0.13 / 0.3 / 0.96 | +0.18 / 0.279 / 0.85 | -0.20 / 0.23 / 0.97 |
| neurosteroid/steroid | TSPO | TSPO | +0.36 / 0.176 / 0.64 | +0.33 / 0.127 / 0.96 | +0.24 / 0.431 / 0.90 | +0.10 / 0.728 / 0.98 |
| neurosteroid/steroid | STAR | STAR | -0.18 / 0.448 / 0.79 | +0.17 / 0.278 / 0.96 | -0.06 / 0.762 / 0.97 | -0.15 / 0.639 / 0.97 |
| neurosteroid/steroid | CYP11A1 | CYP11A1 | low (7.3) | -0.04 / 0.877 / 0.99 | +0.21 / 0.588 / 0.93 | +0.27 / 0.387 / 0.97 |
| neurosteroid/steroid | GABRD | GABRD | -0.05 / 0.833 / 0.95 | -0.70 / 0.283 / 0.96 | +0.06 / 0.738 / 0.96 | +0.01 / 0.956 / 1.00 |
| neurosteroid/steroid | GABRA4 | GABRA4 | -0.22 / 0.304 / 0.71 | -0.33 / 0.196 / 0.96 | -0.07 / 0.643 / 0.95 | +0.09 / 0.482 / 0.97 |
| hormonal | AR | AR | -0.27 / 0.124 / 0.62 | -0.17 / 0.597 / 0.97 | +0.40 / 0.274 / 0.85 | +0.41 / 0.298 / 0.97 |
| hormonal | ESR1 | ESR1 | -0.13 / 0.574 / 0.85 | -0.05 / 0.831 / 0.99 | low (6.3) | low (7.1) |
| hormonal | ESR2 | ESR2 | -0.47 / 0.149 / 0.63 | -0.23 / 0.401 / 0.97 | low (3.3) | low (2.9) |
| hormonal | PRL | PRL | low (1.2) | not in table | low (20.5) | not in table |
| hormonal | PRLR | PRLR | -0.73 / 0.0395 / 0.53 | +0.00 / 1 / 1.00 | low (4.7) | low (2.9) |
| other | NOS1 | NOS1 | -0.23 / 0.209 / 0.66 | -0.25 / 0.365 / 0.96 | +0.26 / 0.399 / 0.89 | +0.30 / 0.461 / 0.97 |
| other | PDE5A | PDE5A | -0.29 / 0.168 / 0.63 | +0.13 / 0.686 / 0.98 | -0.31 / 0.25 / 0.84 | +0.29 / 0.357 / 0.97 |
| other | OXT | OXT | +1.08 / 0.00279 / 0.30 | +0.32 / 0.44 / 0.97 | low (3.1) | low (1.3) |
| other | OXTR | OXTR | +0.13 / 0.369 / 0.74 | -0.06 / 0.784 / 0.99 | -0.29 / 0.223 / 0.83 | +0.05 / 0.845 / 0.99 |
| other | MC4R | MC4R | +0.09 / 0.669 / 0.89 | +0.15 / 0.403 / 0.97 | +0.21 / 0.373 / 0.88 | +0.01 / 0.953 / 1.00 |
| other | SIGMAR1 | SIGMAR1 | +0.18 / 0.0573 / 0.57 | +0.09 / 0.328 / 0.96 | +0.07 / 0.383 / 0.88 | -0.10 / 0.388 / 0.97 |
| other | ADRA2A | ADRA2A | +0.14 / 0.197 / 0.65 | +0.13 / 0.25 / 0.96 | +0.02 / 0.928 / 0.99 | +0.12 / 0.255 / 0.97 |
| other | HRH1 | HRH1 | -0.00 / 0.993 / 1.00 | -0.06 / 0.741 / 0.98 | +0.20 / 0.147 / 0.79 | +0.16 / 0.216 / 0.97 |
| other | BDNF | BDNF | +0.08 / 0.421 / 0.77 | -0.04 / 0.71 / 0.98 | -0.08 / 0.51 / 0.92 | -0.06 / 0.65 / 0.97 |
| neurosteroid/steroid | HSD3B family | HSD3B1 | not in table | low (0.4) | low (0.3) | not in table |
| neurosteroid/steroid | HSD3B family | HSD3B3 | not in table | low (0.3) | not in table | not in table |
| hormonal | PRL | - | not in table | not in table | not in table | not in table |
| dopamine | DRD3 | - | not in table | not in table | not in table | not in table |
| neurosteroid/steroid | AKR1C family (3alpha-HSD) | AKR1C3 | not in table | not in table | low (0.3) | not in table |
<!-- panel_fin:end -->

Panel summary:

- Genome-wide, the smallest FDR for any panel gene in any of the 8 contrasts is 0.28. Nothing is significant.
- Correcting over the panel only (33-44 tested genes per contrast): paroxetine has no gene below 0.10
  (closest, NAc T0: Akr1c8 +0.92, Gabra4 -0.62, Nos1 -0.47, each panel-FDR 0.11). Finasteride hypothalamus T0
  has three: **Th +0.77** (p = 0.0004, panel-FDR 0.017; authors' padj 0.0018), **Scn9a -0.41** (p = 0.003,
  panel-FDR 0.038) and **Oxt +1.09** (p = 0.003, panel-FDR 0.038). None of the three is changed at T1
  (-0.08, +0.07, +0.32; all p > 0.4).
- Persisting panel genes: only Gabra4 in the paroxetine NAc is nominally changed in the same direction at
  both timepoints. Dopamine receptor genes Drd1, Drd2, Drd3 are lower in the NAc at T0 (-0.8 to -1.1,
  p = 0.02-0.08) and still slightly lower at T1 (-0.3 to -0.5, p = 0.06-0.10); none is significant, and
  this is the pattern most exposed to the dissection caveat above.
- No sign of altered Htr1a, Htr2c, Tph2, Srd5a1, Tspo, Star, Ar, Esr1, Oxtr, Mc4r, Pde5a or Bdnf at T1 in
  either tissue - with the power caveat that only large changes were detectable.
- 19 of 304 tested panel cells (6%) across both drugs have raw p < 0.05, about what chance alone
  predicts (5%).

## Limitations

1. **n = 4 per group.** Underpowered for anything but large effects; estimates of effect size for "top"
   genes are inflated by selection.
2. **Normalised counts, not raw counts.** No count-based model could be refitted; log2(x + 1) plus t-tests
   lose power for low-count genes relative to a negative-binomial model.
3. **Bulk tissue, hand-dissected small regions.** Composition differences between animals are large relative
   to drug effects and cannot be separated from them.
4. **Separate cohorts and runs for T0 and T1.** Only within-timepoint contrasts are valid; "persistence" is
   inferred by comparing two independent contrasts.
5. **One sex, one dose, one washout interval, healthy animals, no behavioural phenotype linked to the
   sequenced animals** (as far as the abstract and supplement show). Animals were not selected for showing
   persistent sexual dysfunction, whereas PSSD affects a minority of those exposed; group means may hide a
   responder subgroup.
6. **Wrong tissue for the lead symptom.** Hypothalamus and NAc speak to desire and reward. Genital numbness
   points to dorsal root ganglia, pudendal/dorsal penile or clitoral nerve, spinal cord and genital skin,
   none of which has been profiled after these drugs anywhere we could find.
7. **Unverified design details for paroxetine**: dose, route, strain and exact timing were not read (paywall).
   Group assignment in two tables and tissue identity in four were inferred (see Data).
8. The relabelling test has only 35 possible outcomes; p = 0.029 is its floor and is uncorrected for having
   looked at two gene-set sizes, two tissues and two drugs.

## What a lab should do next

1. **Deposit the existing raw data** (FASTQ and raw count matrices for both studies) in GEO/SRA. This costs
   nothing and would allow joint modelling of T0 and T1 and of both drugs.
2. **Replicate the NAc washout result at adequate power.** From the observed gene-level SD (about 0.2-0.25
   log2 units) and T1 effects of about 0.3-0.5 log2 units (themselves probably overestimates), a plain
   two-group t-test needs about 14-19 animals per group for a 0.5 log2 effect and 19-27 for 0.4 at
   p < 1e-5 (a genome-wide-like threshold), with 80% power. A pre-registered targeted panel tested at
   p < 0.001 needs about 9-17 per group for effects of 0.4-0.5. Pre-register the 54 nominally persisting NAc genes (file
   `results/persistence_genes.csv`) as the hypothesis; confirm the top ones (Pde10a, Slc24a4, Lancl1, Gabra4,
   Grm5, Unc79) by qPCR or in situ in an independent cohort.
3. **Remove the dissection confound**: single-nucleus RNA-seq or spatial transcriptomics of NAc, or at
   minimum punch dissection with marker-based composition correction, and process treated and control
   animals in interleaved order.
4. **Profile the tissues that match the symptom**: L6-S1 dorsal root ganglia, pelvic ganglia, lumbosacral
   spinal cord and penile/clitoral tissue, at end of treatment and after washout, with the sensory channel
   panel (Scn9a, Scn10a, Scn11a, Trpv1, Trpm8, Trpa1, Piezo2, Asic3) as pre-specified readouts. No such
   dataset exists for any of these drugs.
5. **Tie molecules to phenotype**: measure sexual behaviour and genital sensory thresholds in the same
   animals, expect only a subset to stay impaired after washout, and compare impaired vs recovered animals
   rather than only drug vs vehicle.
6. **Extend the design**: females, at least two washout intervals (to distinguish slow recovery from a stable
   state), a longer exposure, and the drugs with no washout data at all (antipsychotics, mirtazapine,
   isotretinoin). Add an epigenomic layer (ATAC-seq or H3K27ac) at T1, since no dataset tests whether a
   chromatin change outlasts any of these drugs in adults.

## Files

- `results/contrast_summary.csv` - one row per contrast: sample sizes, genes tested, counts at each threshold, power figures, how groups were assigned.
- `results/<drug>_<tissue>_<T0|T1>_top_genes.csv` - genes with raw p < 0.01 by either test or authors' padj < 0.10, with all statistics.
- `results/persistence_genes.csv`, `results/persistence_summary.csv` - per-gene T0-to-T1 classification and the concordance statistics.
- `results/candidate_panel.csv` - the panel in all 8 contrasts.
- `results/run_log.txt` - console summary of the run.
