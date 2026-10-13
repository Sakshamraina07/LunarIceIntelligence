# V21 REPORT — N-sensitivity, identifiability of the shadow excess, and an audit of v21

Order: `CLAUDE_CODE_V21_WORKORDER.md`. Repository state: commit `the commit carrying this file (git rev-parse HEAD)` (local, not pushed).
Keys are `file.json::path.to.key`, all under `docs/`. Nothing downloaded. No `.tex` edited.
I report what the data give; I do not decide what the paper says. Rounding is the author's: the
artifacts hold full precision.

## 0. Headline findings (read these first)

1. **F2 STOPS BEING "NONE SIGNIFICANT" AT A CONSTANT N OF 97.6, WHICH IS BELOW 218 (NOT BELOW 69.7).**
   `n_sensitivity_real.json::smallest_N_any_selected_cell_significant.L_20200808 / F2` = 97.589 (F2's largest
   selected R is 1.26624). The whole pass-1 frame: 80.04 (largest selected R 1.29794); S-band F2: 165.89;
   S-band frame 80.16; pass-2 frame 416.96. v21 says "none significant at its local look count (25–76)": that
   stands (76 < 79.6), but it is a statement about N-hat, not about N.
2. **THE RULE'S SIZE PASSES 5 % AT N = 17.84** (±0.11, 2 SE), 10 % at 30.20, 20 % at 55.54
   (`n_sensitivity_core.json::size_first_exceeds`). v21 prints "from N = 19", the first grid value above 5 %.
3. **THE UNCONDITIONAL REGION-DOP NULL PEAKS AND THEN FALLS.** 260 cells: maximum 37.15 ± 1.08 % at achieved
   N = 53.3, falling to 29.75 % at 78.2, 17.2 % at 103.7, 0.60 % at 218. 3647 cells: maximum 86.9 ± 1.1 % at
   N = 78.2 (86.6 % at 103.7), falling to 45.4 % at 148.7 and 11.0 % at 218.
   (`n_sensitivity_region.json::summary`.) **Table II's "37" (260 cells, N = 80) IS THE RATE AT N ≈ 53, NOT 80**
   (§3 E).
4. **SHADOW OR OVER THE SPECIFICATION CURVE** (1024 specifications per set, block bootstrap, B = 500):
   L-band two passes OR 0.16–4.33 (median 0.69); 14 exclude 1 from ABOVE, 82 from below. L pass 1: 0.13–4.29,
   20 above, 68 below. S-band pass 1: 0.06–8.88, 24 above, 149 below.
   **SPECIFICATIONS WITHOUT COHERENCE DO EXCLUDE 1 FROM ABOVE** (14 / 20 / 24 of 512 per set); all of them also
   lack LOLA local incidence, all 14 of the L ones contain the geometry-file incidence. Every specification that
   contains coherence has its interval above 1 nowhere (0 of 512 per set); 33 / 30 / 59 exclude 1 from below.
5. Commit `the commit carrying this file (git rev-parse HEAD)`; gates `32/32 PASS` (before: `31/32, G32 failing`).

## 1. Phase 0

1. v21 files are in `paper/` beside the v20 ones (`*_v20.tex`): master `dfsar_detection_limits_full.tex`,
   `…_submission.tex`, `…_supplement.tex` (all three, plus v20 copies). The four figures in
   `Claude outputs/grsl/` (fig_scene, fig_cpr_dop, fig_joint_power, fig_region_design) are **byte-identical to
   the figures at HEAD** (their v21 versions equal v20's); the supplement's four (fig1_degeneracy, fig2_enl,
   fig3_detection, fig4_external) are unchanged. The .tex files are not staged (as in earlier passes).
2. `V20_AUDIT_REPORT.md` **does not exist**; its open items are in §5 (V20 carry-overs).
3. Gates on the v21 master:
   * `verify_all.py` before my work: 31/32, **G32 FAIL** — v21 moved Table II to the supplement (Table S6)
     and `recompute_manuscript_tables.py` found no six-column sampling row. Fixed by parsing the supplement's
     S6 when the main text has none (71 cells, 0 differ; `table_recompute.json::tables.II_sampling_statistics.parsed_from`).
     No tolerance loosened.
   * `check_submission.py` (run from a scratch directory so `submission_check.json` is not overwritten): master
     **0 FAIL, 2 WARN, 10 PASS, 3 UNAVAILABLE**; submission 0 FAIL, 1 WARN, 11 PASS, 3 UNAVAILABLE. Abstract 249
     words (PASS), 43 cites defined/cited (PASS), 22 refs (PASS). **I cannot confirm "3 WARN, 13 PASS, 10 pages":**
     poppler is not installed (pdffonts/pdfinfo checks UNAVAILABLE, not PASS) and there is no LaTeX, hence no
     `.log` (the undefined-reference and overfull-hbox checks do not run). Read directly from the other Claude's
     compiled PDFs in `Claude outputs/grsl/` (pure-Python): master and submission 10 pages, supplement 7, no
     Type 3, font files embedded. I cannot verify those PDFs were built from the .tex now in `paper/`.

## 2. Gate status (W7)

``verify_all.py` **before** (v21 master, my work not yet applied): 31/32 PASS, **G32 FAIL**. **After:** **32/32 PASS** (`ALL 32 GATES PASS`, run before the commit with the new scripts staged;
`docs/verification.json`). G28 passes once the new generator scripts are tracked (staged) — it failed in an intermediate run only because they were untracked. Gates extended, none loosened:
G26 (+ `fig_n_sensitivity.pdf`, `fig_spec_curve.pdf`, enforced ≥ 7 pt at the printed width, `--inject small` caught), G32 (reads Table S6 when the main text has no sampling row),
G33 (+ v21 W1B, W1A, W1D, W1F, W1E, W2A, W2B anchors; injections `v21_np v21_iut v21_f2 v21_region v21_ladder v21_spec` all caught), G8 stamp (80 artifacts; METHODS §20).
`audit_manuscript_numbers.py` (master / submission / supplement): 337 PASS, 0 MISMATCH, 4 NO SOURCE, 52 ABSENT / 292, 0, 4, 97 / 197, 0, 1, 0. `number_crosscheck.py`: 282/282.
`check_submission.py`: see §1.`

## 3. W1 — N-sensitivity (artifacts: `n_sensitivity.json`, `n_sensitivity_{core,np,region,real,f2point,calcheck}.json`,
`n_sensitivity_table.md/.tex`, `paper/fig_n_sensitivity.pdf`)

Grid N ∈ {5, 7, 10, 13.72, 14.5, 17.4, 21, 28, 34, 38, 39.4, 45, 55, 70, 75.9, 79.6166, 80, 100, 150, 218}.
Full table: `n_sensitivity_table.md`; row k of `n_sensitivity.json::rows`. Summary (percent unless noted):

| N | crit95 | NP bound | rule size ± SE | rule power CPR 1.1 | region null 260 (achieved N) | 3647 | F2 signif. | frame signif. L1/L2/S | IUT region |
|---|---|---|---|---|---|---|---|---|---|
| 5 | 2.978 | 7.63 | 0.69 ± 0.01 | 0.71 | 0.0 (3.7) | 0.0 | 0 | 0/0/0 | no |
| 10 | 2.124 | 8.87 | 2.15 ± 0.01 | 2.18 | 0.15 (9.4) | 0.0 | 0 | 0/0/0 | no |
| 13.72 | 1.895 | 9.66 | 3.43 ± 0.01 | 3.55 | 1.80 (14.5) | 0.0 | 0 | 0/0/0 | no |
| 21 | 1.671 | 11.06 | 6.20 ± 0.02 | 6.51 | 4.50 (19.9) | 0.0 | 0 | 0/0/0 | no |
| 38 | 1.462 | 13.94 | 13.22 ± 0.02 | 14.41 | 28.05 (37.3) | 2.7 | 0 | 0/0/0 | no |
| 39.4 | 1.452 | 14.17 | 13.76 ± 0.02 | 15.09 | 28.05 (37.3) | 2.7 | 0 | 0/0/0 | no |
| 55 | 1.370 | 16.56 | 19.75 ± 0.03 | 22.52 | 37.15 (53.3) | 51.5 | 0 | 0/0/0 | no |
| 79.6166 | 1.2989 | 20.12 | 27.90 ± 0.03 | 33.38 | 29.75 (78.2) | 86.9 | 0 | 0/0/0 | no |
| 80 | 1.298 | 20.17 | 28.02 ± 0.03 | 33.62 | 29.75 (78.2) | 86.9 | 0 | 0/0/0 (the first significant frame cell appears at 80.04) | no |
| 100 | 1.263 | 22.93 | 33.14 ± 0.03 | 41.52 | 17.2 (103.7) | 86.6 | 1 | 225/0/179 | no |
| 150 | 1.210 | 29.43 | 41.66 ± 0.04 | 57.27 | 4.75 (148.7) | 45.4 | 3 | 1504/0/1231 | no |
| 218 | 1.171 | 37.59 | 47.01 ± 0.04 | 71.44 | 0.60 (218.4) | 11.0 | 4 | 3427/0/2782 | no |

The 2 × 10⁶-trial rates carry the binomial SE shown; region rows 2000 (260) / 1000 (3647) regions, SE in the JSON
(`unconditional_mc_se_percent`).

* **A.** crit95 of F(2N,2N) = band edge 1.2988506 at N = 79.6166 (`n_sensitivity_core.json::N_edge_crit_equals_1p2989`);
  band 0.7699 < CPR < 1.2989. 1.882 (N = 14), 1.452 (39.4), 1.298 (80).
* **B. All twelve quoted NP values reproduce** to printed precision (9.72, 11.06, 12.63, 13.94, 14.17, 16.56,
  20.2, 22.9, 29.4, 37.6, 46.5, 64.1 at N = 14, 21, 30, 38, 39.4, 55, 80, 100, 150, 218, 300, 500;
  `n_sensitivity_np.json::reproduction_all_agree` = true; no DIFFERENCE). At the published operating point
  (CPR 1.1, minimum DOP 0.0476): 8.20 / 11.09 / 14.86 / 25.76 at N = 14 / 39.4 / 80 / 218
  (`n_sensitivity_np.json::by_N.*.bound_at_published_operating_point_CPR1p1_DOPmin_percent`).
  **"DOP 0" cannot be evaluated at CPR 1.1, 1.2, 1.25: the coupling DOP ≥ |1 − CPR|/(1 + CPR) makes DOP 0 an
  inadmissible population there. I did not substitute another computation; the minimum-DOP population is the
  admissible lowest and the one the paper uses.**
* **C.** Size 3.43 (13.72), 3.73 (14.5; 3.6 printed at N = 14 interpolates), **13.22 ± 0.02 at N = 38 (printed
  13.2 ✓)**, 13.76 (39.4), **28.02 ± 0.03 at N = 80 (printed 27.9: from 10⁵ trials, SE 0.14; at N = 79.6166 my
  value is 27.90)**. Size first exceeds 5 / 10 / 20 % at **17.84 [17.73, 17.95] / 30.20 [30.05, 30.35] / 55.54
  [55.32, 55.75]** (brackets 2 SE; `size_first_exceeds`). Power at CPR 1.1 / 1.2 / 1.25, minimum DOP:
  e.g. N = 39.4: 15.09 / 14.18 / 13.19 ± 0.025; N = 80: 33.62 / 30.40 / 26.60 (`rows.*.rule.power`).
* **D.** IUT region exists from **N = 232** (edge 0.07629 < q05 0.07644; 1.6 × 10⁷ draws); none through 231;
  size 0.0008 ± 0.0004 % at 232, **0.177 ± 0.007 % at 254**, 1.10 ± 0.02 % at 300 (`iut_onset`, `iut_size_at`).
  80 % pooled looks: `regional_requirement`: 1396 / 2049 / 5241 / 8588 (CPR 1.1 / 1.2 / 1.05 / 1.25). K = ⌈N_eff/N⌉
  cells at N = 14.5 / 39.4 / 80 / 218: CPR 1.1: 97 / 36 / 18 / 7; 1.2: 142 / 53 / 26 / 10; 1.05: 362 / 134 / 66 / 25;
  1.25: 593 / 218 / 108 / 40 (full grid in the JSON). Simulation: K = 100 at N = 14 (N_eff 1400) power **80.24 ± 0.13 %**;
  K = 36 at N = 39.4 (N_eff 1418.4) **80.90 ± 0.12 %** (`pooled_confirmation`; 10⁵ trials). Confirmed.
* **E. Region-mean null.** Populations CPR 0.7/0.176, 0.7/0.20, 1.0/0, × 260 and 3647 cells × independent /
  correlated, full grid in `n_sensitivity_region.json::results`. Per N: conditional, containing fraction,
  unconditional, SE. **Reconciliation of the printed 260-cell figures:** 1.84 / 34.08 / 57.96 % conditional
  at artifact-"achieved N" 14.5 / 38.0 / 75.9, containing 0.9765 / 0.823 / 0.641, unconditional 1.80 / 28.05 / 37.15 %
  **are the artifact's numbers exactly** (`region_mean_null.json::results.CPR 0.7 DOP 0.176.N{13.72,39.4,80}.cells260.correlated`).
  0.823 × 34.08 = 28.05 ✓ — **the abstract's 28 % is the UNCONDITIONAL rate** (34 % is conditional on a region
  containing a CPR ≥ 1 pixel; 82 % of regions do). Independent 7.6 % is the artifact's (2000 trials, SE 0.6);
  my 2 × 10⁴-trial run gives 7.88 ± 0.19 at N = 39.4. Unpolarized 9.1 % = 9.05 % (181/2000 half-up; SE 0.64). 3647
  cells 0 / 2.7 / 91.2 % conditional at 13.8 / 38.4 / 83.6 and unconditional 0 / 2.7 / 90.0 ✓.
  **THE "ACHIEVED N" OF THOSE ARTIFACT ROWS IS MIS-CALIBRATED.** `region_mean_null.correlated` calibrates the looks L
  against N on four realizations of the region's own bounding box. Repeated 40 times at L = 19 that calibration gives
  57.2 ± 10.2 looks (range 38.9–91.3); on 150 000 cells it gives 53.1–53.6 (`n_sensitivity_calcheck.json`). The
  260-cell "N = 80" row used L = 19: **its N is 53.3, not 75.9**. The 3647-cell "83.6" row (L = 31) is 85.8. The 14.5
  and 38.0 rows are within 2–3 % (true 14.5 and 37.3). Re-running the grid on the large-field calibration:
  260 cells, CPR 0.7 / DOP 0.176, correlated, unconditional (SE): 0.00 (3.7), 0.05 ± 0.05 (6.7), 0.15 ± 0.09 (9.4),
  1.80 ± 0.30 (14.5), 3.15 ± 0.39 (18.2), 4.50 ± 0.46 (19.9), 16.25 ± 0.82 (28.2), **28.05 ± 1.00 (37.3)**, 34.5 ± 1.1
  (47.0), **37.15 ± 1.08 (53.3, maximum)**, 32.15 (69.6), **29.75 ± 1.02 (78.2)**, 17.2 (103.7), 4.75 (148.7), 0.60 (218.4);
  3647 cells: 0 below N ≈ 30, 2.7 ± 0.5 (37.3), 21.8 (47.0), 51.5 (53.3), 82.0 (69.6), **86.9 ± 1.1 (78.2, max)**, 86.6
  (103.7), 45.4 (148.7), 11.0 (218.4). Crossings of the unconditional rate: 260 cells **5 % at N = 20.3, never 50 %**;
  3647 cells **5 % at N = 38.5, 50 % at N = 53.0**. **It rises with N to a maximum and then falls** (260: maximum at
  N ≈ 53; 3647: ≈ 78–104): the conditional rate keeps rising (57.96 % at 53, 77.9 % at 78, 93 % at 149) but the
  fraction of regions with any CPR ≥ 1 pixel collapses (0.641, 0.382, 0.051, 0.006), so the *unconditional* rate falls.
  For the 5 / 50 % crossings of the other two populations, and the 0.7 / 0.20 population, see `summary`.
* **F. Real data, per-cell N overridden by a constant** (`n_sensitivity_real.json`, grid + 232, 254, 300). Selected
  (N-free): F2 50, pass-1 frame 26 462, pass-2 frame 24, S-band F2 29, S-band frame 24 288. **Smallest N at which any
  selected cell is significant (CPR-only, F(2N,2N) 95 %): F2 97.59 — BELOW 218, NOT BELOW 69.7.** Frame: 80.04 (pass 1),
  80.16 (S), 416.96 (pass 2). IUT region empty through 231, present at 232; **the IUT selects no F2 cell at any N tested
  (up to 300)**; at N = 254 it selects 26 cells of the pass-1 frame and 19 of the S-band frame (N set constant, not
  estimated), 222 / 184 at N = 300. F2 pooled looks (6.657 independent samples × N): 96.5 / 262.3 / 532.5 at N = 14.5 / 39.4 / 80
  = 0.069 / 0.19 / 0.38 of the 1396 needed; pooled IUT power at CPR 1.1 (minimum DOP): 0.0 / **0.568 ± 0.003 %** /
  28.7 % (10⁷ draws at 262.3: `n_sensitivity_f2point.json`; the grid's 200 000-draw row reads 0.52 because its q05
  came from 2 × 10⁶ draws). v21's "about 0.6 %" **survives**.
* **G. The per-disc firing rule is N-free**, confirmed from code: `gap_v20_frame.py:222`
  `rule = ok & (dop < DOP_T) & (R > 1.0)`; N-hat is formed after it (`:226` `L.local_n`), and enters only the IUT (`:229`) and,
  as ln N-hat (median over the disc), rung (b) (`v21_extract.py`: `median_N_hat`). The disc's cell set (663 cells above the
  noise floor in both channels) and class are N-free. `n_sensitivity_real.json::N_free_audit`.
* **H. Deliverables:** supplement-ready table `n_sensitivity_table.md` / `.tex`; `paper/fig_n_sensitivity.pdf` (7 in wide,
  STIX, fonttype 42, no Type 3, smallest text 7.21 pt at printed size; left: NP bound, rule size ± 2 SE, rule power at CPR 1.1
  vs N with markers at 14, 21, 39.4, 69.7, 79.6; right: region null, 260 and 3647 cells, 2 SE bands), added to G26 with an
  enforced ≥ 7 pt rule (`--inject small` caught). `n_sensitivity.json::keys` maps each printed number to its source.

## 4. W2 — Is the shadow excess identified? (`shadow_identification.json`, `disc_table_v21.json`, `paper/fig_spec_curve.pdf`)

1888 discs (1331 sunlit, 281 shadowed, 276 mixed); S-band pass 1 1300 (843 / 271 / 186); seed 20260930, 146 5×5 blocks (L),
B = 2000.

**A. Table S3, complete.** Everything below reproduces the published values (`A_reproduction`: all 15 rows agree; no DIFFERENCE).
OR (model 95 % | cluster-robust SE | block bootstrap 95 %), `A_ladder.<set>.rungs.<rung>`:

| rung | L two passes | L pass 1 | S-band pass 1 |
|---|---|---|---|
| (a) | +0.582 ± 0.210; 1.79 (1.19–2.70) \| 0.337 \| 0.90–3.50 | 1.80 (1.19–2.72) \| 0.339 \| 0.88–3.62 | 2.93 (1.88–4.58) \| 0.391 \| **1.22–6.47** |
| (b) | 1.29 (0.83–2.00) \| 0.319 \| 0.66–2.50 | 1.31 \| 0.323 \| 0.69–2.54 | 1.62 (1.01–2.62) \| 0.365 \| 0.72–3.36 |
| (c) | **−0.401 ± 0.378**; 0.67 (0.32–1.41) \| 0.391 \| 0.28–1.56 | 0.72 (0.34–1.51) \| 0.398 \| 0.29–1.72 | 0.83 (0.34–1.99) \| 0.471 \| 0.26–2.03 |
| (d) | −0.322 ± 0.395; 0.72 \| 0.388 \| 0.33–1.88 | 0.99 \| 0.371 \| 0.45–2.49 | 0.79 (0.27–2.27) \| 0.510 \| 0.23–2.47 |
| (e) | −0.144 ± 0.467; 0.87 \| 0.398 \| 0.37–2.45 | 0.77 \| 0.399 \| 0.34–2.22 | 0.50 (0.14–1.74) \| 0.577 \| 0.08–1.61 |
| (e0) | +0.011 ± 0.302; 1.01 (0.56–1.83) \| 0.375 \| 0.49–2.38 | 1.01 \| 0.376 \| 0.50–2.47 | 0.49 (0.21–1.14) \| 0.433 \| 0.18–1.30 |
| (f) (e) + terrain | 0.70 \| 0.457 \| 0.24–2.28 | 0.62 \| 0.455 \| 0.23–2.15 | 0.40 \| 0.679 \| 0.04–1.71 |
| (f0) geometry + terrain, no coherence | 0.77 \| 0.384 \| 0.34–1.85 | 0.77 \| 0.385 \| 0.36–1.92 | **0.34 (0.13–0.90) \| 0.494 \| 0.09–0.95** |
| MH, coherence strata | 0.59 (0.34–1.05) block 0.31–1.06 | 0.44 (0.25–0.80) block 0.23–0.78 | 0.99 (0.56–1.77) block 0.42–2.21 |
| MH pass 1 of the two-pass set | **0.44 (0.25–0.80); block 0.23–0.79** | | |

L pass 2 (585 discs, 2 firing): **0 of 10 shadowed discs fire; the PSR coefficient runs to −∞ (complete separation); no estimate**
(`converged` = false in every rung; I report counts, not coefficients). Rung (f): the local-slope radar-shadow fraction is 0 for
every disc, the layover fraction is nonzero for 79 discs (not ray tracing); a constant column was dropped.

**FLAGS (adjusted interval excluding 1):** the only ladder interval excluding 1 from above is the crude (a) S-band 1.22–6.47
(unadjusted, as in v21). **S-band (f0) 0.34 (0.09–0.95) EXCLUDES 1 FROM BELOW** (shadowed fire less); L pass 1 MH
0.23–0.79 excludes from below (known).

**B. Specification curve** (all 2¹⁰ subsets of {ln N-hat, coherence, min SNR, position, slant range, incidence, LOLA local
incidence, slope, roughness (RMS height 100 m), PSR fraction}, class + pass always in, B = 500), `B_spec_curve.<set>.summary`:

| set | OR median (range) | block CI excludes 1 above / below | with coherence: median, above / below | without: median, above / below |
|---|---|---|---|---|
| L two passes | 0.69 (0.16–4.33) | 14 / 82 | 0.58, 0 / 33 | 1.61, **14** / 49 |
| L pass 1 | 0.75 (0.13–4.29) | 20 / 68 | 0.62, 0 / 30 | 1.82, **20** / 38 |
| S-band pass 1 | 0.43 (0.06–8.88) | 24 / 149 | 0.28, 0 / 59 | 1.24, **24** / 90 |

**SPECIFICATIONS WITHOUT COHERENCE EXCLUDE 1 FROM ABOVE (block bootstrap): 14 (L two passes), 20 (L pass 1), 24 (S).** Cluster-robust:
15 / 20 / 24. They are specifications that contain the geometry-file incidence, slant range and/or position and **none contains LOLA
local incidence, coherence, slope, roughness or PSR fraction**. Example (L two passes): class + pass + slant range + incidence: OR 4.04
(1.80–10.28); + ln N-hat + SNR + position + slant range + incidence: 3.13 (1.50–8.24). Adding LOLA local incidence (the published (e0)) gives 1.01.
(S-band: class + position + slant range: 8.68, 2.59–26.33.) The figure: `paper/fig_spec_curve.pdf` (the PSR-fraction covariate is nearly
collinear with class and produces the very wide intervals at the left and right ends; it is in the set because the order lists it).

**C. Outcome decomposition** (`C_outcomes`; B = 1000): disc fires = DOP gate / CPR condition / joint, shadowed vs sunlit discs and
rung (a) → (c) OR (block 95 %): L two passes DOP-gate-only 76/281 vs 139/1331: 2.15 (1.22–4.06) → **1.22 (0.71–2.00)**; CPR-only 52/281 vs
93/1331: 1.99 (1.05–3.98) → 0.80 (0.42–1.53); joint 1.79 → 0.67. S-band: DOP-only 2.82 (1.34–5.91) → 1.05 (0.53–2.16); CPR-only 2.93 (1.20–6.77) →
0.78 (0.28–1.82); joint 2.93 → 0.83. **Cell level** (binomial, cells fired of 663 per disc, cluster-robust): shadowed 0.252 % vs sunlit 0.230 %
of cells fire (OR 0.72 (0.32–1.63) rung (a); 0.53 (0.39–0.73) rung (c) — **excludes 1 from below**); DOP-only cells 1.20 vs 0.69 %.
The disc-level excess is a clustering excess: the per-cell rates are equal.

**D. Overlap and positivity** (`D_overlap`). Standardized mean differences (shadowed − sunlit), L two passes: coherence −0.84, slant range 0.94,
incidence −0.89, roughness 100 m 0.83, slope 0.69, position 0.65 / −0.71, ln N-hat 0.55, LOLA local incidence 0.55, SNR −0.19. Propensity of
being shadowed: AUC 0.93; **17.4 % (L) / 22.5 % (S) of shadowed discs lie outside the sunlit propensity support; 76 % are above the sunlit 95th
percentile**; 66 % of sunlit discs are below the shadowed 5th percentile. Trimmed to common support: rung (a) 1.07 (0.52–2.19) [232 shadowed,
1026 sunlit], (c) 0.90 (0.35–2.79); Crump 0.1–0.9: 0.56 (0.22–1.33); S-band common support 0.68 (0.27–1.53), Crump 0.31 (0.09–0.91 — excludes 1
from below). Exact stratification (Mantel–Haenszel RBG, Breslow–Day–Tarone): coherence strata (by pass) 0.46 (0.26–0.82), Tarone p = 0.98;
**slant-range deciles (by pass) 1.73 (1.14–2.63), Tarone p = 0.40; S-band slant-range deciles 3.31 (2.05–5.35) — EXCLUDE 1 FROM ABOVE
(model-based RBG).** Shadowed discs in strata with no sunlit disc: 0 in every stratification. With a block bootstrap
(`K_geometry_mh_block_bootstrap`, B = 2000): **MH over incidence deciles 2.19 (1.06–4.81) (L two passes), 2.13 (1.04–4.61) (L pass 1), 3.18
(1.33–6.86) (S); MH over slant-range deciles 3.31 (1.30–7.83) (S) — EXCLUDE 1 FROM ABOVE**; slant range (L two passes) 1.73 (0.85–3.50),
(L pass 1) 1.72 (0.81–3.55) include 1; local-incidence deciles 0.72 (0.36–1.38), slope 0.86, roughness 0.82 include 1.

**E. Minimum detectable OR** (80 % power, 5 % two-sided, normal approximation to the cluster-robust SE; `E_minimum_detectable_effect`):
(a) 2.57 / 0.39 (L two passes), (c) 2.99 / 0.33, (e0) 2.86 / 0.35 (above / below 1); L pass 1 (c) 3.05 / 0.33; S (a) 2.99 / 0.34, (c) 3.74 / 0.27,
(e0) 3.36 / 0.30. The observed ORs have power 0.41 (a), 0.18 (c), 0.05 (e0) (L two passes). **The data cannot detect a shadow odds ratio below
about 2.6–3.7 (or above about 0.27–0.39) after adjustment.**

**F. Terrain** (LDEM_80S_20M, 80 m slope baseline, 100 m / 500 m plane-detrended RMS height, local-slope layover/shadow fractions) is in
`disc_table_v21.json` and rungs (f), (f0) above. Not ray-traced; radar shadow by the local-slope criterion is 0 for every disc.

**G. Block sizes and permutation** (`G_block_sizes`, `G_permutation`). OR (cluster-robust | block 95 %), L two passes: 3×3 (310 blocks) (a) 1.02–3.15 | 0.96–3.11,
(c) 0.25–1.78 | 0.22–1.76, (e0) 0.51–2.02 | 0.51–2.04; 5×5 (146) 0.92–3.46 | 0.90–3.50, 0.31–1.44 | 0.28–1.56, 0.48–2.11 | 0.49–2.38; 8×8 (80)
0.84–3.81 | 0.82–3.89, 0.30–1.49 | 0.23–1.63, 0.47–2.16 | 0.46–2.64; 12×12 (48) 0.76–4.19 | 0.74–4.64, 0.24–1.85 | 0.20–2.14, 0.46–2.21 | 0.46–2.85.
S-band (a): 3×3 1.43–6.00 | 1.33–6.20; 5×5 1.36–6.31 | 1.22–6.47; **8×8 1.22–7.05 | 0.99–7.26; 12×12 1.12–7.68 | 0.86–8.26**.
Permutation (2000 draws of a toroidal shift of the class lattice per pass, shifts leaving ≥ 30 % of a pass's discs admissible; the
swath is a 151 × 40 strip, 22 % occupied; the first version shifted over the whole box and left a median of 281 discs, so it was
replaced): observed OR 1.79 (a) has p(upper) = 0.27, two-sided 0.55 (L two passes), 0.52 (L pass 1), S-band OR 2.93 p(upper) = 0.20,
two-sided 0.43; (c) 0.59 / 0.72 / 0.79. **The crude excess is not distinguishable from random shifts of the PSR label lattice.**

**H. The pass-1 reversal (MH 0.44).** Pass-1 strata (coherence): (shadowed fires/n, sunlit fires/n): 0: 33/62 vs 59/75 (OR 0.31); 1: 6/36 vs 9/59
(1.13); 2: 1/46 vs 5/86 (0.49); 3: 0/127 vs 1/624 (1.63); Breslow–Day–Tarone p = 0.30 (no heterogeneity detected). Leaving out stratum 0
(coherence < 0.4, where 79 % of sunlit and 53 % of shadowed discs fire): **MH 0.80 (0.30–2.11)**; leaving out 1, 2, 3: 0.31, 0.45, 0.45. Other
stratifications of pass 1: 5 equal-count **0.64 (0.38–1.07)**, 5 equal-width 0.41 (0.21–0.82), 8: 0.46 / 0.46, 10: 0.49 / 0.40, 15: 0.43 / 0.44. Geometry
strata (MH, pass 1): slant range 1.72 (1.13–2.63), incidence 2.13 (1.37–3.32), LOLA local incidence 0.76 (0.47–1.21), slope 0.81. Pass 2: 10 shadowed, 0 fire,
sunlit 2/487. S-band 0.99 (0.56–1.77). **Mechanism test (noise-floor fraction of the firing cells):** pass 1, firing cells' median min SNR 10.4 dB in
shadowed discs vs 12.9 dB in sunlit, fraction below 6 dB 6.1 % vs 2.1 % (Mann–Whitney p = 0.17); S-band 9.6 vs 11.6 dB, 21.1 % vs 12.1 % (p = 0.11); in
coherence stratum 0 (L): 7.4 % vs 0.1 %. Direction consistent with a noise-floor contribution; not significant.

**I. Reconciliations.** (1) **0.23–0.79 vs 0.23–0.78:** the point 0.4432; resampling the blocks of both passes then taking pass-1 discs gives
0.2282–0.7853 (prints 0.23–0.79: Table III); resampling pass-1 blocks only gives 0.2273–0.7844 (0.23–0.78: METHODS §19.9, the S-band message). One
dataset, two resamplings; **v21 prints the former, METHODS the latter.** (2) **"270 of 271": confirmed**: 271 shadowed lattice cells in each band, 270
in common (L-only (−7, 7), S-only (68, 17)); fired shadowed sets 40 and 40, 26 in common (Jaccard 0.481), not identical. (3) **"96 to 133 firing
discs per band": confirmed** (S pass 1: 96; L two passes: 133; L pass 1: 131). (4) **"geometry is not computed from the polarimetric data":** the
slant-range sample is the SLC column index (the sample axis of the data grid) of a disc's cells (median), the geometry file's tie-point grid is indexed by that
axis and supplies the slant range and incidence by interpolation; neither reads a polarimetric value. The data enter only through *which* 663 cells
qualify as a disc's signal cells (boxcar'd power above the label noise floor in both channels). True as written, with that caveat.

## 5. W3 — Falsifiable claims in the v21 master, and V20 carry-overs

| # | sentence (v21 master) | what would falsify it | verdict |
|---|---|---|---|
| 1 | Abstract: "a cell that meets the criterion has CPR < 1.299, below the 95 % critical value of a CPR-only F(2N,2N) test at any look count under 79.6" | one selected cell with R ≥ 1.2989, or crit95(N) < 1.2989 for N < 79.6 | **SURVIVES** (identity; largest selected R 1.29794; crit95 = 1.2989 at 79.6166) |
| 2 | "the product's homogeneous blocks carry about 39" | block median N-hat outside 38.5–39.5 | **SURVIVES** (39.44; aware 39.2; intervals cover 66–72 %) |
| 3 | "at 14 to 39 looks no level-5 % test … exceeds 9.7 to 14 % power" | bound > 9.72 at N = 14 or > 14.17 at 39.4 | **SURVIVES** (reproduced to 4 decimals) |
| 4 | "80 % power against CPR 1.1 … with about 1400 pooled looks" | simulated IUT power at 1396 looks ≠ 80 % | **SURVIVES** (80.24 ± 0.13, 80.90 ± 0.12) |
| 5 | Abstract/Sec. IV/conclusion: "28 % of simulated 260-cell regions at 39 looks (2 % at 14)" | unconditional rate ≠ 28 / 1.8 | **SURVIVES WITH A REWORDING OF N:** 28.05 ± 1.00 is at achieved N = 37.3 (not 39.4; interpolated ≈ 29 at 39.4); 1.80 ± 0.30 at 14.5. 28 % is the *unconditional* rate (0.823 × 34.08) |
| 6 | Table II: "260 cells (%) 1.8 / 28 / 37" at N = 14 / 39.4 / 80 | the rate at N = 80 | **FALSIFIED as attributed: 37 % is at N ≈ 53; at N = 78–80 it is 29.75 ± 1.02 %.** 3647 cells "0 / 2.7 / 90": **NEEDS REWORDING** (0 / 2.7 ± 0.5 / 86.9 ± 1.1 at 14.5 / 37.3 / 78.2; 90.0 at N = 85.8) |
| 7 | Table II caption: "simulated at log-ratio counts 14.5, 38.0, 75.9 (260 cells) and 13.8, 38.4, 83.6 (3647 cells)" | recalibrated N | **FALSIFIED for 75.9 (53.3) and NEEDS REWORDING for the others** (14.5, 37.3 / 14.5, 37.3, 85.8) |
| 8 | Sec. VI-B: "The size exceeds 5 % from N = 19 (21 with texture)"; "below N = 19 it is [a 5 % test]" | size crossing 5 % below 19 | **NEEDS REWORDING:** 17.84 ± 0.11; between 17.84 and 19 the rule's size is 5.0–5.4 % |
| 9 | "no cell the joint rule selects can pass a CPR-only test unless its look count exceeds 79.6" | a selected cell with R > crit95(N) at N ≤ 79.6 | **SURVIVES** |
| 10 | "the IUT … first happens between N = 218 and 254" | onset outside the interval | **SURVIVES** (232; exact integer N 232, size 0.0008 ± 0.0004 %) |
| 11 | "its size below 0.2 % at 254 looks, where the NP bound still reaches 28 % at CPR 1.1" | IUT size ≥ 0.2 %, bound ≠ 28 | **SURVIVES** (0.177 ± 0.007 %; bound 25.76 at 218, 31.62 at 300 ⇒ ≈ 28.5 at 254) |
| 12 | Sec. VI-C: "In crater F2 … 50 of 663 … none significant at its local look count" ; conclusion "the absence of significant cells in F2 [follows] from the identity" | a selected F2 cell with R > crit95(N-hat) | **SURVIVES** (N-hat 25–76 < 79.6). **F2 cells become significant at a constant N ≥ 97.6** |
| 13 | "Their 6.7 independent samples pool to about 262 looks, where the IUT's power is about 0.6 %" | power ≠ 0.6 | **SURVIVES** (0.568 ± 0.003 %) |
| 14 | Sec. VI-C: noise subtraction "changes F2's selections by at most 14 % (50 to 43) and no disc rate by more than 1.1 points" | a variant outside | **SURVIVES for the v20 reconciliation variants** (§ carry-overs) |
| 15 | Sec. VI-D: "14.2 % (7.6–22.5) of the 281 shadowed … 5.7 % (3.6–8.1) of the 1331 sunlit" | rates | **SURVIVES** (artifact) |
| 16 | Table III / S3 odds ratios | any rung | **SURVIVES** (all reproduce; §4 A) |
| 17 | Sec. VI-D: "Within coherence strata on the first pass the odds ratio falls below 1 (0.44, 0.23–0.79), so shadowed discs there fire less often than sunlit discs of equal coherence" | stratification choice | **NEEDS REWORDING:** carried by stratum 0 (leave-out 0.80, 0.30–2.11); 5 equal-count strata 0.64 (0.38–1.07) include 1 |
| 18 | Sec. VI-D: "Geometry … is not computed from the polarimetric data, but its adjusted intervals are wide" | an adjusted geometry interval excluding 1 | **NEEDS REWORDING / CONTRADICTED IN PART:** geometry-file incidence and slant range without local incidence or coherence give OR 4.04 (1.80–10.28); MH over incidence deciles 2.19 (1.06–4.81). With LOLA local incidence 1.01 (0.49–2.38) |
| 19 | Abstract/VI-D/conclusion: "the excess is not distinguishable from that of depolarization and viewing geometry, so the data do not identify shadow as its cause" | an adjusted interval excluding 1 above | **NEEDS REWORDING:** true for the published (c), (e0), (f), (f0); **false for specifications without coherence and without LOLA local incidence (14 / 20 / 24 of 512 exclude 1 from above).** The *direct* effect of shadow is never detected; the data cannot detect OR < 2.6–3.7; conditioning on coherence or local incidence removes the excess; coherence-adjusted specifications often exclude 1 from *below* |
| 20 | Table scope: "whether shadow itself changes firing (the adjusted intervals are wide)" | — | **SURVIVES** (MDE 2.6–3.7) |
| 21 | Sec. VI-E: "(39.2 against 40.0) … a coherence-aware estimate differs by 2 %" | difference ≠ 2 % | **SURVIVES** (1.98 %) |
| 22 | "the critical value inflated by 1.032 (1.022–1.044), equivalent to 33.6 looks for 39.4" | — | **SURVIVES** (39.436/1.1747 = 33.57) |

**V20 carry-overs** (`V20_AUDIT_REPORT.md` does not exist; items folded in; `v21_carryover_checks.json`):
* "coherence-aware estimate differs by 2 %" (39.2 vs 40.0): 39.196 vs 39.990 = **1.98 %**, over the training halves of the 109 blocks (the standard
  estimator's whole-block median is 39.44). **Survives.**
* "F2 ≤ 14 % / disc rates ≤ 1.1 points over ALL variants": over the ten variants of the v20 reconciliation (nominal and β⁰ noise subtraction, constant
  and range-linear, 3 and 6 dB floors) F2 moves 50 → 48 / 49 / **43** / 50 / 49 (max **14.0 %**) and the pass-1 shadowed-disc rate by at most
  **1.107 points** (14.76 → 13.65), sunlit 0.12 (pass-1), 0.21 (pass-2 sunlit). **Survives for those.** NOT "all variants stored": the legacy v18a
  variants in `snr_control.json::f2` give 48 and **39** (−22 %; the linear-NES0 legacy variant), and the transmit-ellipticity variants (not noise subtraction)
  move F2 from 13 to 59 selected (−74 % to +18 %) and the pooled shadowed rate by up to 2.85 points. The sentence names noise subtraction; the 39 is a variant that
  `v20_reconciliation` supersedes.
* "the 11 dB margin marked nominal": 11.08 dB against the label's nominal NES0 −31.5 dB, v21 marks it nominal ("the label's nominal noise-equivalent σ⁰") and says the
  coherence bound suggests the nominal level overstates noise (1.80 % violate |C_HV|² ≤ C_HH C_VV at nominal against 0.022 % above 10 dB). **Survives.**
* **The S-band ladder section missing from `V20_GAP_REPORT.md`** is supplied in §4 A (S column) and in `docs/METHODS.md` §19.9: S-band pass 1 (a) 2.93 (1.22–6.47), (b) 1.62
  (0.72–3.36), (c) 0.83 (0.26–2.03), (d) 0.79 (0.23–2.47), (e) 0.50 (0.08–1.61), (e0) 0.49 (0.18–1.30), MH 0.99 (0.42–2.21), as printed in Table S3; all reproduce here.
  S-band `stokes_from_slc` pass: written by the earlier v18a session (`12f7c245-…`), entry `20200808S` added 2026-09-30 16:30 UTC.

## 6. W4 — Second scene

1. **Inventory (`data/`):** only two compact-pol acquisitions are complex (SLC) and usable: 2020-08-08 (L, S) and 2020-03-05 (L, S). The **2020-03-05 S-band SLI had not
   been run through the chain; it now has** (`stokes_from_slc_20200305S*.json`, `second_pass_s_v21.json`, `disc_table_v21.json::discs.S_20200305S`):
   896 972 matched cells, DOP < 0.13 in 1.03 %, joint rule 1620 cells (0.181 %), largest R 1.2687 (< 1.2989), **IUT 0**, F2 off the swath (0 signal cells); 584
   discs, 22 fire: sunlit 21/486 = 4.3 % (Wilson 2.8–6.5), **shadowed 0/10 (0–27.8 %)**, mixed 1/88; the ladder is not estimable (separation).
   **It is the same acquisition as L pass 2 — not an independent replication.** `ch2_sar_ncls_20200305t154539649_d_cp_d18.zip` is **0 bytes**; the 2025-11-06
   `nrxl…r0b` product is **L0B raw**, not chain-compatible (previously rejected). The L-band ladder rungs (a), (c), (e0) on this pass: not estimable. `enl_logratio`'s
   block statistics were not run for this product (local N-hat only).
2. **`docs/SECOND_SCENE_RUNBOOK.md`** written (PRADAN filters from the file-name pattern, placement, commands with measured run times, checklist of numbers). The PRADAN
   menu labels themselves were not browsed (flagged in the document).
3. **Mini-RF (not downloaded):** PDS Geosciences Node, `LRO-L-MRFLRO-4-CDR-V1.0`, Level 1 calibrated data records (β⁰, polarimetrically calibrated; each pixel four
   4-byte floats: H and V intensities and the real and imaginary part of the H–V cross power), archive volumes `lromrf_0001…`. **Approximate size per observation: not
   verified** (the pages read do not state it). The Level-2 / polar-mosaic data-set IDs were **not confirmed**. The ODE search (ode.rsl.wustl.edu/moon/) for footprints on F2 is the next step.
   **No download without an explicit yes from the author.**
4. **Sentences that change if a second scene replicates / does not:** in `SECOND_SCENE_RUNBOOK.md` §5.

## 7. W5 — The four figures (`figure_compare_v21.json`)

Regenerated by `make_fig_scene.py`, `make_figures_v12.py`, `make_fig_region.py` (G26) into `paper/`. Against `Claude outputs/grsl/`: **byte-identical: no (all four differ in
CreationDate/ModDate/ID only); identical after removing those: yes; decompressed content streams identical: yes**; all four also identical to the committed figures.
Fonts: embedded, **no Type 3**. **Text at printed size (0.49 \textwidth = 3.51 in): fig_scene 7.05 pt minimum; fig_cpr_dop 4.31 pt; fig_joint_power 5.37 pt; fig_region_design
5.41 pt — THREE OF THE FOUR HAVE TEXT BELOW 7 PT** (the 4.3–5.6 pt is mathtext sub/superscripts at 70 % size and 5.8–6.5 pt legends/marker labels; nominal sizes 7–8 pt).
I did not change the existing figures. Caption facts: fig_scene: PSR outline cyan, the 26 462 selected cells orange, box (b) = 12 × 3.8 km, disc red, 663 of 3647 cells with
signal, 50 selected; right panel 5 883 594 cells. fig_cpr_dop: 2-D log density, coupling curve, DOP 0.13, CPR 1, band edge 1.2989 and the crit95 line at N = 39.4 (1.452), inset
DOP 0–0.2 × CPR 0.7–1.5, admissible band shaded. fig_joint_power: size (solid), in-band selection at minimum DOP (dashed; dotted with markers for speckle), texture, correlated looks;
marked 39.4 and 79.6; shaded 218–254; thin black NP bound; right panel fig_region_design: IUT power (solid) and NP bound (dashed) vs pooled looks for CPR 1.05, 1.1, 1.2, 1.25 at
minimum DOP, dotted 80 %, markers F2 (262 looks) and fully imaged (shaded 900–1400). New: `fig_n_sensitivity.pdf` (min 7.21 pt) and `fig_spec_curve.pdf` (8.15 pt), both in G26.

## 8. W6 — Literal audit (`v21_literal_audit.json`)

| file | v21 rows PASS | MISMATCH | ABSENT | NO-SOURCE | existing table PASS | MISMATCH | NO SOURCE | ABSENT |
|---|---|---|---|---|---|---|---|---|
| master | 44 | 2 | 0 | 0 | 337 | 0 | 4 | 52 |
| submission | 44 | 2 | 0 | 0 | 292 | 0 | 4 | 97 |
| supplement | 4 | 0 | 0 | 0 | 197 | 0 | 1 | 0 |

(Existing table = `audit_manuscript_numbers.py` counts: 393 rows master/submission, supplement table 198.) **No printed number differs from the artifact it cites** (the 2 MISMATCH rows per
file are the deliberate re-calibrated Table II rows: printed 37 and 90 against 29.75 and 86.9 at the recalibrated N). The 4 NO SOURCE rows are literature/closed-form values (1.44, 1.66, Stacy 2.4, the
47 % of Sinha et al.; supplement `x_bound`). The 52 ABSENT rows (master) are v20 literals not printed in v21: 49 moved to the supplement (Table S6, coverage budget, georeferencing, …), 3 removed (the
logistic fit's coherence SE 2.0, SNR −0.08 ± 0.06). Submission ABSENT 97 = those 52 plus 45 rows the submission build lacks (printed in the master / supplement). Rows checked per the order: abstract 28 % and
2 % (PASS vs the unconditional rate), 9.7–14 %, ~1400 (1396 → 1400), 14.2 vs 5.7, 0.7699 / 1.2989 / 79.6; Table II (1.88/1.45/1.30; 9.7/14.2/20.2; 3.6/13.2/27.9; 1.8/28/37; 0/2.7/90) PASS against the
artifacts; Sec. IV 34 / 82 / 28 / 7.6 / 2.7 / 9.1, ±5° 0.002, ±0.5 dB −33…+18; Sec. V–VI literals; Table III; Table S3, S4 kernel sweep (59.9/78.9, 10 110/15 880, 69/270), S6, georeferencing 0.2846 / 0.4550;
`96 to 133`. `number_crosscheck.py`: 282 distinct literals, 282 found in an artifact, 0 without.

## 9. CONTRADICTIONS (quoted; each is also in §5)

* **"Regional rows: CPR 0.7, DOP 0.176, simulated at log-ratio counts 14.5, 38.0, 75.9 (260 cells) and 13.8, 38.4, 83.6 (3647 cells)"** — THE 260-CELL "75.9" IS 53.3 LOOKS; 3647-CELL "83.6" IS 85.8; THE TABLE II ENTRY "37" (260 CELLS, N = 80) IS THE RATE AT N ≈ 53 AND THE RATE AT N = 78–80 IS 29.75 ± 1.02 %.
* **"The size exceeds 5 % from N = 19 (21 with texture)" and "below N = 19 it is [a 5 % test]"** — THE SIZE CROSSES 5 % AT N = 17.84.
* **"Geometry, by contrast, is not computed from the polarimetric data, but its adjusted intervals are wide."** — GEOMETRY-ONLY ADJUSTED INTERVALS EXCLUDE 1 FROM ABOVE: class + pass + slant range + incidence OR 4.04 (1.80–10.28) (L two passes); MH over incidence deciles 2.19 (1.06–4.81) (L), 3.18 (1.33–6.86) (S); MH over slant-range deciles 3.31 (1.30–7.83) (S).
* **"the excess is not distinguishable from that of depolarization and viewing geometry"** — TRUE FOR THE PUBLISHED (c), (e0), (f), (f0); FALSE FOR 14 / 20 / 24 OF 512 SPECIFICATIONS WITHOUT COHERENCE (L two passes / L pass 1 / S): THEIR ADJUSTED BLOCK-BOOTSTRAP INTERVALS EXCLUDE 1 FROM ABOVE (shadowed discs fire MORE after adjustment). All lack LOLA local incidence.
* **"Within coherence strata on the first pass the odds ratio falls below 1 (0.44, 0.23–0.79)"** — THE RESULT DEPENDS ON THE STRATUM DEFINITION: 5 EQUAL-COUNT STRATA GIVE 0.64 (0.38–1.07); LEAVING OUT THE LOWEST-COHERENCE STRATUM GIVES 0.80 (0.30–2.11).
* **"none significant at its local look count"** (F2) — HOLDS FOR N-HAT 25–76; **F2'S LARGEST SELECTED CELL IS SIGNIFICANT AT A CONSTANT N OF 97.59 (BELOW 218)**.
* Adjusted intervals excluding 1 from above anywhere in the ladder (Table S3): none. The crude S-band (a) 1.22–6.47 does (unadjusted, as in v21).
* Printed numbers that differ from their artifact: **none** (W6).

## 10. Commit

`the commit carrying this file (git rev-parse HEAD)`. Staged: the new scripts, artifacts, `paper/make_fig_*.py` and the two new figures, the gate changes (G26, G33, G32, stamp), METHODS §20, REPRODUCIBILITY §23, the runbook,
this report copied to `docs/V21_REPORT.md`. Not staged (standing rules): `Claude outputs/`, `docs/gate10/`, `frontend/scripts/layout_metrics.mjs`,
`frontend/scripts/text_inventory.mjs`, `submission_check.json`, the v21/v20 `.tex` files. Timestamp-only rewrites restored by `git checkout`.
