# Claude Code handoff v2 — Lunar Ice Intelligence (map quality + science correctness)

> Paste everything below the divider into Claude Code, launched from inside `D:\FYP`.
> Self-contained: Claude Code starts with zero memory of previous sessions.
> **v2 supersedes the earlier handoff.** The NASA/polar-CRS plan in v1 was investigated and
> killed — do not resurrect it. See "Dead ends" below.

---

You are continuing my final-year project **"Lunar Ice Intelligence & Traverse Planning System"** — a mission-planning web app that detects *possible* water ice at the Moon's south pole from Chandrayaan-2 DFSAR radar, picks a safe landing site, and plans a rover route. Its core value is one end-to-end go/no-go pipeline plus a scientific-honesty UI ("possible ice", never "confirmed").

## Repo layout

`D:\FYP` — `frontend/` (React 19 + TypeScript + Vite 8 + Tailwind v4 + Leaflet 1.9 + React-Three-Fiber, deployed on Vercel) and `backend/` (Python 3.12 FastAPI + NumPy/SciPy/scikit-learn/OpenCV/Pillow/ReportLab, deployed on Render). Data in `D:\FYP\data\pradan\` (processed) and `D:\FYP\data\pradan\raw\` (the PDS4 bundle). Science modules A–G in `backend/app/modules/`.

## How I want you to work

- **You do the coding.** When you change a file, read the WHOLE file, edit it, and give me back the **complete updated file** — never snippets or partial diffs — so I can drop-in replace.
- **Explain simply:** open each explanation with a short real-life analogy, then the technical detail, with generous line spacing.
- **Verify by running.** After each change, actually run it and look at the output (screenshot the map). Do not assume.
- **Do not invent data.** This codebase already has synthetic data masquerading as real (details below) and it is my single biggest risk. If something can't be computed from real data, label it clearly rather than faking it.
- Read files yourself; everything is in the repo.

## My two goals

1. **Map must look clear, sharp and real.** Right now it is blurry, faded, patchy and "weird", and the ice signal doesn't read.
2. **Landing-site recommendation must be data-driven with visible per-criterion proofs.** A review panel already called similar work "trivial", so defensibility is the point.

## Dead ends — already investigated, do NOT spend time here

**NASA Moon Trek polar basemap + `LunarSouthPoleCRS` switch: abandoned.**
Every `trek.nasa.gov/tiles/Moon/SP/...` URL 404s (product capabilities, service capabilities, all layer-name variants); the apidoc's South Pole section is empty. Only global equirectangular sets are live (`LRO_WAC_Mosaic_Global_303ppd_v02`, `LRO_LOLA_ClrShade_Global_128ppd_v04`, both HTTP 200 with `Access-Control-Allow-Origin: *`).

Independent of the 404s, the idea is structurally wrong: **Leaflet cannot reproject raster tiles client-side.** Pre-rendered WMTS tiles are bitmaps locked to their own projection, so global equirectangular tiles can never align inside a polar-stereographic CRS — and at −85° latitude they are smeared and coarse anyway. `frontend/src/utils/lunarCRS.ts` therefore has nothing to align to. Leave it unused; don't delete it, just don't wire it up.

**Consequence:** all map-quality gains must come from *my own* tiles. That is fine — the bugs below are the real cause of the bad map, not the missing basemap.

## Ground truth: what is real and what is fake (verified — trust this section)

**REAL:** the raw Chandrayaan-2 DFSAR PDS4 bundle in `D:\FYP\data\pradan\raw\data\calibrated\20200808\`. Observation 2020-08-08, orbit 4265, Faustini / south pole. Both L-band (`ncxl`) and S-band (`ncxs`) exist. Products per band: `gri` (ground-range amplitude), `sri` (slant-range amplitude), `sli` (slant-range **complex**), `in` (incidence angle), `ma`, plus `geometry/` and `browse/`.

Key geometry from `ch2_sar_ncxl_20200808t201154198_d_gri_xx_cp_xx_d18.xml`:
- **16943 lines × 786 samples**, `UnsignedLSB2`
- `output_line_spacing` **9.731043 m**, `output_pixel_spacing` **25.0 m**, `swath` 19650 m
- → real footprint ≈ **165 km along-track × 19.65 km across-track, aspect ratio ≈ 8.4 : 1**, with **non-square pixels**
- corners UL(−89.511, −65.405) UR(−89.377, −144.374) LR(−77.444, 167.921) LL(−77.679, −100.425), centre (−84.145, 90.136)
- StripMap, L-band, incidence ≈ 20°, 21 azimuth looks, calibration constant 70.308868 dB, gain LH 1.018442 / LV 1.000923
- Moon radius **1,737,400 m**

The `sli` products are `ComplexLSB8`, **355768 × 759**, ≈ 2.17 GB each for LH and LV. **These are where the ~9 GB comes from** — the 9 GB is the bundle, not one file, and nothing needs hosting.

**FAKE #1 — the DEM is 100 % synthetic.** `backend/scripts/process_real_sar_pipeline.py` lines ~117–133 build elevation from `np.linspace` + `meshgrid` + hand-placed `np.exp` Gaussian blobs + `sin/cos` ripples, then lines 153–156 write that same array to `real_dem.tif`, `ch2_sar_dem.tif`, `faustini_lola_dem.tif` and `shackleton_lola_dem.tif`. **Files named `*_lola_dem.tif` contain zero LOLA data.** Every downstream product — slope, roughness, hazard, illumination, landing scores, rover routes — runs on invented terrain.

**FAKE #2 — the georeferencing is hardcoded.** `metadata_real.json` `bounds` (min_lat −89.5108, max_lat −84.8333, min_lon −19.2567, max_lon 96.6885) are literal constants typed into `process_real_sar_pipeline.py` lines ~168–173, not derived from the data. They contradict the PDS4 label, whose corners reach **−77.44°**, not −84.83°. So there is currently **no real coordinate frame** — which is why a real DEM cannot simply be dropped in without fixing this first.

**FAKE #3 — "CPR" and "DOP" are not CPR and DOP.** The pipeline reads amplitude-only `sri` rasters and computes `0.5(√LH − √LV)² / 0.5(√LH + √LV)²` as "CPR" and `|LH − LV| / (LH + LV)` as "DOP". True hybrid-polarity CPR needs the phase term `2·Im⟨E_H·E_V*⟩`, which amplitude data cannot provide. The tell-tale: measured `cpr_mean` = **0.0153**, `cpr_max` = **0.294**, while published lunar CPR is ≈0.3–0.7 for normal regolith and 0.7–1.3+ for anomalous polar terrain. Being 20–40× low is a broken derivation, not an unusual Moon.

**Consequence — the headline feature is dead.** `backend/app/modules/module_b_radar.py:96` is `radar_mask = (cpr > cpr_th) & (dop < dop_th)` with `CPR_THRESHOLD = 1.00` (`backend/app/core/config.py:29`). Since `cpr_max` = 0.294, **zero pixels ever qualify**: `radar_anomalous_area_km2` is always 0.00 and `classification_label` (line 141) is permanently "Low/No ice signature". Also `module_b_radar.py` lines 113–116 print "Radar signature consistent with potential ice-bearing volume scattering" even when the detected area is 0.00 km² — fix that contradiction.

**Good news:** the phase data is already in the bundle (`sli`, complex), and `module_b_radar.py` already contains correct `compute_cpr_from_stokes()` and `compute_dop_from_stokes()` implementations. The pipeline simply never feeds them real Stokes parameters.

**Unverified — check before trusting:** `data/pradan/ohrc/{faustini,shackleton,shoemaker}_ohrc_pan.tif` and `data/pradan/dem/shoemaker_lola_dem.tif` are not written by `process_real_sar_pipeline.py`, so their provenance is unknown. Given the precedent above, assume synthetic until proven otherwise. If the OHRC panchromatic rasters *are* real, they are 0.25 m/px and would be an excellent deep-zoom layer.

# MAP QUALITY — the specific bugs, ranked

This is my priority. All line numbers are in `backend/scripts/generate_tiles.py` unless stated. Fix them in this order; the first three are cheap and account for most of the ugliness.

### M1. Per-tile contrast normalization → patchwork tiles (**worst offender**)

`array_to_rgba_tile()` receives one 256×256 tile and computes its stretch from *that tile alone* — line 36–41 `vmin = np.percentile(slice_data[valid], 1)` / `vmax = ...99`, and again line 58–59 with 2/98 for science layers. So **every tile gets its own brightness and colour mapping**, producing visible tile-to-tile jumps — a patchwork grid — and amplifying noise in flat tiles to full contrast.

Fix: compute `vmin`/`vmax` **once per layer** from the full array, then pass them into every tile. Keep the percentile idea, just hoist it out of the tile loop.

### M2. Hillshade and slope use a cell size that is 10–25× too large → flat, faded relief

Line 77 `dy, dx = np.gradient(dem, 250.0)` and line 140 the same 250.0. Real spacing is **9.731 m along-track and 25 m across-track**. Using 250 m shrinks every gradient by ~10–25×, so the hillshade is nearly flat and the terrain reads as washed-out plastic.

Same bug breaks the science: `slope_deg` (line 141) is ~10× too small, so `hazard` (line 145) is near zero everywhere, and `MAX_TRAVERSABLE_SLOPE_DEG = 20` / `CRITICAL_LANDING_SLOPE_DEG = 12` in `config.py` can essentially never trigger. One constant is corrupting both the look and the landing safety logic.

Fix: pass the real anisotropic spacing — `np.gradient(dem, dy_spacing, dx_spacing)` — and derive those from the PDS4 label rather than hardcoding.

### M3. Contrast stretch is wrong for the CPR distribution → the ice layer is invisible

CPR is severely right-skewed: min 0.010, median 0.0125, mean 0.0153, max 0.294. A linear stretch across that range maps the median to roughly **2 out of 255** — half the image renders as near-black. This is exactly the "what I want to show doesn't show" complaint.

Fix: use a log or robust percentile stretch tuned to the actual histogram (print the histogram first), and clamp outliers. Do this per layer, not per tile (see M1).

### M4. Frontend upscales tiles → blur

`frontend/src/mission/MissionMap.tsx` sets `maxZoom: 6` but `maxNativeZoom: MAX_NATIVE` (= 3), so Leaflet stretches z3 bitmaps across three further zoom levels.

Fix, in order of preference: (a) generate more real native levels (M6) and raise `maxNativeZoom`; (b) clamp `maxZoom` to the real native max so users never see fake detail; (c) if overzoom must stay, set `image-rendering: pixelated` on the tile images so it looks honestly blocky instead of mushy, and show an "overzoomed — beyond native resolution" badge.

### M5. Science overlays are double-washed-out

`generate_tiles.py` already sets alpha 230, and `MissionMap.tsx` additionally puts the `mc-science` pane in `mixBlendMode: 'soft-light'`. Soft-light is a contrast-*reducing* blend, so the data is faded twice.

Fix: use `normal` blending with a user-facing opacity slider, or `overlay`/`multiply` if you want the hillshade to show through — and let me see a screenshot comparison before you commit to one.

### M6. The pyramid is a square upsample of a downsampled source → wrong shape and no real detail

Line 90 `zoom_dim = 256 * (2 ** z)` with `max_zoom = 3`, and line 93 `cv2.resize(full_data, (zoom_dim, zoom_dim), ...)` **forces a square**. The true swath is **8.4 : 1**, so the map geometry is off by ~8×. That is the "ajeeb" look.

Worse, the source is already tiny: `process_real_sar_pipeline.py` `__main__` calls `process_real_data(512)`, i.e. everything is resampled to 512², while `metadata_real.json` claims `grid_size [2048, 2048]`. **These disagree — check the actual `.tif` dimensions on disk with `tifffile` before doing anything.** If the source really is 512², then z3 (2048²) is a 4× *upsample* and the blur is baked in before tiling even starts.

Fix: stop resampling to a square. Re-run the SAR pipeline preserving the native 16943 × 786 grid (windowed reads, never load a huge file whole), tile the true rectangular extent, and let the pyramid depth follow real pixels. Current output is 85 tiles/layer × 6 layers = 510 PNGs; expect substantially more.

### M7. Colormap choices

Line 152 uses `COLORMAP_JET` for hazard. JET is perceptually non-uniform and invents false edges — a standard criticism in any review. Use a perceptually uniform sequential map (VIRIDIS / MAGMA / CIVIDIS) for magnitude layers and reserve diverging maps for signed quantities. TURBO for CPR is acceptable but justify it.

### M8. Illumination is not illumination

Line 146 `illumination = hillshade * normalized_elevation**1.2` is invented. Real lunar polar illumination needs **horizon-angle / shadow ray-casting** across the DEM with the sun within ~1.5° of the horizon. This matters twice over: permanently shadowed regions (PSRs) are the whole reason to look for ice, and a real shadow map is visually striking (crisp black basin floors) instead of a soft gradient.

Fix after the real DEM lands. Implement a proper horizon scan; label it with the solar geometry used.

### Also
`PRADAN_DIR = Path("d:/FYP/data/pradan")` (line 21) is a hardcoded absolute path — make it relative to `BASE_DIR`. And the module docstring claims "100% native resolution from 1782x6605 raw swath", which matches nothing real; correct it so the next person isn't misled.

# Environment constraints (important)

- Local Python has **only numpy / cv2 / PIL / scipy / tifffile**. **No rasterio, no GDAL, no gdalinfo.** Do not add `rasterio` to `requirements.txt` — Render cannot build scipy from source and the deploy will break.
- Real LOLA is still reachable without GDAL: PDS polar GDR `.img` files are **raw binary**, readable with `np.memmap` (windowed slicing touches only the bytes you need); dimensions, `MAP_SCALE`, `SAMPLE_TYPE`, `SCALING_FACTOR` and `OFFSET` come from the small plain-text `.lbl`. Confirmed live: `ldem_80s_20m.img` ≈ 1.85 GB, with smaller `ldem_75s_240m` / `ldem_75s_120m` variants. **Use an 80S or 75S product** — the 87S products are too narrow, and the craters analysed sit at Faustini ≈87.2°S, Shoemaker ≈88.1°S, Shackleton ≈89.9°S.
- **Re-tiling is deploy-safe.** The tile PNGs are committed to git and served statically, so regenerating them is a local-only operation.
- Never `imread` a multi-GB raster whole. Windowed / memmapped reads only.

# Priority order

**P0 — real georeferencing.** Replace the hardcoded `bounds` in `process_real_sar_pipeline.py` with a real grid→lat/lon mapping derived from the PDS4 label's four corner coordinates. Cheap, and a hard prerequisite for P1: you cannot align a real DEM to the SAR strip without a real coordinate frame.

**P1 — map quality M1–M3, then M4–M7.** M1, M2 and M3 are small edits with the largest visible payoff; do them first and show me before/after screenshots. Then the structural work in M6.

**P2 — real LOLA DEM.** Swap the synthetic block (lines ~117–133) for a real LOLA south-polar DEM clipped to the Faustini footprint. **Keep the output filenames identical** (`real_dem.tif`, `ch2_sar_dem.tif`, `faustini_lola_dem.tif`, `shackleton_lola_dem.tif`) so nothing downstream needs touching. Then re-run and confirm slope/hazard maps show actual craters. This is what finally makes the base layer look like the Moon.

**P3 — real Stokes CPR/DOP from the complex `sli` products.** Highest effort, highest value: it resurrects the dead ice detector and it is the concrete answer to "this is trivial". Approach: `np.memmap` the complex rasters, multi-look in row blocks (the label indicates 21 azimuth looks), form the full Stokes vector including the phase term, then feed the existing `compute_cpr_from_stokes()` / `compute_dop_from_stokes()`. Note `sli` is slant-range L1A, so geocoding to ground range is part of the job.
*Honest cheaper fallback if this proves too expensive:* rename the quantity to what it actually is (a linear depolarization ratio), drop the `CPR > 1` claim, and recalibrate the threshold to the real histogram. Weaker project, but not misleading. Ask me before choosing the fallback.

**P4 — real illumination / PSR map (M8), then landing-site search.** Replace the 5 hardcoded sites in `backend/app/modules/module_e_landing.py` (`Alpha Ridge 18,50 · Beta Plateau 82,75 · Gamma Bench 78,25 · Delta Spur 50,15 · Epsilon Crest 48,85`) with a **per-pixel suitability search**: score every cell on safety (slope/roughness/hazard), illumination, science value (CPR/DOP against `config.py` thresholds) and distance; apply **non-maximum suppression** so picks spread out; return top-N each with a **per-criterion evidence breakdown** ("slope 6.2° < 12° ✓", "CPR 0.31 vs threshold 1.00 ✗") plus a suitability heatmap layer and provenance for every number. Surface the proofs in the UI.

# Verification I expect from you

1. Before editing `generate_tiles.py`, print the **actual on-disk shapes and value histograms** of `cpr_real.tif`, `dop_real.tif`, `real_dem.tif` — do not trust `metadata_real.json` (its `grid_size` says 2048² while the pipeline's `__main__` passes 512).
2. Check whether `data/pradan/ohrc/*_ohrc_pan.tif` and `dem/shoemaker_lola_dem.tif` are real or synthetic, and tell me which.
3. Compare your rendered tiles against ISRO's own browse image in `data/pradan/raw/browse/` as a sanity check on shape and orientation.
4. Run the frontend (`cd frontend && npm install && npm run dev`) and **screenshot the map after each change**. Iterate until it is sharp and seamless. Confirm the existing `Props` and `MissionMapHandle` (`zoomIn`/`zoomOut`/`reset`) still work so `MissionControl.tsx` and `config.ts`'s `LAYER_MAP` don't break.
5. State plainly which numbers in the final UI come from real measurements and which are modelled or assumed.

# Housekeeping

I have uncommitted map-realism work that was built and verified (DEMO badge, scale bar, soft-light data blending, legend hint). Commit it before starting so you have a clean baseline:

```
git add frontend/src/mission/MissionControl.tsx frontend/src/mission/MissionMap.tsx frontend/src/mission/mc.css && git commit -m "Map realism: terrain/science panes, scale bar, legend hint, honest zoom readout"
```

# Where to start

Read `backend/scripts/generate_tiles.py`, `backend/scripts/process_real_sar_pipeline.py`, `frontend/src/mission/MissionMap.tsx`, `backend/app/modules/module_b_radar.py` and `backend/app/core/config.py`. Run verification step 1. Then tell me your exact plan for **P0 + M1–M3** before you edit anything — and give me the complete updated file for each change, with a simple explanation.



