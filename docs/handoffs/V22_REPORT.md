# V22 REPORT — figure scripts adopted, v22 literals audited, five questions closed

Order: the V22 work order (follows V21_REPORT, commit 60b2bab). Commit: `the commit carrying this file (git rev-parse HEAD)` (local, not pushed). Keys are `file.json::path`, all under `docs/`.
No `.tex` edited (v22 copied into `paper/`, the v21 files kept as `*_v21.tex`). Nothing downloaded. Rounding is the author's.

## 0. Four-line answer

1. **Figure sizes after adoption** (smallest text at printed width; 3.51 in for the 0.49-textwidth floats, 7.0 in for the double-column ones): fig_cpr_dop **7.19 pt**,
   fig_joint_power **8.07**, fig_region_design **7.86**, fig_scene **7.05**, fig_n_sensitivity 7.05, fig_spec_curve 7.97. Your four numbers are confirmed exactly. No Type 3, fonts embedded.
2. **C1, the region null at the product's count.** The large-field N of L = 12…16 is 34.55, 36.79, **39.69 ± 0.32**, 41.97, 45.14. L = 14 (N = 39.7) is nearest 39.4 *and* 40;
   L = 13 (36.8) is nearest 38. 260 cells: **30.58 ± 0.73 % at N = 39.7 (27.68 ± 0.71 at 36.8), 30.3 ± 0.7 % interpolated to 39.4**. 3647 cells: **7.15 ± 0.58 % at 39.7
   (2.95 ± 0.38 at 36.8), 6.7 ± 0.5 % interpolated to 39.4 — not 2.7 %.**
3. **C2:** the published 0.59 uses **four fixed-width coherence strata (cuts 0.4, 0.5, 0.6), pooled over passes**; D_overlap's 0.46 uses **deciles of the pooled coherence distribution crossed with
   pass** (only 4 of 20 strata informative) — not "formed within each pass". **C3:** 76 % (215/281) is of **all 281 shadowed discs**, not of the 17.4 % outside the support (the 49 outside are all
   above the sunlit 95th percentile); 66 % (884/1331) is of **all sunlit discs**, on the **propensity score of being shadowed**.
4. **Commit `the commit carrying this file (git rev-parse HEAD)`; gates `32/32 PASS`** (before this pass: 32/32 at 60b2bab).

## 1. A — Figure scripts adopted (`figure_compare_v21.json`, G26)

`Claude outputs/grsl/figscripts_v22/make_figures_v12.py` and `make_fig_region.py` replace `paper/` copies (old ones kept as `make_figures_v12_v21.py`, `make_fig_region_v21.py`).
1. Regenerated `fig_cpr_dop.pdf`, `fig_joint_power.pdf`, `fig_region_design.pdf` (and `fig_scene`, `fig_n_sensitivity`, `fig_spec_curve`) into `paper/`. Against `Claude outputs/grsl/`:
   **decompressed content streams identical for all six.** Bytes differ (dates/IDs; and for the three rebuilt figures also compressed image/font stream bytes — the zlib build differs; 12/12 decompressed
   streams of fig_cpr_dop are equal). I first mis-reported a difference for fig_cpr_dop: `figure_compare_v21.py`'s stream splitter matched the `stream` inside `endstream`; fixed.
2. **G26 extended: all five main-text figures plus fig_spec_curve must have text ≥ 7.0 pt at the printed width** (`MIN_TEXT_PT`/`PRINTED_IN`; fig_scene included; fig1_degeneracy is a supplement figure and is
   not held). Measured: 7.19, 8.07, 7.86, 7.05 (the four floats), 7.05 (fig_n_sensitivity at 7.0 in), 7.97. `--inject small` still caught.
3. Fonts: embedded, no Type 3, for every figure (G26 reads the PDF font dictionaries; pdffonts is not installed).

## 2. B — v22 literal audit (`v22_literal_audit.json`; `audit_manuscript_numbers.py`; `number_crosscheck.py`)

Template audit of every changed/new literal (`backend/scripts/v22_literal_audit.py`; the v21 rows that still stand are reused; 87 rows in all):

| file | PASS | MISMATCH | ABSENT | NO-SOURCE |
|---|---|---|---|---|
| master | 60 | 0 | 0 | 0 |
| submission | 60 | 0 | 0 | 0 |
| supplement | 25 | 2 | 0 | 0 |

Every row of your table PASSES except the two supplement mismatches below: abstract (28 % at 37.3 looks, 2 % at 14.5); Sec. IV (34 / 82 / 28 / 7.6 / 2.7 / 9.1; 0.6 % at 218 = 0.60 ± 0.17); Table II (3.6 / 13.2 / 27.9;
counts 14.5 / 37.3 / 78.2; 260 cells 1.8 / 28 / 30 = 1.80 / 28.05 / 29.75; 3647 cells 0 / 2.7 / 87 = 0 / 2.70 / 86.9; caption peaks 37 % at N = 53 (37.15 at 53.26), 87 % at N = 78 (86.9 at 78.22), 0.6 and 11 %
at 218, empty through 231); Sec. VI-B (17.8 = 17.84, "21 with texture", onset 232, N̂ < 232, 231); Sec. VI-C (97.6 = 97.59, 80.0 = 80.04, IUT none up to 300, "ten" — see §6); Sec. VI-D (17 % = 17.4; 27 % of draws = 26.5, p = 0.55 = 0.551;
1024 / 512 / 14 / 82; MH 0.44 (0.23–0.79), 0.64 (0.38–1.07), 0.80 (0.30–2.11); MDE 2.6 / 2.9–3.7 = 2.57 / 2.86–3.74; Table III (g) 4.04 (1.80–10.28), MH incidence deciles 2.19 (1.06–4.81), 3.18 (1.33–6.86));
Sec. VI-E (all PASS in the existing table); limitations, conclusion and scope table (97.6, 231, 2.6, 37); S-VII (Tables S7, S8 and the text, one template per sentence).
Existing table (`audit_manuscript_numbers.py`, 412 rows master/submission incl. 19 v22 rows, 215 supplement incl. 17): **master 352 PASS / 0 MISMATCH / 4 NO SOURCE / 56 ABSENT; submission 304 / 0 / 4 / 104; supplement 214 / 0 / 1 / 0.**
The 4 NO SOURCE are the literature/closed-form values (1.44, 1.66, Stacy 2.4, Sinha 47 %; supplement `x_bound`). ABSENT = v20 literals not printed in v22: of the 56 (master) 54 moved to the supplement and 2 were removed
(the logistic fit's coherence SE 2.0 and SNR −0.08); submission 104. `number_crosscheck.py`: master and submission **293 / 293** literals found in an artifact, 0 without; supplement **501 / 503** (the two grid lists "80, 100, 150, 200"
and "254, 400, 600", as before). Literals found by diffing v21 against v22 and not on the list: none unkeyed (the diff of 58 new submission tokens maps to the rows above).

**Mismatches, IN CAPITALS:**
* **S-VII: "at the published operating point (CPR 1.1, minimum DOP 0.0476) it is 8.20, 11.09, 14.86 and 25.76 %" — THE 14.86 DIFFERS FROM ITS ARTIFACT: `n_sensitivity_np.json::by_N.80.bound_at_published_operating_point_CPR1p1_DOPmin_percent` = 14.8548, which rounds to 14.85.**
  The 14.86 is MY V21 report's rounding (14.855) that v22 copied; the other three (8.2044, 11.0867, 25.7629) agree.
* S-VII: "the fraction of regions containing a pixel with CPR ≥ 1 collapses (0.641, 0.382, 0.051, 0.006 …)" — the fourth value is 13/2000 = **0.0065 exactly**; printed 0.006 is round-half-even, my half-up rule reads 0.007. A tie, not an error.

## 3. C — The five questions

**C1. Region null at the product's count** (`n_sensitivity_region_39.json`, seed 20261071; 4000 regions at 260 cells, 2000 at 3647, MC SE on the unconditional rate; N(L) on 16 realizations of 256 × 256 cells ≈ 10⁶ cells).

| L | large-field N | 260 cells: conditional / containing / **unconditional** | 3647 cells: conditional / containing / **unconditional** |
|---|---|---|---|
| 13 | 36.79 ± 0.42 | 33.7 % / 0.820 / **27.68 ± 0.71 %** | 2.95 % / 1.000 / **2.95 ± 0.38 %** |
| 14 | 39.69 ± 0.32 | 38.53 % / 0.793 / **30.58 ± 0.73 %** | 7.15 % / 1.000 / **7.15 ± 0.58 %** |
| interpolated to 39.4 (weight 0.90 on L = 14) | | **30.29 ± 0.66 %** | **6.73 ± 0.52 %** |

**Nearest 38 is L = 13 (36.8); nearest 39.4 and 40 is L = 14 (39.7).** For CPR 0.7 / DOP 0.20: 260 cells 20.10 ± 0.63 % at 39.7, 3647 cells 1.30 ± 0.25 % (interpolated 19.8 and 1.2 %).
**The 3647-cell 2.7 % is the rate at N ≈ 37 (re-run at L = 13: 2.95 ± 0.38 %); it rises by about 4 points between 36.8 and 39.7 looks.** The paper can say 39.4 and print 30 % (260 cells) and 7 % (3647 cells), or keep 37 and 28 % and 2.7–3 %.

**C2. The coherence-strata Mantel–Haenszel** (`shadow_identification.json::N_mh_strata_definitions`). *Published (Table III, `A_ladder.*.mantel_haenszel_coherence_strata`):* four strata of **fixed width** on the disc's median coherence,
cuts 0.4 / 0.5 / 0.6 (`np.digitize(coh, [0.4, 0.5, 0.6])`), **pooled over passes** (pass is not a stratifier; "pass 1" = the same cuts on the pass-1 discs). *D_overlap `coherence_deciles`:* **ten equal-count strata** (10th…90th percentiles
of the **pooled** coherence distribution), pooled; `…_by_pass` = decile × pass (20 strata); only strata with both a shadowed and a sunlit disc enter (4 of 10, 4 of 20). L two passes: fixed-width pooled **0.59 (0.34–1.05)** [the published];
deciles pooled 0.64 (0.37–1.11); fixed-width × pass 0.44 (0.25–0.80); deciles pooled × pass **0.46 (0.26–0.82), Tarone p = 0.98** [D_overlap]; deciles within each pass × pass 0.49 (0.27–0.90). They differ in (i) the cut points and (ii) whether pass
is crossed in: the pooled strata mix the second pass's high-coherence sunlit discs (487, 0.4 % firing) with pass 1's. **The published 0.59 uses the fixed-width pooled strata.** *The supplement's "formed within each pass" is imprecise:*
the deciles are those of the pooled distribution crossed with pass; deciles computed within each pass give 0.49.

**C3. Propensity percentages** (`O_propensity_populations`; the score = logistic probability of being shadowed, fitted on shadowed and sunlit discs, mixed excluded). **"76 %": 215 of ALL 281 shadowed discs (76.5 %)** have a score above the sunlit discs' 95th percentile
(L pass 1 208/271 = 76.8 %, S-band 207/271 = 76.4 %). The 17.4 % outside the support (49 discs) is a different population: all 49 lie above the sunlit maximum and so are among the 215; the 76 % is not a share of the 49.
**"66 %": 884 of ALL 1331 sunlit discs (66.4 %)** have a propensity score below the shadowed discs' 5th percentile (variable: the propensity score; L pass 1 515/844 = 61.0 %, S-band 517/843 = 61.3 %).

**C4. The specifications excluding 1 from above** (`M_spec_curve_above`, `docs/spec_curve_above.md`, covariate lists for all 14 + 20 + 24): **confirmed for the 14 L-band specifications: all lack coherence AND LOLA local incidence, all 14 contain the geometry-file incidence,
none contains slope, roughness or PSR fraction** (14 of the 256 specifications lacking both coherence and local incidence exclude 1 from above). **The 20 (L pass 1) and 24 (S-band) satisfy the same rule for coherence, local incidence, slope, roughness and PSR fraction
but not for incidence: 14 of 20 and 14 of 24 contain it** (the others combine position, slant range, SNR and ln N̂, e.g. L pass 1: position alone, 2.13 (1.10–4.07); S-band: class + position + slant range 8.68 (2.59–26.33)).

**C5. METHODS §19.9** now carries one sentence: 0.2273–0.7844 (0.23–0.78) when only the pass-1 blocks are resampled; 0.2282–0.7853 (0.23–0.79, Table III) when the blocks of both passes are resampled and the pass-1 discs taken.
(Also added to §18.4: the achieved-N labels; new §21.)

## 4. D — Artifact labels

`region_mean_null.json` correlated rows (40) each gain `achieved_log_ratio_N_large_field` and `achieved_log_ratio_N_large_field_source`; the artifact gains `achieved_N_labels` (note, script, UTC, rows). **No stored number changed** (verified: the file minus the new keys equals the committed
one). Script `backend/scripts/region_mean_null_relabel.py` (idempotent, draws nothing). Labels (L → large-field N): 1 → 3.7, 5 → 14.5, 13 → 37.3, 19 → 53.3, 31 → 85.8, 43 → 122.7, 55 → 148.7; stored (75.9 for L = 19, 83.6 for L = 31) unchanged beside them.
`audit_manuscript_numbers.py` reads them (rows `v22_n373`, `v22_n53_rmnlf`, `s7_n373`, `s7_n533`; Table II's 78.2 and 14.5 are read from `n_sensitivity_region.json`, which has no row in `region_mean_null.json`: L = 28), and `number_crosscheck.py` finds 37.3, 78.2, 53.3 in the
artifact trees (it takes any number). G33 gained `v22 D` (every row carries its label, L = 19: 75.9 stored / 53.3 large field) and `v22 C4` (the rule), injections `v22_label`, `v22_rule` caught.

## 5. E — Gates

``verify_all.py`: **32/32 PASS** (`ALL 32 GATES PASS`, run with the new scripts staged; `docs/verification.json`); before this pass 32/32 at 60b2bab. Extended, none loosened: G26 (all six main-text figures ≥ 7.0 pt at the printed width; `--inject small` caught),
G33 (+ `v22 D` labels, `v22 C4` rule; injections `v22_label`, `v22_rule` caught), G8 stamp (83 artifacts; METHODS §18.4 note, §19.9 sentence, §21 re-read before re-stamping).
`audit_manuscript_numbers.py`: master 352 PASS / 0 MISMATCH / 4 NO SOURCE / 56 ABSENT; submission 304 / 0 / 4 / 104; supplement 214 / 0 / 1 / 0. `number_crosscheck.py`: master, submission 293/293; supplement 501/503.
`check_submission.py` on the v22 master: **0 FAIL, 2 WARN (placeholders, OPEN block), 10 PASS, 3 UNAVAILABLE**; submission **0 FAIL, 1 WARN (placeholders), 11 PASS, 3 UNAVAILABLE**; abstract 249 words, 43 cites, 22 refs.
**Unavailable here:** pdffonts and pdfinfo (poppler not installed): the Type-3, font-embedding and page-count checks of `check_submission.py`, and — no LaTeX, no `.log` — the undefined-reference and overfull-box checks, so "WARN = one 0.5 pt overfull box" and
"supplement has no undefined reference" cannot be confirmed from a log. Read directly from the compiled PDFs in `Claude outputs/grsl/` (pure Python): master 10 pages, submission 10, **supplement 10**; no Type 3; font files embedded (26 / 26 / 24).
Pure-Python reference check of the .tex: **no undefined `\ref`, no undefined `\cite`, no uncited `\bibitem` in master, submission or supplement** (supplement figures: fig1_degeneracy, fig_n_sensitivity, fig_spec_curve, all present). I cannot verify that the PDFs were built from the .tex now in `paper/`.`

## 6. CONTRADICTIONS (quoted)

* **"in simulation at 37 looks (the correlated simulation's count nearest the product's 39.4)" — THE CORRELATED SIMULATION'S COUNT NEAREST 39.4 IS 39.7 (L = 14), NOT 37 (36.8–37.3, L = 13): AT 39.7 THE 260-CELL RATE IS 30.6 ± 0.7 % AND THE 3647-CELL RATE 7.15 ± 0.58 %, NOT 28 % AND 2.7 %.** (37 looks is the setting nearest 38.) The abstract's "28 % … at 37 looks" and Table II are correct as labelled.
* **Supplement S-VII: "Mantel–Haenszel over coherence strata formed within each pass (not those of Table III) is 0.46"** — THE STRATA ARE DECILES OF THE POOLED COHERENCE DISTRIBUTION CROSSED WITH PASS; DECILES FORMED WITHIN EACH PASS GIVE 0.49 (0.27–0.90).
* **S-VII "14.86" — DIFFERS FROM ITS ARTIFACT (14.8548 → 14.85)** (§2; my V21 rounding).
* **Sec. VI-C: "subtracting the noise in any of ten variants (nominal or β⁰ noise, constant or range-linear, 3 and 6 dB floors) changes F2's selections by at most 14 % (50 to 43)"** — THE TEN VARIANTS ARE THE UNMODIFIED BASE PLUS NINE: nominal/β⁰ × constant/linear (4), 3 and 6 dB floors × nominal/β⁰ (4) and the legacy v18a variant; eight of the nine match the parenthesis. The 14 % and 43 hold (`v21_carryover_checks.json`).
* Adjusted intervals excluding 1 from ABOVE: the v22 text states them (row (g) 4.04 (1.80–10.28); MH over incidence deciles 2.19 (1.06–4.81), 3.18 (1.33–6.86); the 14 L-band specifications). None was found that v22 does not state. For the permutation "27 % of draws": the 27 % is of the 973 of 2000 draws that converged (L two passes), not of 2000.
* Printed numbers differing from their artifact: the single 14.86 above.

## 7. Commit

`the commit carrying this file (git rev-parse HEAD)`. Staged: scripts (`n_sensitivity_region_39`, `shadow_c2_c3_c4`, `region_mean_null_relabel`, `v22_literal_audit`; `figure_compare_v21` fixed), the adopted figure scripts and their `_v21` copies, the three figures regenerated by the new scripts, artifacts, `spec_curve_above.md`,
METHODS (§18.4 note, §19.9 sentence, §21), REPRODUCIBILITY §24, G26/G33/stamp changes, `docs/V22_REPORT.md`. Not staged: `Claude outputs/`, `docs/gate10/`, `frontend/scripts/*.mjs`, `submission_check.json`, the .tex files. Timestamp-only rewrites restored by `git checkout`.
