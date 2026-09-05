# Claude Code handoff v5 — recover the missing half of the swath, then make the terrain real

> Same session as v4. v4's rendering path is accepted and working — do not redo it.
> This handoff has one headline finding, one big new phase, and three approvals you were waiting on.
> Read section 1 first; it changes what the map looks like more than anything else on the queue.

---

## 0 · Verdict on your v4 report

Accepted. The evidence is good and the honesty list is exactly what I wanted. Specifically accepted:

- The before/after is convincing, and the per-tile brightness spread (median 43→153 of 255 at sd 14.1, while p95 stayed pinned at 157.7–167.3 at sd 2.7) is the cleanest proof of per-tile normalisation I could ask for. Keep that table.
- 1,566 → 13 requests and 40.66 → 14.14 MiB, with 406 KiB first paint. Good.
- Deriving the frame from the product's **own GeoTIFF GeoKeys** and then *validating* it against ISRO's 937,296-node geolocation grid to sub-pixel residuals (sample rms 0.2846 px / 7.11 m, line rms 0.455 px / 11.38 m) is better than the bilinear-interpolation plan v4 specified. Your approach wins; keep it.
- Your corrections to v4's numbers are right and mine were wrong: padding is **84.36 %**, not ~75 %. `cpr_max` on the native array is **0.0534**, not the 0.294 I quoted from `metadata_real.json`.
- Roughness being byte-identical before/after M2 is correct — windowed elevation stdev is spacing-invariant. Do not present it as a gain. Good catch.

## 1 · HEADLINE — the valid mask is throwing away more than half the swath

Your own manifest contains the disproof of its own footprint figure. Three independent ISRO-supplied numbers disagree with the 15.64 % valid fraction, and they all agree with each other:

| source | says the valid swath is | ratio to your 15.64 % |
|---|---|---|
| `isro_sri_ma_nonzero_fraction` | **35.63 %** of the frame | 2.28× |
| geolocation grid incidence: 937,296 nodes − 603,682 fill = 333,614 real | **35.60 %** of nodes | 2.28× |
| PDS4 label `swath` | **19,650 m** wide | 2.24× your 8.775 km median ribbon |

Check the closure: `8.775 km × 2.278 = 19.99 km` against a nominal swath of **19.65 km**. Within 2 %. ISRO's mask product, ISRO's incidence grid and ISRO's label independently say the same thing — **the pass illuminated roughly 2.25× more ground than the map is drawing.**

So the map is not showing you an empty frame because the acquisition was thin. It is showing an empty frame because the valid mask is wrong.

### Where to look

`valid_native.tif` is built from the `lh`/`lv` amplitude rasters being non-zero. Two candidate mechanisms, and I want both tested:

1. **Boolean AND vs OR.** If the mask is `(lh > 0) & (lv > 0)`, then any pixel where *either* channel quantised to zero is discarded. The `sri` products are `UnsignedLSB2` — genuine low-amplitude returns at the swath edges, where the antenna pattern rolls off and incidence is unfavourable, will quantise to exact zero in one channel before the other. Print the fraction for `lh > 0`, for `lv > 0`, for the AND, and for the OR. If OR lands near 35.6 %, that is the whole bug.
2. **Use ISRO's own mask instead of inferring one.** The `ma` product is non-zero on 35.63 % and the geolocation grid's non-fill incidence nodes are 35.60 %. Those are not coincidences — one or both is ISRO's authoritative valid-data footprint. Prefer an ISRO-supplied mask over a threshold you invented. Report which one you adopt and why.

### Why this matters beyond looks

Every CPR and DOP statistic in the app is currently fitted over the **brightest 44 %** of the illuminated swath, because the dim edges were classified as no-data. That biases `p50`, `p99.5`, the log stretch, the legend range, the context-bar means, and any threshold anyone later tunes against them. Fix the mask before touching any number downstream.

Expected visible outcome: ribbon median thickness ~351 px → ~800 px, valid fraction 15.6 % → ~35.6 %, and the map stops reading as a broken load.

### One thing NOT to do

Do not crop or rotate to fit the ribbon. Your manifest already tested cropping (`1783 × 6606`, still only 19.84 % valid) and the ground track curves in polar stereographic because the pole is inside the raster, so deskewing cannot straighten it either. That reasoning is correct — the remaining emptiness after the mask fix is real, and section 2 is how the frame gets legitimately filled.

## 2 · P2 — the real LOLA DEM. This is now the top priority after section 1.

Four of six layers being analytic placeholder topography is simultaneously the biggest honesty problem *and* the reason the map does not look like the Moon. One phase fixes both. Do it next, ahead of P3.

**Your own manifest makes this far cheaper than v3/v4 assumed.** You established that the DFSAR frame is:

- south polar stereographic, spherical, tangent, `k0 = 1.0`
- `body_radius_m = 1737400.0`, `latitude_of_origin = -90.0`, `central_meridian = 0.0`
- `false_easting = 0`, `false_northing = 0`, 25.0 m pixels, `PixelIsArea`
- tiepoint easting −13488.786634 m, northing 38611.318869 m

The LOLA PDS polar GDRs (`ldem_80s_20m`) are **the same projection on the same body radius** — south polar stereographic, `CENTER_LATITUDE = -90`, `A_AXIS_RADIUS = 1737.4 km`. So going from a DFSAR pixel to a LOLA pixel is a scale-and-offset in projected metres plus a bilinear sample. **No reprojection, no GDAL, no proj4, no new requirement.** Closed-form index arithmetic in NumPy.

Concretely:

- Read `MAP_SCALE` / `MAP_RESOLUTION`, `LINE_PROJECTION_OFFSET`, `SAMPLE_PROJECTION_OFFSET`, `SAMPLE_TYPE`, `SAMPLE_BITS`, `SCALING_FACTOR`, `OFFSET`, `LINES`, `LINE_SAMPLES` from the plain-text `.lbl`. Parse them; hardcode nothing.
- `np.memmap` the `.img`. Never load it whole — it is ~1.85 GB. Compute the DFSAR frame's projected bounding box (you already have it: easting −13488.79 … 151961.21 m, northing −17838.68 … 38611.32 m), convert to LOLA line/sample, and slice **only that window**. At 20 m/px that window is roughly 8,270 × 2,820 — about 47 MB as int16. Trivial.
- Bilinear-sample that window onto the DFSAR 2258 × 6618 grid. Apply `SCALING_FACTOR` and `OFFSET` to get metres.
- **Check the sign convention and the datum.** LOLA polar GDR elevations are radius-minus-1737400 m in metres after scaling. Print min/max/p50 and sanity-check against known values: Faustini floor is roughly −3 to −4 km relative to the reference sphere. If your numbers come out positive or an order of magnitude off, the label parse is wrong — do not proceed.
- **Keep the output filenames identical** — `real_dem.tif`, `ch2_sar_dem.tif`, `faustini_lola_dem.tif`, `shackleton_lola_dem.tif` — so nothing downstream needs touching. But now the `*_lola_dem.tif` names will finally be true.
- If `ldem_80s_20m.img` is not already on disk, fetch the smaller `ldem_75s_240m` first and prove the whole path end-to-end on it before spending the 1.85 GB download. 240 m is too coarse to ship, but it validates the label parser, the projection arithmetic and the resampling in minutes.

**Then delete the synthetic generator.** Remove the `np.linspace`/`meshgrid`/`np.exp` Gaussian block and the `terrain_undulation` sinusoids from `process_real_sar_pipeline.py` (lines ~117–133), and remove the `s0_resampled` modulation at line ~131 that injected radar brightness into the fake DEM — that injection is the hard seam you observed at the swath edge on the hazard and hillshade panels. It disappears on its own once the DEM is measured.

**What changes visibly:** hillshade, `dem_elevation`, `hazard_map` and `illumination` become real measurements over 100 % of the frame — actual Faustini/Shackleton crater rims and floors instead of Gaussian blobs. The `SYNTHETIC DEM` badges come off those four layers. The radar ribbon then sits on top of real terrain, which is what the map has been missing.

**Verification I want:** the hillshade must show recognisable crater rims that match a published LOLA south-polar shaded-relief image; print the before/after slope and hazard percentile tables again (the M2 numbers were fitted on invented topography, so they will move and that is expected); and re-state which layers are `measured` versus `synthetic` in `layers.json`.

## 3 · Three approvals you were waiting on

**3a — Yes, delete the old tiles.** Run it:

```
git rm -r backend/tiles/faustini backend/scripts/generate_tiles.py backend/scripts/compare_tiles_vs_single.py
```

Before you do, paste the per-tile brightness spread table and the before/after comparison image into the commit message body. The tiles are recoverable from history, but the *measurement* that justified replacing them should be in the log where a reviewer will find it, not only in a chat transcript. Commit the before/after PNG itself into `docs/` so it survives — it is viva evidence.

**3b — Yes, un-gate the map from the mission JSON.** v4 said keep `Props` byte-identical; I am relaxing that here, narrowly, because you found a real defect and the fix serves the whole point of moving imagery to Vercel.

Right now `MissionControl.tsx:118` is `{mission && <MissionMap …/>}`, so on Render's free tier the user stares at nothing for the entire cold start — 30–50 seconds — even though every pixel is already sitting on a CDN and returned in 11–37 ms with the backend dead.

Do it as an **additive** widening, not a restructure:

- `mission` becomes optional/nullable in `Props`. Every other prop keeps its exact name and type.
- `MissionMapHandle` stays byte-identical — `zoomIn` / `zoomOut` / `reset` unchanged.
- With no `mission`: render the raster layers, panes, graticule, scale bar, footprint ring and coord readout. Skip only what genuinely needs the analysis — landing-site markers, rover routes, the target marker.
- Show a small honest status chip while the analysis is in flight, e.g. `TERRAIN LOADED · ANALYSIS PENDING`. Do not fabricate placeholder markers.
- Keep the `Failed to fetch` banner for the analysis panels. The map painting and the analysis failing are different states and should look different.

**3c — Yes, fix the verdict card, and treat it as the highest-priority UI defect.** It currently reads **72 % "EVIDENCE CONSISTENT WITH POSSIBLE ICE"** directly above `Mean P(ice) 0.00 · model confidence Low · screening NOT PASSED` with all five checklist rows at ✗. A panel will read the big number, then read the ✗ column, and conclude the dashboard is decorative. That single card can undo the credibility the rest of this work is buying.

The headline number must be derived from the screening outcome, not from a peak over a model whose slope and temperature features come from placeholder topography. Options, in order of preference: (i) make the headline the screening verdict itself — `SCREENING NOT PASSED` — and demote 72 % to a labelled `peak model output (features include synthetic DEM)` row; (ii) keep a percentage but compute it as the fraction of criteria passed, which is currently 0 of 5. Either is defensible. The present card is not.

## 4 · Context for P3 — the CPR is structurally dead, not merely mis-thresholded

Do not spend any time retuning `CPR_THRESHOLD`. It cannot be rescued, and here is the reason, which is worth knowing before P3 so you build the right thing:

`sigma_sc = 0.5·(√lh − √lv)²` and `sigma_oc = 0.5·(√lh + √lv)²`, so

```
CPR = ((√lh − √lv) / (√lh + √lv))²
```

That is a **channel-imbalance ratio**, squared. When LH and LV backscatter are similar — which is the normal case over regolith — the numerator goes to zero. Your measured `p50 = 0.000565` and `max = 0.0534` are not an unusual Moon; they are that algebra. Published lunar CPR is 0.3–0.7 for normal regolith, so the median is off by roughly three orders of magnitude, and no threshold anywhere in `[0, 1]` makes this quantity behave like CPR.

True hybrid-polarity CPR needs `S3 = 2·Im⟨E_H · E_V*⟩`, i.e. the **phase** between channels, then `CPR = (S0 − S3)/(S0 + S3)` — which `module_b_radar.py` already implements correctly and has never been fed. The phase is present only in the complex `sli` products (`ComplexLSB8`, 355768 × 759, ~2.17 GB per channel).

So P3 is: `np.memmap` the complex rasters, multi-look in row blocks (the label indicates 21 azimuth looks), form the full Stokes vector including the phase term, feed the existing `compute_cpr_from_stokes()` / `compute_dop_from_stokes()`, and geocode from slant range to the `sri` frame. Only after real CPR exists does threshold tuning mean anything.

Also still open, unchanged: `module_b_radar.py` lines 113–116 assert "Radar signature consistent with potential ice-bearing volume scattering" even when the detected area is 0.00 km². Make the interpretation string conditional on the detection actually being non-empty.

## 5 · Also still queued

`mission_service.py` `pixel_scale_m = 250.0` — leave it until the real DEM lands (section 2), then set it from the frame in the same commit as the P2 percentile tables.

`target_coordinates = {x: 50, y: 50}` is the grid centre, not a measured maximum, and all three rover routes terminate there with `science_value: 0`. The five landing sites are hardcoded and, as your screenshot now proves, sit outside the radar footprint. Both are P4. Note that P4 gets much easier after section 2, because a per-pixel suitability search over real topography is the whole point — searching invented Gaussians would be theatre.

`dop_heatmap` is rendered but not exposed in the map's LAYERS control. Add it.

## 6 · Order of work

1. Section 1 — the valid mask. Cheapest, and it is the single biggest change to what the map looks like.
2. Re-run `render_layers.py`. Report the new valid fraction, ribbon thickness, and the corrected CPR/DOP percentiles and stretch, since the old ones were fitted over the bright half only.
3. Section 3b + 3c — un-gate the map, fix the verdict card. Small, high credibility payoff.
4. Section 2 — real LOLA DEM. The big one.
5. Then P3, then P4.

Do 1 and 2 first and show me the map before starting 3, so I can see the ribbon at full width.

Return each touched file complete. Keep `MissionMapHandle` byte-identical throughout.



