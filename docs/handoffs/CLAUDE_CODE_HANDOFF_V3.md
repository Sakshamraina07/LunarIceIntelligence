# Claude Code handoff v3 — corrections + revised phase plan

> Paste everything below the divider into Claude Code in the same session that produced
> the verification report (it has the context). If starting fresh, also read
> `CLAUDE_CODE_HANDOFF.md` history in git for background.

---

Your verification work was good — the bit-exact DEM reconstruction (`corr = 1.0000000000`) and the OHRC generator-signature catch are both quotable evidence. Baseline commit `768ef28` acknowledged. Findings ①, ②, ⑤ accepted. Finding ③ is wrong, and correcting it collapses most of the remaining complexity. Read this before writing code.

## Correction to finding ③ — do NOT switch `sri` → `gri`

I checked the labels directly.

`ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18.xml`:
- `product_type` = **L2-SELENOREF** (seleno-referenced, not raw slant range)
- `output_line_spacing` = **25.000000 m**, `output_pixel_spacing` = **25.000000 m** → **isotropic**
- `no_scans` = **2258**, `no_pixels` = **6618**; Array_2D_Image axes confirm Line 2258 × Sample 6618
- `swath` = 19650 m

So the array the pipeline already reads is `(2258, 6618)`, isotropic 25 m, footprint **56.45 km × 165.45 km**, aspect **2.93 : 1**. It is referenced. The premise "slant range, not map-projected" does not hold for this product.

## Correction to finding ④ — ISRO shipped a geolocation grid **for `sri`** too

`geometry/calibrated/20200808/ch2_sar_ncxl_20200808t201154198_g_xxx_xx_cp_xx_d18.xml` declares three separate grids, and the directory contains three matching CSVs:

| grid | records | samples | interval | CSV | total |
|---|---|---|---|---|---|
| `sli_grid` | 11119 | 25 | 32 / 32 | `..._g_sli_...csv` | 277,975 |
| `gri_grid` | 4237 | 198 | 4 / 4 | `..._g_gri_...csv` | 838,926 |
| **`sri_grid`** | **566** | **1656** | **4 / 4** | **`..._g_sri_...csv`** | **937,296** |

You found the `gri` CSV. Use the **`sri`** one — 566 × 4 = 2264 ≈ 2258 lines, 1656 × 4 = 6624 ≈ 6618 samples. It matches the array the pipeline actually processes, so no product switch is needed. Your point that four-corner bilinear would be badly wrong still stands and is why the grid must be used.

## The architectural change that makes M2 and M5 trivial

**Stop resampling to a square.** Tile at the native `(2258, 6618)` extent.

`generate_tiles.py` currently does `cv2.resize(full_data, (zoom_dim, zoom_dim))`, forcing a 2.93 : 1 strip into a square. That single line causes four separate problems, all of which disappear together:

1. **Spacing stops being a derived guess.** Native spacing is 25.0 / 25.0 straight from the label. Your ⑤ caveat about introducing a new wrong constant no longer applies — nothing is hardcoded, it is read from the XML.
2. **3.23× of real along-track detail returns.** 6618 samples are currently squashed into 2048. That is genuine resolution recovery, not cosmetics.
3. **Hillshade anisotropy streaking is avoided.** On a 2048² array the honest spacing is ≈80.8 m along / ≈27.6 m across — a 2.93× anisotropy that would make `np.gradient` produce directional striping. Native tiling makes it isotropic.
4. **Aspect distortion ends** — a large part of the "weird" look.

Cost: the pyramid becomes a non-square tile grid, so `MissionMap.tsx` needs its `IMAGE_BOUNDS` and `_isValidTile` range updated to match. That is a contained change — **keep `Props` and `MissionMapHandle` byte-identical** so nothing else can regress. I accept that edit in this phase; shipping a knowingly streaky hillshade to avoid it is the worse trade.

## On finding ② — accepted, with the mechanism corrected

You are right that the zero padding is the dominant visual problem, and right to rank masking above global normalisation. The mechanism is slightly different from your description, and the difference matters:

- The radar layers already use `is_solid=False`, whose `valid = isfinite & (>0.005)` mask *does* exclude zeros from the percentile calculation — but **per tile**. So zeros are not dragging a global stretch; instead each tile computes its stretch from whatever few valid pixels it holds. That is why it looks blotchy.
- The `is_solid=True` layers (hillshade, dem_elevation, hazard_map, illumination) derive from the **synthetic DEM**, which is dense everywhere — they have no padding at all. So "padding rendered as opaque colour" is not what is happening on those layers; per-tile normalisation is.
- The padding's real origin: the L2-SELENOREF product is north-up, so a **19.65 km-wide swath runs diagonally through a 56.45 × 165.45 km bounding box**. That geometry explains the ~75 % zeros exactly, and it is inherent to the product — no stretch or mask removes it.
- One knock-on: `process_real_sar_pipeline.py` line ~131 modulates the synthetic DEM by `s0_resampled`, so the fake terrain carries a visible diagonal texture ribbon and smooth Gaussians elsewhere. Another contributor to "weird".

So implement **both** M1 (hoist normalisation to layer scope) and M1b (valid mask, skip all-padding tiles). They fix different things.

## Revised phase plan

**P0 — real georeferencing.** New `backend/app/ingestion/sar_geometry.py`, as you specified, with two changes: parse `sri_grid_no_records` / `sri_grid_no_samples` / `sri_grid_interval_scan` / `sri_grid_interval_pix` from the geometry XML (no hardcoding), and load `..._g_sri_...csv` (937,296 rows → reshape `(566, 1656, 4)` = lat, lon, range, incidence). Expose `pixel_to_latlon(line, sample)` by bilinear interpolation on the grid and `grid_to_latlon(gx, gy)` for the 0–100 UI grid. Compute the footprint by great-circle distance on the grid (R = 1,737,400 m) and return `along_track_m` / `across_track_m` plus metres-per-pixel for a given array shape. Emit a `geodetic_frame` dict with corners read from the CSV, grid shape, spacing, incidence range, and a source string naming the CSV and XML. Then delete the hardcoded `bounds` block at `process_real_sar_pipeline.py` lines ~168–173 and write `geodetic_frame` with provenance instead.

**P0b — fix the `__main__` size bug (finding ①).** Change `process_real_data(512)` so it cannot silently discard resolution. Best: default to native — no resampling at all — and make any downsampling an explicit opt-in argument.

**M0 — native-extent tiling.** Remove the square `cv2.resize`. Emit a non-square pyramid over `(2258, 6618)`. Compute real pyramid depth from the native extent rather than assuming `max_zoom=3`, and report it so M4 has a number to clamp to. Update `MissionMap.tsx` `IMAGE_BOUNDS` / `_isValidTile` to match; `Props` and `MissionMapHandle` unchanged.

**M1 + M1b — normalisation at layer scope, plus valid mask.** Exactly as you designed: `array_to_rgba_tile(slice_data, vmin, vmax, colormap, valid_mask_slice, ...)`, with `vmin`/`vmax` computed once per layer over valid pixels only, and all-padding tiles skipped rather than written.

**M2 — real cell size.** Replace both `np.gradient(dem, 250.0)` calls (lines 77 and 140) with spacing from P0's frame. On the native grid this resolves to 25.0 / 25.0 isotropic. Print before/after slope and hazard percentile tables.

**M3 — histogram-matched stretch.** Your `stretch=` parameter with `log1p(a / p50_valid)` clamped at the 99.5th percentile of valid pixels, linear on robust percentiles for magnitude layers. Print before/after 20-bin histograms and the resulting 8-bit distribution.

**Also fold in:** `PRADAN_DIR` → `BASE_DIR.parent / "data" / "pradan"`, and replace the false `1782x6605` docstring with the verified `2258 × 6618` figures.

**Deferred as you proposed:** M4 (clamp to the real depth M0 now reports), M5 (blend comparison once M1–M3 tiles exist), M7 (JET → VIRIDIS).

## Your decision question — answered

**No flag. Let M2 land, and do not retune any thresholds yet.**

A flag that preserves a knowingly wrong cell size is debt, and "why is there a switch for the incorrect constant?" is a worse viva question than any changed number. Correct arithmetic over synthetic terrain is a legitimate labelled intermediate state.

The one real cost is retuning: `CRITICAL_LANDING_SLOPE_DEG = 12` and the hazard weights would be tuned against invented topography and then need retuning after the real LOLA DEM. So print the before/after tables, label the layers as synthetic-terrain-derived, and leave `config.py` untouched until the real DEM lands.

## Verification for this phase

Regenerate tiles, then compare the rendered pyramid against ISRO's own browse image `raw/browse/calibrated/20200808/ch2_sar_ncls_20200808t201154198_b_brw_xx_cp_xx_d18.png` — shape and orientation of the diagonal ribbon must match. Then before/after screenshots at identical zoom and layer, plus the histogram and slope/hazard tables.

Return each touched file complete: `backend/app/ingestion/sar_geometry.py` (new), `backend/scripts/generate_tiles.py`, `backend/scripts/process_real_sar_pipeline.py`, `frontend/src/mission/MissionMap.tsx`.

## Still queued after this phase

P2 real LOLA south-polar DEM (`ldem_80s_20m.img` via `np.memmap` + `.lbl` parsing, no GDAL — Render cannot build scipy from source, so nothing new in `requirements.txt`). P3 true Stokes CPR/DOP from the complex `sli` products, which is what resurrects the dead ice-detection mask (`CPR_THRESHOLD = 1.00` vs `cpr_max = 0.294`). P4 landing-site search with per-criterion proofs. Also fix `module_b_radar.py` lines 113–116, which assert the ice interpretation even at 0.00 km².

