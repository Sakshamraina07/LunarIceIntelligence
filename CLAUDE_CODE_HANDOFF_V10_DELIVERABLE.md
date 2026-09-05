# HANDOFF V10.1 — MAKE THE MAP ANSWER ITS OWN QUESTIONS

Read `CLAUDE_CODE_WORKING_RULES.md` first. One browser session at the end, not
during.

**Revised to V10.1 after reading the modules rather than trusting the earlier
scope call.** Three additions, all because the user asked for everything real and
the map to be properly good: a new **Step 1b** fixing three bugs that would have
corrupted Step 3's inputs before it ran (single-scalar `pixel_scale_m`, the flat
30.37 km/deg lat/lon conversion, and `scientific_value` containing only distance);
a **Step 8** for map quality, which pulls LOLA 20 m/px in from the V9.1 phase-B
backlog; and three decisions the user has now made — thermal is DERIVED from the
PSR mask with its assumption printed, boulder risk is NO DATA with
`WEIGHT_BOULDER` zeroed and the remaining weights renormalised, and the 20 m
product is being downloaded. `mission_service.py`'s `pixel_scale_m = 250.0` and the
anisotropic 2048 x 2048 grid moved from out-of-scope into Step 1b.

V9.1 landed. The terrain is measured now — `LOLA LDEM_80S_80M V2.0, 80 m/px
native, bilinear to 25 m grid`, `SYNTHETIC: nothing`, slope p50 1.808 deg to
9.343 deg, and the hillshade in the screenshot shows real craters. That part is
done and this handoff does not revisit it.

V10 is about what the screenshot still says. Four of twelve stat cells and four
of five evidence rows read `0.00`, `—`, `NO DATA` or a stale `MODELLED`:

    where is the ice      CANDIDATE AREA 0.00 km2 · ICE VOLUME 0 · P(ice) MODELLED
    where can we land     five hardcoded grid offsets at module_e_landing.py:48-54
    how do we get there   ROVER — not computable
    is it cold enough     PSR AREA — · cold trap 0.00 · doubly-shadowed 0.00 · thermal NO DATA
    how steep is it       MEAN SLOPE 10.58 deg tagged MODELLED — it is measured now

Three of those five were blocked by the placeholder DEM and are unblocked today.
One is blocked by amplitude-only CPR and needs the complex products. One is a
two-line label fix.

## Constraints — unchanged, non-negotiable

- No rasterio, no GDAL. numpy, cv2, PIL, scipy, tifffile only. Nothing added to
  `requirements.txt` — Render cannot build scipy from source.
- Never `imread` a multi-GB raster whole. Windowed `np.memmap` reads only. That
  discipline is what made LOLA work; the `sli` products are ~2.17 GB per channel
  and get exactly the same treatment.
- Do not invent data. An absent quantity gets an explicit absent state the UI can
  render. `np.zeros_like` is not an absent state.
- Do not retune a threshold to make a number look better. If a threshold is
  mis-set, print the distribution and say so. §4.7 of the V9 report already shows
  they are mis-set in both directions.
- Ask before any destructive git operation or file delete.
- Return complete files, not snippets.
- Every new number reaching the UI carries a provenance mark: MEASURED, DERIVED,
  MODELLED, or NO DATA. A number with no defensible mark does not ship.

## Step 0 — the raster overlap. Do this first; it is the thing the user can see.

In `docs/v8_full_extent.png` the terrain block has hard rectangular edges and
two smooth bright blobs that do not look like craters — one around the left
third, one right of centre. Smooth blobs are the signature of the deleted
analytic DEM's Gaussians. Something old is still being painted.

**Measure before you remove anything.** In one browser session print, for every
pane in `.mc-map`:

- every `.leaflet-image-layer` node: `src`, `style.transform`, `naturalWidth` x
  `naturalHeight`, computed `opacity`, and the pane it lives in
- `map.eachLayer` filtered to `L.ImageOverlay`: `_url` and `getBounds()` for each
- whether any `.leaflet-tile-pane` node exists inside `.mc-map` at all

Ranked hypotheses, most likely first:

1. **Two overlays per layer.** `render_layers.py` writes both `{layer}.webp` and
   a 640 px `{layer}.preview.webp`. If `attachRaster` mounts the preview for fast
   first paint and never removes it after the full image fires `load`, you get a
   soft low-resolution copy showing through a sharp one — which is exactly what a
   washed-out blob looks like.
2. **A stale overlay never torn down.** `attachRaster` adding without removing
   when `layers.json` identity changes would leave the previous provenance's
   image mounted underneath.
3. **Cache.** Vercel or the browser serving the pre-LOLA `hillshade.webp` for one
   of the two URLs. Check `naturalWidth`/`naturalHeight` and the response headers,
   not just the URL string.
4. **The old pyramid bleeding in.** `/tiles/faustini/{layer}/{z}/{x}/{y}.png` via
   `GISMapViewer.tsx` mounted at `App.tsx:258`. Those PNGs were rendered from the
   deleted synthetic DEM. See Step 6.

Fix so that **exactly one image overlay exists per active layer at any moment**,
and add that as a gate in `frontend/scripts/verify_v8_view.mjs`:
`imageOverlays.length === expectedActiveLayers`, printing every `_url`.

Separately, report whether the hillshade overlay's bounds equal `geom.bounds`
exactly. If the LOLA-derived raster covers less than the full frame, state the
fraction and the cause. A hard edge is either a bounds mismatch or a genuine
data edge, and those need different fixes — do not paper over it with CSS.

## Step 0b — two things the user asked for directly. Small, do them now.

1. **Surface Relief is the default layer, not Radar Signals (CPR).** Right now the
   map opens with the CPR ribbon on, which paints a narrow speckled band across a
   frame that is 84 % empty, so the first thing anyone sees is the least readable
   view of the scene. Open with `hillshade` plus `Landing Sites`, and let CPR, DOP
   and the rest be opt-in. The user compared both views himself and this is his
   call, not a style preference. Nothing about the layer definitions changes — only
   which ones start visible.

2. **Clamp zoom-out to the frame.** Zooming out currently shrinks the raster into a
   small island in a grey field. Set `minZoom` from Leaflet's own fit calculation
   rather than a literal: `map.setMinZoom(map.getBoundsZoom(geom.bounds, false))`,
   so the furthest zoom-out is exactly the frame filling the view and no further.
   Add `maxBounds` from `geom.bounds` with `maxBoundsViscosity: 1.0` so it cannot be
   dragged into empty space either. Do not hardcode a zoom number — the frame's
   aspect is 2.93:1 and the container width changes, so a literal will be wrong on
   some screen. Recompute on `resize`.

Both are `MissionMap.tsx` only, both additive, `MissionMapHandle` unchanged.

## Step 1 — the stale badge (two lines, do it while you are in there)

`MEAN SLOPE 10.58 deg` carries `MODELLED`. §4.9 of your own V9 report proved it
is measured: 10.5766 is `build_analysis.py`'s `mean_slope_deg` and the displayed
`max 62.8 deg` equals the new native-grid `p100 = 62.787 deg`, both from LOLA.
Flip it to `MEASURED`.

Then audit every other mark against its actual source and change only what the
evidence supports. `PEAK P(ice) 0.72` is a genuine model output and stays
`MODELLED`. Under-claiming is the safe direction but it is still wrong, and a UI
that mislabels its good numbers teaches the examiner to distrust the labels.

## Step 0b — two map-behaviour fixes the user asked for directly. Small, do them now.

1. **The mission map must open on Surface Relief, not radar.** `MissionControl.tsx:109`
   is `useState('cpr_heatmap')` while `STEP_LAYER` at :37 already maps step 1 to
   `'hillshade'` — the initial state contradicts the step table it sits next to.
   Make the initial value `'hillshade'` so step 01 SITE opens on terrain. Do the
   same at `App.tsx:31`. Leave `STEP_LAYER` alone: stepping to 03 RADAR should still
   switch to CPR, and stepping back to 01 should return to relief. The user's point
   is about the default, not about removing the radar view.

2. **Clamp zoom-out to the data bounds.** Right now the raster can be zoomed out
   past fit, so it shrinks into a small image floating in empty space. Fix it in
   the map's own terms, not with CSS:
   - `minZoom = map.getBoundsZoom(geom.bounds, false)` — the zoom at which the whole
     strip exactly fits. Compute it after the container has real size, and recompute
     on resize; a hardcoded number will be wrong on another screen.
   - `maxBounds` = `geom.bounds` with a small pad, plus `maxBoundsViscosity: 1.0`,
     so panning cannot drag the frame off into the void either.
   - Leave `HOME_WINDOW_KM = 40` and the opening view alone. This only changes how
     far OUT the user can go, and `reset()` must still return to the 40 km window.

   State the computed `minZoom` and the fit zoom in the report so the clamp is a
   number, not a claim.

## Step 1b — three bugs that corrupt Step 3 before it starts. Fix these first.

Found by reading the code, not inferred. Step 3 consumes slope and emits lat/lon,
so building it on top of these means building a real search on wrong inputs.

1. **`module_d_terrain.compute_terrain_metrics(dem, pixel_scale_m: float = 250.0)`
   takes one scalar and hands it to `np.gradient(dem, pixel_scale_m)`, which
   applies it to both axes.** Two faults in one line: the 250.0 default is ten
   times the 25.0 m frame, and a single scalar cannot describe this grid — the
   2048 x 2048 analysis array is a square resample of a 2.93:1 swath, so its posts
   are 27.5635 m along lines and 80.7861 m across samples. Change the signature to
   take `spacing_m: tuple[float, float]` and **delete the default entirely** so no
   caller can silently inherit a wrong number. `render_layers.compute_terrain()` at
   :162-170 already does this correctly — copy its shape, do not invent a second
   convention. Then fix the call sites, including `mission_service.py`'s 250.0.
   This is what V10 wrongly listed as out of scope; it is in scope now, because
   every slope, hazard, roughness and landing score downstream is wrong until it
   lands.

2. **`module_e_landing.py:95-96` converts grid offsets to lat/lon with a flat
   30.37 km per degree on both axes.** Latitude is roughly right; longitude is not.
   At 89 deg S one degree of longitude spans about `30.37 * cos(89 deg) = 0.53 km`,
   so the reported longitudes are off by a factor near 57. Every site coordinate
   the UI prints is currently wrong, and a wrong lat/lon is more obviously
   indefensible than any threshold. The correct inverse polar-stereographic already
   exists in `app/ingestion/sar_geometry` and was measured against ISRO's own
   corner coordinates to 13.2 mm — use it. Same fix in `module_f_rover` if it
   repeats the constant; grep `30370` before assuming it does not.

3. **`module_e_landing.py:78` computes `sci_value = max(0.1, 1.0 - dist_km /
   (max_diag_km * 0.7))` and ships it to the UI as `scientific_value`.** Its only
   input is distance, so it is a distance restatement wearing a science label, and
   it is why every route reports `science_value: 0`. Either feed it the Step 5
   anomaly ranking, which is a real measured quantity, or rename the field to what
   it is. A field named `scientific_value` that contains no science is exactly the
   kind of thing that costs credibility for no gain.

Also per the user's decision: set `WEIGHT_BOULDER` to 0 and give boulder risk an
explicit NO DATA state rather than a zeros array, then **renormalise the hazard
weights over the two terms that remain** so hazard stays in [0, 1] instead of
being silently scaled down. There is no real optical product on disk — the fake
OHRC hillshade was deleted in V9.1 — so boulder count cannot be measured, and the
UI must say absent rather than imply "no boulders anywhere".

## Step 1c — the three findings you escalated. All three decided.

**1. Two hazard definitions — the number wins, the picture follows it.**
`render_layers.compute_terrain()` renders `0.6*(slope/25) + 0.4*(rough/40)` while
`build_analysis.hazard_from()` and `module_d_terrain` compute `0.5/0.3`
renormalised over 0.8 with divisors 20 deg / 50 m. Make `render_layers` import and
call the same function the statistics use. Reason: the divisors and weights in the
analysis path come from `config.py`, and a viewer who compares the magma colour to
the `hazard` figure on the card must be looking at one quantity. Delete the second
formula rather than parameterising both — two definitions with a caveat is still
two definitions. Print the layer's percentile table before and after so the colour
change is a stated fact.

**2. `module_f_rover.py` — the no-op is noted, the real bug is the roughness.**
Good catch that `30370` is absent; drop that half of 1b(ii) and say so in the
report. `pixel_scale_m: float = 250.0` at :83 is still a 1b(i) call site and gets
the same treatment: tuple spacing, no default. The one that matters more is the one
you found on your own — the search costs cells using an elevation delta as
roughness while the telemetry reconstruction substitutes a constant 5.0. That means
the reported energy does not describe the path that was chosen. Make both read the
same roughness raster. If they cannot, the energy figure is not DERIVED and must
not be presented as if it were.

**3. `P(ice)` comes out of the UI entirely.**
This is the one that settles the user's "no simulated data anywhere" requirement,
and your finding is what settles it. `module_c_ice.py` fits a Random Forest to
labels invented by `np.random.uniform`, with class 1 defined as CPR 1.05-2.5 inside
a PSR — so the forest learned the CBOE threshold rule, and this frame's CPR maxes
at 0.053, entirely outside that range. Every pixel is an extrapolation from
synthetic training data. `PEAK P(ice) 0.72` is therefore not a weak number, it is a
number about nothing, and it currently sits in the headline row.

So: remove the `P(ice)` stat cell, remove the `Possible Ice P(ice)` layer from the
LAYERS panel, and stop treating the missing `ml_likelihood.webp` as a gap to fill —
it must never be rendered. Put the Step 5a measured relative CPR anomaly ranking in
that cell's place. Leave `module_c_ice.py` on disk, unwired, with a docstring
stating why it is unwired, so the work is visible in the repo without being visible
in the product. If anything about this frame later carries real labels, that is when
it comes back.

Report what the headline row reads after this change. A row with one fewer cell and
no fiction in it is stronger than a full row with a random-forest-on-random-numbers
in the middle of it.

## Step 1c — the last simulated thing in the app. It has to go.

Your own finding, and the most important one in the report: `module_c_ice.py` fits
the Random Forest to labels invented by `np.random.uniform`, where class 1 is
defined as CPR 1.05-2.5 with low DOP inside a PSR. So the forest never learned ice;
it learned the CBOE threshold rule it was handed. Then this frame's CPR maxes at
0.053, entirely outside that training range, so every pixel it scores is an
extrapolation from fabricated examples.

The user's instruction is explicit: nothing simulated reaches the UI, not even
labelled as such. `PEAK P(ice) 0.72 MODELLED` is therefore not shippable, and
MODELLED actually understates the problem — the model's training data does not
exist.

- Delete the synthetic-label fit. Do **not** replace it with a different
  classifier. There are no ground-truth ice labels in this project, and inventing
  them again in another shape is the same fault wearing a new name.
- Replace `P(ice)` with an explicit criteria screen: the same named criteria the
  evidence checklist already prints, each with its measured value, its threshold
  and its pass/fail. That is defensible, and the verdict card is already doing it
  correctly today — the ice cells simply are not reading from it.
- Until Step 5b lands, those cells read `NOT SCREENABLE — CPR from amplitude alone
  cannot reach the CBOE threshold`. The UI already says exactly this in prose next
  to a number that contradicts it. The number and the note must agree.
- Delete the `ml_likelihood` layer, or keep its raster and relabel it as the
  criteria screen it becomes. Either way `MODELLED` disappears from the ice path.

Two calls from your report that are mine to make, so you are not blocked:

1. **Two hazard definitions — make the picture follow the number.**
   `build_analysis.hazard_from()` / `module_d_terrain` (0.5 / 0.3 renormalised over
   0.8, divisors 20 deg / 50 m) is authoritative, because that is the number the
   verdict and the landing search consume. Change `render_layers.compute_terrain()`
   to render exactly that formula and delete its 0.6 / 0.4, 25 deg / 40 m variant. A
   hazard image that disagrees with the hazard figure is worse than either being
   slightly off, because it means one of them is decorative.
2. **`module_f_rover` energy.** Use the same elevation-delta roughness in the
   telemetry reconstruction that the search used. The constant 5.0 makes the
   reported energy describe a different traverse than the one that was planned.
   Report before/after on the three existing routes.

Good catch on `module_f_rover` having no `30370` — that half of Step 1b(ii) is a
no-op, and reporting it as measured rather than assumed is the right call. It is
still a Step 1b(i) call site at :83.

## Step 2 — PSR and illumination, computed from LOLA

This is the biggest unlock in V10 and it fills four cells at once: `PSR AREA`,
`Overlap with a shadowed cold trap`, `Overlap with a doubly-shadowed core`, and
`Thermal stability expected`. All four read 0.00 or NO DATA today for one reason:
the placeholder DEM pushed 98.24 % of the frame below the shadow cut, which is
degenerate, so the honest call was `UNAVAILABLE`. With measured topography the
computation becomes real.

The current `illumination` layer is `hillshade * norm_elev^1.2`. That is invented
and must go. Real polar illumination is a horizon problem, not a shading problem.

**Method.** For each pixel, the horizon elevation angle in direction `az` is
`max over r of atan((h(p + r*u_az) - h(p)) / r)`. A pixel is lit for sun state
`(az, el)` when `el > horizon(az)`. At the lunar south pole the Sun sweeps all
360 deg of azimuth over a lunar day and its elevation stays within roughly
+/-1.54 deg, so sample `az` at 1 deg and `el` from 0 to 1.54 deg. Output
`illumination_fraction` in [0, 1] per pixel, and `psr_mask = (fraction == 0)`.

**Three things that decide whether this is science or decoration:**

1. **Compute the horizon on the FULL 7600 x 7600 LOLA array, not the frame
   window.** At the pole the horizon is set by crater rims tens of kilometres
   outside the 165 x 56 km frame. A horizon computed only inside the frame will
   invent sunlight that the real terrain blocks. This is now possible because the
   whole 80S product is on disk — use it, then crop.
2. **Rotate-and-scan, not per-pixel ray marching.** For each azimuth, rotate the
   DEM with `scipy.ndimage.rotate(order=1)`, take a running maximum of
   `(h - h0)/r` along rows, rotate back. That is O(N) per azimuth instead of
   O(N * ray length). Decimate the array until it completes in reasonable time
   and **report the resolution you actually used**. A 240 m far-field horizon with
   an 80 m near field is a legitimate multi-scale technique; a silently
   downsampled one is not.
3. **Label the resolution.** Shadow masks derived from 80 m posts must not be
   presented at 25 m. Emit `native_metres_per_pixel` and the decimation factor
   alongside the mask, and let the UI say so.

`doubly-shadowed core` means never directly lit **and** receiving no scattered
light from lit terrain. Approximate it with a sky-view factor restricted to lit
horizon, and if that cannot be computed defensibly, emit the absent state and say
which term was missing. Do not silently reuse the single-shadow mask for both.

**Thermal stability — decided, no download.** No thermal product is on disk, so
this is not measured and must not claim to be. Derive it from the PSR mask: a
pixel that is never directly lit sits below the roughly 110 K water-ice stability
limit, so emit `thermal_stability: DERIVED` carrying the assumed threshold and the
words "inferred from illumination, not from measured temperature" through to the
UI. If a Diviner product arrives later this becomes MEASURED and nothing else
changes. `NO DATA` was the alternative and was rejected because the inference is
defensible when its assumption is printed.

## Step 3 — landing sites, searched instead of asserted

Delete the five hardcoded grid offsets at `module_e_landing.py:48-54`. Alpha
(18,50), Beta (82,75), Gamma (78,25), Delta (50,15), Epsilon (48,85) were never a
search — they were positions, scored after the fact. That is the single easiest
thing for an examiner to break.

Score every pixel instead, against `config.py` thresholds and the now-real
layers:

- slope below the limit — this finally discriminates: `slope > 15 deg` covers
  25.161 % of the frame against 3.819 % on the placeholder
- roughness below the limit
- hazard below the limit
- inside the amplitude mask, i.e. where radar actually returned signal. A site
  recommended outside it has no radar evidence and must say so rather than be
  quietly excluded
- distance to the nearest PSR within rover range — this is the ice-access term
- `illumination_fraction` above a minimum — this is the solar-power term, and it
  is in direct tension with the previous one. That tension **is** the science:
  close to the cold trap but still able to charge. Report both numbers per site,
  do not collapse them into one score and hide them.

Then non-max suppression with a stated minimum separation so the top N are not
five pixels of one crater floor. Every returned site carries: grid coordinates,
lat/lon, each criterion's value, each criterion's pass/fail against the named
threshold, and the mark for each. Weights and thresholds live in `config.py`, not
in the function.

Emit a suitability heatmap as a layer so the recommendation is visibly the
argmax of something, not an opinion.

## Step 4 — the traverse, and the shortest-distance question

`ROVER — not computable` is the honest current state. Make it computable.

Build a traversal cost surface from the LOLA slope and hazard rasters: per-cell
cost rising with slope, and hard-impassable where slope or hazard exceeds the
rover limits in `config.py`. Then run `scipy.sparse.csgraph.dijkstra` over the
graph of passable cells — scipy is already allowed, so no new dependency.

Deliver:

- pairwise shortest-path distances between the Step 3 sites, as a matrix
- the path polylines, in grid coordinates and lat/lon
- path length in metres, and an energy proxy (cumulative climb, or integrated
  cost) stated as DERIVED
- the shortest tour visiting the selected sites. N is small; for N <= 8 solve it
  exactly by enumeration and say that is what you did, rather than shipping a
  heuristic labelled as optimal
- **`UNREACHABLE` as an explicit state.** If no passable path exists between two
  sites, that is a finding worth showing — it is never a distance of 0.

All three current routes terminate at frame centre with `science_value: 0`
because `target_coordinates` is the grid centre, not a measured peak. Once
Step 3 produces real sites and Step 5 produces a real anomaly ranking, the
targets come from those. Do not leave the centre hardcoded.

## Step 5 — the ice question. Two parts, and only the second one is the real fix.

`CANDIDATE AREA 0.00 km2` and `ICE VOLUME 0` are not a bug in the threshold. They
are the correct output of a measurement that cannot reach the threshold. This
build computes `CPR = ((sqrt(lh) - sqrt(lv)) / (sqrt(lh) + sqrt(lv)))^2`, a
squared channel-imbalance ratio that tends to zero whenever LH is close to LV,
which is the normal regolith case. Native `p50 = 0.000565`, `max = 0.0534`
against a 1.00 threshold. **No value in [0, 1] fixes this. Do not retune
`CPR_THRESHOLD`.** The UI already states this correctly and that framing stays.

**5a — ship something honest now.** Add a *relative* CPR anomaly ranking within
the measured swath: top percentiles of the measured CPR field, with their area and
locations, labelled `RELATIVE ANOMALY WITHIN THIS SWATH — NOT A CBOE DETECTION`.
That answers "which places are most worth looking at" without claiming an ice
detection the product cannot support. It is a ranking, and the label must say
ranking.

**5b — the real fix: Stokes from the complex products.** True hybrid-polarity CPR
needs the phase term. `S3 = 2 * Im<E_H . E_V*>`, then
`CPR = (S0 - S3) / (S0 + S3)`. The complex `sli` products are already on disk in
`data/pradan/raw/data/calibrated/20200808/` — `ComplexLSB8`, 355768 x 759,
~2.17 GB per channel, 21 azimuth looks.

- Windowed `np.memmap` only. Same discipline as LOLA. Never whole-array.
- Average the Stokes parameters over the azimuth looks before forming ratios —
  averaging after the ratio is a different and wrong quantity, and speckle on a
  single look will swamp the result.
- `module_b_radar.py` already contains correct `compute_cpr_from_stokes()` and
  `compute_dop_from_stokes()`. They have never been fed. Feed them; do not write
  new ones.
- Parse the PDS4 label for the complex layout rather than assuming interleave or
  endianness. The V9.1 lesson stands: `LSB_INTEGER` vs `MSB`, and units inside
  angle brackets, are exactly where silent corruption enters.
- Confirm the label's own declared min/max or statistics where present, the same
  fatal check that validated LOLA. A read that cannot reproduce a number the
  product carries about itself is not trusted.

Then `module_b_radar.py:113-116` stops printing an ice interpretation over
0.00 km2, and `CANDIDATE AREA` becomes a measurement either way — including a
measured zero, which is a legitimate scientific result and should be presented as
one.

## Step 6 — the tile pyramid. Decision made; nothing is lost.

You held the `git rm` and listed three ways out. Take the second one, in this
order, and nothing is destroyed:

1. `git checkout -b parked/tile-pyramid` and commit the 421 insertions /
   142 deletions currently uncommitted in `backend/scripts/generate_tiles.py`,
   plus `compare_tiles_vs_single.py`. That authored work is real and recoverable
   forever once it is a commit. Report the branch name and SHA.
2. Back on the working branch, rewire the two live consumers off
   `/tiles/faustini/{layer}/{z}/{x}/{y}.png` — `GISMapViewer.tsx`'s
   `LunarTileLayer`, mounted at `App.tsx:258`, and `lunarBasemap.ts:93` — to the
   single-image layers already described by `layers.json`. This is a frontend
   change beyond the V9 approval, and it is approved now, because leaving it
   unrewired is the worse outcome: **those PNGs were rendered from the deleted
   synthetic DEM, so every tile still being served is stale synthetic terrain.**
   That is the whole reason this is not merely cleanup.
3. Then `git rm -r backend/tiles/faustini backend/scripts/generate_tiles.py
   backend/scripts/compare_tiles_vs_single.py`. The 510 tracked files stop
   refusing once the local modifications are committed in step 1. Report the
   file count actually removed.

If step 2 turns out to need more than a swap to `L.imageOverlay` with
`geom.bounds`, stop and report what else `GISMapViewer` depends on rather than
half-rewiring it.

## Step 7 — report

Per numbered step: the command run, the numbers measured, what changed, and the
provenance mark now carried by every value that reaches the UI. Specifically:

- Step 0: the overlay inventory before and after, `imageOverlays.length` against
  `expectedActiveLayers`, and the hillshade-bounds-vs-`geom.bounds` verdict with
  the covered fraction if it is not 1.0
- Step 2: `PSR AREA` in km2, `illumination_fraction` percentiles, the azimuth
  count and elevation samples used, the decimation factor and the effective
  metres per pixel of the horizon computation, and whether the doubly-shadowed
  term was computed or emitted absent
- Step 3: the top N sites with every criterion value, its threshold, its
  pass/fail and its mark; the NMS separation used; and the PSR-distance vs
  illumination pair for each site, unreduced
- Step 4: the distance matrix, the tour length, the method (exact enumeration or
  otherwise), and any `UNREACHABLE` pairs
- Step 5: the CPR percentiles from the complex read, the label statistic you
  reproduced as the fatal check, and the final `CANDIDATE AREA` — including if it
  is a measured zero
- Step 6: branch name and SHA, the consumers rewired, the file count removed
- Step 1b: the new `spacing_m` signature and every call site changed; one site's
  lat/lon before and after the projection fix, in degrees; and what
  `scientific_value` now contains
- Step 8: which LOLA product was actually ingested and its native post spacing,
  and which hillshade azimuth scheme shipped

Then one browser session at the end, zoom fixed, `setZoom(z, {animate: false})`,
waiting on the image `load` event. Re-run `npx tsc --noEmit -p tsconfig.app.json`
and `node frontend/scripts/verify_v8_view.mjs` before reporting.

State plainly which of the twelve stat cells and five evidence rows still read
`0.00`, `—` or `NO DATA` after V10, and for each one whether that is now a
measured fact or a remaining gap. A cell that legitimately reads zero is a
result; a cell that reads zero because the code path is unfinished is not, and
the report must distinguish them.

## Step 8 — make the map read like a map (last, and only after 0-7 pass)

The user's other request is that the map look properly good, and Step 0 only
removes the duplicate overlay. `render_layers.py` already writes full-resolution
`6618 x 2258` lossless WebP with a single global stretch, so the softness is not a
render cap and must not be chased in CSS. Three honest upgrades, in this order:

**First, two UI defaults the user asked for directly. Both are small — do them
before the rendering work.**

- The map opens with `Radar Signals (CPR)` active, so the first thing anyone sees is
  a speckle ribbon covering 15.6 % of the frame while the real terrain sits behind
  it. Open on `Surface Relief` with `Landing Sites` on, and make CPR / DOP opt-in.
  The per-layer legend and caveat text already switch correctly with the active
  layer, so only the default changes.
- Zooming out shrinks the raster into a small image floating in empty space. Clamp
  `minZoom` so the fully zoomed-out view **is** the raster's own bounds, computing it
  from `layers.json` `crs` rather than hardcoding a number, and set `maxBounds` to
  those bounds with `maxBoundsViscosity` so the frame cannot be dragged off-centre.
  `HOME_WINDOW_KM = 40` stays the opening window; this only changes how far out the
  user is allowed to pull.

- **LOLA 20 m/px is being downloaded and is now IN scope.** `LDEM_80S_20M.IMG` +
  `.LBL`, same code path, one `--input` change, exactly as V9.1 phase B promised.
  Note what this actually buys: at 80 m native the 25 m grid is a 3.2x upsample, so
  three of every four pixels of apparent detail are interpolation — which is what
  `render_layers.py` already prints as "carries no relief finer than 80 m". At 20 m
  native the 25 m grid becomes a slight DOWNSAMPLE, so the displayed detail is
  real. Do not change the 25 m grid to chase 20 m; the gain is already there, and
  changing the grid would ripple through every layer, mask and bound.
- Multi-directional hillshade in place of the single 315 deg sun at
  `render_layers.compute_hillshade`, weighted over about four azimuths. Slopes
  facing away from the one current light direction currently flatten out. Keep the
  single-azimuth path available and state which one shipped.
- A hypsometric tint under the hillshade for `dem_elevation`, plus contours at a
  stated interval. Both are display choices, not data, and `layers.json` must say
  so.

Do not restyle anything else. `MissionMapHandle` stays byte-identical and prop
changes are additive only.

## Out of scope for V10 — do not start these

The missing `ml_likelihood.webp`; `MissionControl.tsx:118` un-gating; the marker
occlusion under the LAYERS panel; an LRO Diviner ingest (thermal is DERIVED from
illumination per Step 2); real optical imagery for boulder detection (boulder risk
is NO DATA per Step 1b). Each is its own handoff.

One expectation to state plainly in the report rather than engineer around:
`PEAK P(ice) 0.72` comes from a likelihood model with no ground-truth ice labels
anywhere in this project, so it can never be MEASURED. MODELLED is its honest
ceiling. If it is in fact a fixed weighted combination of measured layers, call it
a weighted index and drop the ML framing — a weighted index that admits what it is
survives questioning; an ML claim with no training labels does not.

## V10.2 — decided after your Step 0/1 report. These override anything above.

Step 0's premise was false and you were right to measure instead of retouch. The
bit-identity of `dem_native_synthetic.tif` to `ldem_frame_25m.tif` and the r =
0.999986762 hillshade reproduction settle it, and `assert_dem_is_lola()` is a better
outcome than the fix I asked for. Your three findings each needed a call.

**1. Two hazard definitions — collapse them, keep the config-driven one.**
`render_layers.compute_terrain()` uses 0.6/0.4 over divisors 25 deg / 40 m;
`build_analysis.hazard_from()` and `module_d_terrain` use 0.5/0.3 renormalised over
0.8 with divisors 20 deg / 50 m. A picture and a number that disagree is worse than
either being wrong, because the map is what a reader points at while quoting the
figure. Make `module_d_terrain` the single source and have `render_layers` import
it, so the image is the quantity. Keep 20 deg / 50 m: 20 deg is
`MAX_TRAVERSABLE_SLOPE_DEG` in `config.py` and therefore a stated rover limit,
while 25 deg / 40 m are display scalings with no cited source. Print the rendered
layer's before/after percentile table — the picture changes even though the number
does not.

**2. `module_f_rover` — fix the roughness disagreement, not just the call site.**
Confirmed no `30370`, so Step 1b(ii) is a no-op there; report it as one. But
`pixel_scale_m = 250.0` at :83 is still a Step 1b(i) call site. And a search that
costs an elevation-delta roughness while telemetry reconstructs with a constant 5.0
means the reported energy does not describe the path that was actually chosen. Use
one roughness in both. If they genuinely must differ, carry both numbers and say
which is which — a single energy figure belonging to neither path is not a result.

**3. P(ice) is not a weighted index. Delete it.** You found `module_c_ice.py` fits
the forest to labels drawn from `np.random.uniform`, class 1 defined as CPR
1.05-2.5 with low DOP inside a PSR. So it learned the CBOE rule it was handed, and
this frame's CPR maxes at 0.053 — every pixel is an extrapolation outside the
training range. That is not a model with weak labels; it is a threshold rule in a
Random Forest costume, evaluated where it was never fitted. The user's requirement
is that nothing simulated reaches the UI, and this is the one place where the word
is literally in the code.

Remove the `PEAK P(ice)` cell and the `ml_likelihood` layer from the UI. Put the
Step 5a measured quantity in that cell instead: the CPR anomaly percentile within
the measured swath, marked MEASURED, labelled `TOP 1% CPR WITHIN THIS SWATH —
RANKING, NOT A DETECTION`. Keep `module_c_ice.py` on disk with a header stating why
it is unwired, so the work survives if real labels ever exist. Do not retrain it on
better synthetic labels — better synthetic labels are still synthetic.

## Step 9 — two things the user can see. Small, do them early.

- **Default the open map to Surface Relief, not Radar Signals (CPR).** The relief
  layer is the one that reads as terrain. The CPR ribbon painted over it on first
  paint is what made the map look wrong on arrival — the swath is 15.6 % of the
  frame, so the default view was a confetti band across a landscape nobody had been
  shown yet. Radar stays one click away with its own legend, exactly as it already
  works.
- **Clamp zoom-out to the frame.** Derive `minZoom` from
  `map.getBoundsZoom(geom.bounds)` so the raster fills the viewport at the widest
  zoom, and set `maxBounds` to `geom.bounds` with a viscosity so panning cannot
  drift into empty space. Right now zooming out shrinks the strip into a small
  picture floating in a void, which reads as a screenshot rather than a map. Do not
  hardcode a zoom number — derive it, or it breaks the next time the raster changes.
  `HOME_WINDOW_KM = 40` stays as the opening view; this only changes how far out the
  user can go.

Both are additive. `MissionMapHandle` stays byte-identical.

## Order from here

1b (backend modules, all eleven call sites, `grid_to_latlon`, boulder NO DATA) →
9 (the two visible UI fixes, they are cheap) → 2 (PSR/illumination) → 3 (landing
sites) → 4 (traverse) → 5a (anomaly ranking, which also fills the cell vacated by
P(ice)) → 5b (Stokes from the complex products) → 6 → 8.

Steps 2, 3 and 4 are what put shapes and markers on the map, so they come before
5b even though 5b is the harder problem. 5b decides whether `CANDIDATE AREA` is a
real number or a real zero, and both outcomes ship.

<!-- V10_3 -->

## V10.3 — accepted, plus one thing your report exposed that outranks Step 2

Step 1b and Step 9 accepted in full. Three things in that report were better than
what I asked for, and I want them on the record: the `frac>0.5 19.684% -> 29.478%`
percentile table, because it proves the collapse changed the picture and not just
the label; `roughness byte-identical across the spacing change, on purpose`, because
declining to claim an improvement you did not make is the whole discipline; and
`cells identical: False` on two of three routes, because that is the difference
between a renamed number and a corrected one.

The scratch files: **yes, delete both.** `%TEMP%\old_module_f.py` and
`route_delta.py` are outside the repo, the numbers they produced are in your report,
and `test_anisotropic_spacing_changes_reported_distance` is the durable form of the
same check. Nothing is lost.

### Do this before Step 2 — Step 10

The user's instruction is that nothing simulated appears anywhere on the site. I
had been reading that as "the map and the stat cells". Your `shackleton -> DEMO
spacing 250.0 / 250.0 demo-generator` line made me grep for the rest of it, and the
demo path is still wired into five served surfaces. The inversion matters: the
cells the user complains about read `0.00` because they are honest, while the
best-looking numbers in the app are the seeded ones. Fix the ones that look good.

**1. The silent fallback has to become a refusal.** `mission_service.py:103` and
`:249` fall through to `demo_generator.generate_crater_environment()` when the
rasters are missing, and the comment justifies it with "the UI already labels this
DEMO". A label is not enough when the payload it labels carries
`scientific_screening_status: 'PASS'` and `ml_ice_likelihood_mean: 0.96`
(`missionData.ts:53-60` documents exactly this). Return an explicit
`NOT_INGESTED` payload instead — HTTP 200, a status field, no numeric fields at
all rather than zeros. `np.zeros_like` is not an absent state and neither is a
seeded array.

**2. Defaults flip to REAL.** `config.py:18 DATA_MODE = "DEMO"`,
`api_router.py:36 Query("DEMO")`, `mission_service.py:76 data_mode: str = "DEMO"`,
and the same default in `module_a_psr`, `module_b_radar`, `module_c_ice`,
`module_d_terrain`, `module_g_volume`. A caller who passes nothing should get the
truth, not the demo.

**3. `lunar_generator.py` stays on disk, for pytest only.** `test_pipeline.py:12`
runs shackleton/shoemaker/faustini and it should keep working. Gate the generator
behind an env flag that pytest sets and the server never does, so importing it in
a request path raises. Do not delete it — it is the fixture that makes the
anisotropy test meaningful.

**4. `targets.ts` is showing invented science on the landing page.** Six targets
each carry `psrFraction` (0.9 / 0.82 / 0.75 / 0.6 / 0.7 / 0.45), an `evidence`
tier and a `label` like `Promising candidate`, all `demo: true`, none computed
from anything. The `loadTargets()` honesty gate at `missionData.ts:74` correctly
refuses to *overwrite* them with DEMO payloads, but it leaves the placeholders on
screen. `lat`, `lon` and `diameterKm` are published IAU/USGS facts and stay. The
three screening fields must not render for a target with no ingested swath —
`NOT INGESTED · NO DFSAR SWATH IN THIS BUILD` reads better than a fabricated 0.9,
and it makes the one crater that does have a swath mean something.

**5. Two artefacts that look official and are not.** `pdf_generator.py:91-92`
defaults to `crater_name "Shackleton Crater"` / `data_mode "DEMO"` and line 229
prints "Deterministic demo executions use fixed pseudo-random seed 42" inside a
formal report — refuse to generate the PDF unless the run is REAL. And
`WorkflowViews.tsx:931` renders `Seed: {mission.psr.provenance.random_seed}`; once
Step 2 makes PSR measured there is no seed, and the field must disappear rather
than print `None`. While you are there,
`experiments_runner.py:79` asserts "System demonstrates stable parametric
convergence across realistic lunar sensor calibrations" as a
`scientific_conclusion` — report whether anything renders it before you touch it.

### The roughness saturation — your call was right, here is the resolution

You flagged that hazard is scored *after* the resample: on ~1 km serving cells
roughness p50 is 214.5 m against a 50 m divisor, so `clip(roughness/50)` pins to
1.0 and slope stops contributing. Live hazard mean 0.635 with p99 = 1.0 is not a
terrain map, it is a saturation artefact.

Your own proposal is the fix and it is not a retune: **score hazard on the native
25 m frame, then area-average the hazard field down to the serving grid.** At 25 m
the p50 you measured is 5.8 m and the divisor behaves as intended. Averaging a
bounded 0-1 field is a legitimate aggregation; computing roughness across 1 km
cells measures regional relief, which is a different physical quantity wearing the
same name. Do not touch the 50 m divisor.

Carry **two** numbers per serving cell, because the mean alone is wrong for a
rover: `hazard_mean` for traverse cost, and `slope_max` for the hard-impassable
gate in Step 4. A cell that averages safe can still contain a 25° face. Report the
percentile table before and after, as you did for the collapse.

### One consequence for Step 3

Step 3 must run its suitability search on the native 25 m frame, not on the
100 x 100 grid. A site chosen on 1 km cells is located to ±500 m, which is not a
landing site. Score all 14.9 M pixels vectorised, run NMS there, and send only the
resulting site list to the UI.

### Minor

`onCoords` now prints `≈{lat}° ≈{lon}°`. The `≈` is honest, but
`app/ingestion/sar_geometry` is validated to 13.2 mm, so use its inverse for the
cursor readout and the `≈` can go. If you keep the approximation, state its
residual in the report instead of hedging in the UI.

### Revised order

10 (purge the demo path) → hazard-before-resample → 2 → 3 (native grid) → 4 → 5a →
5b → 6 → 8.

Step 10 moves ahead of Step 2 for one reason: every step after it writes numbers
into surfaces that a demo payload can still overwrite, and there is no point
computing a real PSR fraction into a card that a seeded 0.9 can replace on a cold
start.

<!-- V10_4 -->

## V10.4 — all three of your Step 10 questions answered. You were right on all three.

Stopping the chain was the correct call. Taking them in the order you raised them.

### Finding 1 — the filename gate. Approved, and it supersedes item 1.

`3a0911941aa169da25828304e3db391b` appearing on `faustini_lola_dem.tif`,
`shackleton_lola_dem.tif`, `real_dem.tif` and `ch2_sar_dem.tif` is the same class of
bug as the four identical `data/pradan/dem/*.tif` files that broke the Faustini-floor
sanity check earlier in this project — a check that keys on a filename cannot
discriminate between files that share bytes. You are right that this outranks the
DEMO fallback, and for the reason you gave: **DEMO labels itself, and this would
not.** Shackleton serving Faustini's terrain and Faustini's swath under a `REAL`
mark is the worst failure mode available to this app.

Gate on the catalogue's `is_real_data` + `product_id`. Do not gate on
`os.path.exists`. Shoemaker's 40,176-byte rasters are the sample writer's output and
must fail the gate too — size is not the test, provenance is.

One addition: **assert the bytes, do not just trust the catalogue.** `build_analysis`
already has `assert_dem_is_lola()` with tolerance 0.0. Give the per-crater gate the
same shape — a crater marked `is_real_data` whose raster hashes equal another
crater's raster is a hard failure, not a warning. Report the hash table you just
produced as the fixture for that check.

### Finding 2 — the experiments pane. In scope. Fix it, and here is how far to go.

Confirmed by reading it: `WorkflowViews.tsx:794-814` and `:820-836` are hardcoded
JSX literals. `fetchExperiments()` at `api.ts:53` having no callers means
`experiments_runner.py` is dead code, so the fabricated strings there are harmless —
**leave `experiments_runner.py` alone**, it is not on a screen and touching it is
scope you do not need.

The rendered pane is the problem and it is worse than the table you quoted.
Experiment 5 is a fabricated ablation with a suspiciously clean monotonic
sequence — `10.4 -> 11.6 -> 12.2 -> 12.8 km` against `H 0.58 -> 0.45 -> 0.38 ->
0.25` — and its fourth row is **`+ Boulder Hazard`**. Boulder hazard is
`WEIGHT_BOULDER = 0` and NO DATA in this build, by your own V10.1 decision. So the
pane claims a measured effect from the one input the pipeline explicitly cannot
measure. That single row is the most falsifiable sentence in the application.

Four things, and no more:

1. Render Experiment 4 from `mission.rover_routes` — `total_distance_km`,
   `mean_hazard_encountered`, `max_slope_encountered_deg` all exist on
   `RoverRouteResult` and now carry the corrected `18.06 / 39.37 / 18.06`.
2. The `Science Yield` column reads NO DATA.
   `total_scientific_value_collected` exists on the type, but Step 1b(iii)
   established it is a distance restatement wearing the name `scientific_value`.
   A column cannot be honest before the quantity behind it is. Delete the `+193%`
   here and the prose repeat at `:554`.
3. Delete Experiment 5's four hardcoded rows outright. Do not approximate them.
4. **Delete both honesty banners** — the `:779` subtitle claiming "No fabricated
   accuracy claims" and the `:788` ContextBanner claiming "Adheres to strict
   scientific honesty standards". An app does not get to assert its own rigour; it
   shows provenance marks and lets the reader conclude. Those two strings sitting
   directly above fabricated numbers is the single most quotable defect in the
   build, and removing the numbers while keeping the boast leaves the worse half.

A real ablation is genuinely available later and it is worth doing — rerun the
planner with `compute_hazard_score`'s weights zeroed one at a time and report the
measured deltas, with boulder permanently absent rather than fabricated. That is
**Step 11**, after Step 4. Do not start it inside Step 10.

### Finding 3 — your deviation. Accepted, and it is better than what I wrote.

You are right and item 2 was wrong. In those five modules `data_mode` is a
provenance label, not a behaviour switch, and defaulting a provenance label to
`"REAL"` means a caller who forgets gets the strongest possible claim attached to
whatever it happened to be handed. That is the wrong failure direction for the one
field whose entire job is to not lie.

Required with no default, exactly as `spacing_m` was treated, for exactly the same
reason. `test_science.py:58` passing `"DEMO"` explicitly is correct — it is a
synthetic-area test and saying so is the point. `config.py`, `api_router.py` and
`run_full_mission_pipeline` flip to `"REAL"` as specified, because there the
parameter does choose behaviour.

Generalise it: **a provenance field never gets a default.** Add that to the
standing rules alongside "every number reaching the UI carries a mark".

### Continue

`NOT_INGESTED` payload and the per-crater gate, then the three REAL flips, then
`targets.ts` and its two renderers, then the PDF refusal and the `Seed:` field,
then the experiments pane as scoped above. Report at the end of Step 10 — the
hash-equality check and the four pane edits are the two items I want measured
output for.
