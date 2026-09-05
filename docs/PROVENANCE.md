# PROVENANCE — every number the mission screen can display

**GENERATED FILE. Do not edit by hand.**

```
python backend/scripts/emit_provenance.py
```

Emitted from `frontend/public/analysis/faustini.json`, which is the same asset the
UI reads — so this table cannot describe a different run than the one on screen.
The emitter fails the build if any value reaches the UI unmarked, if any value
is marked `MODELLED`, or if an absent value carries no reason.

---

## The scene

| | |
|---|---|
| Crater | Faustini Crater (Chandrayaan-2 SAR Swath) |
| Centre | -87.69°, 81.46° |
| Instrument | Chandrayaan-2 DFSAR (L-band, hybrid circular polarimetry) |
| Product | `ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18` |
| Observed | 2020-08-08 |
| Frame | 2258 × 6618 @ 25 m/px = 9,340 km² |
| Measured swath | 1,460.68 km² (15.640 % of frame) — every MEASURED radar figure uses this mask only |
| Thresholds | CPR > 1, DOP < 0.13 — read from backend/app/core/config.py (CPR_THRESHOLD, DOP_THRESHOLD, MAX_TRAVERSABLE_SLOPE_DEG, CRITICAL_LANDING_SLOPE_DEG), **not retuned** |
| Generated | 2026-09-05T18:57:34.356071+00:00 |

## Mark counts

| Mark | Count | Meaning |
|---|---:|---|
| `MEASURED` | 37 | An observation, or a direct geometric consequence of one. |
| `DERIVED` | 3 | An assumption model applied on top of a measured quantity. |
| `MODELLED` | 0 | **Asserted zero.** A non-zero count fails the build — see the emitter. |
| `UNAVAILABLE` | 14 | Cannot be computed honestly yet. Each names the phase that fills it. |
| **Unmarked** | **0** | Asserted. A number with no defensible mark does not ship. |

`MODELLED = 0` is the load-bearing row. It is the machine-checkable statement
that no output of the random-label Random Forest reaches a screen: the model was
fitted to `np.random.uniform` labels whose positive class was CPR 1.05–2.5, a
range this amplitude-only product cannot reach, so every probability it produced
was an extrapolation from fabricated examples. It is unwired, not retrained.

---

## Every value

| Value | Shown | Mark | Computed at | Source raster | Limitation / reason | Resolved by |
|---|---|---|---|---|---|---|
| `candidate_area_km2` | 0.0 km² | `MEASURED` | `build_analysis.py:1036` | native/cpr_native.tif + native/dop_native.tif | Pixel count passing both criteria, times the frame's own cell area. A measured zero here is a result, not a gap. | — |
| `cpr_max` | 0.053411 | `MEASURED` | `build_analysis.py:1008` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `cpr_mean` | 0.001312 | `MEASURED` | `build_analysis.py:1002` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Mean over the 2,337,086 pixels carrying amplitude. The request path reports 0.000221 by averaging across the never-observed void. | — |
| `cpr_p50` | 0.000565 | `MEASURED` | `build_analysis.py:1005` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `cpr_p90` | 0.003546 | `MEASURED` | `build_analysis.py:1006` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `cpr_p99` | 0.009258 | `MEASURED` | `build_analysis.py:1007` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `cpr_pass_fraction` | 0.0 | `MEASURED` | `build_analysis.py:1028` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Fraction of the measured swath with CPR > 1. | — |
| `cpr_std` | 0.00196 | `MEASURED` | `build_analysis.py:1009` | native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `criteria_passed` | 1 | `MEASURED` | `build_analysis.py:1039` | native/cpr_native.tif + native/dop_native.tif | Of 5 named criteria: CPR above CBOE threshold = FAIL, DOP depressed (volume scattering) = PASS, Overlap with a shadowed cold trap = WITHHELD, Overlap with a doubly-shadowed core = WITHHELD, Thermal stability expected = WITHHELD | — |
| `critical_hazard_fraction` | 0.114575 | `MEASURED` | `build_analysis.py:1070` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Fraction of the frame above a 0.70 composite hazard. The 0.70 cut is a display convention stated here, not a measured property; the hazard field under it is measured. | — |
| `dop_max` | 0.438779 | `MEASURED` | `build_analysis.py:1017` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `dop_mean` | 0.057053 | `MEASURED` | `build_analysis.py:1010` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Mean over the amplitude mask. The request path reports 0.009234. | — |
| `dop_min` | 0.0 | `MEASURED` | `build_analysis.py:1012` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Minimum over measured pixels only; the request path's 0.0 is padding. | — |
| `dop_p50` | 0.047532 | `MEASURED` | `build_analysis.py:1014` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `dop_p90` | 0.11868 | `MEASURED` | `build_analysis.py:1015` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `dop_p99` | 0.190668 | `MEASURED` | `build_analysis.py:1016` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Over the amplitude mask at native 25 m/px. The request path resamples to 100 x 100 and averages across the never-observed void, which moves CPR mean by 5.5x and destroys the DOP median outright. | — |
| `dop_pass_fraction` | 0.92714817 | `MEASURED` | `build_analysis.py:1030` | native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask) | Fraction of the measured swath with DOP < 0.13. | — |
| `hazard_p50` | 0.335508 | `MEASURED` | `build_analysis.py:1067` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Slope and roughness both come from measured LOLA topography, so the hazard blend is measured too -- but it is a two-term blend at 80 m posts, not the three-term one config.py describes. 80 m-POST QUANTITY. The gradient is taken on the 25 m… | — |
| `hazard_p90` | 0.721047 | `MEASURED` | `build_analysis.py:1068` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Slope and roughness both come from measured LOLA topography, so the hazard blend is measured too -- but it is a two-term blend at 80 m posts, not the three-term one config.py describes. 80 m-POST QUANTITY. The gradient is taken on the 25 m… | — |
| `hazard_p99` | 0.787368 | `MEASURED` | `build_analysis.py:1069` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Slope and roughness both come from measured LOLA topography, so the hazard blend is measured too -- but it is a two-term blend at 80 m posts, not the three-term one config.py describes. 80 m-POST QUANTITY. The gradient is taken on the 25 m… | — |
| `landable_slope_fraction` | 0.624944 | `MEASURED` | `build_analysis.py:1058` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Fraction at or below CRITICAL_LANDING_SLOPE_DEG = 12°. 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25… | — |
| `max_elevation_m` | 1957.37 m | `MEASURED` | `build_analysis.py:1076` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px native, bilinear to 25 m grid. Despite its filename, native/dem_native_synthetic.tif holds that measured LOLA topography bit-for-bit (verified every run: max\|diff\| 0.0 m against lola/ldem_fram… | — |
| `max_slope_deg` | 62.7868 ° | `MEASURED` | `build_analysis.py:1053` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `mean_hazard` | 0.364696 | `MEASURED` | `build_analysis.py:1066` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Slope and roughness both come from measured LOLA topography, so the hazard blend is measured too -- but it is a two-term blend at 80 m posts, not the three-term one config.py describes. 80 m-POST QUANTITY. The gradient is taken on the 25 m… | — |
| `mean_roughness_m` | 6.7183 m | `MEASURED` | `build_analysis.py:1062` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `mean_slope_deg` | 10.5766 ° | `MEASURED` | `build_analysis.py:1049` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `measured_area_km2` | 1460.68 km² | `MEASURED` | `build_analysis.py:1018` | native/valid_native.tif | Amplitude mask area: where DFSAR actually returned signal. Every MEASURED radar statistic on this page is taken over this and nothing else. | — |
| `min_elevation_m` | -4246.08 m | `MEASURED` | `build_analysis.py:1075` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px native, bilinear to 25 m grid. Despite its filename, native/dem_native_synthetic.tif holds that measured LOLA topography bit-for-bit (verified every run: max\|diff\| 0.0 m against lola/ldem_fram… | — |
| `pointed_area_km2` | 3327.84 km² | `MEASURED` | `build_analysis.py:1022` | native/footprint_native.tif (ISRO sri_ma) | ISRO sri_ma > 0: where the beam was pointed. The difference from the measured area is swath that was pointed at and returned literal zero. | — |
| `roughness_p50_m` | 5.8058 m | `MEASURED` | `build_analysis.py:1063` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `roughness_p90_m` | 12.9228 m | `MEASURED` | `build_analysis.py:1064` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `roughness_p99_m` | 21.649 m | `MEASURED` | `build_analysis.py:1065` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `safe_slope_fraction` | 0.896826 | `MEASURED` | `build_analysis.py:1054` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | Fraction of the frame at or below MAX_TRAVERSABLE_SLOPE_DEG = 20°, read from config.py. 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Re… | — |
| `screening_pass_fraction` | 0.0 | `MEASURED` | `build_analysis.py:1032` | native/cpr_native.tif + native/dop_native.tif | Fraction of the MEASURED SWATH passing both criteria — not of the frame. The frame is 84 % never-observed padding and a fraction over it would be meaningless. | — |
| `slope_p50_deg` | 9.343 ° | `MEASURED` | `build_analysis.py:1050` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `slope_p90_deg` | 20.1725 ° | `MEASURED` | `build_analysis.py:1051` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `slope_p99_deg` | 31.5309 ° | `MEASURED` | `build_analysis.py:1052` | native/dem_native_synthetic.tif = LOLA LDEM_80S_80M V2.0 | 80 m-POST QUANTITY. The gradient is taken on the 25 m grid, but LOLA measured the surface at 80 m posts and the upsample added no relief below that. Read this as a 80 m slope, not a 25 m one. Elevation is LOLA LDEM_80S_80M V2.0, 80 m/px na… | — |
| `conservative_volume_m3` | 0.0 m³ | `DERIVED` | `build_analysis.py:1089` | derived from candidate area — no raster of its own | candidate area x 2 m assumed depth x 0.05 assumed pore fraction. Both assumptions are untested in this build; neither is a measurement. | — |
| `expected_volume_m3` | 0.0 m³ | `DERIVED` | `build_analysis.py:1090` | derived from candidate area — no raster of its own | candidate area x 5 m assumed depth x 0.15 assumed pore fraction. Both assumptions are untested in this build; neither is a measurement. | — |
| `upper_volume_m3` | 0.0 m³ | `DERIVED` | `build_analysis.py:1091` | derived from candidate area — no raster of its own | candidate area x 10 m assumed depth x 0.3 assumed pore fraction. Both assumptions are untested in this build; neither is a measurement. | — |
| `ablation_runs` | — | `UNAVAILABLE` | `build_analysis.py:1094` | — | A real ablation reruns the planner with each hazard weight zeroed in turn and reports the measured deltas in distance, mean hazard and max slope. It needs the Phase 4 planner. The previous experiments_runner.py returned four hand-written e… | Phase 4 — replan with each hazard weight zeroed in turn |
| `boulder_risk` | — | `UNAVAILABLE` | `build_analysis.py:1074` | — | No boulder detector and no optical product exist in this build; data/pradan/ohrc/ is empty. Boulder risk is UNMEASURED, not zero. The weight is dropped and the blend renormalised over slope and roughness, so hazard is a two-term hazard and… | NEVER in this build — no optical product; WEIGHT_BOULDER = 0 (PRD §5) |
| `doubly_shadowed_area_km2` | — | `UNAVAILABLE` | `build_analysis.py:988` | — | A doubly-shadowed core is terrain that is never directly lit AND receives no scattered light from lit terrain. This build computes neither term. The previous definition -- the brightness proxy's shadow intersected with the lowest elevation… | Phase 2 — sky-view factor restricted to lit horizon |
| `landing_site` | — | `UNAVAILABLE` | `build_analysis.py:1079` | — | The five sites are hardcoded grid offsets (18,50 / 82,75 / 78,25 / 50,15 / 48,85), asserted and then scored, not searched -- and their lat/lon came from a flat 30.37 km per degree constant that is wrong by about 57x in longitude at this la… | Phase 3 — per-pixel six-criterion search over the native frame |
| `landing_site_score` | — | `UNAVAILABLE` | `build_analysis.py:1080` | — | The five sites are hardcoded grid offsets (18,50 / 82,75 / 78,25 / 50,15 / 48,85), asserted and then scored, not searched -- and their lat/lon came from a flat 30.37 km per degree constant that is wrong by about 57x in longitude at this la… | Phase 3 |
| `landing_sites_evaluated` | — | `UNAVAILABLE` | `build_analysis.py:1081` | — | The five sites are hardcoded grid offsets (18,50 / 82,75 / 78,25 / 50,15 / 48,85), asserted and then scored, not searched -- and their lat/lon came from a flat 30.37 km per degree constant that is wrong by about 57x in longitude at this la… | Phase 3 |
| `mean_illumination_fraction` | — | `UNAVAILABLE` | `build_analysis.py:993` | — | There is no illumination fraction here, only a brightness proxy. Illumination here is NOT a horizon computation. It is the expression hillshade(sun 1.5 deg) * elev_norm**1.3 -- an invented brightness proxy with no physical horizon in it, i… | Phase 2 — per-pixel lit fraction over a 360° solar azimuth sweep |
| `p_ice_max` | — | `UNAVAILABLE` | `build_analysis.py:1045` | — | WITHDRAWN, not missing. The Random Forest behind this figure was fitted to np.random.uniform labels with a fixed seed, and its ice class was defined as CPR 1.05-2.5 -- a range this amplitude-only product cannot reach at all, since the swat… | NEVER — withdrawn, not deferred. No ground-truth ice label exists in this project. |
| `p_ice_mean` | — | `UNAVAILABLE` | `build_analysis.py:1046` | — | WITHDRAWN, not missing. The Random Forest behind this figure was fitted to np.random.uniform labels with a fixed seed, and its ice class was defined as CPR 1.05-2.5 -- a range this amplitude-only product cannot reach at all, since the swat… | NEVER — withdrawn, not deferred. |
| `psr_area_km2` | — | `UNAVAILABLE` | `build_analysis.py:987` | — | The topography is measured, but the shadow on top of it is not. Illumination here is NOT a horizon computation. It is the expression hillshade(sun 1.5 deg) * elev_norm**1.3 -- an invented brightness proxy with no physical horizon in it, in… | Phase 2 — horizon computation over the full LDEM_80S_80M array |
| `rover_energy_wh` | — | `UNAVAILABLE` | `build_analysis.py:1085` | — | No traverse is planned from this file. The cost surface would be measured LOLA slope and hazard, but the target is still a hardcoded grid centre and no Dijkstra solve runs here, so a distance or an energy figure would be an unfinished code… | Phase 4 |
| `rover_mean_hazard` | — | `UNAVAILABLE` | `build_analysis.py:1086` | — | No traverse is planned from this file. The cost surface would be measured LOLA slope and hazard, but the target is still a hardcoded grid centre and no Dijkstra solve runs here, so a distance or an energy figure would be an unfinished code… | Phase 4 |
| `rover_traverse_km` | — | `UNAVAILABLE` | `build_analysis.py:1084` | — | No traverse is planned from this file. The cost surface would be measured LOLA slope and hazard, but the target is still a hardcoded grid centre and no Dijkstra solve runs here, so a distance or an energy figure would be an unfinished code… | Phase 4 — Dijkstra over a slope-and-hazard cost surface |
| `thermal_stability_k` | — | `UNAVAILABLE` | `build_analysis.py:997` | — | No thermal product is on disk and no thermal model runs in this build. Phase 2 derives a stability flag from the illumination fraction and labels it DERIVED, not MEASURED. | Phase 2 — DERIVED from illumination; no thermal product is on disk |

---

## Evidence checklist — the five named criteria

| Criterion | Measured | vs threshold | Verdict | Mark |
|---|---|---|---|---|
| CPR above CBOE threshold | 0.053411 (peak CPR in swath) | > 1.0 | FAIL | `MEASURED` |
| DOP depressed (volume scattering) | 0.047532 (median DOP) | < 0.13 | PASS | `MEASURED` |
| Overlap with a shadowed cold trap | — (no horizon computation) | — | **WITHHELD** | `UNAVAILABLE` |
| Overlap with a doubly-shadowed core | — (no scattered-light term) | — | **WITHHELD** | `UNAVAILABLE` |
| Thermal stability expected | — (no thermal model) | — | **WITHHELD** | `UNAVAILABLE` |

> 1 of 2 criteria that can be evaluated in this build passed. The other 3 are WITHHELD, not failed: two shadow terms awaiting the Phase 2 horizon computation, and thermal stability, for which no product and no model exist here. A withheld criterion is not evidence against ice.

> **This is a NULL RESULT on an incomplete measurement, not evidence against ice. Peak CPR in the swath is 0.0534 against a 1.00 threshold — the product cannot reach it, because this build derives CPR from amplitude alone. The Stokes S3 phase term from the complex sli products is required before this scene can be screened at all.**

---

## Why the ice screen is empty — an identity, not a measurement

This build forms both polarimetric quantities from the same two smoothed
amplitudes, so with `x = ln(lh/lv)`:

```
cpr = tanh(x/4)**2   dop = |tanh(x/2)|
=>  cpr = tanh(artanh(dop) / 2)**2
```

They are not two observables — they are **two reparameterisations of one**
**channel ratio**, 1 degree of freedom between them. So `DOP < 0.13` places a hard
ceiling on achievable CPR:

| | |
|---|---|
| Ceiling implied by the DOP gate | **CPR < 0.0042611** |
| Highest CPR observed where DOP passes | 0.0042611 |
| Configured `CPR_THRESHOLD` | 1 — **235× the ceiling** |
| Identity verified over | 2,337,086 pixels |
| max\|residual\| · rms · Pearson r | 1.241e-06 · 8.025e-09 · 0.999999999994 |

No pixel with DOP < 0.13 can exhibit CPR > 0.0042611, whatever the terrain and whatever the instrument. The configured CPR_THRESHOLD of 1 is 235x above that ceiling, so this screen is LOGICALLY EMPTY, not merely unsatisfied. A candidate area of exactly 0.0 is the only arithmetically possible answer, and a non-zero value here would be a bug rather than a detection.

The true Stokes forms are built from DIFFERENT combinations of the four Stokes parameters -- CPR = (S0 - S3)/(S0 + S3) and DOP = sqrt(S1^2 + S2^2 + S3^2)/S0 -- so they are genuinely independent and their conjunction selects a real population. The amplitude proxy's defect is not that it is small: it collapses two independent physical observables onto one degree of freedom. Phase 5b.

---

## Sensitivity — measured, not scaled

Each row re-thresholds the native arrays and counts pixels, so every area is a
measurement. Marked `●` is the configured operating point.

### cpr threshold (baseline 1)

| Threshold | Pixels | Area km² | Volume m³ |
|---|---:|---:|---:|
| 0 | 2,166,823 | 1354.2644 | 1,015,698,281 |
| 0.000565 | 998,738 | 624.2112 | 468,158,438 |
| 0.003546 | 63,481 | 39.6756 | 29,756,719 |
| 0.009258 | 0 | 0.0000 | 0 |
| 0.016204 | 0 | 0.0000 | 0 |
| 0.053411 | 0 | 0.0000 | 0 |
| 0.15 | 0 | 0.0000 | 0 |
| 0.3 | 0 | 0.0000 | 0 |
| 0.45 | 0 | 0.0000 | 0 |
| 0.6 | 0 | 0.0000 | 0 |
| 0.75 | 0 | 0.0000 | 0 |
| 0.9 | 0 | 0.0000 | 0 |
| 1 ● | 0 | 0.0000 | 0 |
| 1.05 | 0 | 0.0000 | 0 |
| 1.2 | 0 | 0.0000 | 0 |

### dop threshold (baseline 0.13)

| Threshold | Pixels | Area km² | Volume m³ |
|---|---:|---:|---:|
| 0 | 0 | 0.0000 | 0 |
| 0.047532 | 0 | 0.0000 | 0 |
| 0.0625 | 0 | 0.0000 | 0 |
| 0.11868 | 0 | 0.0000 | 0 |
| 0.125 | 0 | 0.0000 | 0 |
| 0.13 ● | 0 | 0.0000 | 0 |
| 0.1875 | 0 | 0.0000 | 0 |
| 0.190668 | 0 | 0.0000 | 0 |
| 0.25 | 0 | 0.0000 | 0 |
| 0.250531 | 0 | 0.0000 | 0 |
| 0.3125 | 0 | 0.0000 | 0 |
| 0.375 | 0 | 0.0000 | 0 |
| 0.4375 | 0 | 0.0000 | 0 |
| 0.438779 | 0 | 0.0000 | 0 |
| 0.5 | 0 | 0.0000 | 0 |

> candidate_area_km2 is a pixel count times the frame's own cell area, so it is MEASURED at every row. volume_m3 is DERIVED from it by the assumed depth and pore fraction. The CPR axis is degenerate at the configured operating point: the swath's peak CPR is 0.053411, so every threshold at or above it returns exactly zero pixels. That flat line is the measurement, not a defect in the sweep.

---

## Volume tiers — assumptions carried as data

| Tier | Assumed depth | Assumed pore fraction | Volume | Rate |
|---|---:|---:|---:|---:|
| conservative | 2 m | 0.05 | 0 m³ | 100,000 m³ per km² |
| expected | 5 m | 0.15 | 0 m³ | 750,000 m³ per km² |
| upper | 10 m | 0.3 | 0 m³ | 3,000,000 m³ per km² |

---

## What each stage can show

| # | Stage | Status | Basis |
|---:|---|---|---|
| 1 | Target Selection | `COMPLETE` | Crater catalogue plus the frame's own georeferencing. |
| 2 | Shadow & PSR | `UNAVAILABLE` | The topography is measured, but the shadow on top of it is not. Illumination here is NOT a horizon computation. It is the expression hillshade(sun 1.5 deg) * elev_norm**1.3 -- an invented brightness proxy with no physical horizon in it, inherited from the ingest path. It puts 77 % of the frame belo… |
| 3 | DFSAR Radar | `COMPLETE` | Masked native statistics from the calibrated L2 amplitude products. |
| 4 | Ice Criteria Screen | `COMPLETE` | Five named criteria. Two are measured and evaluated; three are withheld (two shadow terms, one thermal) and say so. |
| 5 | Terrain Hazards | `COMPLETE` | Slope, roughness and hazard from measured LOLA topography. |
| 6 | Landing Sites | `UNAVAILABLE` | The five sites are hardcoded grid offsets (18,50 / 82,75 / 78,25 / 50,15 / 48,85), asserted and then scored, not searched -- and their lat/lon came from a flat 30.37 km per degree constant that is wrong by about 57x in longitude at this latitude. Withheld until the Phase 3 per-pixel search over the… |
| 7 | Rover Traverse | `UNAVAILABLE` | No traverse is planned from this file. The cost surface would be measured LOLA slope and hazard, but the target is still a hardcoded grid centre and no Dijkstra solve runs here, so a distance or an energy figure would be an unfinished code path rather than a result. Phase 4. |
| 8 | Volume Estimate | `COMPLETE` | Three DERIVED tiers over the measured candidate area, each carrying its own assumed depth and pore fraction as data. |
| 9 | Sensitivity Studio | `COMPLETE` | Real sweeps computed by re-thresholding the native arrays. |
| 10 | Ablation | `UNAVAILABLE` | A real ablation needs the Phase 4 planner to rerun with each hazard weight zeroed. The previous four hand-written experiments were deleted in Phase 0. |
| 11 | Viva Rationale | `COMPLETE` | Reads the evidence rows and the provenance legend in this file. |
| 12 | Provenance | `COMPLETE` | Source rasters, masks, thresholds and the generator that produced this file. |

