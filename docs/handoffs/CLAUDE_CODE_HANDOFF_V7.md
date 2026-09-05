# Claude Code handoff v7 — the map looks broken because we are multiplying 84 % of it by 0.18

> Section 2 of v6 is accepted and done. This handoff is the **compositing and vector layer**, and it is
> entirely front-end: no re-render of `render_layers.py` output is required, no backend change,
> no new data. Two files: `MissionMap.tsx` and `mc.css`.
>
> Read section 1 before writing anything. The bug is not in the imagery.

---

## 0 · Accepted — section 2 of v6 is done and the diagnostics were exactly right

The three diagnostics are the good kind: they found a cause I had guessed at *and* a second one I had not.

Confirmed as I expected: the deployed endpoint returns HTTP 200 with `data_mode: "DEMO"`, silently discards `?data_mode=REAL`, and ships `data_source_tag: "Simulated placeholder — pending real data"` inside the same payload as `ml_ice_likelihood_max: 0.96` and `expected_volume_m3: 17,580,000`. Byte-identical to the screenshot. And there is no client-side fallback — `api.ts` throws, `MissionControl` sets `error`, everything is gated on `mission &&`. A fabricated payload arriving with a 200 is not catchable at the client. That is the whole argument for moving the verdict to a static asset, and it now is.

**My memory-limit reasoning was wrong and yours is right.** I sized the request path against `2258 × 6618 × 4 = 59.8 MB` per array; you measured it and the path never touches the native frame — 2048² float32 at 16.8 MB, downsampled to 100² immediately, peak RSS 224 MB. Memory was never the binding constraint. `git ls-files data/` returning zero, plus hardcoded `d:/FYP/...` absolutes at `mission_service.py:105-110`, is the actual cause. Correcting my note.

**The second defect you found on your own is the more important one.** `process_real_dem(target_shape=(100,100))` resampling 2048² → 100² means each output cell averages 419 native pixels of which 84.4 % are literal zero padding, so every statistic was being taken over the void:

| quantity | native, masked | 100² bilinear | error |
|---|---|---|---|
| CPR mean | 0.001312 | 0.000238 | 5.5× low |
| CPR max | 0.053411 | 0.043846 | 18 % low |
| DOP mean | 0.057053 | 0.009463 | 6.0× low |
| DOP p50 | 0.047532 | 0.000000 | destroyed |

Even the "honest" local REAL numbers were wrong. Nobody asked you to look there. Good.

Both judgment calls stand. PSR as `UNAVAILABLE` rather than `MODELLED` is right — 98.24 % of the frame below the shadow cut is a statement about the placeholder surface, not about cold traps, and a `MODELLED` badge would have let a degenerate model keep printing a number. And recording P(ice)'s own incoherence — 48.91 % of measured pixels at P ≥ 0.5 while peak CPR sits 19× under threshold, from a classifier trained on CPR 1.05–2.5 that this product cannot reach — is exactly the kind of thing that turns a weakness into a finding. Keep that note in the JSON verbatim.

Noted and agreed on `missionData.ts` still hitting `/api/mission/{crater}` for the landing page. Out of scope here; it is on the list below.

---

## 1 · Why the map "looks worse than before" — do the composite arithmetic

The user's complaint is that the map used to look white and real and now looks dark and strange. He is right that it looks worse, and the cause is not the imagery, the normalisation, or the WebP. **It is one number in `MissionMap.tsx`.**

Trace a single pixel outside the pointed swath through the stack you have today.

`mc.css:449` lifts the base first:

```
.mc-raster--base { filter: contrast(1.14) brightness(1.16) saturate(0.92); }
```

Take a mid-grey hillshade sample, `v = 140`. Contrast about the 128 pivot: `(140 − 128) × 1.14 + 128 = 141.7`. Brightness: `141.7 × 1.16 = 164.4`. So the terrain arrives at the compositor at **164 / 255** — bright, healthy, exactly what it should be.

Then `MissionMap.tsx:495-498` puts this on top of it:

```
L.polygon([frame, swathRing], { fillColor: '#03060c', fillOpacity: 0.82 })
```

`#03060c` is `(3, 6, 12)`. Straight alpha compositing:

```
R = 0.18 × 164.4 + 0.82 ×  3 = 32.1
G = 0.18 × 164.4 + 0.82 ×  6 = 34.5
B = 0.18 × 164.4 + 0.82 × 12 = 39.4
```

**RGB ≈ (32, 35, 39) — 12.6 % relative luminance.** Indistinguishable from the `#03060c` map background at `mc.css:204`. And `footprint.padding_fraction` says this applies to **84.36 % of the frame.**

The second scrim, at `fillOpacity: 0.5` over pointed-but-silent ground:

```
0.5 × 164.4 + 0.5 × (3, 6, 12) = (83.7, 85.2, 88.2)
```

Mid-grey. That is precisely the band visible in the screenshot. **The arithmetic reproduces the screenshot exactly, so there is nothing else to look for.**

Now compare against what he remembers as better. The old tile build had **no scrim at all**, and every tile was percentile-stretched *individually*, so each tile pushed its own local range up to near-full — the measured spread was median 43→153 with p95 pinned at 157.7–167.3. Bright everywhere. It looked "white and real" because it was **wrong in a flattering direction**: brightness was a rendering artefact, not the surface.

So there are two changes stacked on top of each other, and they must be judged separately:

- **Correct global normalisation** replaced per-tile stretching. This is a genuine fix. **Do not undo it, do not soften it, do not reintroduce any per-region stretch.**
- **The 0.82 scrim** is a compositing decision I asked for, and at that value it is a bad one. Fix this.

### Why 0.82 is wrong on its own terms

The scrim exists to say *"no radar measurement here"*. At 0.82 it does not say that — it says **"no data here at all"**, which is false: there is a full-frame DEM under it, and after v6 §4 that DEM will be *real measured LOLA topography*. Encoding "unmeasured by instrument A" as "black" throws away everything instrument B knows about the same ground. A geological map does not black out the area outside a survey line; it hatches it.

There is also an honesty inversion worth naming. Darkness reads to a viewer as *absence*, not as *fabrication*. The region under the scrim is the region containing **placeholder topography** — the part of the map that most needs to be marked as not-real. Making it dark hides the placeholder instead of flagging it. A visible hatch with a legible label marks it *more* honestly than blackness does, and keeps the terrain readable at the same time.

---

## 2 · The fix — encode category with texture, keep luminance for data

Three tiers stay, and stay unambiguous. What changes is that tier is carried by **texture and outline**, not by crushing brightness.

Target composite luminance, as a fraction of the base:

| tier | area | today | target | how |
|---|---|---|---|---|
| never observed (outside `swathRing`) | 64.4 % of frame | **0.18** | **≈ 0.70** | diagonal hatch + flat tint `0.20` |
| pointed, no amplitude returned | 20.0 % | 0.50 | **≈ 0.90** | flat tint `0.10` + existing grey outline |
| amplitude ribbon (`ring`) | 15.6 % | 1.00 | 1.00 | unchanged |

Tier separation stays far above threshold: ~20 % luminance steps across large areas, against a just-noticeable difference of roughly 1–2 % for fields this size. Nobody will confuse them. But the crater relief survives in all three, which is the entire point once LOLA lands.

**Implementation, in `MissionMap.tsx`:**

Inject an SVG `<defs><pattern>` into the `mc-void` pane's SVG root after the renderer exists, then give the outer polygon a `className` and let CSS fill it with `url(#mc-hatch-void)`. Pattern: 7 px pitch, 1 px stroke, `rgba(132, 156, 178, 0.34)`, 45°. Keep `fillOpacity` low and flat underneath it so the hatch reads as marking rather than shading.

Leaflet builds its SVG lazily, so do the injection inside a `map.whenReady()` (or immediately after the first polygon is added, which forces the renderer to exist) and **guard it**: if the SVG root or `pattern` support is missing, fall back to a flat `fillOpacity: 0.34` of `#0a1420` and log once. A hatch that silently fails to a transparent fill would erase the distinction entirely, which is worse than a flat tint.

Do not use `mix-blend-mode` here. M5 already established that blending destroys the ribbon; the same risk applies to the scrim.

**Also make the scrim's meaning depend on the base layer's provenance, read from the manifest.** These are two different statements and they will both be true at different times:

- base is `synthetic` (today) → hatch + label `PLACEHOLDER TERRAIN — NO RADAR COVERAGE`
- base is `measured` (after v6 §4) → drop the hatch to a light tint only, label `NO RADAR COVERAGE · LOLA TERRAIN`

Drive it off `manifest.layers[].provenance` for the base entry, not a constant. Then v6 §4 requires no second visual pass — the map re-labels itself when the data becomes real. This is the same discipline as the per-value provenance marks in the verdict card: the UI states what it has, and changes when what it has changes.

**Then re-check the base filter, measured not guessed.** With the scrim at 0.82 the `brightness(1.16)` at `mc.css:450` was compensating for a crush that is about to disappear. Print the 8-bit histogram of `hillshade.webp` — mean, median, p2, p98, and the clipped fraction at 0 and 255. Rule, not a guess: if the post-filter median exceeds ~190 or more than 1 % of pixels clip at 255, walk `brightness` back until neither holds. Report the numbers before and after.

---

## 3 · The vectors — they are outside the data, and the map should say so

Second half of the complaint: routes and markers run out into ground where nothing is visible. That is not a projection error. `gridToPixel` maps the backend's 0–100 grid linearly across the full 2.93 : 1 extent, which correctly un-squashes the square analysis grid — the geometry is right. The problem is that the positions themselves are hardcoded grid offsets (`module_e_landing.py`: Alpha 18,50 · Beta 82,75 · Gamma 78,25 · Delta 50,15 · Epsilon 48,85) and `target_coordinates` is the grid centre `{x: 50, y: 50}`, so they land wherever they land — mostly in the void, and all three routes terminate at frame centre.

The honest fix is not to hide this. It is to **measure it and show it**, because it is the argument for P4.

**1. Add a point-in-polygon test** — plain ray casting, ~20 lines, no dependency — against `geom.ring` and `geom.swathRing`, both of which are already in CRS units in `MapGeometry`. Classify every landing site and every route waypoint as `amplitude` / `swath` / `outside`.

**2. Style by classification, do not delete:**

- inside the amplitude ribbon → current styling, unchanged
- inside the pointed swath only → same colour, `dashArray`, `opacity: 0.6`
- outside both → hollow, `weight: 1`, `opacity: 0.35`, no fill

**3. Say it in the tooltip,** on every marker and route that is not fully inside the ribbon:

> Outside DFSAR radar coverage. This position is a fixed grid offset, not a terrain-search result — see `module_e_landing.py`.

**4. Print the count and surface it.** A small map chip, driven by the computed result and not by a constant:

```
PLACEHOLDER SITES · 4 OF 5 OUTSIDE RADAR COVERAGE
```

I do not know whether it is 4 of 5 — compute it and let the chip say whatever is true. Also print, per route, the fraction of waypoints inside the amplitude ribbon. `Science-Aware` claiming a science-weighted path while spending most of its length over ground with no radar measurement is a number a reviewer will ask for, and it is better coming from you.

**5. Stop flying to a point in the void.** `MissionMap.tsx:671` does `map.flyTo` to `target_coordinates` unconditionally, and that target is frame centre — so the opening move is a zoom into empty ground, which is a good part of why the map reads as broken on load. Gate it: fly to the target only when the target tests inside the amplitude ribbon; otherwise fly to `geom.ribbonCentre`, which is already computed at line 246. Keep the marker drawn either way, styled per rule 2, with the same tooltip. Leave the opening `zoom: geom.nativeZoom` and the `reset` → `flyToBounds(geom.bounds)` behaviour alone.

---

## 4 · Then v6 §4, unchanged, and it is the real answer to "it doesn't look real"

Everything above makes the map *legible*. It cannot make it look like the Moon, because `dem_native_synthetic.tif` is Gaussians and sinusoids and no compositing rescues that. Real LOLA is what makes the terrain real:

`ldem_80s_20m` is the same south polar stereographic projection on the same 1737.4 km radius as the DFSAR frame, so DFSAR pixel → LOLA pixel is scale-and-offset in projected metres plus a bilinear sample. `np.memmap` the `.img`, slice only the frame's projected bbox (easting −13488.79 … 151961.21 m, northing −17838.68 … 38611.32 m ≈ 8270 × 2820 int16 ≈ 47 MB), parse `MAP_SCALE` / `LINE_PROJECTION_OFFSET` / `SAMPLE_PROJECTION_OFFSET` / `SCALING_FACTOR` / `OFFSET` / `LINES` / `LINE_SAMPLES` from the plain-text `.lbl` and hardcode nothing. Validate the whole path on `ldem_75s_240m` first. Sanity check before proceeding: Faustini floor ≈ −3 to −4 km against the reference sphere; if it comes out positive or an order of magnitude off, the label parse is wrong. Keep output filenames identical. Then delete the synthetic block at `process_real_sar_pipeline.py` ~117-133 and the `s0_resampled` modulation at ~131 — that injection is the hard seam at the swath edge on hazard and hillshade, and it disappears on its own.

After it lands: re-run the slope and hazard percentile tables (the M2 numbers were fitted on invented topography and will move — that is expected, not a regression), flip the four `provenance` tags in `layers.json`, and the scrim in section 2 re-labels itself automatically.

---

## 5 · Still open, unchanged

`missionData.ts` still fetches `/api/mission/{shackleton,shoemaker,faustini}`, so the landing page shows the DEMO figures the mission view no longer does. Same defect, same fix — point it at the precomputed asset or withhold the numbers. Do it after section 3.

`module_b_radar.py:113-116` asserts the ice interpretation at 0.00 km². `mission_service.py` `pixel_scale_m = 250.0`. `target_coordinates` and the five landing sites are hardcoded — P4, and much easier after section 4, since a per-pixel suitability search over invented Gaussians would be theatre.

Do not retune `CPR_THRESHOLD`. `CPR = ((√lh − √lv)/(√lh + √lv))²` is a squared channel-imbalance ratio that collapses to zero whenever LH ≈ LV, which is the normal regolith case; `p50 = 0.000565` is that algebra, not the Moon. Only real `S3 = 2·Im⟨E_H·E_V*⟩` from the complex `sli` products fixes it, and `module_b_radar.py` already implements `compute_cpr_from_stokes()` correctly and has never been fed.

Approved, still pending: `git rm -r backend/tiles/faustini backend/scripts/generate_tiles.py backend/scripts/compare_tiles_vs_single.py`, with the per-tile brightness table in the commit body and the before/after PNG preserved in `docs/`.

---

## 6 · Order of work and the gate

**Process:** `CLAUDE_CODE_WORKING_RULES.md` applies. Build all four sections' code first, typecheck clean, *then* verify — two browser passes for the whole handoff, not one per change. The "before" screenshots are the one thing that must be captured first, in a single pass, before any file is edited.

1. Section 2 — scrim, hatch, provenance-driven label, base-filter re-check. `MissionMap.tsx` + `mc.css`.
2. Section 3 — point-in-polygon, vector styling by coverage, coverage chip, gated `flyTo`.
3. Section 5 — `missionData.ts`.
4. Section 4 — real LOLA DEM.

Sections 1 and 2 are one file each and touch no data, so this is a short pass, not a phase.

**Gate — four screenshots at identical zoom and centre, before and after, two layers:**

- `Surface Relief` selected, so the base is judged on its own with no science overlay on top
- `Radar Signals (CPR)` selected, matching the screenshot already in the thread

With each, print: the measured mean RGB inside each of the three tiers (sample the actual canvas, do not recompute the formula), the hillshade histogram before and after any filter change, the site and waypoint coverage counts, and confirmation that the hatch rendered rather than falling back.

The three tiers must still be immediately distinguishable, and crater relief must be visible in all three. If the never-observed region is still darker than roughly 0.6 of the base, the scrim is still winning and the numbers are not there yet.

Return each touched file complete. `MissionMapHandle` byte-identical — `zoomIn` / `zoomOut` / `reset`, unchanged.
