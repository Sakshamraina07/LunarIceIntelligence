# Lunar Ice Intelligence

### Screening Chandrayaan-2 DFSAR over the Moon's south pole for water ice — and reporting what the data can and cannot support

**Project type:** Final year engineering capstone
**Domain:** Planetary remote sensing · radar polarimetry · SAR detection statistics · GIS · path planning
**Stack:** FastAPI + numpy/scipy backend, Vite + React + Leaflet frontend. No GDAL, no rasterio, no machine learning.

---

## Relation to the TGRS manuscript

This repository is the code and verification record behind *Identifiability and Significance of a
Lunar Radar Ice Criterion on a Chandrayaan-2 Compact-Polarimetric SAR Product* (Raina, Raina and
Pandey, submitted to *IEEE Transactions on Geoscience and Remote Sensing*, 2026). The manuscript is
the statistical core of the system described below: it asks what the published criterion
CPR > 1 together with DOP < 0.13 (Sinha et al., *npj Space Exploration*, 2026) can establish on
this product, at its measured look count. The application (map, landing sites, traverse, report)
is the capstone project the analysis grew out of; the two share one pipeline and one set of
artifacts. The table maps each result in the paper to the script that produced it and the
artifact it is printed from; `backend/scripts/manuscript_audit_table.py` is the machine-readable
version of this map, and `python backend/scripts/audit_manuscript_numbers.py` checks every printed
number against it.

| In the paper | Script | Artifact / figure file |
|---|---|---|
| Amplitude interval [c, 1/c] and the coupling identity DOP ≥ \|1−CPR\|/(1+CPR) (Secs. III–IV) | `backend/scripts/dop_exclusion.py`, `joint_criterion.py` | `docs/dop_exclusion.json`, `docs/joint_criterion.json` |
| Fig. 1(a) sample CPR over the frame | `backend/scripts/f2_complex_product.py`, `paper/make_fig_scene.py` | `paper/fig_scene.pdf` (needs the scene) |
| Fig. 1(b) every complex-product cell in (DOP, CPR) | `backend/scripts/stokes_from_slc.py`, `paper/make_figures_v12.py` | `paper/fig_cpr_dop_density.npz` → `paper/fig_cpr_dop.pdf` |
| Table I, look counts (label, moment, log-ratio, coherence, multilook control, bootstrap) | `measure_enl.py`, `enl_logratio.py`, `coherence_nhat.py`, `slc_multilook_control.py`, `bootstrap_enl.py`, `stokes_from_slc.py` | `docs/enl*.json`, `docs/enl_logratio.json`, `docs/coherence_nhat.json`, `docs/slc_multilook_control.json`, `docs/bootstrap_enl.json`, `docs/stokes_from_slc*.json` |
| Fig. 2(a) the joint rule as a test; size, in-band selection, NP bound | `dop_sampling_bias.py --curve`, `np_power_bound.py`, `paper/make_figures_v12.py` | `docs/joint_power_curve.json`, `docs/np_power_bound.json` → `paper/fig_joint_power.pdf` |
| Fig. 2(b) regional design curve (pooled looks for 80 % power) | `region_design_curve.py`, `paper/make_fig_region.py` | `docs/region_design_curve.json` → `paper/fig_region_design.pdf` |
| Table II, dependence of every result on N (critical value, IUT onset, size) | `detection_statistics.py`, `n_sensitivity_*.py`, assembled by `n_sensitivity_assemble.py` | `docs/detection_statistics.json`, `docs/n_sensitivity.json`, `docs/n_sensitivity_table.tex` |
| Crater F2 (Sec. VI-C) | `f2_maximum.py`, `f2_complex_product.py`, `check_f2_footprint.py` | `docs/f2_maximum.json`, `docs/f2_complex_product.json`, `docs/f2_footprint.json` |
| Table III, shadowed-versus-sunlit odds ratios with block-bootstrap intervals (Sec. VI-D) | `v21_extract.py` (disc table), `shadow_identification.py`, `psr_domains.py` | `docs/disc_table_v21.json`, `docs/shadow_identification.json`, `docs/psr_domains.json` |
| Measured tails against the F law (Sec. VI-E) | `tail_calibration_ci.py` | `docs/tail_calibration_ci.json` |
| Supplement Fig. S1 (amplitude pixels on the analytic curve) | `dop_exclusion.py`, `paper/make_figures.py` | `paper/fig1_density.npz` → `paper/fig1_degeneracy.pdf` |
| Supplement Fig. S2 (power bound, size and power against N; region-mean null) | `n_sensitivity_np.py`, `n_sensitivity_region.py`, `n_sensitivity_assemble.py`, `paper/make_fig_n_sensitivity.py` | `docs/n_sensitivity.json` → `paper/fig_n_sensitivity.pdf` |
| Supplement Fig. S3 (specification curve, 1024 specifications) | `shadow_identification.py`, `paper/make_fig_spec_curve.py` | `docs/shadow_identification.json::B_spec_curve` → `paper/fig_spec_curve.pdf` |
| Supplement Tables S1 (published moments), S4 (kernel sweep), S5 (coverage budget), S6 (sampling statistics) | `published_moments.py`, `gap_v20_frame.py`, `process_real_sar_pipeline.py`, `detection_statistics.py` | `docs/published_moments.json`, `docs/kernel_sweep.json`, `frontend/public/analysis/faustini.json::masks`, `docs/detection_statistics.json` |
| Literature search (Supplement S-II) | `literature_screen.py`, `literature_search_gate.py` | `docs/literature_search_record.csv`, `docs/literature_screen.json` |

**What you can reproduce without the ISRO data.** Every artifact above is tracked, so every table and
every figure except Fig. 1(a) regenerates from this checkout alone: `cd paper && python make_figures.py
&& python make_figures_v12.py && python make_fig_region.py && python make_fig_n_sensitivity.py &&
python make_fig_spec_curve.py` (environment: `requirements-analysis.txt`). Every table's artifact is
tracked; `recompute_manuscript_tables.py`, `audit_manuscript_numbers.py` and `number_crosscheck.py` diff
them against the manuscript source, which is not tracked until the submission is tagged, so in a fresh
clone they stop with MANUSCRIPT NOT FOUND. The simulation artifacts (`detection_statistics`, `joint_power_curve`, `np_power_bound`,
`region_design_curve`, `n_sensitivity*`) regenerate from fixed seeds with no data. Recomputing the
measured artifacts — look counts, Stokes statistics, the shadow study, Fig. 1(a) — needs the
Chandrayaan-2 scene from PRADAN and the LOLA products, as described under *Reproducing* below.
`paper/README.md` says which of the figure files are in the paper and which are superseded.

## What this is

An end-to-end, fully provenance-marked go/no-go pipeline over one real
Chandrayaan-2 DFSAR pass and real LOLA topography. **Every number on screen
carries a mark — `MEASURED`, `DERIVED` or `NO DATA` — and the build fails if one
does not.**

**The headline result is a null result with a proof.** The screen returns
0.0000 km² of candidate ice, and the reason is
closed-form rather than empirical: with CPR derived from amplitude alone it is a
strictly increasing function of DOP, so `CPR > 1.00 AND DOP < 0.13` is
arithmetically empty. That is not a failure to find ice. It is a measurement of
what this product can decide. No interval is attached to that zero, and the
absence is deliberate: a zero forced by arithmetic has no sampling uncertainty
to quantify (METHODS §11.2, corrected 2026-09-16). What the amplitudes *do*
decide is the split — **40.21 %** of measured pixels excluded from the DOP
condition outright, **59.79 %** undecidable.

**And you do not have to take that on trust.** The map carries a probe: click
anywhere and it reports the measured CPR and DOP at that point, each against its
threshold, and how far below the one-sided 95 % critical value the reading
falls. It is not a
predictor — there is nothing to predict — but it turns the null from something
asserted into something checkable, everywhere in the frame.

## Four findings

**1. The quantity everyone calls CPR, computed from amplitude, is not CPR.**
Monte Carlo at the measured look count: across a true CPR range of 0.30 → 1.50
its median moves **0.00043**, while 3 dB of channel imbalance at unchanged CPR
moves it by a factor of **68**. The circular polarisation ratio lives in the H–V
*phase*, and taking magnitudes discards it. It is a channel-imbalance estimator
carrying CPR's name. (`docs/METHODS.md` §7.9.2)

**2. The equivalent number of looks is 5–6, not the nominal 21** — and forming
21 looks from the single-look complex two different ways gives 4.5 and 9.9, so
*Corrected 2026-09-16:* that gap is a difference in effective azimuth
**resolution**, not in delivered looks — smoothed to a common width the two
arms agree to −1.00 ± 0.57 looks (§7.4b). In the records examined, this is the
first ENL measured on a DFSAR product. (§7.3–7.4)

**3. The look count decides whether a published detection clears its own
significance floor, and it is not reported.**

| feature | CPR | N=6 | N=9 | N=21 | N=38 | N=100 |
|---|---|---|---|---|---|---|
| *95 % critical value* | | *2.69* | *2.22* | *1.67* | *1.46* | *1.26* |
| F2 | 1.95 | no | no | **yes** | yes | yes |
| H3 | 1.30 | no | no | no | no | **yes** |

Read *down* a column. This accuses nobody of being wrong; it says that in the
records examined the critical value is not reported, so a reader cannot tell. (§11.3)

**4. The distributed L2 product ships an incidence-angle raster that fails three
geometric tests.** 80.53 % of its values sit below the spacecraft look angle,
which is impossible on a convex body (`sin θ = ((R+h)/R)·sin η`); its
pixel-to-pixel step is 35–41× the geometric ramp; and it does not track slope, so
it is not a local incidence either. We measured it; no published work reports it.
A Bragg-domain criterion therefore cannot be applied to this product, and ours is
**withheld** rather than estimated. (§12)

## What it actually computes

| | |
|---|---|
| **shadow** | horizon computation over the full 2533² LOLA polar array, 360 azimuths, finite solar disc — validated against the LOLA team's own published PSR mask at **Jaccard 0.714** |
| **terrain** | LOLA `LDEM_80S_20M`, 20 m native, low-passed with a **measured** anti-alias σ and carried onto the 25 m DFSAR grid |
| **radar** | Chandrayaan-2 DFSAR L-band compact-pol, one pass, **15.64 %** of the frame returned amplitude |
| **landing sites** | argmax of a six-criterion search over all **14,943,444** native 25 m pixels, each with per-criterion evidence and an interpolation verdict |
| **traverse** | Dijkstra at a stated 100 m planning resolution, connectivity reported **before** any distance, `UNREACHABLE` an explicit state — all **177 waypoints** drawn on the map, each one hoverable |
| **the probe** | click any point and read the **measured** CPR and DOP there against their thresholds and the one-sided 95 % critical value — a 200 m block mean, labelled as one, with `NO DATA` where the radar returned nothing |
| **incidence** | Putrevu et al. 2023's 20° Bragg criterion is **withheld**: the product's incidence raster has **80.53 %** of its values below the label's own look angle, which is geometrically impossible, and the field cannot be re-derived from a label with no ephemeris (`docs/METHODS.md` §7.12) |

## Repository layout

```
frontend/         Vite + React + Leaflet. The application. `npm run dev` from the root proxies here.
backend/app/      FastAPI request path: /api/mission, the point probe, the PDF report.
backend/scripts/  The offline producers and the verification-gate scripts: ingest, build_analysis,
                  render_layers, detection_statistics, verify_all, check_repo_complete.
paper/            Figure scripts and the figures they regenerate, content-stream-identical to the
                  authors' 4 Oct 2026 manuscript build (docs/REPRODUCIBILITY.md section 17).
docs/             Methods record, provenance, reproducibility manifest, derived artifacts (JSON);
                  docs/handoffs/ holds superseded handoffs, session reports and withdrawn documents.
data/             Raw and derived rasters (~9 GB Chandrayaan-2 DFSAR + LOLA). Gitignored; never committed.
```

`docs/PROVENANCE.md` is generated, not written: `python backend/scripts/emit_provenance.py`
fails the build if any value reaches the UI unmarked. `requirements-analysis.txt` pins the
exact environment the analysis scripts were run with for the manuscript;
`backend/requirements.txt` pins the (older) service runtime (`docs/REPRODUCIBILITY.md` §4).

## Quick start

```bash
npm run dev                                  # frontend, http://localhost:5173
npm run backend                              # FastAPI, http://127.0.0.1:8000
python -u backend/scripts/rebuild_all.py --skip-ingest    # regenerate everything
python -u backend/scripts/verify_all.py      # every gate, mapped to PRD section 6
```

The ~9 GB of Chandrayaan-2 and LOLA rasters are not in this repository: they are
gitignored, none was ever committed (`check_repo_complete.py` reads all of
history), and the repository holds no layer, tile or screenshot that renders a
DFSAR-derived quantity finer than 200 m per pixel; `DATA.md` states the one manuscript
figure that is finer. **Without the rasters the app reports `NOT_INGESTED` and serves no
numbers at all** — not zeros, which would be a measurement claim. There is no demo
or synthetic fallback on any serving path. See *Reproducing* below.

## The report

`GET /api/report/pdf/{crater}` renders the PDF **from the same four artifacts the
mission screen reads** — it computes nothing of its own. Every figure carries a
provenance mark, because a reader holding a printout cannot hover a number to
find out where it came from.

It did not use to. Until this pass the report was generated from the on-demand
backend's legacy payload and printed **five landing sites that Phase 3 had
deleted** — one marked RECOMMENDED — beside a rover traverse of 18.06 km and
3,137.5 Wh for an invented 30 kg vehicle, while the screen reported NO DATA for
the same quantity. `assert_pdf_agrees_with_analysis.py` now reads the rendered
bytes and fails the build on any figure that is not in the artifacts.

## Verification

`verify_all.py` runs thirty-two gates and maps each to a statement in PRD section 6.
One of them loads the **production build** in a browser, in all three backend
states, and fails on a blank page.
Five of them also run on every rebuild, and any non-zero exit stops the build.
Each was verified by making it fail on purpose — including seven cases where the
verification apparatus itself turned out to be wrong (`docs/METHODS.md` §0), one
of them an injection that passed for a reason that was not its own claim.

## Reproducing

`python -u backend/scripts/verify_all.py` ends in three counts: **PASS**, **REQUIRES LOCAL DATA** and **FAIL**, and it
exits non-zero only on FAIL. REQUIRES LOCAL DATA means a file the gate reads does not exist in this checkout. The gate
was not run, verified nothing, and is not a pass. A file that exists but is wrong still FAILS the gate that reads it. The
table at the end names, gate by gate, the file each one needs. On the author's machine every gate passes; in a fresh clone
none fails and the rest list what they need.

**Runs with nothing downloaded** (these read tracked files only): G6, G9, G10, G12, G13, G16, G17, G18, G19, G21, G22,
G23, G25, G29, G30, G33. Four of them (G9, G16, G17, G18) import the service package `backend/app`, so besides
`requirements-analysis.txt` they need `fastapi`, `pydantic`, `reportlab` and `httpx` (on the author's host: fastapi
0.127.0, pydantic 2.12.5, reportlab 5.0.1, httpx 0.28.1); `pip install fastapi pydantic reportlab httpx` in the same
environment is enough. In a fresh clone without them those four gates FAIL on the import, not on the content.

**Needs the Chandrayaan-2 scene from PRADAN:** G2, G3, G4, G20, G27, G31, and, through the rasters derived from it, G1, G5,
G7, G8 and G24.

| what | product identifier | where it goes |
|---|---|---|
| the DFSAR scene the paper analyses | `ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18` (archive identifier `urn:isro:isda:ch2_cho:sar_calibrated`), with its `gri` and `sli` siblings for G27 | `data/pradan/raw/data/calibrated/20200808/` |
| the second scene G20 replicates on | `ch2_sar_ncxl_20200305t114902885_*` | `data/generality/20200305/data/calibrated/20200305/` |
| NASA PDS LOLA (public domain) | `LDEM_80S_20M`, `LDEM_80S_80M`, `LPSR_75S_120M_201608`, `AVGVISIB_75S_120M_201608` | `data/pradan/lola/` (the last two in `illumination/`) |

With those in place, `python -u backend/scripts/rebuild_all.py` writes the derived rasters and sidecars the other gates read
(`data/pradan/native/`, `data/pradan/lola/*.provenance.json`, `horizon_240m.npz`, `data/pradan/dfsar/`).

**Needs something local that is not data:** G15 needs `npm install` in `frontend/` and a Chrome or Edge executable
(`VERIFY_BROWSER=<path>`); G26 needs `data/derived/fig_scene/fig_scene_cache.npz` (written by `f2_complex_product.py`); G32 needs the
manuscript and supplement `.tex`, which are not tracked; G6b needs the author's two local 25 m layer files, and G28 (check C8b)
needs `data/local_layers/`, the author's local copies of the removed renderings, which it compares with their recorded sha256.

**Why the ISRO rasters are not here.** ISRO keeps the copyright in Chandrayaan-2 data. PRADAN gives it free of charge for
non-profit scientific use and says users do not have the right to copy, lease or loan it (the terms are quoted in `DATA.md`).
A public repository would be redistribution, so none of it is here, in any commit. You obtain the scene yourself, from
PRADAN after registering, under those terms. Nothing in this repository fetches it for you.

## Documentation

| document | what it holds |
|---|---|
| [`docs/METHODS.md`](docs/METHODS.md) | **the single methodological record** — 13 sections, every measured figure under a staleness stamp over 40 artifacts |
| [`docs/PROVENANCE.md`](docs/PROVENANCE.md) | generated, not written: every value, its mark, its source raster and the line that produced it |
| [`docs/assumptions.md`](docs/assumptions.md) | the register of what is **not** measured |
| [`docs/testing.md`](docs/testing.md) | the gates, and what each refuses to let ship |
| [`docs/architecture.md`](docs/architecture.md) | what actually runs |
| [`PRD.md`](PRD.md) | the specification. The only active one — `docs/handoffs/` holds the nine superseded handoffs, the V21–V25 session reports, and the text of four withdrawn documents |

The documents that once described the deleted machine-learning component, the deleted
experiment runner and the superseded rover planner are kept, verbatim, under
"Superseded documents" in [`docs/handoffs/README.md`](docs/handoffs/README.md).
## What was removed, and why it matters

A Random Forest reporting `P(ice) = 0.96` was deleted in Phase 0: it was trained
on labels generated by `np.random.uniform`, so it modelled a random number
generator. It was the most impressive-looking number in the application and the
least real. **Deleting it is one of this project's findings.**
