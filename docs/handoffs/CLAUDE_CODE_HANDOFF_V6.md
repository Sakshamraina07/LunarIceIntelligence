# Claude Code handoff v6 — the analysis panel is serving fabricated "ice found" numbers

> Same session. Read section 1 before doing anything else, including 3b/3c and the LOLA DEM.
> Section 0 is me conceding two points to you.

---

## 0 · Accepted — you were right and I was wrong, twice

**The valid mask is not a bug. I withdraw section 1 of v5.** Your test of the raw pre-geocoding `gri` frame is the correct experiment and it settles it: 786 samples × 25.0 m = 19,650 m matches `isda:swath` exactly, with no projection, padding or rotation in the way, and amplitude in that rectangle is still only 46.34 % with a p50 per-line extent of 352 samples = 8.80 km and zero interior holes on 265/265 sampled lines. The area closure both ways (amplitude 1501.2 vs 1460.7 km², +2.77 %; footprint 3239.8 vs 3327.8 km², −2.65 %) confirms geocoding lost nothing. The across-track staircase — 0 → 36.26 → 97.04 → 63.75 → 2.95 → 0 % — is a receive window narrower than the nominal swath walking across range down-track. The data is not there to recover.

My error was conflating two different quantities. ISRO's 35.6 % is **where the beam pointed**. 15.64 % is **where signal came back**. Three ISRO sources agreeing on 35.6 % told me the mask was lossy; what they actually told me is the swath outline. Your two-mask model is the right answer, and `amplitude / footprint = 43.89 %` is a real, publishable number — "the fraction of the pointed swath that returned signal" is a better sentence than anything v5 would have produced.

**And the stretches never needed refitting.** You are right that `fitted_over_fraction: 0.156395` is the whole amplitude population, not a bright subset of it — the excluded pixels are literal integer zeros, not dim-but-real returns. My 44 % was amplitude-as-a-fraction-of-swath. Nothing was biased. Good that you pushed back instead of refitting on my word.

Also accepted: the pane-sibling explanation for `total_paths: 32`, the `document.hidden` / `requestAnimationFrame` note about animated Leaflet moves stalling under automation, and `dop_heatmap` now exposed.

The two-tier map is the best thing in this project so far. Black = never observed, grey = pointed but silent, turbo = measured signal. It reads like a real instrument product instead of a poster.

## 1 · STOP — your screenshot contradicts your own report, and the screenshot is the dangerous one

Your report text says the verdict card reads **72 % above `Mean P(ice) 0.00 · confidence Low · screening NOT PASSED` with 5/5 ✗**, and that native CPR is `max 0.053411 / p50 0.000565`.

The screenshot you delivered in the same message says something completely different:

| panel value in the screenshot | your report / your measured arrays |
|---|---|
| PEAK MODELLED P(ICE) **96 %**, "PROMISING CANDIDATE" | 72 % |
| `Mean P(ice) 0.96 · confidence High · screening PASSED` | `0.00 · Low · NOT PASSED` |
| evidence checklist **5/5 ✓** | 5/5 ✗ |
| CPR (MEAN) **0.525**, peak **2.292** | max **0.0534**, p50 0.000565 |
| DOP (MEAN) 0.529, min 0.04 | p50 0.0475 |
| MEAN SLOPE **8.24°**, max 70.6° | M2 slope p50 **1.8083°** |
| PSR AREA **79.62 km²** | 533 km² |
| ICE VOLUME **17.58M m³** | 0.00M m³ |
| ROVER **13.69 km** | 9.79 km |

Every number moved. A CPR mean of 0.525 with a peak of 2.292 cannot come from an array whose maximum is 0.0534 — those are textbook published lunar values, which is exactly what makes them so convincing and so fake.

**Most likely cause, which you should confirm first:** you restored `frontend/.env.local` to `VITE_API_BASE=https://lunariceintelligence.onrender.com` and stopped the local uvicorn. So `localhost:3000` is a Vite dev server drawing its **map** from local static WebP (backend-independent, exactly as designed) while drawing its **analysis** from the **deployed Render backend running pre-change code in `data_mode: DEMO`**. The two halves of that screen come from different code and different data modes. Check whether the frontend also has a mock/demo fallback that engages when the API errors — that would produce the same symptom.

### Why this is now the top priority

In that screenshot the CPR legend truthfully says *"this build's CPR is σ_sc/σ_oc from amplitude only, max 0.053; true hybrid-polarity CPR needs the Stokes S3 phase term."* Thirty centimetres to its right the app says **96 %, PROMISING CANDIDATE, screening PASSED, five green ticks, 17.58M m³ of ice.**

That is worse than the contradiction v5 flagged. v5's card was self-defeating — big number, ✗ column. This one is *coherent and wrong*: a reviewer sees measured Chandrayaan-2 imagery next to a confident, internally consistent "we found ice" verdict, with one small `DEMO` chip in the header as the only defence. If this is what the deployed URL serves, the live site currently claims a discovery.

## 2 · The fix — precompute the analysis and serve it statically, exactly like the layers

First, three diagnostics I want printed before any code changes:

1. `curl` the deployed Render backend's mission endpoint and print the raw `data_mode`, `data_source_tag`, `mean_cpr`, `max_cpr`, `radar_anomalous_area_km2` and `classification_label`. Confirm it is DEMO.
2. Run the same endpoint against the **local** backend on the current code and print the same fields. Confirm it returns the measured values.
3. Grep the frontend for any mock/fallback/demo fixture that supplies mission data when the API fails, and report whether it can substitute silently.

Then the architectural fix, which is the same move that already fixed the map:

**The analysis result is a constant.** The rasters never change, the thresholds are in `config.py`, and the pipeline is deterministic. There is no reason to compute it per request on a 512 MB free-tier instance that cannot hold the native arrays — which is very likely *why* the deployed build falls back to DEMO in the first place. Check the Render instance memory limit against `2258 × 6618 × 4 bytes = 59.8 MB` per float32 array and count how many the request path holds simultaneously; if the real path cannot fit, DEMO is not a bug on Render, it is the only thing that can run there, and no frontend change will fix that.

So: **precompute the real analysis offline and commit it as a static asset**, next to `layers.json`.

- New script emits `frontend/public/analysis/faustini.json` (and one per crater) from the real arrays, with the same provenance discipline as `layers.json` — `data_mode: "REAL"`, source rasters, thresholds used, and a per-criterion evidence block carrying the actual measured value beside the actual threshold.
- The mission view loads that JSON from the CDN. No backend, no cold start, no DEMO fallback path for the default view.
- Keep the backend for what genuinely needs computation on demand: the sensitivity studio, custom thresholds, report generation. Those can fail loudly without taking the headline verdict with them.
- Regenerating it becomes part of the same command that regenerates the layers, so the imagery and the numbers can never again describe different data.

**And make the mode structurally visible, not a chip.** Whatever the source, no fabricated number should be able to render in the same visual register as a measured one. Minimum bar: every value in the verdict card and the context bar carries its own provenance mark — `MEASURED`, `MODELLED (synthetic DEM)`, or `SIMULATED` — and `SIMULATED` values render visibly degraded (muted, struck, or replaced by an em dash with the label). If the app cannot get real numbers, it should say so in the place where the number would have been, not substitute a plausible one.

This supersedes v5 §3c. Do not just rewrite the headline; remove the mechanism that lets a simulated verdict occupy the same slot as a measured one.

## 3 · Then v5 §3b, unchanged

Un-gate the map from the mission JSON — `MissionControl.tsx:118` `{mission && <MissionMap …/>}`. Additive widening of `Props` only, `MissionMapHandle` byte-identical, terrain and footprint render while analysis is pending, honest `ANALYSIS PENDING` chip, no placeholder markers. After section 2 this becomes mostly moot for the default view, but it still matters for the endpoints that stay live.

## 4 · Then the real LOLA DEM — with one new constraint from your screenshot

Section 2 of v5 stands as written: same south polar stereographic projection, same 1737.4 km radius, so DFSAR pixel → LOLA pixel is scale-and-offset plus bilinear, window-sliced with `np.memmap`, label-parsed, validated on `ldem_75s_240m` first, output filenames unchanged, synthetic block and the `s0_resampled` modulation deleted.

**New constraint the screenshot revealed:** your void scrim is `#03060c` at **0.82 opacity** over the never-observed region. That is right today, because outside the swath there is genuinely nothing but placeholder terrain. Once LOLA lands it becomes wrong — that region will hold *real measured topography*, and an 82 % scrim will hide the best new asset in the project. Plan for the scrim to express "no radar here" without also meaning "no data here": drop it to a light tint, or switch to a sparse diagonal hatch, so real crater relief reads through while the radar boundary stays unambiguous. Two masks, two meanings — same discipline you applied to footprint versus amplitude.

## 5 · Unchanged from v5

Do not retune `CPR_THRESHOLD`. `CPR = ((√lh − √lv)/(√lh + √lv))²` is a squared channel-imbalance ratio that collapses to zero whenever LH ≈ LV, which is the normal regolith case — your `p50 = 0.000565` is that algebra, not the Moon. Only real `S3 = 2·Im⟨E_H·E_V*⟩` from the complex `sli` products fixes it (P3), and `module_b_radar.py` already has the correct `compute_cpr_from_stokes()`.

Still open: `module_b_radar.py` lines 113–116 assert the ice interpretation at 0.00 km²; `mission_service.py` `pixel_scale_m = 250.0`; `target_coordinates {x: 50, y: 50}` is the grid centre and all three routes terminate there at `science_value: 0`; the five landing sites are hardcoded and, as the screenshot shows, Site 1 and its traverse sit in the void outside the amplitude ribbon. All P4, and all much easier after the real DEM.

Approved and still pending: `git rm -r backend/tiles/faustini backend/scripts/generate_tiles.py backend/scripts/compare_tiles_vs_single.py`, with the per-tile brightness table in the commit body and the before/after PNG preserved in `docs/`.

## 6 · Order of work

1. The three diagnostics in section 2. Report before changing anything.
2. Static precomputed analysis JSON + per-value provenance marks. This is the fix for the fabricated verdict.
3. v5 §3b un-gating.
4. Real LOLA DEM, with the scrim change.
5. P3, then P4.

Gate: after step 2, show me the same screenshot again — same layer, same zoom — and I want the verdict card, the five checklist rows and all eight context-bar values to be reconcilable line-by-line against the printed measured statistics. If a value cannot be traced to a measurement, it should not be a number on that screen.

Return each touched file complete. `MissionMapHandle` byte-identical throughout.


