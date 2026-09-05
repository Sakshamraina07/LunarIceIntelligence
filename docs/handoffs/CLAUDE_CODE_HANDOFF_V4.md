# Claude Code handoff v4 — kill the tile pyramid, ship single-image layers

> Paste everything below the divider into Claude Code, in the session that has the
> verification context. This **replaces** the tiling work in v3 (M0/M1/M1b). P0, M2 and M3
> survive in modified form. Read the "Why" section before writing code.

---

Stop building a tile pyramid. It is over-engineering for this dataset and it is the source of most of the pain. Switch to **one image per layer** rendered with `L.imageOverlay`.

## Why — the data does not justify a pyramid

The native science array is `(2258, 6618)` = **14.9 megapixels**, isotropic 25 m (verified from the `sri` L2-SELENOREF label). That is smaller than a modern phone photo. A browser displays it in a single `<img>` without effort.

Do the viewport arithmetic: 6618 px covers 165.45 km, so native detail is 25 m/px. On a ~1400 px-wide map panel showing the full swath you are already at ~118 m/px — a 4.7× downsample. Native resolution is only reached after zooming in 4.7×. **There is no detail below 25 m to stream**, so a pyramid buys nothing. The only dataset that would have justified one was OHRC at 0.25 m/px, and that was proven synthetic (100×100 uint8, identical mean 176.4 across three craters).

## What this deletes outright

These stop being bugs to fix and become impossible by construction:

- **Per-tile normalisation (old M1).** With one image there is exactly one normalisation pass over the whole array. The blotchy patchwork cannot occur.
- **Tile seams** in hillshade and every derived layer.
- **The `cv2.resize(..., (zoom_dim, zoom_dim))` square distortion (old M0)** — the overlay bounds carry the true 2.93 : 1 aspect.
- **All tile-URL machinery** in `MissionMap.tsx`: `class LunarTileLayer`, the additive y-flip `coords.y + n`, `_isValidTile`, `maxNativeZoom` vs `maxZoom` mismatch, `TILE_BASE`. Delete them.
- **~2000 HTTP requests.** Native tiling would have needed ≈331 tiles/layer × 6 layers. One request per layer instead.
- **Slow regeneration.** `Image.save(..., optimize=True)` per tile is what made this take minutes. Six files takes seconds, so iterating on a colormap or stretch stops being a batch job.

## Serve the images from Vercel, not Render

Write the layer images to `frontend/public/layers/`. Vercel serves them from its CDN, so the map paints without touching the Render backend at all — no cold start, no per-request overhead. The backend then serves only JSON analysis results, which is what it is good at. This is the actual fix for "lag free".

## Deliverables

**1. New `backend/scripts/render_layers.py`** (replaces `generate_tiles.py`).

For each layer, from the native arrays:
- Normalise **once** over the whole array, over **valid pixels only** (`np.isfinite(a) & (a > 0)` for radar layers; dense layers use all finite pixels). This is where old M1 and M1b collapse into one correct step.
- **Stretch (old M3):** for CPR/DOP use `log1p(a / p50_valid)` clamped at the 99.5th percentile of valid pixels; magnitude and terrain layers stay linear on robust percentiles (2nd–98th). Print the before/after 20-bin histogram and the resulting 8-bit distribution so the choice is evidence-based.
- **Colormaps:** replace `COLORMAP_JET` (hazard) with a perceptually uniform map — VIRIDIS, MAGMA or CIVIDIS. JET manufactures false edges and is a known scientific-visualisation error a panel may call out.
- **Alpha channel** carries the padding mask: `alpha = 0` where invalid. The ~75 % zero padding — the diagonal 19.65 km swath inside a 56.45 × 165.45 km north-up bounding box — becomes cleanly transparent instead of coloured.
- Save **lossless WebP** (`Image.save(path, format="WEBP", lossless=True, quality=100)`). Lossy compression on scientific rasters is not acceptable. If PIL lacks WebP support, fall back to PNG with `compress_level=6` — do **not** use `optimize=True`.
- Also emit a **~640 px-wide preview** per layer (`{layer}.preview.webp`, expect ~20–40 KB) for instant first paint.

**2. `frontend/public/layers/layers.json` manifest** — per layer: filename, preview filename, pixel dimensions, the `geodetic_frame` from P0, vmin/vmax and the stretch used, colormap name, and a provenance string naming the source rasters. The UI reads bounds and legend ranges from this instead of hardcoding them.

**3. `frontend/src/mission/MissionMap.tsx`** — replace the tile layer with `L.imageOverlay`.
- Bounds from the manifest's true aspect ratio: width 256 units → height `256 × 2258 / 6618 ≈ 87.3`, so `IMAGE_BOUNDS = [[0, 0], [87.3, 256]]`. Read it from `layers.json`; do not hardcode.
- Load the preview first, swap to the full image on its `load` event — gives progressive feel without a pyramid.
- Past native zoom set `image-rendering: pixelated` on the overlay image. Honest sharp pixels instead of mushy interpolation, and it makes the resolution limit visible rather than hidden.
- **Keep `Props` and `MissionMapHandle` byte-identical.** Panes, graticule, scale bar, markers, routes and the coord readout all stay.

**4. Keep from v3, unchanged in intent:** **P0** — `backend/app/ingestion/sar_geometry.py` built on the **`sri`** geolocation grid (`..._g_sri_...csv`, 937,296 rows → `(566, 1656, 4)`; parse `sri_grid_*` from the geometry XML, no hardcoding), and delete the hardcoded `bounds` at `process_real_sar_pipeline.py` lines ~168–173. **P0b** — fix `process_real_data(512)` so it defaults to native and never silently discards resolution. **M2** — replace both `np.gradient(dem, 250.0)` calls with spacing from P0's frame, which on the native grid is 25.0 / 25.0 isotropic; print before/after slope and hazard percentile tables, and leave `config.py` thresholds untouched.

## Retiring the old tiles

`backend/tiles/faustini/` holds 510 committed PNGs that become dead weight. Recommend `git rm -r backend/tiles/faustini` once the new path renders correctly — it is recoverable from history, but confirm with me before running it. Keep `generate_tiles.py` in history; delete it from the tree in the same commit.

## Verification

Compare the rendered layers against ISRO's own browse image `raw/browse/calibrated/20200808/ch2_sar_ncls_20200808t201154198_b_brw_xx_cp_xx_d18.png` — the diagonal ribbon's shape and orientation must match. Then: before/after screenshots at identical zoom and layer, printed histograms, slope/hazard percentile tables, total payload size per layer, and confirmation that the map paints with the backend stopped.

Return each touched file complete.

## Still queued after this

P2 real LOLA south-polar DEM (`ldem_80s_20m.img` via `np.memmap` + `.lbl` parsing — no GDAL, nothing new in `requirements.txt`, Render cannot build scipy from source). P3 true Stokes CPR/DOP from the complex `sli` products, which is what resurrects the dead detection mask (`CPR_THRESHOLD = 1.00` vs measured `cpr_max = 0.294`). P4 landing-site search with per-criterion proofs. Also fix `module_b_radar.py` lines 113–116, which assert the ice interpretation even when the detected area is 0.00 km².
