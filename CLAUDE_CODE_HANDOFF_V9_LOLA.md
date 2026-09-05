# HANDOFF V9.1 — INGEST A REAL LOLA POLAR DEM

Read `CLAUDE_CODE_WORKING_RULES.md` first. One browser session at the end, not
during.

**Revised after the V9 report.** Both objections it raised against V9 were
correct and are fixed here: Step 4's line numbers now point at
`synthetic_placeholder_dem()` at 153-188 (not `_stat_block()`/`_ribbon()` at
117-133), and Step 3.2 is downgraded to reported-not-enforced because it cannot
discriminate. New in 9.1: Step 1 is split into a 120 MB phase A that runs today
and a 1.9 GB phase B that follows, the three OHRC decisions are approved, the
`git rm` is approved, Step 4b corrects the report's stale picture of the frontend
tree, and the full-file paste rule is formally waived for the new script only.

## Why this is the only task that matters

Four of the six map layers — `hillshade`, `dem_elevation`, `hazard_map`,
`illumination` — carry `"provenance": "synthetic-terrain-derived"` in
`frontend/public/layers/layers.json` and are all derived from one array built by
`synthetic_placeholder_dem()` in `backend/scripts/process_real_sar_pipeline.py`
(defined ~line 153, called ~line 363, logs `[SYNTHETIC] building analytic
placeholder DEM (no LOLA data involved)`). It is Gaussians plus sinusoids.

`backend/app/ingestion/pradan_pipeline.py:221-225` then writes the "optical"
products from a hillshade of that same fake array:

```python
ohrc_file = PRADAN_DATA_DIR / "ohrc" / f"{crater_id}_ohrc_pan.tif"
hill = compute_hillshade(env["dem"])
ohrc_img = (hill * 255.0).astype(np.uint8)
cv2.imwrite(str(ohrc_file), ohrc_img)
```

So there is no real terrain anywhere in `data/pradan/**`, and no real optical
image either. Every UI change made so far has been styling a placeholder. Until
this handoff is done, "zoom in and identify terrain" is not a UI problem.

`metadata_real.json` already says so, verbatim, under
`product_provenance.synthetic_placeholder_warning`.

## Constraints — non-negotiable

- No `rasterio`, no GDAL, no `gdalinfo`. Local Python 3.13 has numpy, cv2, PIL,
  scipy, tifffile only. Do not add anything to `requirements.txt` — Render
  cannot build scipy from source.
- Never `imread` a multi-GB raster whole. Windowed `np.memmap` reads only.
- Parse the PDS `.lbl` as plain text. Hardcode nothing that the label states.
- Do not invent data. If a step cannot be computed, label it and stop.
- Ask before any `git rm`.

## Step 1 — the download (the user must do this)

`data/pradan/` contains no LOLA product; confirm with
`git ls-files data/ | findstr /i ldem` and a recursive listing before assuming
otherwise. Source: the LOLA PDS node at https://imbrium.mit.edu, path
`/DATA/LOLA_GDR/POLAR/`. The `JP2/` subdirectory is confirmed to exist; the raw
`IMG/` sibling is where the .IMG/.LBL pairs live — check both. The JP2 variants
are lossy-compressed derivatives with no reader in the allowed dependency set,
so take the .IMG, not the .JP2. WUSTL ODE (https://ode.rsl.wustl.edu/moon) is
the alternative search interface if the directory listing moves.

**Ingest in two phases. Do not wait for phase B to start phase A.**

**Phase A — `LDEM_80S_80M.IMG` + `.LBL` (~110 MB, 80 m/px, 80S to the pole).**
**DOWNLOADED — the user has both files. The `.LBL` has been read and verified;
see the corrections block in Step 2. Start here.**
This is the whole ingest, end to end, on real measured LOLA topography, at a
download size that finishes today. It covers the frame — confirmed against the
label, not assumed. Run every step against it, ship it, and let the map stop
being synthetic. The resample to the 25 m DFSAR grid is an upsample by 3.2x, so:

- the provenance string must name the product and its native resolution, e.g.
  `"LOLA LDEM_80S_80M v2.0, 80 m/px native, bilinear to 25 m grid"` — never just
  "measured". The number the reader needs is 80, not 25. The product is a shape
  map whose values are heights above the 1737.4 km reference sphere, LOLA Laser
  1+2 through 2017-02-02, GRAIL 900C-consistent; that lineage belongs in the
  sidecar.
- write `native_metres_per_pixel` and `resample_ratio` into the provenance
  sidecar so the upsample is a stated fact, not a silent one.
- do NOT re-derive slope or hazard thresholds as if they were 25 m slopes.
  Slope over an 80 m post is a different quantity; label the tables with the
  post spacing they were computed at.

**Phase B — `LDEM_80S_20M.IMG` + `.LBL` (~1.9 GB, 20 m/px).** Same code path,
same output filenames, one `--input` change. This is the one the frame really
wants: the DFSAR frame reaches 89.26S at one end and roughly 84.5S at the
other, so the tighter `LDEM_875S_20M` does NOT cover it. When it lands, re-run
and update the provenance string and the percentile tables. Nothing downstream
should need editing — if it does, phase A was wired wrong.

Phase A doubles as the Step 3.1 reader validation, so no third product is
needed. Place both under `data/pradan/lola/`. Stop and report if phase A is
absent; do not substitute.

## Step 2 — windowed read

The frame to cut, in south polar stereographic metres (spherical, tangent,
k0 = 1.0, R = 1737400, lat_0 = -90, lon_0 = 0, 25.0 m pixels, PixelIsArea) —
these come from `metadata_real.json`, re-read them rather than trusting this file:

    easting   -13488.79 … 151961.21 m
    northing  -17838.68 …  38611.32 m

At 20 m/px the window is about 8270 x 2820; at 80 m/px it is 2069 x 706. Either
way it is tens of MB of int16, not gigabytes. Read it with
`np.memmap(path, dtype=<from SAMPLE_TYPE/SAMPLE_BITS>, mode='r', shape=(lines, samples))`
and slice — never materialise the full array. Resample to the DFSAR
2258 x 6618 grid at 25 m with `scipy.ndimage.map_coordinates(order=1)`. Derive
the window from the label's own `LINE_PROJECTION_OFFSET` /
`SAMPLE_PROJECTION_OFFSET` and `MAP_SCALE`, so the same code serves both
products with no constant changed.

### The phase-A label has been read. Four things in this handoff were wrong.

`LDEM_80S_80M.LBL` is on disk and verified. Corrections, all of which would have
produced silent garbage:

1. **`SAMPLE_TYPE = LSB_INTEGER`, `SAMPLE_BITS = 16` → dtype is `<i2`, little
   endian.** This handoff's earlier `'>i2'` was wrong. Byte-swapped int16 reads
   as plausible-looking noise, so nothing would have crashed. Keep deriving
   dtype from the label and never hardcode endianness.
2. **`HEIGHT = DN * SCALING_FACTOR`. Do NOT add `OFFSET`.** This handoff said
   "scale by `SCALING_FACTOR` and `OFFSET`" — that is wrong. The label states
   `OFFSET = 1737400.` is the reference sphere radius and is used only for
   `PLANETARY_RADIUS = DN*SF + OFFSET`. Adding it to elevation gives ~1737 km
   heights. `SCALING_FACTOR = 0.5`, so elevation in metres is `DN * 0.5`.
3. **`MAP_SCALE = 80 <m/pix>` — metres, not km.** The V9 report warned that
   polar labels use `<KM/PIXEL>`; this one does not. Both spellings exist in the
   same product family, which is exactly why the unit must be parsed out of the
   angle brackets rather than assumed either way.
4. **There is no `MISSING_CONSTANT` in this label.** LOLA GDRs are fully
   interpolated grids. Step 3.3 must check "no NaN" only and must not invent a
   fill value. If a `MISSING_CONSTANT` is absent, say so in the sidecar; do not
   substitute a guessed sentinel.

Numbers to check against, taken from the label itself:

    LINES = LINE_SAMPLES        7600 x 7600
    RECORD_BYTES                15200  (= 7600 x 2, so no line prefix)
    expected .IMG size          7600 x 15200 = 115,520,000 bytes exactly
    LINE/SAMPLE_PROJECTION_OFFSET  3799.5 px both axes
    MAP_SCALE                   80 m/px
    A=B=C_AXIS_RADIUS           1737.4 km
    CENTER_LATITUDE / LONGITUDE -90 / 0, MAP_PROJECTION_ROTATION 0.0
    MIN/MAXIMUM_LATITUDE        -90 / -80
    DERIVED_MINIMUM / MAXIMUM   -14592 / 14052 DN
    → Step 3.1 fatal target     -7296.0 m / +7026.0 m after x0.5

Two independent geometry confirmations already done from the label, worth
reproducing in the run log because they validate the projection assumption
rather than assuming it:

- Array half-width is `3800 x 80 = 304,000 m`. The analytic polar-stereographic
  radius of the -80 deg parallel on a 1737400 m sphere, tangent, k0 = 1, is
  `2 x 1737400 x tan(5 deg) = 304,006 m`. Agreement to 6 m confirms MAP_SCALE,
  the radius, k0 and the tangent-plane assumption simultaneously.
- The DFSAR frame's farthest corner sits at
  `hypot(151961.21, 38611.32) = 156,790 m` from the pole, i.e. 84.83 deg S —
  which matches `metadata_real.json`'s own southern limit and is well inside the
  304,000 m half-width. **Phase A covers the whole frame with 147 km to spare.**
  Confirm this in code before reading; do not take it from this file.

The projection parameters match the DFSAR frame exactly — same sphere, same
tangent point, same rotation — so DFSAR pixel to LOLA pixel remains
scale-and-offset in projected metres plus bilinear. No reprojection.

`LINE_PROJECTION_OFFSET = 3799.5` is a half-integer against `LINE_FIRST_PIXEL = 1`,
and the label's DESCRIPTION says "pixel registration". PDS3 line/sample origin
conventions differ by a half pixel between implementations, and at 80 m a
half-pixel slip is 40 m. Do not hand-derive it: settle it with the existing
`--selftest-crs` fixture plus two hard assertions on the real product — the pole
must land at the array centre to under one pixel, and the mid-edge sample must
read -80.000 deg latitude to under 0.001 deg. Report both residuals as numbers.

## Step 3 — sanity checks

1. **Fatal.** The read reproduces the product's own label `MINIMUM`/`MAXIMUM`
   elevation to within one quantisation step, from raw bytes, on whichever
   product is being ingested. This is the only check here that can tell a real
   product from a fabricated one, because it is the only one that compares
   against a number the product carries about itself. Run it via `--check-only`
   before the full read.
2. **Reported, not enforced.** Faustini's floor lands at roughly -3 to -4 km
   relative to the 1737.4 km sphere. Print the number; do not tune anything to
   hit it. This check cannot discriminate and must not be treated as if it can:
   the four existing `data/pradan/dem/*.tif` are byte-identical copies of one
   2048x2048 synthetic array (md5 4a3363114e18bce876320c670366e350) spanning
   -4138.232 to -1753.338 m, so the placeholder already passes it. Two of those
   filenames claim LOLA and one claims "real"; Shackleton and Faustini sharing a
   single array is impossible for measured data.
3. **Fatal.** Resampled frame has no NaN and no label `MISSING_CONSTANT` values
   surviving into the output.

Unresolvable offline, so it must be written into the provenance sidecar verbatim
rather than assumed silently: whether LOLA's +y axis means the same direction as
DFSAR's +y. Both labels state south polar stereographic, sphere, centre latitude
-90, centre longitude 0, no rotation, so they are taken to agree — but settling it
would need a third elevation source, which does not exist offline.

## Step 4 — swap it in

- Delete `synthetic_placeholder_dem()` at
  `process_real_sar_pipeline.py:153-188`, called at :362. The radar-amplitude
  modulation is inline at :179-186 and goes with it — elevation must come from
  LOLA alone. Do NOT touch :117-133: that is `_stat_block()` and `_ribbon()`,
  which feed the statistics written into `metadata_real.json`.
- Keep every output filename identical so nothing downstream needs to change.
- Re-run the slope and hazard percentile tables — the old thresholds were fitted
  to analytic topography and are meaningless against real relief. Print the new
  distributions.
- Flip the four `provenance` tags in `layers.json` from
  `"synthetic-terrain-derived"` to a string that names the source product and its
  native resolution (see Step 1 phase A). `MissionMap.tsx` reads that string; the
  test it applies is
  `PLACEHOLDER_PROVENANCE = /synthetic|placeholder|analytic|unknown|unavailable/i`,
  so the new string must contain none of those six words or the UI will keep
  captioning real LOLA data as a placeholder. Do not touch the tooltip text and
  do not touch that regex.
- **Approved — do it.** Delete the write at `pradan_pipeline.py:222-225`, reached
  only from `api_router.py:124`. A hillshade of a DEM is not an OHRC product and
  must not be written to a file named as if it were. Then delete the three
  existing 8 KB `*_ohrc_pan.tif` files, because deleting the write does not stop
  consumption — `mission_service.py:180` is `.exists()`-guarded and would still
  read them. Confirm they are not tracked by git before deleting; if they are,
  `git rm` them so the deletion is recorded rather than showing as local drift.
- **Approved — do it.** Replace that guard's `np.zeros_like(dem)` fallback with an
  explicit absent state the UI can report. A zero array is an unlabelled "no
  boulders anywhere" claim and reads as a measurement. Boulder count absent and
  boulder count zero are different facts and the payload must be able to say
  which.
- **Approved — do it.** Run the previously agreed
  `git rm -r backend/tiles/faustini backend/scripts/generate_tiles.py backend/scripts/compare_tiles_vs_single.py`.
  The tile-pyramid approach was abandoned for single-image layers; this is dead
  weight and stays recoverable in history. Report what was removed.

## Step 4b — the frontend working tree is NOT what the V9 report assumed

The V9 report states "No frontend file was touched this session" and treats the
`M` entries under `frontend/` as prior v7 work. That is stale. A v8 pass landed
in that same working tree and it is unverified:

- `MissionMap.tsx` — the coverage panel is **already deleted**, so drop it from
  the "still carried" list. Also deleted: the `mc-void` pane, the three void fill
  polygons, `ensureHatch()` and its SVG `<pattern>`, all `TINT_*` / `HATCH_*` /
  `VOID_TINT` constants, and `covSitesRef` / `covTargetRef` / `covRoutesRef`.
  Added: `OUT_OF_COVERAGE = '#f2c14e'`, `HOME_WINDOW_KM = 40`, and
  `homeBounds` / `homeKm` on `MapGeometry`. `MissionMapHandle` is byte-identical;
  `reset()` now flies to `homeBounds`, not the full extent.
- `mc.css` — `.mc-void-hatch`, `.mc-void-hatch--measured`, `.mc-void-scrim` and
  the entire `.mc-map-coverage` key block deleted. `.mc-map-degraded` and
  `.mc-map--pixelated .mc-raster` preserved.
- `.env.local` — every line is now a comment; `api.ts` falls back to
  `http://127.0.0.1:8000`, so **the local FastAPI backend must be up on :8000**
  or the UI shows the Render host's DEMO payload.

Required before reporting: re-run `npx tsc --noEmit -p tsconfig.app.json` (the
earlier exit 0 may predate these edits), then one browser session on
`localhost:3000#mission` with the backend up, confirming four things — no
coverage panel in the DOM, no `mc-void` pane, the opening view is the 40 km
window rather than the 1:2.93 full strip, and "Reset view" returns to that same
window. Report the five landing sites and three routes as visible-in-amber or
not. If any of the four is wrong, say which and stop rather than styling around
it.

## Step 5 — report

State, per numbered step: the command run, the numbers measured, and what
changed. If a step failed, say which and stop. One browser session at the end,
zoom fixed, `setZoom(z, {animate: false})`, wait on the image `load` event.

## Out of scope for V9 — do not start these

True Stokes CPR from the complex `sli` products; the landing-site suitability
search; `mission_service.py` `pixel_scale_m` (still 250.0 against a 25.0 m
frame); the missing `ml_likelihood.webp`. Each is its own handoff.

## Standing-rule exemption, granted

`ingest_lola_polar_dem.py` does not need to be pasted back in full. The
"return the complete updated file" rule exists so a file being edited on the
user's behalf can be diffed and dropped in; a brand-new 1,221-line script with
no prior version and no pending edit has nothing to diff against. Print only the
parts that change, plus any function whose behaviour a reviewer would need to
check. The rule still applies in full to `MissionMap.tsx`, `mc.css`,
`process_real_sar_pipeline.py`, `pradan_pipeline.py`, `mission_service.py` and
`layers.json`.

Two things the report got right that are worth keeping in the record. The four
`data/pradan/dem/*.tif` being one md5 means `real_dem.tif` and
`faustini_lola_dem.tif` are the same fabricated array under different names —
that is what killed the Faustini-floor check as a discriminator. And
`MAP_SCALE = 0.020 <KM/PIXEL>` is a 1000x trap that produces plausible-looking
floats; parsing the unit out of the angle brackets and raising when it is absent
is the correct handling, and the same treatment belongs on every dimensioned
label field, not just the two already covered.
