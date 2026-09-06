# PRD — Lunar Ice Intelligence & Traverse Planning System

**Status:** active. This document **supersedes and replaces** `CLAUDE_CODE_HANDOFF.md`,
`_V3`, `_V4`, `_V5`, `_V6`, `_V7`, `_V9_LOLA`, `_V10_DELIVERABLE` and
`CLAUDE_CODE_WORKING_RULES.md`. Those nine files are a conversation log, not a
specification: they contradict each other (V5 §1 was withdrawn in V6 §0; V10 §1c
appears three times with different wording; V10.2 overrides V10 which overrides
V9). **Move them to `docs/handoffs/` and read only this file.**

**Audience:** Claude Code, launched from inside `D:\FYP`. Assume zero memory of
previous sessions. Everything needed is in this file or in the repo.

**Last verified against the working tree:** 2026-09-05.

**Revision v1.8** — **the novelty question is settled.** A 34-search sweep confirmed
three clean nulls: nobody propagates speckle statistics into a per-pixel CPR
significance test, nobody reports ice area with a confidence interval, nobody reports
a false-positive rate for the CPR>1 test. Phase 8 is now DETECTION STATISTICS — the
statistical twin of the algebraic ceiling already proved. Phase 9 (m-chi/m-delta on
compact-pol) is a second confirmed gap; the dual-frequency work is demoted to Phase 10.

**Revision v1.7** — **Phase 8 re-framed after a ten-paper review, and this is the
settled answer on novelty.** The contribution is executing the multi-wavelength radar
comparison that Fa & Cai (2013) and Virkki & Bhiravarasu (2019) explicitly recommend
in their conclusions and that Sinha et al. (2026) and Saran et al. (2026) had the data
for and skipped — on Faustini, the crater those two 2026 papers dispute. Plus a second
free result: S-band polar coverage is >99% (Fa & Cai) while L-band is sparse strips,
so the deepest-penetrating radar has the thinnest coverage. Not a priority claim;
a stated open recommendation, which is why it is safe.

**Revision v1.6** — **Phase 8 rewritten.** v1.5's dual-frequency novelty claim was
checked against the literature and retracted: it is substantially published, on this
crater (npj Space Exploration, 6 May 2026), and PSR accessibility/traverse planning
is well covered too. Phase 8 is now **"Coverage is not evidence"** — an evidential-
status audit of cold traps, which is a question the detection literature does not ask
and which only this project's provenance architecture can answer. Also: the paper's
CPR>1 / DOP<0.13 criterion is now a **citation for config.py's thresholds**, and an
F2-in-footprint check is added to Phase 5a.

**Revision v1.5** — adds **Phase 8, optional: dual-frequency depth-differential
scattering**. The bundle contains simultaneous L-band AND S-band products from the
same pass; their 2:1 penetration-depth ratio is a physically motivated discriminant
for the ice-vs-roughness ambiguity, testable against the LOLA roughness this project
already computes independently. Runs after Phase 7, before 5b. 8-12 h, skippable.

**Revision v1.4** — after the Phase 2 interim report. Two changes, both material:
Gate 2 gains **external validation against LOLA's own published PSR and average-
illumination products** (same PDS node, same label format) plus a citable sanity
anchor, and a **domain-discipline rule** — a full-array PSR figure is a diagnostic,
the UI value is PSR ∩ frame. Phase order changed: **6 now runs before 3** (it
rewrites the terrain the site search consumes) and **6 and 7 run before 5b**, so
the one phase that can fail is not standing between you and a finished product.

**Revision v1.3** — after the Gate 1 report. Phase 1 closed. §2 rule 14 corrected
(`verify_v8_view.mjs`, not the deleted `verify_map.mjs`). **Phase 5 gains a new
subsection proving the amplitude-only ice screen is self-contradictory, not merely
unreachable** — that is the most consequential change in this revision. Two
follow-ups recorded in the Phase 1 banner.

**Revision v1.2** — 1E resolved from repo evidence (see Phase 1E); the deploy-root hold is lifted and three v1.1 instructions there are corrected.

**Revision v1.1** — after the Phase 0 report. Six statements in v1.0 were wrong and
are corrected here; the Phase 0 report found all of them. Changed sections:
§1.1 (one false claim removed), §1.3 (rewritten — `lunarBasemap.ts` is live, not
dead), **new §1.2b** (seven live defects v1.0 missed), Phase 0 (closed), Phase 1
(four items added, execution order stated), Phase 2 (**resolution decision changed
— this is the one that affects the science**), Phase 7.3. Read those before
starting. Everything else stands.

---

## 0 · What this project is, in one paragraph

A mission-planning web app that screens Chandrayaan-2 DFSAR L-band radar over the
Moon's south pole for possible water ice, scores landing sites on real LOLA
topography, and plans a rover traverse. Its value is **one end-to-end, fully
provenance-marked go/no-go pipeline** — not a discovery. **A measured null result
is a valid and defensible outcome.** The thing being graded is whether every
number on screen can be traced to a measurement or is honestly marked as absent.

---

## 1 · Ground truth — verified state of the repo

Read this before believing anything in the old handoffs.

### 1.1 What is REAL and measured today

| Quantity | Source | Evidence |
|---|---|---|
| Radar amplitude LH/LV | `ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_{lh,lv}_d18.tif` — L2-SELENOREF, 2258 × 6618 @ 25.0 × 25.0 m | `data/pradan/raw/data/calibrated/20200808/` |
| Georeferencing | Product's own GeoTIFF GeoKeys, validated against ISRO's 937,296-node geolocation grid | sample rms 0.2846 px, line rms 0.4550 px; corner residual **13.2 mm** (`ldem_frame_25m.provenance.json`) |
| Amplitude mask | `native/valid_native.tif` | valid fraction **0.156395**, area **1460.68 km²** |
| ISRO pointed swath | `sri_ma` product | fraction **0.356313**, area **3327.84 km²**; amplitude/swath = **0.438927** |
| Elevation | **LOLA LDEM_80S_80M V2.0**, 80 m/px native → bilinear to the 25 m DFSAR grid | label range check PASS (residual 0.0, tol 0.5); CRS selftest worst corner error 4.34e-07°; `assert_dem_is_lola()` enforces **bit-identity, tolerance 0.0 m** every run |
| Slope / roughness / hillshade / hazard | Derived from that DEM with per-axis spacing `(25.0, 25.0)` read from GeoKeys | `layers.json.m2_gradient_spacing` |
| CPR / DOP (amplitude-only) | `((√lh − √lv)/(√lh + √lv))²` and `|lh−lv|/(lh+lv)` | native p50 **0.000565**, max **0.053411** |

The whole imagery *pipeline* is genuinely clean: six lossless WebP layers at full
native 6618 × 2258, one global stretch per layer, served from Vercel's CDN.

**Correction (v1.1):** v1.0 wrote that the "map paints with the backend stopped".
That is false and the Phase 0 report proved it. The imagery *can* paint without
the backend, but `MissionControl.tsx:220` renders `{mission && <MissionMap …>}`,
so the component never mounts until `/api/mission/{id}` answers. With the backend
down the verdict card and context bar render from the static analysis and the map
area is empty. The capability was built; the gate was never removed. See §1.2b
item 25 and Phase 1D.

### 1.2 What is NOT real and still reaches a screen

Ranked by how badly it damages the project under questioning.
`L` = renders in the **live** app; `R` = present in the **repo** only (dead code,
but an examiner reading the source will find it).

| # | Defect | Location | L/R |
|---|---|---|---|
| 1 | Random Forest trained on `np.random.uniform` labels, seed 42. Class 1 is *defined* as CPR 1.05–2.5, a range this frame (max 0.053) can never reach. Every P(ice) pixel is an extrapolation from fabricated examples. Feeds modules **E, F and G**. | `module_c_ice.py:33-66`, wired at `mission_service.py:50,363` | **L** |
| 2 | Sensitivity sweep computes nothing. `scale = max(0.2, 1.0-(val-1.0)*0.8)`, `best_landing_site_id="site_1"` constant, `rover_distance_km = 11.2 + val*0.1`, `rover_energy_wh = 145.0 + val*2.5`. Served at `/api/sensitivity/*` with default `base_area_km2=8.75`. **Rendered in Step 9.** | `module_g_volume.py:100-158`, `api_router.py:61-69`, `StepPanel.tsx:55,307-312` | **L** |
| 3 | Five landing sites are hardcoded grid offsets, scored after the fact. No search exists anywhere in `backend/`. 20 % of the "composite score" (`scientific_value`) is a restatement of the distance term already subtracted. | `module_e_landing.py:70-76, 102, 112-113` | **L** |
| 4 | Ice interpretation string is unconditional: *"Detected 0.00 km² … Radar signature consistent with potential ice-bearing volume scattering."* | `module_b_radar.py:120-123` | **L** |
| 5 | `anomaly_classification` pairs the **frame max CPR** with the **frame min DOP** — almost certainly different pixels. | `module_b_radar.py:131` | **L** |
| 6 | Two contradicting values for the same quantity on one screen: verdict card shows `PSR AREA —  NO DATA` and `ROVER — NO DATA`, while StepPanel Steps 2 and 7 print confident km² and km from the backend. | `VerdictCard.tsx` vs `StepPanel.tsx:98-101, 231-234` | **L** |
| 7 | StepPanel renders **no provenance marks at all** and has no null handling — a null renders as `undefined`/`NaN`. | `StepPanel.tsx:39-47` and every `Metric` | **L** |
| 8 | Unmarked physics claims in StepPanel: `"remain below 40 K"` (there is no thermal model), `"RandomForest n=50"`, `"Gating Rule: CPR > 1.0"` as a literal beside the live threshold, `Slope ≤ 12°` next to `cutoff is 20°`. | `StepPanel.tsx:96,104,121,137,164,167,169,171,180` | **L** |
| 9 | `(250.0, 250.0)` placeholder spacing still lets the pipeline publish areas, volumes and traverse km; only a string in `grid_dimensions` says so. | `mission_service.py:245-252` | **L** |
| 10 | `np.zeros_like` as an absent state. Worst case: `pradan_pipeline.py:98-100` sets S1=S2=S3=0, which makes `compute_cpr_from_stokes` return **1.0 everywhere** and DOP **0.0 everywhere** — i.e. a frame that half-passes the ice screen. | `mission_service.py:288`, `pradan_pipeline.py:98-100` | **L** (reachable by any direct caller) |
| 11 | PDF: rover table `.get()` defaults `12.0 km / 0.25 / 140.0 Wh / 8.0`; three fully invented rover rows on the empty case; and the limitations text asserts *"No pseudo-random seed is involved"* — contradicted by item 1 and by its own paragraph 2. | `pdf_generator.py:220-232, 259-261` | **L** |
| 12 | `schemas.py` gives four radar fields plausible **defaults**, one of them ice-positive: `anomaly_classification = "Candidate signature consistent with potential ice"`. | `schemas.py:63-66` | **L** |
| 13 | `CandidateLandingSite`, `RoverRouteResult`, `SensitivityPoint/Result`, `ExperimentResult` carry **no `provenance` and no `data_mode` field**. Fabricated numbers there are structurally impossible to label. | `schemas.py:94-195` | **L** |
| 14 | `experiments_runner.py` — 178 lines, **zero computation**, publicly served at `/api/experiments`, and three of its four experiments are stamped `is_synthetic_evaluation=False`. | whole file, `api_router.py:72-74` | **L** endpoint, no caller |
| 15 | `module_f_rover`: canned `avoidance_explanations` printed for every route regardless of geometry; A\* heuristic in **cells** against costs floored at 0.1 → inadmissible; `max_slope_limit_deg=22.0` contradicts `config.MAX_TRAVERSABLE_SLOPE_DEG=20.0`; cost scalers 15.0 / 5.0 / 8.0 cited nowhere. | `module_f_rover.py:85,199-211,220,294-302` | **L** |
| 16 | Windows absolute paths `d:/FYP/data/pradan` in three files. On Render every crater is NOT_INGESTED — this is the real cause of the deployed DEMO payload, not memory. | `mission_service.py:188-190,228`, `real_data_gate.py:42`, `pradan_pipeline.py:22` | **L** |
| 17 | Illumination is an invented brightness proxy **in two mutually inconsistent forms**: `render_layers` uses `hillshade(alt 30°) · elev_norm^1.2`; `build_analysis` uses `hillshade(alt 1.5°) · elev_norm^1.3`. The picture and the 77.18 % number come from different expressions. `doubly_shadowed` = PSR ∧ lowest elevation quintile — an elevation percentile, not a second shadowing event. | `render_layers.py:768-770`, `build_analysis.py:356-371` | **L** |
| 18 | `ml_likelihood` is in the LAYERS panel but absent from `layers.json`, so it silently falls back to the backend base64 path and is squashed from a square 2048² grid onto the 2.93 : 1 bounds. | `config.ts:128`, `MissionMap.tsx:867-873` | **L** |
| 19 | Cursor lat/lon readout uses a flat `KM_PER_DEG_LAT = 30.37` for both axes — wrong by ~57× in longitude at 88° S — while `sar_geometry` has an inverse validated to 13.2 mm. | `MissionMap.tsx:124,512-514` | **L** |
| 20 | Unknown crater id silently becomes Shackleton. | `mission_service.py:156-157` | **L** |
| 21 | `module_a_psr.py:104` has no `"Low"` branch — confidence can never be reported low; `:90-91` hardcodes the hillshade geometry into provenance as literals instead of recording the arguments. | `module_a_psr.py` | **L** |
| 22 | **Step 11 "Explainability Dossier"** — 14 literal bullets: `Slope below 8°`, `78% solar illumination`, `88.4 / 100`, `22° cliffs`, `0.0% solar radiance`, `P > 0.80`. Every one has a live prop equivalent that is ignored, including `selection_rationale`, which Step 6 renders correctly. | `WorkflowViews.tsx:858-890` | **R** |
| 23 | Tile URL hardcodes `http://127.0.0.1:8000` **and** `faustini`; `||` fallbacks print a specific `product_id` and observation date as provenance for a mission that supplied neither. | `GISMapViewer.tsx:114, 588-591` | **R** |
| 24 | `MODE: REAL` printed unconditionally; loading strings claim "L2 calibrated Stokes vectors" and "Random Forest ice probability inference". | `App.tsx:207, 43-50` | **R** |

### 1.2b Live defects v1.0 missed — found by the Phase 0 report

| # | Defect | Location | Phase |
|---|---|---|---|
| 25 | **The map is gated on the backend.** `{mission && <MissionMap …>}` — with the backend down, or during a 30–50 s Render cold start, the user stares at nothing while every pixel is already on the CDN. This is V5 §3b, specified once and never done. | `MissionControl.tsx:220` | **1D** |
| 26 | `backendChandrayaanTiles()` and `ALL_PROVIDERS` in `lunarBasemap.ts` point at `/tiles/{crater}/{layer}/{z}/{x}/{y}.png` — an endpoint Phase 0 deleted. Dead references to a 404. | `lunarBasemap.ts:82-93, 124-128` | 1C |
| 27 | `STATIC_DEM` describes `/lunar-dem.png` as a `'Real elevation raster'` in `notes` and a `'bundled demo asset'` in `attribution`, in the same object, and names no body, mission or resolution. It textures the Moon on the landing page — the first thing anyone sees. An unverified provenance claim is the exact failure this project exists to avoid. | `lunarBasemap.ts:111-114`, `Moon.tsx:16` | 1C |
| 28 | **A third dead surface: a Next.js scaffold at the repo root** (`app/`, `components/`, `lib/`, `next.config.mjs`, root `package.json`) duplicating `frontend/src`, whose only page redirects to a hardcoded `localhost:5173`. `lib/api.ts` still calls the now-404 `/api/experiments`. In a submitted repo this is worse than clutter — a marker opening the root finds a second, broken app. | repo root | **1E** |
| 29 | `frontend/scripts/verify_map.mjs` is already dead: it asserts `getPane('mc-void')`, a pane v8 deliberately removed, and exits 3 before producing any evidence. A dead verifier in the tree is a trap for every gate that follows. | `verify_map.mjs` | **1F** |
| 30 | `verify_v8_view.mjs` gate `routes_visible` returns a **false FAIL**: it flags `stroke #4fd1e6 w 9.5 o 0.15` as "too faint to see", which is the Science-Aware route's own deliberate glow underlay. Deterministic across runs. A gate that cries wolf is how a real failure gets waved through later. | `verify_v8_view.mjs`, vs `MissionMap.tsx:1043` | **1F** |
| 31 | Six more `d:/FYP` absolutes in `backend/scripts/` — `analyze_cpr_clusters`, `fast_cluster_analysis`, `inspect_channels`, `inspect_geometry`, `inspect_pds4_raw`, `sanity_check_sar`. Dev-only and never imported, but they are scripts a reviewer may run, and they name the author's D: drive. | `backend/scripts/` | 1C |
| 32 | `__pycache__` / `*.pyc` are tracked in git and churn on every run, so every future diff is noisy. | `.gitignore` | 1C |

### 1.3 Phase 0 outcome — the dead-code trace, corrected

v1.0 predicted eight unreachable frontend files. The Phase 0 import trace found
**seven of the eight, plus one v1.0 missed, minus one v1.0 got wrong.** The trace
is the authority; this section records its result.

`main.tsx → Root.tsx → { LandingPage | MissionControl }` — 25 reachable,
8 unreachable. Removed in Phase 0 (`425584e`, parked at `parked/tile-pyramid`
`4a683ea`):

```
App.tsx · App.css · WorkflowViews.tsx · GISMapViewer.tsx
MissionStepper.tsx · HenryAICopilotDrawer.tsx · utils/lunarCRS.ts
components/Common/Tooltip.tsx          <- v1.0 missed this; only importer was WorkflowViews
```

**`landing/services/lunarBasemap.ts` is LIVE and was correctly kept.**
`landing/scene/Moon.tsx:16` imports `DEFAULT_SURFACE_PROVIDER` from it. v1.0
listed it as having no importer; that was a tooling error on my side, not a
judgement — the file had not finished landing when the import graph was read, and
the result was trusted without a retry. Deleting it as v1.0 instructed would have
broken the landing page. **This is why §2 rule 17(d) exists, and why Phase 0.2
required the trace to be proved rather than assumed.** Two live defects inside
that file are now §1.2b items 26 and 27.

Also confirmed by Phase 0: `frontend/src` went 33 → 25 source files;
`/api/experiments` and `/tiles/...` both 404; 510 tracked tile PNGs (1,567 files,
44 MB) removed and recoverable; `tsc` exit 0, `pytest` 17 passed, `vite build`
exit 0.

**One thing the report surfaced that is not a code defect and matters more than
any of them:** every piece of real work in this project — `sar_geometry.py`,
`build_analysis.py`, `render_layers.py`, `analysis.ts`, `public/layers/` — was
**uncommitted** until `4a683ea`. It is baselined now. Push both branches to a
remote before Phase 1 touches anything.

### 1.3.1 Historical note — why v1.0 called this "the finding that changes the plan"

`main.tsx` → `Root.tsx` → `LandingPage` (default route) or `MissionControl`
(`#mission`). **`App.tsx` is imported by nothing.** Its own docstring in
`Root.tsx` still claims `#mission → App.tsx`; the code below it imports
`MissionControl`. Verified by import graph.

Therefore these files are **in the repo but never rendered**:

```
frontend/src/App.tsx                                16.6 KB
frontend/src/App.css
frontend/src/components/Views/WorkflowViews.tsx     49.1 KB   <- items 22
frontend/src/components/Map/GISMapViewer.tsx        31.4 KB   <- item 23, only /tiles/ consumer
frontend/src/components/Workflow/MissionStepper.tsx  7.5 KB
frontend/src/components/Copilot/HenryAICopilotDrawer.tsx 10.1 KB
frontend/src/landing/services/lunarBasemap.ts        5.9 KB   (no importer)
frontend/src/utils/lunarCRS.ts                       1.8 KB   (killed in v2, never rewired)
```

Two consequences that shrink the remaining work substantially:

1. **The tile pyramid has zero live consumers.** V10 Step 6 asked for rewiring two
   of them before deleting. There is nothing to rewire — `backend/tiles/faustini`
   (510 PNGs rendered from the deleted synthetic DEM) can simply go.
2. **~122 KB of the most quotable fabrication is deletable, not fixable.** Item 22
   does not need rewriting to read from props; the file it lives in needs to leave
   the tree.

**Verify this yourself before deleting** — run the import trace in Phase 0 and
report it. Do not delete on the strength of this document alone.

---

## 2 · Non-negotiable rules

These never relax. They are the working rules from the old
`CLAUDE_CODE_WORKING_RULES.md`, plus what the last ten sessions established.

**Data honesty**

1. **Never invent a number.** If it cannot be computed from real data, emit an
   explicit absent state and let the UI render it. `np.zeros_like` is not an
   absent state. A plausible placeholder in the slot where a measurement belongs
   is the worst outcome available.
2. **Every number reaching the UI carries a provenance mark**: `MEASURED`,
   `DERIVED`, `MODELLED`, or `NO DATA`. A number with no defensible mark does not
   ship.
3. **A provenance field never gets a default.** Same treatment as `spacing_m`:
   required, keyword-only, no default. A caller who forgets must fail, not
   inherit the strongest possible claim.
4. **Do not retune a threshold to make a number look better.** If a threshold is
   mis-set, print the distribution and say so.
5. A **measured zero is a result** and must be presented as one. A zero produced
   by an unfinished code path is not, and the report must distinguish them.
5a. **A rendered layer's badge, legend and caption are driven by `layers.json`,
   written by the same script that renders the pixels. A layer must not be able
   to wear a badge describing a different computation.** Same class as the
   provenance marks, and it exists for the same reason: the illumination layer
   became a real horizon computation over measured LOLA topography while its
   legend went on reading "MODEL OUTPUT", because the badge lived in
   hand-maintained frontend config that nothing forced to agree with the
   renderer. A caption is a claim about provenance and gets the same discipline
   as a number.
5b. **A criterion that admits everything is not a criterion.** Any filter, gate
   or screening term that passes more than 99 % or less than 1 % of its domain
   must be reported as NON-DISCRIMINATING at the point of use, with the fraction
   printed. Reporting "six criteria" when one of them selects 100 % of the frame
   overstates how constrained the answer is, in exactly the way a plausible
   placeholder overstates a measurement. Such a criterion may be kept when it is
   a real mission constraint that a different frame would bind on -- but it must
   never be counted as evidence of selectivity.
5c. **A caption asserting ABSENCE over a real measurement is the same defect
   class as a plausible placeholder standing in for one.** Both are a caption
   that stopped tracking its own computation; they differ only in direction, and
   **understating is not safer than overstating.** Step 2's panel rendered
   `<StepUnavailable title="Shadow and PSR mapping">` above four real MEASURED
   and DERIVED values, under a heading reading "This build does not have one
   yet", for as long as it took anyone to look — all three written before Phase 2
   and none updated when the horizon computation shipped. When a phase lands,
   its panel copy, its step gate and its notes are part of the deliverable, not
   commentary on it.

**Engineering**

6. No `rasterio`, no GDAL, no `gdalinfo`. Local Python has numpy, cv2, PIL, scipy,
   scikit-learn, tifffile. **Nothing new in `requirements.txt`** — Render cannot
   build scipy from source.
7. Never `imread` a multi-gigabyte raster whole. `np.memmap` and windowed reads.
8. Parse PDS labels as plain text and **parse units out of the angle brackets**.
   `MAP_SCALE = 0.020 <KM/PIXEL>` vs `80 <m/pix>` is a 1000× trap that produces
   plausible floats. Raise when the unit is absent.
9. Return every touched file **complete**, not as a diff or a snippet. Exception:
   a brand-new file over ~800 lines with no prior version may be reported by its
   changed parts plus any function a reviewer must check.
10. `MissionMapHandle` stays byte-identical: `zoomIn` / `zoomOut` / `reset`.
    Prop changes are additive only unless a phase says otherwise.
11. **No destructive git operation or file delete without explicit confirmation
    in the session.**

**Process**

12. **Build the whole phase before opening a browser.** The only gate before
    verification is `npx tsc --noEmit -p tsconfig.app.json`, exit 0.
13. **Two browser sessions per phase, maximum.** Pass A = the "before" capture in
    one go, only if the phase asks for it. Pass B = full verification after every
    file is written. Pass C only if B fails the gate — then fix **every** finding
    in one batch and re-verify once. The change→look→change→look loop is what
    eats the time.
14. Verification is a **script**, not a poking session:
    `node frontend/scripts/verify_v8_view.mjs` (v1.3: v1.0–v1.2 named
    `verify_map.mjs`, which Phase 1F deleted as already-dead). Two facts that make a single pass
    survive, both already measured in this project: `document.hidden === true`
    under automation so `requestAnimationFrame` never fires and every animated
    Leaflet move silently stalls — use `setZoom(z, {animate:false})` and
    `setView(c, z, {animate:false})`, never `flyTo`/`flyToBounds`; and wait on the
    image `load` event, never a timer, or you will screenshot the 640 px preview.
15. **Prefer numbers over pictures.** Percentile tables, histograms, counts,
    residuals, byte sizes, request counts. Screenshots only for what the gate asks.
16. **If a number and a screenshot disagree, say so in the report** instead of
    picking one. That contradiction going unflagged is how a fabricated verdict
    shipped once already.
17. **One report at the end of each phase**, not a running commentary:
    (a) files touched with line counts, (b) typecheck result, (c) the evidence the
    gate asked for in the order it asked, (d) **anything that disagreed with this
    PRD, with the measurement that shows it**, (e) what is still open and what you
    chose not to touch. Section (d) is the most valuable part — this document has
    been wrong before and saying so has been right every time.

---

## 3 · The one architectural decision

**There must be exactly one source of truth for every number on screen.**

Today there are two, and they contradict each other on the same screen:

- `frontend/public/analysis/faustini.json` — precomputed offline by
  `backend/scripts/build_analysis.py`, native-grid, provenance-marked, honest.
  Feeds the verdict card and the context bar.
- `GET /api/mission/{crater}` — recomputes at request time on a **100 × 100**
  bilinear resample of the padded frame, unmarked. Feeds all twelve StepPanel
  steps.

The resample alone destroys the statistics — measured on this frame:

| quantity | native, masked | 100² bilinear | error |
|---|---|---|---|
| CPR mean | 0.001312 | 0.000238 | 5.5× low |
| CPR max | 0.053411 | 0.043846 | 18 % low |
| DOP mean | 0.057053 | 0.009463 | 6.0× low |
| DOP p50 | 0.047532 | 0.000000 | destroyed |

**Decision: `build_analysis.py` becomes the single producer.** Extend the analysis
JSON to carry everything the twelve steps need, and rewrite `StepPanel.tsx` to
read it through `analysis.ts` with the same `AnalysisValue` / provenance-mark
discipline the verdict card already uses.

The backend keeps only what genuinely needs on-demand computation:

- `GET /api/craters` — catalogue.
- `GET /api/sensitivity/{param}` — **only after Phase 1 makes it real.**
- `GET /api/report/pdf/{crater}` — refuses unless the run is REAL.
- `GET /api/health`, `GET /api/ingest/status` — diagnostics.

Everything else on the mission screen is static, on the CDN, and cannot be
overwritten by a cold-start fallback.

**Regenerating the analysis and the layers must be one command**, so the imagery
and the numbers can never again describe different data:

```
python backend/scripts/rebuild_all.py     # new: runs ingest → sar pipeline → build_analysis → render_layers
```

---

## 4 · Phases

Each phase is self-contained, ends at a gate, and is one Claude Code session
unless stated. **Do not start a phase before its gate predecessor passes.**

---

### PHASE 0 — Cut the clutter — ✅ **COMPLETE** (`425584e`, parked `4a683ea`)

Gate 0 passed: `tsc` exit 0, `pytest` 17 passed, `vite build` exit 0, import trace
delivered, 42 files changed / +182 / −3,642, `frontend/src` 33 → 25 files.
Deviations from spec, all correct: `lunarBasemap.ts` kept (live), `Tooltip.tsx`
additionally removed (dead). **LOLA 20 m download continues in the background —
nothing before Phase 6 needs it (see Phase 2).** Retained below for the record.

Nothing here changes a number. It removes ~122 KB of unreachable fabricated code
and nine contradictory specification files, so every later phase is read against
one document and one live code path.

**0.1** Move the nine superseded handoffs into `docs/handoffs/` (git mv, not
delete). Keep this PRD at the repo root.

**0.2** Prove the dead-code claim in §1.3 before acting on it. Print, for each
file listed there, every importer found by a full-tree grep. Report the table.
If any file has a live importer, **stop and say which** — do not delete it.

**0.3** With confirmation, remove the dead shell in **one commit**, message body
carrying the import trace:

```
git rm frontend/src/App.tsx frontend/src/App.css \
       frontend/src/components/Views/WorkflowViews.tsx \
       frontend/src/components/Map/GISMapViewer.tsx \
       frontend/src/components/Workflow/MissionStepper.tsx \
       frontend/src/components/Copilot/HenryAICopilotDrawer.tsx \
       frontend/src/landing/services/lunarBasemap.ts \
       frontend/src/utils/lunarCRS.ts
```

Fix the stale docstring in `Root.tsx` that still says `#mission → App.tsx`.

**0.4** The tile pyramid now has no consumer. Park the authored work first so
nothing is lost, then remove:

```
git checkout -b parked/tile-pyramid
# commit the uncommitted work in backend/scripts/generate_tiles.py and compare_tiles_vs_single.py
git checkout <working-branch>
git rm -r backend/tiles/faustini backend/scripts/generate_tiles.py backend/scripts/compare_tiles_vs_single.py
```

Report the branch name, the SHA, and the file count actually removed. Keep
`docs/map_before_*.png` / `map_after_*.png` — they are viva evidence.

**0.5** Delete `backend/app/modules/experiments_runner.py` and the
`GET /api/experiments` route. It has no caller (`fetchExperiments` in `api.ts` is
unreferenced), computes nothing, and marks three of four fabricated experiments
`is_synthetic_evaluation=False`. Also delete `fetchExperiments`,
`ExperimentResult` and `AblationStepResult` from the frontend. A **real** ablation
returns in Phase 4.

**0.6** Replace the three `d:/FYP/...` Windows absolutes with paths derived from
`Path(__file__).resolve().parents[N]`, in `mission_service.py`,
`real_data_gate.py`, `pradan_pipeline.py`.

**0.7** Start the LOLA 20 m download **now**, in the background, so Phase 6 is not
waiting on it. `LDEM_80S_20M.IMG` + `.LBL` (~1.9 GB) from **PDS Geosciences**,
`https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/`,
into `data/pradan/lola/`. *(Amended after Phase 2: `imbrium.mit.edu` is down
entirely — not one path but the host — so PDS Geosciences is the documented
source for every LOLA product from here on. Identical products, same release.)* Take
the `.IMG`, **not** the `.JP2` — the JP2s are lossy and no reader exists in the
allowed dependency set. `LDEM_875S_20M` does **not** cover this frame (it reaches
84.83° S at one corner); 80S does, with 147 km to spare.

**Gate 0** — `npx tsc --noEmit -p tsconfig.app.json` exit 0; `pytest` green;
`npm run build` succeeds; `#mission` and the landing page both render; the import
trace table is in the report; the parked branch SHA is reported.

---

### PHASE 1 — One truth surface, zero fabricated numbers (2–3 sessions)

This is the phase that decides whether the project survives questioning. It has
three parts; do them in order.

> **✅ PHASE 1 COMPLETE** (`0750451` → `29bf48c` → `4e80bca` → `ebf75c7`, pushed).
> Gate 1 passed: 54 values · MEASURED 37 · DERIVED 3 · **MODELLED 0** · UNAVAILABLE 14 ·
> unmarked 0 · unscheduled 0, generated by `emit_provenance.py` into
> `docs/PROVENANCE.md`, with all four assertions proved to fail by injection.
> `tsc` 0, `pytest` 17, root build 0, `verify_v8_view.mjs` 8/8 (was 7/8),
> `rebuild_all.py` byte-deterministic. 1D verified with the backend killed.
> **The zero MODELLED count is the machine-checkable proof that the random-label
> Random Forest no longer reaches the UI** — quote that figure, not the 37.
>
> **Two follow-ups carried forward, both cheap:**
> (i) Add a **unit/range assertion** to `emit_provenance.py`: any value whose unit
> is `%` must lie in [0, 100], any `fraction` in [0, 1], any `km²` ≤ the frame
> area. The `<Figure suffix=" %">` bug that printed `0.897 %` for an 89.7 %
> traversable surface was measured, marked and traced *correctly* and was still
> wrong on screen — provenance discipline does not catch a unit error, and only
> the browser pass did. **Units and scaling are part of a value's contract.**
> (ii) Add the Phase 5 ceiling assertion described in that phase.
>
> Retained below for the record.

#### 1A · Make the producer complete

Extend `build_analysis.py` so `frontend/public/analysis/faustini.json` carries,
for every one of the twelve steps, an `AnalysisValue` per number: `{value, unit,
provenance, reason?, threshold?, comparison?, source?}`. Nothing is added to the
JSON that is not either computed from a raster or explicitly absent.

Specifically add:

- **Step 2 (PSR):** absent for now — `psr_area_km2`, `doubly_shadowed_area_km2`,
  `mean_illumination_fraction` all `UNAVAILABLE` with the reason already written
  in `ILLUM_MODEL`. They become real in Phase 2. **Do not carry the 77.18 %
  proxy forward as if it were a shadow fraction.**
- **Step 3 (radar):** masked native statistics only. `screening_pass_fraction`
  over the amplitude mask, not the frame.
- **Step 4 (ice):** the criteria screen, not a probability. Five named criteria,
  each with measured value, threshold, comparison and pass/fail.
- **Step 5 (terrain):** slope, roughness, hazard percentiles **and** the weights
  actually used, read from `config.py`, not restated in prose.
- **Step 8 (volume):** three tiers, each `DERIVED`, each carrying its assumed
  depth and fraction **as data**, so the UI never hardcodes "2m / 5%".
- **Step 9 (sensitivity):** see 1B.
- Steps 6, 7, 10 remain `UNAVAILABLE` until Phases 3 and 4.

#### 1B · Make the sensitivity studio real or remove it

The sweep over CPR and DOP thresholds is **trivially computable** from the
precomputed native arrays — re-threshold, count, multiply by cell area — and
completely fabricated today. Compute it offline in `build_analysis.py` over a
stated grid of thresholds and ship it in the JSON:

```
for th in cpr_grid:
    n = ((cpr > th) & (dop < dop_th) & valid).sum()
    area_km2 = n * cell_area_km2          # MEASURED
    volume_m3 = area_km2 * 1e6 * depth * fraction   # DERIVED
```

Drop the `rover_distance_km` and `rover_energy_wh` columns entirely until Phase 4
makes replanning possible; drop `best_landing_site_id` until Phase 3. **Delete
`run_sensitivity_sweep` from `module_g_volume.py`.** If the endpoint is kept, it
serves the precomputed table, not an invented curve.

#### 1C · Purge the live surfaces

Backend:

- `module_b_radar.py:120-123` — make the interpretation conditional on
  `anomalous_cells > 0`. At zero it must read as a measured null result.
- `module_b_radar.py:131` — stop pairing frame-max CPR with frame-min DOP. Either
  classify per pixel and report the count, or remove `anomaly_classification`.
- `module_b_radar.py:15-22` — delete `compute_cpr_from_sigma`, called from nowhere.
- `module_c_ice.py` — **unwire it entirely.** Remove the import and call from
  `mission_service.py:50,363`; replace `ml_likelihood` and
  `scientific_candidate_mask` in the E/F/G call sites with the **criteria-screen
  mask** (`cpr > th & dop < th & valid`), which is measured. Leave the file on
  disk with a header stating why it is unwired: it is fitted to
  `np.random.uniform` labels whose class 1 lies entirely outside this product's
  achievable CPR range, so every prediction is an extrapolation from fabricated
  examples. **Do not retrain it on better synthetic labels — better synthetic
  labels are still synthetic.**
- `module_e_landing.py:102` — `scientific_value` currently contains only
  distance. Until Phase 3, rename it to `distance_proximity_index` and remove it
  from the composite score, so 20 % of the ranking stops double-counting the
  distance term already subtracted at `:113`.
- `module_f_rover.py:294-302` — delete the canned `avoidance_explanations`.
  Replace with statements derived from the path, or an empty list.
- `module_f_rover.py:85` — remove the `max_slope_limit_deg=22.0` default; read
  `settings.MAX_TRAVERSABLE_SLOPE_DEG`. Delete the two `"> 22°"` literals at `:237`.
- `module_f_rover.py:220` — either scale the A\* heuristic into cost units or
  set `algorithm="Dijkstra"` as the only supported mode and say so. An
  inadmissible heuristic labelled A\* is a claim of optimality that is false.
- `mission_service.py:245` — the `(250.0, 250.0)` fallback must become **fatal**.
  If spacing cannot be resolved, return `NOT_INGESTED`. It must not be possible to
  publish a km² off a placeholder.
- `mission_service.py:288` and `pradan_pipeline.py:98-100` — remove
  `np.zeros_like` as an absent state. A missing Stokes component must raise, not
  silently produce CPR = 1.0 everywhere.
- `mission_service.py:156-157` — an unknown crater id must 404, not become
  Shackleton.
- `mission_service.py:206` — `real_radar_available = True` is hardcoded, making
  the Stokes branch at `:269-272` unreachable. Derive it, or delete the dead
  branch until Phase 5 wires it properly.
- `module_a_psr.py:90-91` — record the arguments actually passed, not literals.
  `:104` — add the missing `"Low"` branch, or remove `confidence_level`.
- `schemas.py:63-66` — delete all four defaults, especially the ice-positive
  `anomaly_classification`. Make them required.
- `schemas.py:94-195` — add `provenance: ProvenanceMetadata` and `data_mode` to
  `CandidateLandingSite`, `RoverRouteResult` and the sensitivity types. Without
  this, the fabricated numbers in E and F are structurally unlabelable.
- `pdf_generator.py:220-232` — remove every `.get()` default and the three
  hardcoded rover rows; render an explicit `NO DATA` row like the landing table
  already does at `:196-200`. `:150` and `:256` — read the assumptions from the
  payload. `:259-261` — delete the false "no pseudo-random seed is involved"
  claim.

Frontend:

- **`StepPanel.tsx` — rewrite.** Every figure reads an `AnalysisValue` from the
  static analysis, renders through the existing `Pv`/`showValue` helpers, shows
  `—` plus the reason when absent, and carries a provenance chip. Delete every
  hardcoded threshold and physics claim listed as item 8 in §1.2 — a threshold is
  read from `analysis.thresholds`, a weight from `analysis.hazard_model`.
- `MissionControl.tsx:85` — remove the `Peak P(ice)` cell. Put the Phase 5a
  measured CPR-anomaly percentile there instead, marked `MEASURED` and labelled
  `TOP 1% CPR WITHIN THIS SWATH — RANKING, NOT A DETECTION`.
- `config.ts:128` — remove the `ml_likelihood` layer. It has no manifest entry, so
  it is the one layer whose pixels come from the DEMO-capable backend, drawn
  squashed onto the wrong aspect beside five measured rasters.
- `config.ts:102,109,116,131,138,145` — these layer descriptions duplicate
  constants that `layers.json` already carries (`valid_fraction`,
  `ribbon_thickness_km`, `vmin`/`vmax`). Interpolate from the manifest, as
  `MissionMap.tsx:710-716` already does correctly, so they cannot drift.
- `MissionMap.tsx:124,512-514` — replace `KM_PER_DEG_LAT = 30.37` with the
  inverse projection from `app/ingestion/sar_geometry` (validated to 13.2 mm).
  Export it to the frontend as a small closed-form function, or precompute a
  coarse lat/lon lookup grid into `layers.json`. Then the `≈` in the readout can
  go. If you keep an approximation, **state its residual in the report** rather
  than hedging in the UI.
- `VerdictCard.tsx:45-51` — evidence rows 3 and 4 print `0.00 vs > 0.00`.
  Suppress a threshold clause when the threshold is 0.
- `lunarBasemap.ts:82-93, 124-128` — delete `backendChandrayaanTiles()` and
  `ALL_PROVIDERS`. They point at the tile endpoint Phase 0 deleted. Keep
  `STATIC_DEM` and `DEFAULT_SURFACE_PROVIDER`; `Moon.tsx:16` imports them.
- `lunarBasemap.ts:111-114` — `STATIC_DEM` calls `/lunar-dem.png` a *"Real
  elevation raster"* in one field and a *"bundled demo asset"* in the next, and
  names no body, mission or resolution. **Establish its provenance or withdraw
  the claim.** If it cannot be traced, relabel it as a decorative texture with no
  provenance claim. Do not guess a source. (A later, optional improvement: texture
  the landing-page Moon from the real LOLA product you already have — out of scope
  for Phase 1, worth noting in `docs/`.)

Housekeeping, same phase:

- Fix the six remaining `d:/FYP` absolutes in `backend/scripts/` (§1.2b item 31)
  with `Path(__file__).resolve().parents[N]`. Phase 1 already edits
  `build_analysis.py`; do the other five in the same pass.
- Add `__pycache__/` and `*.pyc` to `.gitignore` and `git rm -r --cached` them
  (§1.2b item 32), so every later diff is readable.

#### 1D · Un-gate the map from the backend

`MissionControl.tsx:220` is `{mission && <MissionMap …>}`. Remove the gate. This
is V5 §3b, approved once and never executed, and it is the highest visible payoff
in the phase: the imagery is already on the CDN and returns in tens of
milliseconds with the backend dead.

Do it as an **additive widening, not a restructure**:

- `mission` becomes optional/nullable in `Props`. Every other prop keeps its exact
  name and type. **`MissionMapHandle` stays byte-identical.**
- With no `mission`: render the raster layers, panes, graticule, scale bar,
  footprint rings and coordinate readout. Skip only what genuinely needs the
  analysis — landing-site markers, rover routes, the target marker.
- Show an honest status chip while analysis is in flight:
  `TERRAIN LOADED · ANALYSIS PENDING`. **Do not fabricate placeholder markers.**
- Keep the failure banner for the analysis panels. The map painting and the
  analysis failing are different states and must look different.

After 1A, the map's vectors should read the **static analysis**, not the backend
— so the correct final gate is `analysis && <vectors>` inside an unconditionally
mounted map, and the backend stops being on the map's critical path at all.

#### 1E · Delete the Next.js root scaffold — **prove the deploy root first**

§1.2b item 28. A second, non-functional app at the repo root that redirects to a
hardcoded `localhost:5173` is the first thing a marker sees.

**Resolved (v1.2) — the scaffold is not deployable, so it cannot be what deploys.**
The Phase 1E hold is lifted. Four pieces of repo evidence, any one of which is
close to decisive and which together leave no other reading:

1. **`next.config.mjs` redirects `/` → `http://localhost:5173/`.** A deployed Next
   app at the repo root would send every visitor to *their own* localhost and
   render nothing. There is no working production site behind that config.
2. **Root `package.json` `"build": "npm run build --prefix frontend"`** emits
   `frontend/dist`, while a repo-root Next preset looks for `.next`. That pairing
   cannot produce a site. Note also that `next dev` is deliberately a *separate*,
   differently-named script (`"dev:next": "next dev -p 3000"`) — the primary
   `dev` / `build` / `preview` all proxy to `frontend`.
3. **The scaffold is v0.dev boilerplate.** `.gitignore`'s first block is literally
   `# v0 sandbox internal files` (`__v0_runtime_loader.js`, `.v0-trash/`), and the
   root deps are the v0/shadcn stack (`shadcn`, `@base-ui/react`,
   `class-variance-authority`, `tw-animate-css`, `components.json`). The project is
   still named `"my-project"` — the untouched generator default.
4. **No deployment configuration exists**: no `vercel.json`, no `.vercel/`
   (which is gitignored, so a CLI-linked project would leave one locally), and no
   deployed URL anywhere in the repo or README.

**Both surviving cases lead to the same action.** If Vercel's Root Directory is
`frontend`, Vercel never reads the repo root at all and the scaffold is inert. If
there is no Vercel project yet, nothing is load-bearing either. The only case that
would have justified stopping — repo root builds and serves the Next app — is
ruled out by (1) and (2). **Proceed with the removal.**

Same treatment as Phase 0 — park it on a branch, then remove `app/`,
`components/`, `lib/`, `next.config.mjs`, `next-env.d.ts`, root
`postcss.config.mjs`, `components.json`, root `tsconfig.json`, `AGENTS.md`
(generated by `next dev`), `pnpm-workspace.yaml` (it exists only to pin
`@next/*` release ages) and the untracked `.next/` directory. Report the file
count.

**Three amendments to v1.1, which got one instruction wrong:**

- **KEEP the root `package.json`.** v1.1 said to remove it; that was wrong. It
  carries five scripts you actually use — `dev`, `build`, `preview`, `backend`,
  `test` — and README §2 documents running `npm run dev` from the root. **Strip
  only** the Next/shadcn/v0 dependencies and the `dev:next` script; keep the five
  proxy scripts and `react`/`react-dom` if anything at root still needs them
  (nothing should, after the removal — check).
- **Keep `frontend/postcss.config.mjs` and `frontend/tsconfig*.json`.** Only the
  root copies go. Confirm `npm run build` from the root still succeeds afterwards,
  since it now proxies into `frontend` with no root config beside it.
- **Verify after, don't assume.** If a Vercel project does exist, trigger a
  redeploy once the removal is committed and confirm the live site loads and
  `/layers/layers.json` still resolves, before closing Gate 1. The park branch
  makes it reversible either way. If no Vercel project exists, say so in the
  report — that is itself worth knowing before submission.

#### 1F · Repair the verifier — Gate 1 needs a working instrument

- **Delete `frontend/scripts/verify_map.mjs`** (§1.2b item 29). It asserts a pane
  v8 removed and exits 3 before producing evidence. This moves here from Phase 7.3
  because every gate from now on depends on the verifier being trustworthy.
- **Fix the `routes_visible` false FAIL** in `verify_v8_view.mjs` (§1.2b item 30).
  The check is flagging the Science-Aware glow underlay
  (`MissionMap.tsx:1043`, `weight: s.weight + 6, opacity: 0.15`) as an invisible
  route. Evaluate the route stroke, not every polyline in the pane — exclude the
  underlay by class, or test the maximum opacity among strokes sharing a path.
  **Do not waive the gate and do not lower its threshold.** A gate that cries wolf
  is how a real failure gets waved through three phases from now.
- Extend it with the Gate 1 assertion: `imageOverlays.length === expectedActiveLayers`,
  printing every `_url`.

#### Execution order within Phase 1

One backend pass, one frontend pass, one tooling pass — not twelve small ones:

**1A → 1B** (both are `build_analysis.py`) **→ 1C backend** → **1C frontend +
1D together** (both consume the new JSON; doing 1D first would touch
`MissionMap`/`MissionControl` twice) **→ 1E → 1F.** One report at Gate 1.

**Gate 1** — this is the hard one. Produce a single table with one row per number
rendered on `#mission`, listing: the label, the value shown, the provenance mark,
and the file:line of the computation that produced it. **Every row must resolve to
a raster read or an explicit absent state.** Any row that cannot is a defect, not
a caveat. Plus: typecheck exit 0, `pytest` green, and one browser pass at fixed
zoom confirming the verdict card, the five evidence rows and every StepPanel
figure reconcile line-by-line against the printed statistics.

---

### PHASE 2 — Real illumination and PSR (1–2 sessions)

The single biggest unlock: it fills `PSR AREA`, `cold-trap overlap`,
`doubly-shadowed core` and `thermal stability`, and it is the physical reason to
look for ice at all.

Delete both invented illumination expressions (item 17). Compute a horizon.

**Method.** For each pixel, the horizon elevation angle in azimuth `az` is
`max over r of atan((h(p + r·u_az) − h(p)) / r)`. A pixel is lit for sun state
`(az, el)` when `el > horizon(az)`. At the lunar south pole the Sun sweeps all
360° of azimuth over a lunar day and its elevation stays within about ±1.54°.
Sample `az` at 1° and `el` from 0° to 1.54°. Output `illumination_fraction ∈ [0,1]`
per pixel and `psr_mask = (fraction == 0)`.

**Three things that decide whether this is science or decoration:**

1. **Compute the horizon on the FULL `LDEM_80S_80M` array — 7600 × 7600 — then
   crop.** At the pole the horizon is set by crater rims tens of kilometres
   outside the 165 × 56 km frame. A horizon computed only inside the frame
   invents sunlight that real terrain blocks.

   **Resolution decision (v1.1), and it is a real design change, not a note.**
   The Phase 0 report established that `LDEM_80S_20M` is **30400 × 30400 =
   924 M pixels** (label validated: `SAMPLE_BITS 16`, `MAP_SCALE 20 <m/pix>`,
   1,848,320,000 bytes matching `Content-Length` exactly), not the 57.8 M v1.0
   specced against. At float32 that is a **3.7 GB** array; rotating it 360 times
   is not feasible on this machine, and it is not necessary either.

   **The horizon runs on the 80 m product. The 20 m product is for terrain
   rendering in Phase 6 and nothing else.** The horizon at a point is set by
   distant rim crests, so its useful angular resolution is coarse — a multi-scale
   horizon (coarse far field, finer near field) is standard practice in lunar
   illumination work, not a compromise. At 7600² float32 = 231 MB, 360 azimuths
   of rotate + running-max + rotate-back is minutes, not hours.

   Optionally refine the near field (within a few km) at 20 m once it lands, and
   **report both scales**. Do not silently mix them.

   **Consequence for scheduling: Phase 2 is NOT blocked on the download.** It can
   start the moment Gate 1 passes. Phase 6's ingest reads only the frame's
   projected bbox as a windowed `np.memmap` (~8270 × 2820 at 20 m), so the file
   being 16× larger costs Phase 6 nothing either.
2. **Rotate-and-scan, not per-pixel ray marching.** For each azimuth, rotate with
   `scipy.ndimage.rotate(order=1)`, take a running maximum of `(h−h0)/r` along
   rows, rotate back. O(N) per azimuth instead of O(N · ray length). Decimate
   until it completes in reasonable time and **report the resolution you actually
   used.** A 240 m far-field horizon with an 80 m near field is a legitimate
   multi-scale technique; a silently downsampled one is not.
3. **Label the resolution.** A shadow mask derived from 80 m posts must not be
   presented at 25 m. Emit `native_metres_per_pixel` and the decimation factor
   alongside the mask.

`doubly-shadowed core` means never directly lit **and** receiving no scattered
light from lit terrain. Approximate with a sky-view factor restricted to lit
horizon. If it cannot be computed defensibly, emit the absent state and say which
term was missing. **Do not silently reuse the single-shadow mask for both** — the
current code uses the lowest elevation quintile, which is not a shadowing event.

**Thermal stability — DERIVED, no download.** No thermal product is on disk. A
pixel that is never directly lit sits below the ~110 K water-ice stability limit,
so emit `thermal_stability: DERIVED` carrying the assumed threshold and the words
*"inferred from illumination, not from measured temperature"* through to the UI.
If a Diviner product ever arrives it becomes MEASURED and nothing else changes.

Then re-render the `illumination` layer from the **same** array the statistics
use — one expression, one sun, one number. Update its `layers.json` provenance
string. Note the string is regex-tested by `MissionMap.tsx:385`
(`/synthetic|placeholder|analytic|unknown|unavailable/i`) — the new string must
contain none of those six words or the UI will keep captioning it a placeholder.

#### External validation against LOLA's own published PSR product (v1.4 — added)

This was not in v1.0–v1.3 and it is now the strongest single piece of evidence
available to this project. **The LOLA team publishes its own permanently-shadowed
masks and average-illumination rasters, on the same PDS node the DEM came from,
in the same `.IMG` + `.LBL` format `ingest_lola_polar_dem.py` already parses.**

`https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/extras/illumination/img/`

*(Was `imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION/`. That host is down entirely
and PDS Geosciences is the documented source path for LOLA products from now
on; this is where Phase 2 actually fetched LPSR and AVGVISIB from.)*

| product | m/px | coverage | use |
|---|---|---|---|
| `LPSR_75S_120M_201608` | 120 | 75°S → pole | **binary PSR mask — covers the whole frame (outer corner −84.833°)** |
| `AVGVISIB_75S_120M_201608` | 120 | 75°S → pole | average **solar** illumination — validates the *continuous* `illumination_fraction`, not just the mask |
| `LPSR_85S_060M_201608` | 60 | 85°S → pole | finer, but does **not** reach the frame's outer corner |
| `LPSR_65S_240M_201608` | 240 | 65°S → pole | coarse fallback |

Take **`LPSR_75S_120M`** and **`AVGVISIB_75S_120M`** (tens of MB each, `.IMG` not
`.JP2`). Same south polar stereographic projection on the same 1737.4 km sphere,
so the DFSAR ↔ LPSR mapping is the same scale-and-offset arithmetic
`verify_projection.py` already validates — no reprojection.

Report three things:

1. **Confusion matrix** of our PSR mask against `LPSR_75S_120M`, over the frame:
   true positive / false positive / false negative, plus **Jaccard and Dice**.
   Resample the coarser product to the finer grid with nearest-neighbour, never
   bilinear — a shadow mask is categorical.
2. **Correlation** of our `illumination_fraction` against `AVGVISIB_75S_120M`
   over the frame: Pearson r, rms difference, and a scatter or 2-D histogram.
3. **A stated expectation before you look.** Agreement will not be 100 % and
   should not be: their product is 120 m and epoch-specific, ours is 80 m posts
   with a closed-form subsolar band. Finer topography resolves more small
   shadows, so **a modest positive bias in our PSR area is expected and
   defensible; a large one is not.** Say which you got and which way.

If the agreement is good this is the answer to *"how do you know your shadows are
right?"* — not an argument, a measurement against the instrument team's own
product. If it is poor, that is a finding worth having before Gate 2 closes
rather than after submission.

**Sanity anchor, independent of the above.** Mazarico et al. (2011, LPI Volatiles
abstract 6007) report **3,660 km² of PSR poleward of 87.5°S** at 240 m/px, and
explicitly note theirs is *larger* than earlier studies (2,751 km² for the same
band). The 87.5°S circle is 18,060 km², so that is **20.3 %** of it. Clip our own
mask to poleward of 87.5°S and compare directly against 3,660 km². That is a
like-for-like number in a citable paper.

**Gate 2** — `PSR AREA` in km², **stated with its domain**; `illumination_fraction`
percentiles; the azimuth count, the subsolar band and how it is integrated; the
decimation factor and effective metres per pixel; whether the doubly-shadowed term
was computed or emitted absent; a visual check that the PSR mask lands on crater
floors, not on a smooth gradient; **the LPSR confusion matrix and the AVGVISIB
correlation**; and **the >87.5°S clipped area against Mazarico's 3,660 km²**.

**Domain discipline — do not skip this.** The horizon runs on the full
608 × 608 km LOLA array (369,664 km²; the inscribed 80°S circle is 290,344 km²),
but the DFSAR frame is only **9,339.65 km²**. A full-array PSR figure is a
diagnostic, **not** a UI value — 26,900 km² is 2.88× the entire frame and would be
nonsense in the analysis JSON. Every PSR area that reaches `faustini.json` must be
**PSR ∩ frame**, and the report must print both with their denominators beside
them.

---

### PHASE 3 — Landing sites, searched instead of asserted (1 session)

Delete the five hardcoded offsets at `module_e_landing.py:70-76`.

**Run the search on the native 25 m frame**, not the 100 × 100 serving grid. A
site chosen on 1 km cells is located to ±500 m, which is not a landing site.
Score all 14.9 M pixels vectorised and send only the resulting site list to the UI.

Per-pixel criteria, all against `config.py` thresholds:

- slope below `CRITICAL_LANDING_SLOPE_DEG` — this finally discriminates: on real
  LOLA, `slope > 15°` covers **25.161 %** of the frame against 3.819 % on the
  deleted placeholder
- roughness below its limit
- hazard below its limit
- inside the amplitude mask. A site outside it has no radar evidence and must
  **say so**, not be quietly excluded
- distance to the nearest PSR within rover range — the ice-access term
- `illumination_fraction` above a minimum — the solar-power term

The last two are in direct tension, and **that tension is the science**: close to
the cold trap but still able to charge. Report both numbers per site. Do not
collapse them into one score and hide them.

Then non-maximum suppression with a **stated** minimum separation, so the top N
are not five pixels of one crater floor. Every returned site carries grid
coordinates, lat/lon from `sar_geometry`, each criterion's value, each criterion's
pass/fail against the named threshold, and a provenance mark.

Emit a **suitability heatmap** as a layer, so the recommendation is visibly the
argmax of something rather than an opinion.

**One correction to carry in:** hazard is currently scored *after* the resample.
On ~1 km serving cells roughness p50 is 214.5 m against a 50 m divisor, so
`clip(roughness/50)` pins to 1.0 and slope stops contributing — live hazard mean
0.635 with p99 = 1.0 is a saturation artefact, not a terrain map. **Score hazard
on the native 25 m frame (where p50 is 5.8 m) and area-average the bounded 0–1
field down to any serving grid.** Do not touch the 50 m divisor. Carry **two**
numbers per serving cell: `hazard_mean` for traverse cost and `slope_max` for the
hard-impassable gate — a cell that averages safe can still contain a 25° face.

**Gate 3** — the top N sites with every criterion value, threshold, pass/fail and
mark; the NMS separation used; the PSR-distance vs illumination pair for each
site, unreduced; the hazard percentile table before and after the
score-then-average change.

---

### PHASE 4 — The traverse, and a real ablation (1 session)

Build a traversal cost surface from LOLA slope and hazard: per-cell cost rising
with slope, hard-impassable where slope or hazard exceeds the rover limits in
`config.py`. Run `scipy.sparse.csgraph.dijkstra` over the graph of passable cells
— scipy is already allowed, no new dependency.

A 14.9 M-cell graph is ~119 M edges and will not fit comfortably. Aggregate to a
**stated** planning resolution (100 m cells → 565 × 1655 ≈ 935 k cells ≈ 7.5 M
edges is comfortable), carrying `hazard_mean` and `slope_max` per planning cell as
above. **Report the planning resolution as a number**, and state that path length
is quantised to it.

Deliver:

- pairwise shortest-path distances between the Phase 3 sites, as a matrix
- path polylines in grid coordinates and lat/lon
- path length in metres, and an energy proxy (cumulative climb or integrated
  cost), marked `DERIVED`
- the shortest tour visiting the selected sites. N is small; for N ≤ 8 solve it
  **exactly by enumeration** and say that is what you did, rather than shipping a
  heuristic labelled optimal
- **`UNREACHABLE` as an explicit state.** If no passable path exists between two
  sites, that is a finding worth showing — never a distance of 0

`target_coordinates` must stop being the grid centre. Targets come from Phase 3's
sites and Phase 5a's anomaly ranking.

Then the **real ablation** that replaces the deleted `experiments_runner`: rerun
the planner with `compute_hazard_score`'s weights zeroed one at a time and report
the measured deltas in distance, mean hazard and max slope. Boulder is
permanently absent (`WEIGHT_BOULDER = 0`, no optical product on disk), so it
appears as `NO DATA`, never as a row with a number.

**Gate 4** — the distance matrix; the tour length; the method (exact enumeration
or otherwise); any `UNREACHABLE` pairs; the planning resolution; the ablation
table with boulder marked absent.

---

### PHASE 5 — The ice question (2–3 sessions; the hard one)

`CANDIDATE AREA 0.00 km²` is not a bug in the threshold. It is the correct output
of a measurement that cannot reach the threshold. This build computes

```
CPR = ((√lh − √lv) / (√lh + √lv))²
```

a **squared channel-imbalance ratio** that collapses to zero whenever LH ≈ LV,
which is the normal regolith case. Native p50 = 0.000565, max = 0.053411 against
a 1.00 threshold. **No value in [0, 1] fixes this. Do not retune `CPR_THRESHOLD`.**

#### The screen is not merely unreachable — it is self-contradictory (v1.3)

The Phase 1 sensitivity sweep reported a cliff between the measured CPR p90 and
p99, and read it as an anticorrelation in the data. It is stronger than that: it
is an **algebraic identity**, and it can be proved in three lines. Put it in the
report and in `docs/METHODS.md`.

Write `r = lh/lv` and `x = ln r`. Then

```
CPR_amp = ((√lh − √lv)/(√lh + √lv))²  =  tanh²(x/4)
DOP_amp = |lh − lv| / (lh + lv)       =  |tanh(x/2)|
```

Both are monotone functions of the **same single variable** `|ln(lh/lv)|`. They
are not two independent observables — they are two reparameterisations of one
channel ratio, so `CPR_amp` is a strictly increasing function of `DOP_amp`:

```
CPR_amp = tanh²( artanh(DOP_amp) / 2 )
```

The screening rule is `CPR > cpr_th` **AND** `DOP < dop_th`, i.e. one condition
pushing `|x|` up and the other pushing it down on the same axis. So the DOP
condition places a **hard ceiling on achievable CPR**:

```
DOP < 0.13  ⟹  |x| < 2·artanh(0.13) = 0.261477
            ⟹  CPR < tanh²(0.261477/4) = 0.0042610
```

**No pixel satisfying `DOP < 0.13` can ever exhibit `CPR > 0.00426`, whatever the
terrain, whatever the instrument, whatever the threshold.** The screen is
logically empty for every `CPR_THRESHOLD` above 0.00426 — 235× below the
configured 1.00.

> **SUPERSEDED AS THE DEEPEST RESULT (v1.8, Phase 8 groundwork).** The ceiling
> above is a bound on the proxy's *magnitude*, and it holds only under the DOP
> gate. The Monte Carlo in `METHODS §7.9.2` proves something strictly stronger
> and unconditional: **at equal channel powers the proxy's population value is
> exactly zero for every value of CPR.** Across a factor of five in true CPR its
> median is constant to five decimal places (0.00043); hold the CPR fixed and add
> 3 dB of channel imbalance and it moves by a factor of 68, landing on its
> population value to four decimals. The circular polarisation ratio lives in the
> **H–V phase**, and taking magnitudes discards it before the ratio is formed.
> **The quantity this build calls CPR is a channel-imbalance estimator carrying
> CPR's name** — it is not a weak estimator of CPR, it is not an estimator of CPR
> at all.
>
> The two results were derived independently, share no step, and agree: the
> ceiling from the identity, the same fact from the sampling distribution. The
> Monte Carlo is now the primary statement and the algebra is its corroboration.
> The simulator behind it is itself validated against the swath in §7.9.3, by a
> pre-registered test that failed on its first run and caught a real omission.

This predicts the observed sweep exactly, and that agreement is the check:

| CPR threshold | ceiling 0.00426 | pixels passing | observed |
|---|---|---|---|
| 0.003546 (measured p90) | below | > 0 | **63,481** ✓ |
| 0.009258 (measured p99) | above | 0 | **0** ✓ |

Confirm it once more against the extremes: the frame's maximum CPR of 0.053411
implies `|x| = 4·artanh(√0.053411) = 0.9412`, so that pixel's DOP is
`tanh(0.4706) = 0.4386` — 3.4× above the DOP gate. The brightest "CPR anomaly" in
the swath is the *least* depolarised pixel in it. That also settles §1.2 item 5
twice over: pairing frame-max CPR with frame-min DOP does not merely describe two
different pixels, it describes **two pixels that cannot be the same pixel by
construction.**

**Two consequences that change what Phase 5 is for.**

1. **Phase 5a must state this, not just rank.** The relative anomaly ranking is
   still worth shipping, but its caption is now much stronger than "not a CBOE
   detection": the amplitude-only screen *cannot* return a detection at any
   defensible threshold, and here is the closed-form reason. Add an assertion to
   `emit_provenance.py`: if `CPR_THRESHOLD > 0.00426` while the CPR source is
   amplitude-only, the candidate area **must** be exactly 0.0 — a non-zero value
   there is a bug, not a discovery.
2. **It sharpens why 5b is the fix, beyond "the phase term is missing."** With the
   true Stokes vector, `CPR = (S0 − S3)/(S0 + S3)` and
   `DOP = √(S1² + S2² + S3²)/S0` are built from **different combinations** of the
   four Stokes parameters and are genuinely independent quantities. The
   conjunction `high CPR AND low DOP` then selects a real physical population.
   The amplitude proxy's defect is not that it is small — it is that it
   **collapses two independent physical observables onto one degree of freedom**,
   which is why their conjunction is empty. That is the sentence to say in the
   viva.

#### Phase order revision (v1.9) — 6 now runs BEFORE 3

**Current order: `2 → 6 → 3 → 4 → 5a → 8 → 7 → 9 → 5b`.**

#### Phase order revision (v2.0) — 8 now runs BEFORE 7

Phase 7 was specified as "write the documentation". It is no longer that job.
`docs/METHODS.md` has been written continuously alongside the work and stands at
ten sections with fourteen artifacts under a staleness stamp, so what remains of
Phase 7 is *finalise*: consolidate the verifier, refresh the README and the stale
`docs/*.md`, rehearse. **Doing that before Phase 8 means doing it twice**, because
Phase 8's findings land in the same documents.

Phase 8 is also far less risky than when it was first ordered.
`cpr_significance.py`, the Monte Carlo validated against the swath, the ENL
control and the F(2N,2N) machinery all exist. What remains is assembly, not
construction.

Reason, and it is a data dependency rather than a preference: **Phase 6 ingests
`LDEM_80S_20M` and recomputes slope, roughness and hazard. Phase 3's site search
consumes exactly those three rasters.** Running the search first means Phase 6
changes the terrain underneath it and the whole search is invalidated — the
ranking, the NMS, the per-criterion evidence and the suitability raster all have
to be regenerated. Doing 6 first costs nothing extra and means the sites that
finally ship were chosen on the final terrain.

`LDEM_80S_20M.IMG` has been on disk and unused since Phase 0.7, so Phase 6 is
unblocked now. Phase 6 must **not** change the 25 m analysis grid: only the
source DEM changes, through one `--input`, down the same code path. The slope and
hazard percentile tables are expected to MOVE — that is the measurement, not a
regression.

#### Phase order revision (v1.4) — 6 and 7 now run BEFORE 5b

v1.0–v1.3 ordered `… → 5a → 5b → 6 → 7`. **Change it to `… → 5a → 6 → 7 → 5b`.**

Reason: **5b is the only phase in this plan that can fail to deliver.** It is
8–14 hours against two 2.17 GB complex products, a slant-range geocoding step and
a label layout that has to be parsed exactly right, and its honest outcome may
still be a measured zero. Phase 6 (map clarity, 3–4 h) and Phase 7 (the
provenance and methods documents, 3–4 h) are short, certain, and are what make
the project *finished*.

Putting 5b last means a 5b that overruns or fails costs nothing — you already have
a complete, documented, sharp product with a null ice result explained in closed
form. Putting 5b before them means a bad week in 5b leaves the map unimproved and
the documentation unwritten. **Do not let the one uncertain phase stand between
you and a finished deliverable.**

5a still runs before 6, because it fills the stat cell vacated by P(ice) and takes
about an hour.

#### 5a · Ship something honest now (¼ session)

Add a **relative** CPR anomaly ranking within the measured swath: top percentiles
of the measured CPR field, with their area and locations, labelled
`RELATIVE ANOMALY WITHIN THIS SWATH — NOT A CBOE DETECTION`. It answers "which
places are most worth looking at" without claiming a detection the product cannot
support. It is a ranking and the label must say ranking. This also fills the cell
vacated by P(ice) in Phase 1.

#### 5b · The real fix — Stokes from the complex products

True hybrid-polarity CPR needs the phase term: `S3 = 2·Im⟨E_H · E_V*⟩`, then
`CPR = (S0 − S3)/(S0 + S3)`. `module_b_radar.py` **already contains correct
`compute_cpr_from_stokes()` and `compute_dop_from_stokes()` and has never been fed.**
Feed them; do not write new ones.

The data is on disk and verified present:

```
data/pradan/raw/data/calibrated/20200808/
  ch2_sar_ncxl_20200808t201154198_d_sli_xx_cp_lh_d18.tif   2,165,948,598 bytes
  ch2_sar_ncxl_20200808t201154198_d_sli_xx_cp_lv_d18.tif   2,165,948,598 bytes
  ch2_sar_ncxl_20200808t201154198_d_sli_xx_cp_xx_d18.xml   (the label)
```

355768 × 759, `ComplexLSB8`, 21 azimuth looks.

Rules:

- Windowed `np.memmap` only. Same discipline as LOLA. Never whole-array.
- **Average the Stokes parameters over the azimuth looks BEFORE forming ratios.**
  Averaging after the ratio is a different and wrong quantity, and single-look
  speckle will swamp the result.
- Parse the PDS4 label for the complex layout rather than assuming interleave or
  endianness. `LSB_INTEGER` vs `MSB`, and units inside angle brackets, are exactly
  where silent corruption enters.
- **Fatal check, same shape as the LOLA one:** reproduce a statistic the product
  carries about itself from raw bytes before trusting the read.
- `sli` is slant-range L1A. Geocoding to the `sri` ground-range frame is part of
  the job — the `sli_grid` (11119 × 25, interval 32/32) in
  `geometry/calibrated/20200808/` is the mapping.

**Both outcomes ship.** If real CPR reaches published lunar values (≈0.3–0.7
regolith, 0.7–1.3+ anomalous polar), the detector is alive and `CANDIDATE AREA`
becomes a real number. If it does not, that is a **measured zero** — a legitimate
scientific result — and it is presented as one.

**Fallback, only with explicit approval:** if 5b proves too expensive, rename the
amplitude quantity to what it actually is (a linear depolarisation ratio), drop
the `CPR > 1` claim, and recalibrate the threshold to the real histogram. Weaker
project, but not misleading. **Ask before choosing this.**

**Gate 5** — the CPR percentiles from the complex read; the label statistic
reproduced as the fatal check; the geocoding residual against the `sri` frame; and
the final `CANDIDATE AREA`, including if it is a measured zero.

---

### PHASE 6 — Map clarity (1 session + download time)

`render_layers.py` already writes full-resolution 6618 × 2258 lossless WebP with a
single global stretch, so the remaining softness is **not** a render cap and must
not be chased in CSS. Four honest upgrades, in order.

**6.1 — LOLA 20 m/px.** This is the real fix and it is the largest single gain
available to the look of the map. At 80 m native, the 25 m grid is a **3.2×
upsample** — three of every four pixels of apparent detail are interpolation,
which is exactly what `layers.json` already prints as *"carries no relief finer
than 80 m"*. At 20 m native the 25 m grid becomes a slight **downsample**, so the
displayed detail is real. Same code path as Phase A, **one `--input` change**:

```
python backend/scripts/ingest_lola_polar_dem.py --input data/pradan/lola/LDEM_80S_20M.IMG
```

**Do not change the 25 m grid to chase 20 m.** The gain is already there, and
changing the grid ripples through every layer, mask and bound. Re-run the slope
and hazard percentile tables afterwards — they will move, and that is expected,
not a regression. Update `native_metres_per_pixel` and `resample_ratio` in the
provenance sidecar and the layer provenance strings, keeping all six banned words
out of them.

**6.2 — Multi-directional hillshade.** `render_layers.compute_hillshade` uses a
single sun at azimuth 315°, altitude 30°. Slopes facing away from that one light
flatten out completely. Replace with a weighted blend over about four azimuths
(e.g. 225/270/315/360 at equal weight, or the standard Swiss 315-dominant
weighting). Keep the single-azimuth path available behind a flag and **state which
one shipped** in `layers.json`.

**6.3 — Hypsometric tint and contours for `dem_elevation`.** Today it is a flat
viridis ramp with no relief cue at all — the relief exists only in the separate
`hillshade` layer. Multiply an elevation-classed tint by the hillshade, and add
contours at a stated interval. Both are **display choices, not data**, and
`layers.json` must say so.

**6.4 — Re-check the base CSS filter with numbers, not by eye.** After 6.1–6.3 the
`mc.css` `.mc-raster--base` filter (currently `contrast(1.06) brightness(1.10)`) is
compensating for a DEM that has changed. Print the 8-bit histogram of
`hillshade.webp`: mean, median, p2, p98, and the clipped fraction at 0 and 255.
Rule, not a guess: if the post-filter median exceeds ~190 or more than 1 % of
pixels clip at 255, walk `brightness` back until neither holds. Report before and
after.

Do not restyle anything else. The two-tier coverage encoding, the graticule, the
scale bar and the amber out-of-coverage styling are all measured decisions from
earlier phases and stay.

**Gate 6** — which LOLA product was ingested and its native post spacing; the
before/after slope and hazard percentile tables; which hillshade azimuth scheme
shipped; the hillshade histogram before and after any filter change; total payload
per layer; and four screenshots at identical zoom and centre — Surface Relief and
Radar Signals, before and after.

---

### PHASE 7 — Make it defensible on the day (1 session)

**7.1** `docs/PROVENANCE.md` — one table, every number the app can display, its
source raster, its computation, its mark, and its known limitation. This is the
document to hand a reviewer.

**7.2** `docs/METHODS.md` — the actual method for each phase: the georeferencing
validation (13.2 mm), the LOLA label parse and its four traps, the horizon
algorithm and its resolution, the site search and NMS, the traverse graph and its
planning resolution, the Stokes derivation. Include the numbers, not the prose.

**7.3** *(Moved to Phase 1F — `verify_map.mjs` was already dead and the
`routes_visible` false positive had to be fixed before Gate 1 could mean
anything.)* What remains here: confirm the single surviving verifier reproduces
every gate's evidence in one command and writes to `docs/`, and that each gate it
asserts corresponds to a statement in §6.

**7.4** Update `README.md` and the four stale `docs/*.md`
(`ml-methodology.md` in particular describes the deleted Random Forest).

**7.5** Rehearse the three questions this project will actually be asked:

- *"You didn't find any ice."* → Correct. Here is the measured CPR distribution,
  here is why an amplitude-only product cannot reach the CBOE threshold, here is
  the Stokes derivation that can, and here is the measured result either way.
- *"This is trivial."* → Here is the per-pixel site search over 14.9 M cells with
  six criteria and stated NMS separation; here is the horizon-based PSR
  computation over the full 7600² LOLA array; here is the sub-pixel
  georeferencing validation against ISRO's own 937,296-node grid.
- *"How do I know these numbers are real?"* → Every one carries a mark, every mark
  resolves to a raster read, and `assert_dem_is_lola()` fails the build at
  tolerance 0.0 m if the elevation is not the LOLA product.

---

### PHASE 8 (v1.8) — **THE NOVELTY: detection statistics for the CPR ice test**

**This supersedes v1.6 and v1.7 as the headline contribution.** A second literature
sweep (34 searches, full-text term-checks) established three clean nulls across the
entire lunar polar radar ice literature:

- **Zero** papers propagate speckle / multi-look statistics into a per-pixel CPR
  uncertainty and test whether `CPR > 1` is significant at that pixel.
- **Zero** papers report detected ice area with confidence intervals or error bars.
- **Zero** papers report a false-positive rate, ROC curve, or statistical power for
  the `CPR > 1` test.

Sinha et al. 2026 — a Nature-family paper announcing subsurface ice — contains
**zero occurrences** of "uncertainty", "error", "±", "significance" or "looks".

**And the machinery to fix it is fifty years old and mature**: Touzi, Lopes &
Bousquet (1988, *IEEE TGRS* 26:764) built a CFAR ratio detector that sets
thresholds at a specified false-alarm probability; Lee, Hoppel, Mango & Miller
(1994, *IEEE TGRS* 32:1017) give the closed-form PDF of the multilook intensity
ratio. **Neither has ever been carried across to lunar CPR.** The two literatures
never co-occur in a search.

#### The core statistics — verified, reproduce these before building

If SC and OC are each N-look intensity estimates, then `R / CPR_true ~ F(2N, 2N)`.

**1. The published error bar is the wrong statistic.** Bhiravarasu et al. (2021,
*PSJ* 2:134) — the DFSAR instrument paper — states *"an approximate 1/N^{1/2}
uncertainty in the CPR measurements of ±0.16"* and elsewhere *"±0.2"*. But `1/√N`
is the error of a **single channel**, not of a **ratio**. The correct relative
standard deviation is `√((2N−1)/(N(N−2)))`:

| N looks | correct rel. SD | published 1/√N | understated by |
|---|---|---|---|
| 7 | 0.6094 | 0.3780 | **1.61×** |
| 21 (DFSAR azimuth looks) | 0.3206 | 0.2182 | **1.47×** |
| 38 | 0.2341 | 0.1622 | 1.44× |
| 49 | 0.2052 | 0.1429 | 1.44× |

There is also a **positive bias**, `E[R] = CPR·N/(N−1)` — +5.0 % at N = 21 — which
pushes estimates *toward* exceeding the threshold. Nobody corrects it.

**2. The false-positive rate is large.** Probability an **ice-free** pixel registers
`CPR > 1` from speckle alone:

| true CPR | N=7 | N=21 | N=38 | N=49 |
|---|---|---|---|---|
| 0.3 | 1.57 % | 0.01 % | 0.00 % | 0.00 % |
| 0.5 | 10.35 % | 1.35 % | 0.14 % | 0.04 % |
| **0.7** | **25.66 %** | **12.59 %** | 6.11 % | 3.95 % |
| **0.9** | **42.33 %** | **36.72 %** | 32.36 % | 30.15 % |

Published lunar regolith CPR runs 0.3–0.7 typical and up to ~0.9 on blocky terrain.
So **ordinary rocky ground false-positives at double-digit rates.**

**3. The single-pixel detection floor is far above the threshold.** For a pixel to
read `>1` with 95 % confidence, its *true* CPR must exceed:

| N | 7 | 21 | 38 | 49 |
|---|---|---|---|---|
| floor | **2.484** | **1.671** | 1.462 | 1.396 |

The threshold in use is **1.00**. At DFSAR's look count the test has **no
single-pixel significance anywhere near where it is applied.**

**4. Multiple comparisons — the "peak CPR" statistic is uninterpretable.** A
reported peak is a maximum over thousands of noisy pixels. Median maximum over
ice-free pixels at N = 21:

| true CPR | 500 px | 1,500 px | 5,000 px |
|---|---|---|---|
| 0.5 | 1.29 | 1.43 | 1.59 |
| 0.7 | 1.80 | **2.00** | 2.23 |

F2 is 1.1 km across ≈ 1,520 pixels at 25 m. **With zero ice and a uniform true CPR
of 0.7, the median peak over F2 is 2.00. Sinha et al. report 1.95.**

**State that responsibly.** It is *not* proof their detection is noise — the look
count of their full-pol product, their pixel size, their true background CPR and
the inter-pixel correlation are all unknown to us. What it *does* establish is that
**a peak-CPR statistic is uninterpretable without a multiple-comparisons
correction, and nobody publishes one.** Compute it properly with their stated
parameters, present it as a methodological finding, and let the reader draw the
inference.

**5. A systematic error nobody folds in.** Carter, Neish, Patterson et al. (2014,
LPSC #2152) report a Mini-RF range-direction artifact with *"CPR magnitude
variations of up to ~0.2-0.3"* — the same size as the whole random budget, and the
same size as the margin by which anomalous craters exceed 1.

#### Why this is the right novelty for this project

It is the **statistical twin of the algebraic ceiling you already proved.** You have
a deterministic limit (`CPR_amp ≤ 0.0042610` where `DOP < 0.13`) and this adds a
statistical one. Together they are a **complete detection-limit analysis for lunar
polar radar ice screening** — deterministic and statistical — which is exactly the
project's thesis: *report what could not have been found.*

It also does **not depend on your own frame having high CPR**, which the ceiling
proof shows it cannot. The deliverable is a method plus a re-analysis of published
values, and it upgrades automatically when Phase 5b produces true Stokes CPR.

And it is uncontested: the live 2026 Sinha/Saran dispute is entirely about
**physics** — the CPR formula, roughness, the DOP sign. **Nobody is arguing about
the statistics.**

#### What to build (6–10 h)

1. `backend/scripts/cpr_detection_stats.py` — parse the true look count from the
   PDS4 label (do not assume 21); implement the `F(2N,2N)` ratio statistic, the
   bias correction, the per-pixel confidence interval, the false-alarm curve, the
   detection floor, and the multiple-comparisons correction for a peak over an area.
   `scipy.stats.f` only; nothing new in `requirements.txt`.
2. **A per-pixel `cpr_significance` layer** — not "is CPR high" but "is CPR
   *significantly* above threshold", with the confidence stated.
3. **Report candidate area with a confidence interval**, the first in this
   literature. A measured zero with a CI is still a result.
4. **A re-analysis table** of the published F2/F3/S1/H3 values against their
   detection floors — with every assumption you had to make listed beside it.
5. Add to `emit_provenance.py`: any reported detection area must carry its CI.

#### One sentence for the viva

> *"Everyone tests whether CPR exceeds 1. Nobody asks whether that test can tell
> the difference — so I computed its false-positive rate, and at this instrument's
> look count, ordinary ice-free rock reads above the threshold 12 % of the time."*

---

### PHASE 9 (optional, 6–8 h) — m-χ / m-δ / m-α on DFSAR compact-pol

A second confirmed gap from the same sweep, and **you have exactly the right data
type for it.** Every published DFSAR paper applies *full-pol* decompositions
(H-A-α, Freeman–Durden, Pauli, Yamaguchi) to DFSAR, while applying the *hybrid-pol*
Raney decompositions (m-χ, m-δ, m-α) to **Mini-SAR / Mini-RF instead** — confirmed
explicitly in Sahu et al. 2025 (*Remote Sensing* 17:31) and the Singh 2021 IIRS
thesis. ISRO's own MIDAS tool implements m-χ and m-δ; no published DFSAR compact-pol
result uses them.

Your products are **compact-pol** (`_cp_`, LH/LV) — the exact mode these
decompositions were designed for — and Phase 5b already produces the Stokes vector
they consume, so the marginal cost is ~20 lines of numpy. They separate **even-bounce
(dihedral/rocks)** from **odd-bounce (surface)** from **volume** scattering, which is
the physical distinction the entire ice-vs-roughness dispute turns on.

**Verify first:** obtain IEEE APSAR 2021 doc 10.1109/APSAR52370.2021.9688528,
*"Chandrayaan-2 DFSAR Full and Compact Polarimetric Data Analysis"* — it is the one
place a prior m-χ/m-δ DFSAR result could hide, and the sweep could not read it.

Also flagged and unread: Putrevu et al. 2023, *JGR Planets*,
10.1029/2023JE007745, whose title is literally *"Full-Polarimetric Analysis of
Chandrayaan-2 Dual-Frequency SAR Data"* — read it before claiming any L-vs-S gap.

---

### PHASE 10 (demoted from v1.7) — The step four papers asked for and nobody took

**Read this before the v1.6 text below, which it supersedes as the headline.**
A ten-paper review settled the novelty question. The contribution is not a new
method and not a new detection. It is **executing a step that the radar literature
has explicitly recommended twice and skipped four times**, on the one crater
currently under dispute. That framing is citable, it cannot be beaten on priority,
and it is one sentence to explain.

#### The finding — thirteen years, four papers, two explicit recommendations, zero execution

| paper | year | dual-frequency data in hand? | did it separate bands? |
|---|---|---|---|
| Fa & Cai, *JGR Planets* 118, 1582 | 2013 | Mini-RF S **and** X band | **No** — and its conclusions recommend X-band as *"a feasible way"* |
| Virkki & Bhiravarasu, *JGR Planets* 124, 3025 | 2019 | Mini-RF S **and** C/X band | **No** — and its conclusion states *"constraints obtained using observations at other wavelengths are needed"* |
| Sinha et al., *npj Space Exploration* 2:22 | 2026 | DFSAR **L and S**, full-pol | **No** — advertises both in the abstract, reports not one band-resolved number |
| Saran et al., Research Square preprint | 2026 | DFSAR **L and S** | **No** — even though its own proposed discriminator (coherent backscatter) is wavelength-dependent |

**Two papers asked for it. Two more had the data and did not do it.** This project
has simultaneous L-band and S-band from a single DFSAR pass over **Faustini** —
the exact crater the 2026 dispute is about.

#### Why nobody did it — and this is the second, free contribution

Fa & Cai (2013) state, verbatim: *"Mini-RF coverage ratio is **>99% for the polar
region (with latitude > 80°)**, which is much larger than that of the equatorial
region with a value of 66% on average."*

So **S-band coverage of the pole is essentially complete.** DFSAR **L-band**
coverage is narrow, discontinuous strips — plainly visible in Saran et al.'s own
Figure 1, and **quantified by nobody**. Sinha et al. say only *"Radar data are
unavailable for one of the doubly shadowed craters (crater F4)."*

That gives a one-sentence result worth stating on its own:

> **The deepest-penetrating radar has the thinnest coverage.** L-band, which
> reaches 2.0–5.8 m into dry regolith against S-band's 1.0–2.9 m, images only a
> small fraction of the polar cap that S-band covers almost completely — so the
> depth comparison is possible only in the few places where both exist, and this
> frame is one of them.

That both motivates Phase 8 and explains why the step has gone untaken.

#### The live dispute this lands in

The two 2026 papers disagree about the same crater by a factor of two:

| | Sinha et al. 2026 | Saran et al. 2026 |
|---|---|---|
| F2 CPR | peak **1.95**, 47 % of interior pixels > 1 | mean **1.01 ± 0.3** |
| F2 DOP | **0.1–0.13** where CPR elevated | mean **0.32 ± 0.1** |
| verdict | *"Strong evidence"* for subsurface ice | *"better explained by roughness-induced changes"* |

Saran et al. further argue Sinha's CPR formula *"only applies to the special case
of dihedral scatterers where there are no cross-pol (HV/VH) components, and is
uncommon for natural surfaces"*, and that low DOP is the **wrong** sign for thick
clean ice, since coherent backscatter should drive DOP **up**, not down. They then
prescribe an evidence standard — *"strong radar linear and circular polarization
ratios, and enhanced DOP values, along with a high degree of correlation between
radar-bright features and regions of permanent shadow"* — **and do not compute
that correlation themselves.**

**Note the pol-mode difference before building.** Both 2026 papers use
**full-pol** (HH/HV/VH/VV). This project's products are **hybrid/compact pol**
(`_cp_`, channels LH/LV), where the Stokes formulation
`CPR = (S0 − S3)/(S0 + S3)` is the standard and correct one — already implemented
in `module_b_radar.compute_cpr_from_stokes()`. So the project **cannot** replicate
the formula dispute directly, and must not claim to. It can state which mode it
used and why its derivation is the correct one for that mode.

#### What to build — unchanged in substance from v1.6, changed in framing

1. **Ingest S-band** through the existing path; parse S-band's own calibration and
   incidence from its own label.
2. **Compute both bands' quantities over the amplitude mask**, and emit the
   **L−S differential** as a per-pixel layer. Do not call the amplitude quantity
   CPR (Phase 5's ceiling proof).
3. **Regress the differential against the independent LOLA roughness field** —
   stating first that LOLA roughness is a *decametre-scale proxy* for the
   centimetre-scale roughness that drives depolarisation.
4. **Stratify by the Phase 2 PSR mask** — do pixels inside PSRs differ at matched
   roughness?
5. **Quantify the L-band coverage gap**: PSR area with S-band coverage vs L-band
   coverage vs neither. This is the "coverage is not evidence" work below, now
   correctly scoped to **L-band**, since Fa & Cai settle S-band at >99 %.

**Cost 8–12 h.** Run after Phase 7, before 5b. If 5b lands, redo with true Stokes
at both bands — that is the strong version.

#### One sentence for the viva

> *"Two papers recommended a multi-wavelength radar comparison and did not do it.
> Two more had dual-frequency data and reported neither band separately. I did it,
> on the crater those two 2026 papers are arguing about, and I first measured why
> nobody had: the L-band coverage that makes it possible barely exists."*

---

### PHASE 8 (v1.6 text, retained) — "Coverage is not evidence": an evidential-status audit of cold traps under DFSAR (6–9 h)

**v1.6 supersedes v1.5's framing of this phase.** v1.5 pitched the dual-frequency
L/S differential as novel. A literature check — which v1.5 told you to run and
did not run itself — found it substantially published, on this crater:
[npj Space Exploration, 6 May 2026](https://www.nature.com/articles/s44453-026-00038-9)
studies nine doubly-shadowed craters including F1/F2/F3 **inside Faustini**, using
DFSAR full-pol L- and S-band, with the criterion **CPR > 1 and DOP < 0.13** — the
exact constants in `config.py`. Accessibility and traverse planning to PSRs is
likewise well covered (Cannon & Britt 2020; Frontiers 2026 on 31 priority PSRs;
Wueller 2026 JGR Planets). **Neither is this project's novelty. Cite both; claim
neither.**

#### What IS this project's own contribution

Not a detection, and not a method — a **question the detection literature does not
ask, which this architecture is uniquely able to answer**:

> **What does the DFSAR archive actually permit anyone to say about a given cold
> trap — and about which cold traps does it permit nothing?**

The detection papers report ice signatures in the craters they examined. Nobody
publishes the **denominator**. This project can, because it carries three distinct
spatial masks at matched resolution plus an independently computed PSR mask, and
because every pixel already knows its own evidential status.

**Three failure modes, all measured here, that "covered by a radar swath" hides:**

1. **Never pointed.** Outside the ISRO `sri_ma` footprint entirely — 64.4 % of
   this frame.
2. **Pointed but silent.** Inside the pointed swath, no amplitude returned. This
   project's own measurement: `amplitude / footprint = 0.438927`, i.e. **56.1 % of
   the ground DFSAR actually illuminated in this pass returned no usable signal.**
   That number is striking, it is yours, and nobody publishes it.
3. **Measured but below the product's algebraic ceiling.** Even where amplitude
   exists, the distributed `sri`/`gri` amplitude products **cannot** reach the
   published criterion — see Phase 5: `DOP < 0.13` caps `CPR_amp` at **0.0042610**,
   235× below the threshold. So a cold trap can sit in a fully measured swath and
   still be **unscreenable with the products most users will reach for.**

#### What to build

For each connected component of the Phase 2 PSR mask within the frame, emit:
area; the fraction of that area in each of the three states above; within the
measured fraction, the CPR/DOP statistics and the explicit
`screenable_with_this_product: false` with the ceiling as its reason; and distance
to the nearest measured pixel.

Deliverables: a table of N cold traps with evidential status, a **map layer
coloured by evidential status** (not by signal), and one headline sentence of the
form —

> *Of N cold traps in this frame totalling X km², M % of their combined area has
> never been pointed at by DFSAR, P % was pointed but returned no signal, and
> **0 % is screenable against the published CPR > 1 / DOP < 0.13 criterion using
> the distributed amplitude products.***

**Optional regional extension, if PRADAN publishes swath footprint metadata:**
repeat the audit over all polar DFSAR passes using footprints alone — no bulk
download. Confirm the metadata exists before promising this.

#### Calibrate the claim honestly

This is a **framing and quantification** contribution, not a new method and not a
new detection. That is the correct size for a final-year project, and it is
defensible precisely because it does not overreach. Say "we derive and quantify",
never "we discovered".

**Before claiming leg 3 or the coverage framing, run the literature check.** A
search for radar-coverage completeness of lunar PSRs returned no direct prior
work, but *absence of a search hit is weak evidence*. Look properly, and if prior
work exists, cite it and position as extension. That instruction cost this
document one retraction already.

#### Why the honesty architecture is the enabling capability

Worth stating in the report, because it reframes what looked like mere
engineering: this audit is **only** computable because the pipeline marks
provenance per value and carries the two coverage masks separately from the signal.
A conventional pipeline that renders CPR and stops cannot produce it — it has
thrown away the distinction between "zero" and "never looked". **The provenance
discipline is not scaffolding around the science. It is the instrument that makes
this particular result possible.**

#### Superseded — the dual-frequency differential

Still worth doing as a **replication with one extension**, if time allows after
the above: the L−S differential as a *per-pixel map* regressed against the
independent LOLA roughness field, where the published work uses per-crater
aggregates with depth-to-diameter and ShadowCam boulders. **Read the paper's
methods section before asserting that gap exists.** The physics stands either way:
penetration depth goes as λ, giving L-band 2.0–5.8 m against S-band 1.0–2.9 m — a
2:1 ratio set by wavelength alone — and because both bands share one pass, the
incidence and geometry terms cancel exactly. Both product sets are on disk
(`ncxl` and `ncxs`, identical timestamp and byte sizes; verify from the labels).
Do not call the amplitude quantity CPR.

#### Immediate high-value check, do this in Phase 5a

The npj paper's crater **F2 is centred 87.39°S, 82.31°E**, 1.1 km across, inside
Faustini, with **max CPR 1.95 over ~47 % of its interior**. That is ~79 km from
the pole; this frame's projected bbox spans easting −13.5 … +152 km and northing
−17.8 … +38.6 km, so it is **plausibly inside**. Run it through
`sar_geometry`'s validated forward projection — not by hand — and report whether
F2 falls inside the frame, and separately whether it falls inside the **amplitude
ribbon** (15.6 % of the frame). If it does, the null result becomes directly
comparable to a published positive, and Phase 5b's value stops being theoretical.

#### The finding this rests on

`data/pradan/raw/data/calibrated/20200808/` contains **two** complete product
sets, not one:

```
ch2_sar_ncxl_20200808t201154198_...    L-band, ~1.25 GHz, lambda 24 cm
ch2_sar_ncxs_20200808t201154198_...    S-band, ~2.50 GHz, lambda 12 cm
```

**Identical timestamp, identical orbit, identical byte sizes** (`sri` LH/LV
29,905,588 each; `sri_in` 59,792,476 each; `sri_ma` 14,962,144 each). DFSAR is one
of very few planetary radars that acquires both frequencies **simultaneously**, so
these are the same ground pixels, the same incidence angle, the same epoch, the
same speckle realisation geometry. **Verify this from the two labels before
building on it** — do not take it from this document.

#### Why it matters — it attacks the field's actual open problem

The unresolved question in lunar polar radar is not "is CPR high?" It is
**"is high CPR ice, or is it surface roughness and blocky ejecta?"** That
ambiguity is why Mini-RF results were contested for a decade. A single-frequency
instrument cannot separate the two.

Two frequencies can, because the two mechanisms scale with wavelength differently:

- **Penetration depth** goes as lambda. Computed for dry regolith
  (`delta = lambda / (2*pi*sqrt(eps')*tan_delta)`), with `eps' = 2.7–3.5`,
  `tan_delta = 0.004–0.010`: **L-band 2.0–5.8 m, S-band 1.0–2.9 m — a clean 2:1
  ratio set by wavelength alone.** L and S therefore sample *different depths of
  the same column*.
- **Surface/roughness scattering** depends on roughness relative to wavelength, so
  a surface that is electrically rough at 12 cm can be smoother at 24 cm. Blocky,
  cm-to-decimetre roughness depolarises S more than L.
- **Volume scattering** from buried inclusions depends on penetration, so a
  subsurface volatile-bearing layer weights toward L.

**So the sign of the L-minus-S differential is a physically motivated
discriminant**, and — because both bands share one pass — the geometric and
incidence terms cancel exactly rather than approximately. That cancellation is the
methodological advantage, and it is rare.

#### What to build

1. **Ingest S-band through the existing path.** Same code, one product id. Parse
   S-band's *own* calibration constants and incidence from its *own* label — never
   reuse L-band's.
2. **Compute per pixel, over the amplitude mask, at both bands:** calibrated
   `sigma0_total`, and the channel ratio. **Do not call the amplitude quantity
   CPR** — Phase 5 proves it is a reparameterised channel imbalance. Name it what
   it is. If 5b lands, redo this with true Stokes at both bands; that is the
   strong version.
3. **Emit the differentials as layers:** `sigma0_L / sigma0_S` and the
   channel-ratio difference, with the same stretch, mask and provenance discipline
   as every other layer.
4. **The falsifiable test — this is the contribution.** Regress the differential
   against **LOLA-derived roughness**, which you already compute independently and
   which is not radar-derived. Almost no CPR study has an independent roughness
   measurement at matching resolution; you do.
   - **State honestly that LOLA roughness (5x5 elevation std at 25 m posts) is a
     decametre-scale proxy for the centimetre-scale roughness that actually drives
     depolarisation.** They correlate because blocky terrain is rough at both
     scales, but they are not the same quantity. Report the correlation
     coefficient whatever it is, including if it is weak. **That caveat, stated
     first, is what makes the result credible rather than overclaimed.**
5. **The payoff analysis — stratify by shadow.** Using the Phase 2 PSR mask, ask:
   **do pixels inside PSRs show a different L/S signature than pixels outside PSRs
   at matched LOLA roughness?** Report as a stratified comparison with counts,
   medians, and a distribution overlap statistic per roughness bin.

#### Every outcome is publishable, which is why this is safe to attempt

| result | what it means |
|---|---|
| differential tracks roughness, no PSR effect | the swath's scattering is roughness-dominated — **a direct, measured contribution to the ice-vs-roughness debate for this frame** |
| PSR effect survives at matched roughness | a genuine anomaly worth naming, stated as an anomaly and not as a detection |
| no structure in either | the frame is homogeneous at these wavelengths — still a measured null, with the discriminant's sensitivity quantified |

**Gate 8** — verification that L and S share a grid, epoch and geometry, from the
labels; both calibrations, parsed separately; the two differential layers with
percentiles; the roughness regression with its scale caveat stated first; the
PSR-stratified comparison with per-bin counts; and a plain statement of which of
the three outcomes above was observed.

## 5 · Out of scope — do not start these

- LRO Diviner thermal ingest. Thermal is `DERIVED` from illumination (Phase 2).
- Real optical imagery for boulder detection. Boulder risk is `NO DATA` and
  `WEIGHT_BOULDER = 0`.
- A second crater. `cpr_real.tif` / `dop_real.tif` are crater-agnostic shared
  filenames; `assert_no_shared_real_rasters` will `SystemExit` the moment a second
  crater becomes eligible. Shackleton and Shoemaker are correctly `NOT_INGESTED`.
- NASA Moon Trek polar basemap / `LunarSouthPoleCRS`. Investigated and killed in
  v2: every `trek.nasa.gov/tiles/Moon/SP/...` URL 404s, and independently, Leaflet
  cannot reproject raster tiles client-side, so pre-rendered equirectangular tiles
  can never align inside a polar-stereographic CRS. `frontend/src/utils/lunarCRS.ts`
  has nothing to align to.
- Retraining any classifier on synthetic labels, in any shape.
- Retuning `CPR_THRESHOLD`.
- The AI copilot. It is dead code after Phase 0.

---

## 6 · Definition of done

The project is done when all seven statements are true and each is backed by a
number in a report:

1. Every number rendered on `#mission` resolves to a raster read or an explicit
   absent state, and carries a mark. (Gate 1)
2. PSR area, cold-trap overlap and illumination fraction come from a horizon
   computation over the full LOLA array, at a stated resolution. (Gate 2)
3. Landing sites are the argmax of a six-criterion per-pixel search over
   14.9 M native cells with stated NMS separation, each with per-criterion
   evidence. (Gate 3)
4. The traverse is a Dijkstra path over a slope-and-hazard cost surface at a
   stated planning resolution, with `UNREACHABLE` as a real state. (Gate 4)
5. CPR is either a Stokes-derived measurement or an explicitly-labelled
   amplitude-only ratio with the claim withdrawn — and `CANDIDATE AREA` is a
   measurement either way, including a measured zero. (Gate 5)

   **And a figure that is an upper bound is never quoted as if it were a rate,
   nor computed at the wrong look count.** (Gates 10 and 13) There is one CPR
   field and it has one ENL: the threshold touches the boxcar-smoothed field at
   **13.72**, so the operating point is a 1.895 floor and an FP rate of up to
   17.79 % at true CPR 0.7 — not the 2.978 and 29.16 % the narrative was quoting
   from the raw product's 5.83. The false-positive rates in METHODS §7.7 assume the two circular
   channels are independent; §7.10 shows from Putrevu et al. 2023's own Byrgius C
   dispersion that they are correlated at |ρ|² ≥ 0.36, so every one of those
   rates is a bound. "29 % of ordinary rock crosses the threshold" and "up to
   29 % does" are different claims, and the difference is one phrase — the kind
   that survives one edit and is gone by the third.
6. The map's relief is real at 25 m (LOLA 20 m native), lit from more than one
   direction, and the base filter is set from a histogram rather than by eye.
   (Gate 6)
7. **The PDF report is a rendering of the analysis artifacts, not a second
   computation of them**, and every figure it prints appears in those artifacts
   at the precision printed. (Gate 9)
8. **There is one incidence field, and it satisfies `incidence > look angle` at
   every pixel.** (Gate 12) That is an identity on a convex body —
   `sin θ = ((R+h)/R) sin η` — so no correct implementation can violate it. The
   project shipped a Bragg-domain criterion built on a field where **80.53 %** of
   the values sat below the look angle; the criterion is withheld and the gate
   fails the build if anything consumes such a field again.

   Added after the report was found printing five landing sites that Phase 3
   deleted — Alpha Ridge, Beta Plateau, Gamma Bench, Delta Spur, Epsilon Crest,
   one of them marked RECOMMENDED — beside a rover traverse of 18.06 km and
   3,137.5 Wh while the screen's ROVER cell read NO DATA. It was generated from
   `mission_service`'s legacy payload, and Gate 7 compares that payload against
   the analysis on slope, roughness and hazard only, so nothing looked at it.
   **A PDF is the one artefact that leaves the browser without the provenance
   badge beside it**, which makes it the surface where a stale number does the
   most damage and the last one that had no gate.
