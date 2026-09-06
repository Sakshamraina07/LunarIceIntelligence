# METHODS

The actual method behind each number, with the numbers. `PROVENANCE.md` says
*what* every value is and where it came from; this says *how*, and what each
method can and cannot support.

Sections are added as phases land. Anything not listed here is not yet computed,
and `PROVENANCE.md` names the phase that will compute it.

## 0 · The recurring defect in this project

*Three patterns, twelve instances. The first two are below in full; the third —
one transform written twice — follows them.*

**Five instances so far of one failure: a caption, a name or a summary that
stopped tracking the computation it describes.** The illumination layer's
`MODEL OUTPUT` badge over a real horizon computation; a `StepUnavailable`
heading above four measured values; a `within 2.00%` summary printed over a row
gated at 5%; one DEM product name hardcoded in twelve places and stale in all
twelve at once; and `dem_native_synthetic.tif` holding real LOLA elevation.

They are not five unrelated bugs, and the direction varies — two overstated, two
understated, one merely drifted. What they share is that a human wrote a
description once and nothing afterwards forced it to agree with the thing it
described. The fixes are all the same shape: make whatever produces the number
also produce the words about it, and fail the build when they part company. That
is what PRD rules 5a–5c, `emit_provenance.py`, `assert_paths_agree.py` and
`stamp_methods.py` exist to do. **Provenance discipline does not catch a stale
sentence; only a generator or a gate does.**

### The second pattern: the verification apparatus itself being wrong

Five instances, and it is a distinct failure from the one above, because the
thing that has drifted is the thing meant to catch drift.

1. **`verify_map.mjs` asserted a pane v8 had removed.** It exited 3 before
   producing any evidence at all — a true negative reported as a tool failure.
   Deleted in Phase 1F.
2. **`routes_visible` flagged the Science-Aware route's own emphasis glow as an
   invisible route**, failing the gate on every run for a style that was correct.
   Fixed by making the glow distinguishable, not by lowering the opacity floor.
3. **The hillshade histogram check tested `contrast(1.14) brightness(1.16)` while
   `mc.css` shipped `1.06 / 1.10`** — restated as literals under a comment that
   said "what mc.css says today".

4. **`composite_contrast.py` measured a quantity that could be satisfied without
   the thing it was checking for.** Its first version scored only *relief
   retention* — how much high-frequency structure survives in the composite. The
   radar layers scored **2.61 at opacity 0.72, more structure than the bare
   hillshade**, while the landforms underneath were completely hidden: the
   structure being counted was the layer's own speckle. Adding a correlation test
   against the base's high-pass turned three PASSes into FAILs.

5. **`roughness_vs_latitude.py` tested the wrong sign.** Latitude runs −90 at
   the pole to −84.8 at the equatorward edge, so roughness falling equatorward is
   a **negative** correlation. The check asked `corr > 0.6` and would have
   reported "no artifact" for a perfect artifact. It measured −0.498 and printed
   a clean bill of health.

**A test with the wrong sign is worse than no test at all.** No test leaves a
question open; a test with the wrong sign closes it with the wrong answer, and
hands you a green light to cite. The fifth instance would have certified a
perfect interpolation artifact as clean terrain, and the site list would have
shipped with that certification attached.

**The fourth is the only one found BY DESIGN rather than by accident.** It was
caught because the number was implausible on its face — a composite cannot carry
*more* terrain relief than the terrain — and that is what a measurement is for.
The first three were each noticed by a person looking at something else.

**The third is the worst of the four**, and it is worth being precise about why.
The first two *failed* — noisily, uselessly, but visibly. The third *passed*, on
a filter the application does not apply. A gate that validates something other
than what ships does not merely fail to catch a problem; **it certifies the wrong
thing**, and its green light is then evidence for a claim nobody checked. Two of
the first three were found by accident rather than by any process.

The rule now applied, and the reason `hillshade_histogram.py` parses `mc.css`
and `stamp_methods.py` digests artifacts rather than quoting them:

> **A verifier must READ the value the application uses. It must never restate
> it.** A verifier that restates the thing it verifies is not a verifier — it is
> a second copy of the same assumption, and it will agree with itself.

### The third pattern: one transform, written twice

Two instances, both found while drawing the Phase 4 routes on the map for the
first time, and both are the closing rule of the second pattern applied to
something that is not a verifier.

1. **`plan_traverse.py` re-derived the inverse projection and got the longitude
   backwards.** Rather than calling `frame.pixel_to_latlon`, it computed
   `lat` and `lon` inline and used `arctan2(x, -y)` — the `y_away_lam0`
   convention of the LOLA polar product
   (`ingest_lola_polar_dem.py:272`) — against a DFSAR frame whose transform is
   `arctan2(x, y)` (`sar_geometry.py:198`, validated against ISRO's 937,296-node
   geolocation grid to 13.2 mm). **Latitude was unaffected.** Longitude came out
   as `180° − lon`: route 1 started at 97.33971° where the frame puts site 1 at
   82.64773°, and 177 waypoint longitudes across five routes were written wrong.

   Nothing caught it because nothing compared the two files that have to agree.
   Every existing check on this script looks at length, climb, energy,
   connectivity or the detour ratio — quantities the longitude does not enter,
   all of which were correct. The fix is one line plus a gate: the first waypoint
   of a route *is* its site, so it must plot within one planning cell of that
   site's own `lat_deg`/`lon_deg` in `landing_sites.json`. It now measures
   **25.0–55.8 m** against a 150 m tolerance, and says so on every run.

   Re-running the planner changed **177 longitudes and nothing else**: 0
   latitudes, 0 lengths, 0 climbs, 0 energies, 0 cell counts, 0 connectivity
   figures, 0 detour ratios. Verified by walking both JSON documents scalar by
   scalar, which is also the evidence that §10 needed no revision.

2. **`MissionMap.tsx` plotted the Phase 3 sites through the coarse-grid
   transform.** `gridToPixel` maps the backend's 0–100 grid; the searched sites
   are in native raster pixels. Passing `(line 965, sample 5026)` through a
   function that divides by 100 placed site 1 at CRS `(−755, 12867)` on an
   `87 × 256` extent — off the raster by two orders of magnitude, in both axes,
   for all five sites.

   **It was invisible for two reasons, and the second is the interesting one.**
   Leaflet clips an off-view path to `M0 0` rather than erroring, so the markers
   existed in the DOM with plausible attributes. And the console line underneath
   already read *"5/5 outside the measured amplitude ribbon"* — a sentence
   written for the API's hardcoded offsets, which genuinely were outside. **The
   new symptom arrived wearing the old symptom's label**, and a log line that is
   expected to say something is not a check.

   The gate that closes it does not compare the map to a sentence. It compares
   the map to the search's own verdict: `in_amplitude_mask` is a hard criterion
   of Phase 3, so a site carrying it passed is inside the measured ribbon by
   construction, and a map that plots it elsewhere is wrong. Before the fix the
   console read `#1 outside … #5 outside`; after it, `#1 amplitude … #5
   amplitude`, matching all five records.

**Drawing the deliverable then surfaced three more of the FIRST pattern in one
afternoon, all of them prose written before Phase 3 and 4 ran and never revisited.**

- The degraded-state banner read *"landing sites and rover routes need the
  on-demand backend, which is not reachable"* — printed directly over five
  searched sites and a five-route traverse, both from static artifacts. It now
  names what actually needs the backend: the sensitivity studio, the stage panels
  and the PDF.
- Stage 06 asserted *"the five sites are hardcoded grid offsets … asserted and
  then scored, not searched"* and stage 07 *"no traverse is planned"*, beside a
  map drawing both. Both stages now report from the artifact that holds the
  result — `landing_sites.json` and `traverse.json` — and fall back to the
  absence notice only when it is genuinely absent. The corresponding reasons in
  `build_analysis.py` were rewritten to say where the answer is rather than that
  there is not one; **zero numeric or boolean values in `faustini.json` changed**,
  verified scalar by scalar, and the marks stayed 41 MEASURED / 5 DERIVED /
  0 MODELLED / 10 UNAVAILABLE / 0 unmarked.
- And the sharpest one: `if (!mission) return` at the top of the landing-site
  effect meant that **with the backend down, no landing sites were drawn at all**
  — including the five that come from a static file and need no backend. The
  guard was right when written, when the only sites came from the API. It had
  simply stopped tracking what it guards. It now sits on the API branch, which
  really does need `mission`.

The last of those is worth the emphasis: the banner and the code were making the
same claim, the banner's version was corrected first, and for one commit the app
told the truth in a sentence and contradicted it in a render.

**Both of the first two are the same defect as the five in the second pattern,
one step upstream.** There, a *verifier* restated the value it was meant to check. Here a
*producer* and a *consumer* each restated a transform that already existed
elsewhere in the repository — and, as always, the second copy agreed with the
first until it did not. The rule generalises without amendment:

> **One transform, one implementation, called from everywhere.** Where two
> artifacts must describe the same point, make one of them check the other; a
> quantity nothing compares is a quantity nothing is testing.

The second instance also carries its own smaller lesson. The five landing sites
had been on that map, in the wrong place, since Phase 3 shipped. They were never
noticed because **nobody had drawn a route between them** — the traverse existed
only in `traverse.json`. Rendering a deliverable is not only presentation; it is
the first time two computations are made to agree on a screen.

---

## 1 · The polarimetric ice screen, and why it is empty by construction

**This is the most important result in the project so far, and it is a negative
one.** It is also the answer to "you didn't find any ice", so it is worth stating
precisely.

### 1.1 What this build actually computes

`backend/scripts/process_real_sar_pipeline.py:405-431` calibrates the two
amplitude channels to σ⁰, applies a 5×5 boxcar multi-look, and forms:

```
σ_sc = ½(√lh − √lv)²                 σ_oc = ½(√lh + √lv)²
CPR  = σ_sc / σ_oc                   DOP  = |lh − lv| / (lh + lv)
```

where `lh`, `lv` are the smoothed σ⁰ of the two channels. Both quantities are
built from **the same two numbers**.

### 1.2 The identity

Write `r = lh/lv` and `x = ln r`. Then

```
CPR = ((√lh − √lv)/(√lh + √lv))²  =  ((√r − 1)/(√r + 1))²  =  tanh²(x/4)
DOP = |lh − lv|/(lh + lv)         =  |(r − 1)/(r + 1)|     =  |tanh(x/2)|
```

Both are monotone functions of the **same single variable** `|x|`. They are not
two observables; they are two reparameterisations of one channel ratio. Eliminate
`x`:

```
CPR = tanh²( artanh(DOP) / 2 )
```

CPR is a **strictly increasing** function of DOP. The two quantities carry
**one degree of freedom between them**, not two.

### 1.3 The consequence for the screen

The screening rule is `CPR > cpr_th` **AND** `DOP < dop_th` — one condition
pushing `|x|` up, the other pushing it down, along the same axis. The DOP
condition therefore imposes a hard ceiling on achievable CPR:

```
DOP < 0.13  ⟹  |x| < 2·artanh(0.13) = 0.2614770
            ⟹  CPR < tanh²(0.2614770/4) = 0.0042611
```

**No pixel satisfying `DOP < 0.13` can exhibit `CPR > 0.0042611` — whatever the
terrain, whatever the instrument, whatever the threshold.** The configured
`CPR_THRESHOLD = 1.00` is **235×** that ceiling, so the screen is *logically
empty*, not merely unsatisfied. `CANDIDATE AREA 0.00 km²` is the only
arithmetically possible answer.

### 1.4 Numerical verification

Run on all 2,337,086 measured pixels of the Faustini frame
(`backend/scripts/build_analysis.py`, emitted as `cpr_dop_identity` and asserted
by `emit_provenance.py`):

| Check | Result |
|---|---|
| `CPR` predicted from `DOP` alone, max\|residual\| | **1.241 × 10⁻⁶** (float32 storage precision) |
| rms residual | 8.025 × 10⁻⁹ |
| Pearson r between predicted and stored CPR | **0.999999999994** |
| Ceiling implied by `DOP < 0.13` | CPR < 0.0042611 |
| Highest CPR observed among pixels with `DOP < 0.13` | **0.0042611** — the ceiling, hit exactly |

The Phase 1 sensitivity sweep brackets the ceiling without having been designed
to. Its grid was built from the measured percentiles, and the transition falls
exactly where the algebra says it must:

| CPR threshold | vs ceiling 0.0042611 | predicted | observed |
|---|---|---|---|
| 0.003546 (measured p90) | below | > 0 | **63,481 px** ✓ |
| 0.009258 (measured p99) | above | 0 | **0 px** ✓ |

One more check at the extreme. The frame's maximum CPR is 0.053411, implying
`|x| = 4·artanh(√0.053411) = 0.941439`, so that pixel's DOP must be
`tanh(0.941439/2) = 0.438780`. Its **measured** DOP is **0.438779**.

That pixel is 3.4× *above* the DOP gate. **The brightest "CPR anomaly" in the
swath is necessarily the least depolarised pixel in it.** This also settles the
old `anomaly_classification` defect twice over: pairing the frame's maximum CPR
with its minimum DOP did not merely describe two different pixels — it described
two pixels that *cannot be the same pixel by construction*.

### 1.5 What this does and does not mean

It does **not** mean there is no ice at the lunar south pole, and it is **not**
evidence against ice. It means this measurement cannot address the question, and
it says so in closed form rather than as a caveat.

The defect is not that the amplitude proxy is *small*. It is that it **collapses
two independent physical observables onto one degree of freedom**, which is why
their conjunction is empty. With the true Stokes vector,

```
CPR = (S0 − S3)/(S0 + S3)          DOP = √(S1² + S2² + S3²)/S0
```

are built from **different combinations** of the four Stokes parameters and are
genuinely independent. `high CPR AND low DOP` then selects a real physical
population. Recovering `S3` requires the phase term `2·Im⟨E_H·E_V*⟩`, which
exists only in the complex `sli` products — 2 × 2.17 GB, on disk, not yet
ingested. That is Phase 5b, and this is the reason it is the fix.

### 1.6 The assertion that keeps this honest

`emit_provenance.py` gate 6 fails the build if `candidate_area_km2` is non-zero
while the CPR source is amplitude-only and `CPR_THRESHOLD` exceeds the ceiling.
A non-zero area there is arithmetically impossible, so it can only be a broken
mask, a swapped threshold, or a silently changed CPR source — **never a
discovery**. The distinction is automatic rather than dependent on somebody
remembering the algebra.

### 1.7 Do not retune the threshold

Lowering `CPR_THRESHOLD` below 0.0042611 would make the screen return area
again. That area would be "pixels whose two channels differ by a little", which
is not a CBOE signature and is not evidence of ice. PRD §2 rule 4 stands: if a
threshold is mis-set, print the distribution and say so. The distribution is
printed above.

---

## 2 · Georeferencing

The frame is south polar stereographic on a sphere of radius 1,737,400 m
(the product's own `A_AXIS_RADIUS`), read from the GeoTIFF GeoKeys of
`ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_lh_d18.tif`.

```
lat/lon → x,y :  ρ = 2·R·k₀·tan(π/4 + φ/2),  x = ρ·sin(λ),  y = ρ·cos(λ)
x,y → lat/lon :  ρ = √(x² + y²),  φ = 2·atan(ρ/2Rk₀) − π/2,  λ = atan2(x, y)
```

`PixelIsArea`, so the tiepoint names the **corner** of pixel (0,0) and a
half-pixel offset is applied for centres.

| | |
|---|---|
| Validated against | ISRO's own 937,296-node geolocation grid shipped with the product |
| Sample residual (rms) | 0.2846 px |
| Line residual (rms) | 0.4550 px |
| Corner residual | **13.2 mm** |
| Peak scale distortion over the frame | 0.2036 % |

`backend/app/ingestion/sar_geometry.py` is the implementation;
`frontend/src/mission/MissionMap.tsx` carries a direct port of the inverse, so
the cursor readout and the backend agree by construction. This replaced a flat
`30.37 km/°` approximation that was wrong by ~25× in longitude at −87.7° and
~570× at −89.9°.

---

## 3 · Elevation

LOLA `LDEM_80S_80M` V2.0 (`LRO-L-LOLA-4-GDR-V1.0`), 80 m native posts, bilinearly
resampled onto this frame's 25 m grid.

- The PDS label is parsed as plain text and **units are parsed out of the angle
  brackets**: `MAP_SCALE = 80 <m/pix>` versus `0.080 <KM/PIXEL>` is a 1000× trap
  that produces entirely plausible floats. The parser raises when the unit is
  absent rather than assuming metres.
- `SCALING_FACTOR = 0.5`, `OFFSET = 1737400.0`, `SAMPLE_TYPE = LSB_INTEGER`,
  `SAMPLE_BITS = 16`. Height = DN × 0.5; radius = height + OFFSET.
- Read via `np.memmap`, never `imread` — the 20 m product is 1.85 GB and the
  80 m product 116 MB.
- `assert_dem_is_lola()` re-measures, on **every** run, that the file the
  pipeline reads is bit-identical to the LOLA crop, at tolerance **0.0 m**. It is
  a hard failure, not a warning, because the file is still named
  `dem_native_synthetic.tif` for historical reasons and that name must never
  quietly become true again.

**Resolution honesty.** Slope, roughness and hazard are 80 m-post quantities
carried on a 25 m grid. They contain no relief finer than 80 m, and every
terrain value emitted names 80 in its own note — the number a reader needs in
order to judge them is 80, not 25.

---

## 4 · Masks, and what "measured" means

| Mask | Source | Pixels | Area | Fraction |
|---|---|---:|---:|---:|
| Frame | the full raster | 14,943,444 | 9,339.65 km² | 100 % |
| ISRO pointed swath | the product's own `sri_ma` | 5,324,544 | 3,327.84 km² | 35.63 % |
| Amplitude returned | `valid_native.tif` | 2,337,086 | 1,460.68 km² | 15.64 % |

Amplitude / pointed = **43.89 %**. The remaining 56.11 % of the pointed swath
returned literal integer zero: the beam was aimed there and nothing came back.

**Every `MEASURED` radar statistic in this project is taken over the amplitude
mask only.** The request path used to average over the whole frame — 84 %
never-observed padding — which moved the CPR mean by 5.5× and destroyed the DOP
median outright. Nothing is resampled and nothing is averaged across the void.

---

## 5 · Illumination, and permanent shadow

### 5.1 What replaced what

Two invented brightness proxies, which disagreed with each other:

```
render_layers.py    hillshade(alt 30°) × elev_norm^1.2
build_analysis.py   hillshade(alt 1.5°) × elev_norm^1.3     < 0.05  →  "PSR"
```

Neither contains a horizon term, so neither is solar geometry. The second put
77.18 % of the frame in "shadow", which is a statement about the expression and
not about the Moon. The map and the statistics were computed from *different*
formulas for the same quantity, and nothing in the build could notice.

The old "doubly shadowed" mask was that proxy's shadow intersected with the
lowest elevation quintile of the DEM. An elevation percentile is not a shadowing
event.

Both are deleted. Illumination is now a horizon computation, and the layer and
the statistics are the same array.

### 5.2 The quantity

For a point `p` and azimuth `az`, the horizon is the elevation angle of the
highest terrain along that ray:

```
horizon(p, az) = max over r > 0 of  atan( (h(p + r·u_az) − h(p)) / r )
```

`p` is lit for a sun at `(az, el)` when `el > horizon(p, az)`. A permanently
shadowed region is a point for which that is false for every sun state.

**Not a running maximum.** The obvious implementation — sweep along the ray
keeping a running max of `(h − h₀)/r` — is wrong, because `r` differs for every
pair: a low ridge nearby can subtend a larger angle than a high one far away, so
the maximising point is not the highest point. `app/ingestion/horizon.py`
implements the O(n) skyline scan (Dozier, Bruno & Downey 1981; Dozier & Frew
1990), vectorised across rows so the per-row Python loop disappears.

| Check | Result |
|---|---|
| Fast scan vs O(n²) brute force, 12 profiles across white / smooth / spiky / monotone terrain | **max diff 1.7 × 10⁻⁶** |
| Crest index reproduces its own reported slope | 4.7 × 10⁻⁷ |
| Backward-scan crest indices lie behind their column | true |

### 5.3 The correction that matters — solar elevation is not capped at 1.54°

**This is a correction to the specification, not a bug fix, and it changes the
headline number by a factor of 2.4.**

The natural-sounding model is: *at the lunar south pole the Sun stays within
±1.54° of the horizon, so sample the solar elevation over [0°, 1.54°]*. That is
true only **at** the pole. 1.54° is the Moon's obliquity to the ecliptic, which
bounds the **subsolar latitude** — not the elevation seen from a site.

```
sin(el) = sin(φ)·sin(δ) + cos(φ)·cos(δ)·cos(H)
```

At φ = −90° the first term is all that survives and the bound really is 1.54°.
Away from the pole `cos(φ)` grows and the second term dominates, giving a
maximum elevation of **1.54° + (90° − |φ|)**:

| latitude | naive cap | true maximum solar elevation |
|---|---|---|
| −90.000° | 1.54° | **1.54°** |
| −89.000° | 1.54° | 2.54° |
| −88.000° | 1.54° | 3.54° |
| −85.000° | 1.54° | 6.54° |
| **−84.833408°** (this frame's outer edge) | 1.54° | **6.7066°** |
| −80.000° | 1.54° | 11.54° |

The DFSAR frame spans −89.263057° to −84.833408°, so the naive model
under-illuminates it by between 1.6× and 4.4×.

**Measured consequence.** The full sweep was run both ways over the same array.
**Both figures below are over the full 608 × 608 km LOLA array — 369,567 km² —
which is a diagnostic domain, not this project's scene.** See §5.8 for why that
distinction is load-bearing.

| sun model | PSR ∩ full array | of 369,567 km² |
|---|---:|---:|
| naive, `el ∈ [0°, 1.54°]` for every pixel | 65,398 km² | 17.70 % |
| **per-pixel, `sin(el) = sin φ sin δ + cos φ cos δ cos H`** | **26,900 km²** | **7.28 %** |

The naive figure is 2.40× the corrected one. It would have been this phase's
headline number, and nothing about it would have looked wrong.

**Azimuth.** Near the pole the solar azimuth measured from north is `−H` to
within a fraction of a degree — the exact form
`A = atan2(−sin H cos δ, cos φ sin δ − sin φ cos δ cos H)` differs from `−H` by
0.05° at −88° and 0.14° at −84.8°, both well inside the 1° azimuth sampling.
That approximation is what allows the sun model to ride along inside the
per-azimuth horizon sweep instead of requiring a per-pixel horizon lookup table
of 360 planes (9.2 GB).

### 5.4 The lit fraction is integrated, not sampled

For each azimuth the fraction of the subsolar band in which the Sun clears the
pixel's horizon is computed **in closed form** rather than by sampling `n`
discrete subsolar latitudes. `sin(el)` is very nearly linear in `δ` across the
±1.54° band — its curvature is bounded by `|cos φ|·δ_max²/2 ≤ 8.7 × 10⁻⁵` — so
`sin(el)` is evaluated *exactly* at both band endpoints and the crossing is
interpolated between them.

| Check | Result |
|---|---|
| Closed form vs 20,001-sample brute force, 25 (cos H, horizon) combinations × 5,000 latitudes | **max error 0.00059** — 0.06 % of the band |

This is both faster (it removed ~7 s from every one of 180 rotations) and more
correct: discrete sampling quantises every pixel's illumination fraction to
multiples of `1/n` and puts a sampling artefact into the headline number.

### 5.5 Computed on the full array, then cropped

At the pole the horizon is set by crater rims tens of kilometres outside the
165 × 56 km frame, so the sweep runs over the whole 7600 × 7600 LOLA polar array
and the frame is cropped out afterwards. A horizon computed only inside the
frame would invent sunlight that real terrain blocks.

The square's corners reach 430 km from the pole — beyond the −80° circle the
product nominally covers — and were checked rather than assumed: 0.01 % zeros,
min −7,274 m, max +5,071 m, 245 distinct values in a sample block. They hold real
terrain, so the rotation uses `reshape=True` and keeps them.

Azimuth `a` and `a + 180°` are the same line scanned in opposite senses, so 360
azimuths cost 180 rotations.

### 5.6 Resolution, and how it is labelled

The horizon runs on the 80 m LOLA product decimated 3× by **block mean** to
240 m. Block mean rather than stride-sampling (which would drop narrow rim
crests entirely and un-shadow a crater floor) or block max (which would
manufacture occlusion). The mean slightly lowers sharp crests, which biases
marginally toward calling a pixel **lit** — the conservative direction for a
shadow map, so a PSR reported here is not an artefact of the smoothing.

The 20 m LOLA product is deliberately **not** used: it is 30400 × 30400 = 924 M
pixels, 3.7 GB as float32, and rotating that 180 times is neither feasible nor
necessary, because a horizon is set by distant rim crests and is a coarse
quantity. It is for terrain rendering in Phase 6.

Every consumer receives `native_metres_per_pixel`, the decimation factor and the
effective spacing alongside the arrays, and
`horizon_frame.assert_resolution_declared()` fails a caller that publishes
illumination without them. **A 240 m shadow mask resampled onto the 25 m grid is
still a 240 m shadow mask.**

`psr_mask` is *re-derived* on the frame grid by the same `fraction == 0` rule,
never interpolated — bilinear interpolation of a boolean would invent
half-shadowed pixels.

### 5.7 The polar → frame mapping, checked end to end

`app/ingestion/horizon_frame.py` is the single place the two grids meet. Its
mapping was verified by using it to sample **elevation** — the one quantity that
exists on both grids and was produced by a different code path — and comparing
against `ldem_frame_25m.tif`, which `ingest_lola_polar_dem.py` produced
independently and which was validated separately against ISRO's geolocation grid.

| | rms | bias | Pearson r |
|---|---:|---:|---:|
| Mapping as implemented | **2.93 m** | **−0.00 m** | **0.999997870** |
| Control: same mapping shifted one decimated pixel (240 m) | 36.34 m | — | 0.999673870 |

A 240 m block mean cannot reproduce a 25 m crop exactly; the point is that there
is no *offset*. The control shows a half-pixel error would be caught.

### 5.8 Every PSR area, with the denominator it belongs to

**An area without its domain is as defective as a number without its provenance
mark.** The horizon runs over the whole polar array; the DFSAR frame is 3.9 % of
it. Quoting the full-array total as "the PSR area" would state a figure 2.88×
larger than the entire scene.

`backend/scripts/psr_domains.py` prints all four, and only the last may reach
`faustini.json`:

| domain | PSR | of domain | % | status |
|---|---:|---:|---:|---|
| full 608 × 608 km array | 26,899.6 km² | 369,566.7 km² | 7.28 % | **diagnostic only** |
| inscribed 80°S circle | 25,848.8 km² | 290,345.3 km² | 8.90 % | the product's nominal coverage |
| poleward of 87.5°S | 5,474.9 km² | 18,057.4 km² | 30.32 % | Mazarico comparison band |
| **DFSAR frame** | **2,264.2 km²** | **9,339.7 km²** | **24.24 %** | **the only value in the UI** |

### 5.9 Sanity anchor — Mazarico et al. (2011)

Mazarico et al. (2011, LPI *Lunar Volatiles* abstract 6007) report **3,660 km²**
of PSR poleward of 87.5°S at 240 m/px, and note explicitly that their figure is
*larger* than earlier work (2,751 km² for the same band).

| | area poleward of 87.5°S | % of the 18,060 km² band |
|---|---:|---:|
| Mazarico et al. 2011, 240 m/px | 3,660 km² | 20.3 % |
| **this project, 240 m/px** | **5,475 km²** | **30.3 %** |
| ratio | **1.50×** | |

**We report 50 % more shadow than the published figure, and the direction is
worth stating rather than explaining away.** Three candidate causes, in the order
I think they matter:

1. **A point Sun.** This model treats the Sun as a point. Its true angular radius
   is ~0.25°, which is large next to a ±1.54° subsolar band at grazing incidence.
   A finite solar disc lights terrain a point source leaves dark, so a point Sun
   systematically **over**-predicts shadow. This is the most likely single cause
   and it has the right sign.
2. **Uniform band weighting.** The subsolar latitude is sampled uniformly over
   ±1.54°, whereas the real ephemeris does not distribute uniformly. `psr_mask`
   is *never lit under any state*, so it is insensitive to weighting — but it is
   sensitive to whether the extreme states are reachable at all.
3. **An exact-zero definition.** PSR here is `illumination_fraction == 0` with no
   tolerance. A definition with any threshold above zero returns less area.

Decimation is **not** a candidate: block mean lowers crests and raises floors,
both of which reduce shadow, so it biases the other way.

The decisive comparison is not this one but §5.10 — against the LOLA team's own
published PSR raster, on the same grid, pixel for pixel.

### 5.10 External validation — against the LOLA team's own published PSR

Everything above §5.10 is an internal consistency argument: the algorithm matches
its own brute force, the projection has no offset, the closed form matches
sampling. **None of that says the shadows are right.**

The LOLA team publishes its own permanently-shadowed masks and average-visibility
rasters — same instrument, same PDS node, same PDS3 `.IMG` + `.LBL` format, same
south polar stereographic projection on the same 1737.4 km sphere. So this is not
an argument. It is a measurement against the instrument team's own product, pixel
for pixel, with no reprojection.

| product | m/px | role |
|---|---:|---|
| `LPSR_75S_120M_201608` | 120 | binary permanent-shadow mask |
| `AVGVISIB_75S_120M_201608` | 120 | average solar visibility — checks the *continuous* field, not just the mask |

Fetched from **PDS Geosciences** (`pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/
lrolol_1xxx/extras/illumination/img/`); `imbrium.mit.edu` was unreachable
throughout this session, including the path that served the DEM. Identical
products, same 2016 release.

**The mask is resampled nearest-neighbour, never bilinear.** An interpolated
boolean invents half-shadowed pixels and would quietly improve the very agreement
it is meant to test. `AVGVISIB` is continuous and is resampled bilinearly.

#### The prediction, stated before looking

> Ours is 80 m posts decimated to 240 m; theirs is 120 m and epoch-specific.
> Finer topography resolves more small shadows, and this model treats the Sun as
> a **point** when its angular radius is ~0.25° — large next to a ±1.54° band at
> grazing incidence. Both bias toward more shadow. **Predicted: we over-call PSR
> by roughly 1.2–1.6×, with high recall and lower precision.**

#### The result

Confusion matrix over the frame (14,943,444 px):

| | LPSR shadow | LPSR lit |
|---|---:|---:|
| **ours shadow** | 2,577,749 | 1,045,041 |
| **ours lit** | 206,513 | 11,114,141 |

| | |
|---|---:|
| our PSR ∩ frame | 2,264.2 km² |
| their PSR ∩ frame | 1,740.2 km² |
| **ratio** | **1.301×** |
| Jaccard (IoU) | 0.6732 |
| Dice | 0.8047 |
| precision | 0.7115 |
| recall | 0.9258 |
| overall agreement | 0.9162 |

Against `AVGVISIB`, on the continuous field:

| | |
|---|---:|
| Pearson r | **0.8925** |
| rms difference | 0.0890 |
| least-squares fit | ours = 0.755 × theirs − 0.018 |

**Measured 1.301×, inside the predicted 1.2–1.6× band, in the predicted
direction, with the predicted shape** — recall 0.926 against precision 0.712, i.e.
we find nearly all of their shadow and add some of our own. The regression slope
of 0.755 says the same thing from the other side: we report systematically *less*
illumination than they do.

Nine out of ten pixels agree. The disagreement is one-sided and its sign was
predicted from the physics before the comparison was run.

### 5.11 The doubly-shadowed term — computed, and its approximation stated

A doubly-shadowed core is terrain that is **never directly lit** *and* **receives
no scattered light from lit terrain**. Pass 1 gives the first half. Pass 2
(`compute_horizon.py --doubly`, a second full sweep) approximates the second:

> For each azimuth, find the crest that forms this point's horizon, and ask
> whether **that crest** is itself permanently shadowed. A point is doubly
> shadowed when this holds in **every** azimuth.

The crest mask is rotated with `order=0` (nearest) — a PSR flag is boolean and
interpolating it would invent half-shadowed crests.

| | |
|---|---:|
| doubly shadowed ∩ frame | **0.94 km²** |
| as a fraction of our PSR ∩ frame | 0.04 % |

**What it captures and what it does not.** It captures the dominant term: a floor
ringed by rims that are themselves in permanent shadow has no nearby sunlit
surface to scatter from. It does **not** test every cell visible below each crest,
and models neither multiple scattering nor thermal re-radiation. So it is marked
`DERIVED`, not `MEASURED`, and a floor it calls doubly shadowed could still
receive some scattered light from lit terrain lying below a dark crest.

It is **not** the discarded proxy. That was the brightness proxy's shadow
intersected with the lowest elevation quintile of the DEM — an elevation
percentile, which is not a shadowing event.

---

## 6 · The screening thresholds, and whose they are

`CPR_THRESHOLD = 1.00` and `DOP_THRESHOLD = 0.13` are **not** inherited magic
numbers. They are exactly the published criterion in:

> Sinha, R. K. et al. (2026). *npj Space Exploration* **2**:22.
> doi:[10.1038/s44453-026-00038-9](https://doi.org/10.1038/s44453-026-00038-9)

which reports crater **F2** inside Faustini at 87.39°S, 82.31°E, ~1.1 km across,
with peak CPR **1.95** and CPR > 1 over ~47 % of its interior, DOP 0.1–0.13 where
CPR is elevated, and reads the combination as strong evidence for subsurface ice.

The criterion is **disputed**. Saran et al. (2026, Research Square preprint)
report mean CPR 1.01 ± 0.3 and DOP 0.32 ± 0.1 for the same feature and attribute
it to roughness. That is precisely why the thresholds are *cited* rather than
tuned (PRD §2 rule 4).

### 6.1 We cannot replicate their formula, and do not claim to

Both 2026 papers use **full polarimetry** (HH/HV/VH/VV). These products are
**hybrid / compact pol** (`_cp_`, channels LH/LV), for which the correct
formulation is the Stokes one:

```
CPR = (S0 − S3)/(S0 + S3)        DOP = √(S1² + S2² + S3²)/S0
```

already implemented in `module_b_radar.compute_cpr_from_stokes()`. This project
can state which mode it used and why its derivation is the right one for that
mode. It cannot enter the formula dispute, and must not imply it has.

### 6.2 Does the published detection fall inside our data?

Run through `sar_geometry`'s forward projection — the one validated to 13.2 mm —
and not by hand:

| question | answer |
|---|---|
| F2 projected position | E 78,445.7 m, N 10,592.3 m → frame pixel line 1,120.3, sample 3,676.9 |
| Inside the 2258 × 6618 frame? | **YES** |
| Inside ISRO's pointed swath? | **YES — 100 %** of the 1,521-pixel disc |
| Inside the measured amplitude ribbon? | **No — only 17.09 %** of the disc returned amplitude |

**So F2 was targeted, and this product carries almost no usable signal over it.**
That is itself a finding: a published detection sits in a part of the swath where
56 % of the pointed area returned literal zero.

Over the 260 pixels of F2 that *did* return amplitude:

| | mean | median | extreme |
|---|---:|---:|---:|
| CPR (amplitude-only) | 0.001442 | 0.000798 | max **0.015383** |
| DOP | 0.061965 | 0.056468 | min 0.000455 |

### 6.3 It is a different pass, and that is the point

Their detection is almost certainly **not** a different reduction of our data. It
cannot be, because the two use different acquisition modes.

| | this project | Sinha et al. 2026 |
|---|---|---|
| polarimetric mode | **compact / hybrid pol** | **full pol** |
| channels | LH, LV (`num_polarizations = 2`) | HH, HV, VH, VV |
| product | `ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_*` | — |
| beam mode | `STRIPMAP`, look `RIGHT`, band `L` | L **and** S |
| pass | orbit **4265**, 2020-08-08 | not stated in the open text |

The left column is read directly from our own PDS4 label. The right is from the
paper's own description — it reports *"full-polarimetric L- and S-band
observations"* and states it used *"the full-polarimetry data from Chandrayaan-2
DFSAR for the first time"*.

**A radar records one mode per pass.** DFSAR's full-pol and compact-pol are
distinct acquisition configurations, so a single observation cannot be both.
*(That is an inference from the instrument's design, not a quoted statement — the
paper is paywalled and its orbit numbers were not verifiable from the open
text.)* Their F2 detection therefore comes from a **different DFSAR pass over the
same ground**.

Which gives the finding its real shape:

> **Even for a crater with a published detection, a different pass over the same
> ground returned usable signal on only 17.09 % of it — with 100 % of it pointed
> at. Radar coverage is per-pass, not per-crater.**

That is Phase 8's thesis — that L-band polar coverage is thin and unquantified —
confirmed against a specific published claim on a specific 1.1 km crater, rather
than argued in general. It also sharpens why the two 2026 papers can disagree by
a factor of two about the same feature: they are not necessarily looking at the
same returned signal.

### 6.4 Why the CPR numbers still cannot be compared

Their peak CPR of 1.95 is **127× our maximum** — and **this is not a
contradiction**. Our CPR is the amplitude-only ratio, which §1 proves cannot
exceed 0.0042611 wherever DOP < 0.13 and cannot reach 1.95 anywhere by
construction. Different polarimetric mode, different quantity. The comparison
becomes meaningful only after Phase 5b recovers true Stokes CPR — at which point
it becomes a direct test against a specific published claim on a specific 1.1 km
crater, which is a far stronger position than a general improvement.

---

### 6.5 A planned traverse mostly crosses ground the radar never saw

The coverage thesis is usually argued from the frame: 15.64 % of it carries
amplitude, and even F2 — a crater with a published detection — returned usable
signal on 17.09 % of itself while 100 % of it was pointed at. This is the same
fact met from the other direction, and it is the form a mission planner would
actually feel.

Three rover strategies are planned across this frame by Dijkstra over measured
slope, roughness, hazard and illumination. Classifying each of their 33 waypoints
by what the radar did there (`docs/rover_coverage.json`):

| strategy | km | inside the amplitude ribbon | pointed, no return | never observed | **no radar return** |
|---|---|---|---|---|---|
| Shortest | 18.1 | 9 (27.3 %) | 9 (27.3 %) | 15 (45.5 %) | **72.7 %** |
| **Safest** | **34.6** | **3 (9.1 %)** | 11 (33.3 %) | 19 (57.6 %) | **90.9 %** |
| Science-Aware | 18.1 | 9 (27.3 %) | 9 (27.3 %) | 15 (45.5 %) | **72.7 %** |

**The safest route is the worst covered.** That is not a coincidence and it is
the point: safety is scored from LOLA topography, which covers the whole frame,
while radar covers a thin ribbon — so optimising for terrain safety walks the
rover *away* from the only ground with any radar evidence on it. Nine tenths of
the route a lander would actually prefer crosses terrain about which this
instrument says nothing at all.

Two honest qualifications. The destination is a hardcoded grid centre — the
screen found no candidate, so there is nothing to route *to* — which is why the
UI marks the route DEMO TARGET and reports no traverse distance. And "pointed, no
return" and "never observed" are different failures: the first is a radar that
looked and got nothing back, the second is ground outside the swath entirely.
They are counted separately above rather than merged into one comfortable number.

## 7 · The radar product itself — looks, speckle, and what a DN means

Everything in Phase 8 is a function of the look count *N*: a per-pixel
significance test on CPR is built out of speckle statistics, and speckle
statistics are parameterised by *N* and nothing else. So *N* is measured here,
from the label and then from the pixels, before anything is built on it.

Reproduce with `python -u backend/scripts/measure_enl.py`; the numbers below are
written to `docs/enl.json`.

### 7.1 The declared look count

| field (from `..._d_sri_xx_cp_xx_d18.xml`) | value |
|---|---|
| `range_looks` | **1** |
| `azimuth_looks` | **21** |
| **total nominal looks** | **21** |
| `azimuth_look_bandwidth` | 51.016 Hz |
| `total_processed_azimuth_bandwidth` | 1071.336 Hz |
| `range_window` | HAMMING, coefficient 0.7 |
| `azimuth_window` | HAMMING, coefficient 1.0 |

Two internal checks that the field means what it says. First, 21 × 51.016 =
1071.336 Hz, which is the total processed azimuth bandwidth **exactly** — the
looks are non-overlapping sub-bands that tile the aperture, which is the
configuration that can deliver 21 statistically independent looks. Second, the
single-look product from the same pass (`_sli_`) declares `azimuth_looks = 1`
and `range_looks = 1`, and is stored as `ComplexLSB8` I/Q. The field
discriminates between products from the same processor on the same day.

### 7.2 Are the DN amplitude or intensity? — and why the obvious test fails

This propagates into results that already exist. The CPR proxy forms
`0.5*(sqrt(a) ∓ sqrt(b))²`, which is `sigma_sc`/`sigma_oc` only if `a` and `b`
are **intensities**; if they are already amplitudes the derivation carries a
spurious square root and the 0.0042610 ceiling would need recomputing.

The tempting test is the variance ratio: an *N*-look intensity has
`mean²/var = N`, its amplitude has `≈ 4N`, and 21 against 83 look far apart.
**That test cannot settle it, and the reason is worth recording.** For small
coefficient of variation, `mean²/var` of `X^k` is about `1/k²` times that of `X`.
So *every* power of the DN yields a self-consistent story with its own implied
look count, and reading 21 off one of them assumes the answer. Measured:
`mean²/var` is 21.2–24.4 on DN and 5.3–6.5 on DN², which fits "intensity with
21 looks" and "amplitude with 5.3 looks" equally well. The declared 21 cannot
break the tie, because a real product is entitled to under-deliver its nominal
looks — which, as §7.3 shows, this one does.

**The label settles it, against the instrument's own noise floor.** The same
label carries the noise-equivalent sigma-zero, and a scene cannot sit below the
noise floor of the radar that recorded it. With `calibration_constant`
K = 70.3089 dB, incidence 20.00°, and a median LH DN of 542:

| hypothesis | σ⁰ = | median σ⁰ | relative to NESZ |
|---|---|---|---|
| **DN are amplitude** | DN² · sin θ / 10^(K/10) | −20.3 dB | **+11.2 dB** |
| DN are intensity | DN · sin θ / 10^(K/10) | −47.6 dB | **−16.1 dB** |

(NESZ from `nes0_coeff_0`: LH 7.038×10⁻⁴ = −31.5 dB, LV 6.065×10⁻⁴ = −32.2 dB.)

The intensity reading puts the entire scene 16 dB *beneath* the instrument's own
detection floor, which is not a worse fit but a physical impossibility. The
amplitude reading puts it 11 dB above the floor, and −20.3 dB is an ordinary
lunar L-band backscatter at 20° incidence.

**Verdict: the DN are amplitude.** This is also the convention in the DFSAR
instrument paper, whose calibration equation carries `(DN)²`
(Bhiravarasu et al. 2021, *Planet. Sci. J.* **2**, 134, doi 10.3847/PSJ/abfdbf).

**Nothing downstream changes.** `process_real_sar_pipeline.py` already computes
`sigma0 = DN² · sinθ / (K_lin · G²)`, so the arrays the CPR proxy consumes are
intensities, its `sqrt()` correctly recovers a field amplitude, and the
0.0042610 ceiling stands as published. The ambiguity was real and worth
resolving; the answer is that the existing code was right.

### 7.3 The measured ENL, which is not 21

ENL is `mean²/var` on intensity — here on DN², over patches lying entirely
inside the DN mask (entirely, not mostly: one zero-fill pixel would dominate a
patch's variance and manufacture a low outlier). The estimate is the **mode** of
the per-patch distribution rather than its mean, because terrain texture adds
variance and therefore only ever biases ENL *downward*; the population has a
ceiling, not a centre.

| patch | LH | LV |
|---|---|---|
| 16 × 16 (400 m) | **5.30** | **6.46** |
| 32 × 32 (800 m) | 2.64 | 2.40 |
| 64 × 64 (1.6 km) | 1.51 | 1.61 |

Spread at 16 × 16 (LH): p5 0.77, median 4.12, p95 9.14.

**Measured ENL is 5–6 against a nominal 21.** On this evidence alone the honest
statement was a wide bound — texture is inseparable from speckle without a
homogeneous target, so the true value could have been anywhere from about 5 to
21 — and every quantity in a significance test scales with it. §7.4 closes that
bound to a number, using data rather than an argument.

A skewness cross-check was run and **did not discriminate** — measured third
moments (+0.90 on DN, +1.74 on DN²) sit well above every speckle-only
prediction, because bright scatterers dominate the third moment long before they
dominate the second. It is recorded here as attempted and uninformative rather
than quietly dropped.

### 7.4 The control: forming 21 looks ourselves, from the single-look complex

The single-look complex from the **same pass** is on disk — 355,768 azimuth
lines × 759 slant-range bins of `ComplexLSB8`, which is contiguous `complex64`
at byte 5,725,302. That layout is not assumed: the script asserts
`offset + lines × samples × 8` against the file size and gets an **exact** match,
and refuses to memmap a raster whose geometry is unconfirmed.

So we can build our own 21-look product and measure it with the *identical*
patch estimator. Reproduce with
`python -u backend/scripts/slc_multilook_control.py --windows 9`; results in
`docs/slc_multilook_control.json`.

**Two checks that the reading of the file is right, before any conclusion rests
on it.** First, the azimuth power spectrum gives an occupied bandwidth of
**1071.2 Hz** in 9 windows out of 9, against the label's declared
`total_processed_azimuth_bandwidth` of **1071.336 Hz** — agreement to 0.01 %,
which independently confirms the byte layout, the complex interpretation, the
PRF and which axis is azimuth. Second, the single-look intensity measures
**ENL 1.04** (range 0.93–1.12) against a theoretical **1.00**, so the estimator
is unbiased on data whose answer is known analytically.

**Why 21 looks need not be 21.** Azimuth is sampled at the PRF, 3321.64 Hz, but
only 1071.34 Hz of azimuth bandwidth is processed — a measured oversampling
factor of **3.10**, identical in all 9 windows. Averaging 21 *consecutive*
samples therefore averages 21 samples that are not independent, and can deliver
at most 21 / 3.10 ≈ **6.8** looks. Splitting the processed band into 21
non-overlapping sub-bands and averaging their intensities gives looks that are
independent.

Both were built, from the same complex data, decimated to the same grid, and
measured with the same patches:

| how the 21 looks are formed | measured ENL | ceiling |
|---|---|---|
| single look (control) | 1.04 | 1.00 |
| **21 by spatial average** | **4.52** | 6.77 = 21 / 3.10 |
| **21 by sub-band split** | **9.95** | 21 |
| *the delivered `sri` product* | *5.30 / 6.46* | *21 (nominal)* |

**The answer is a third outcome, and neither of the two that were anticipated.**
It is not scene texture: the single-look control measures 1.04, so there is no
detectable texture depressing these numbers, and in any case spatial and
sub-band multilooking were measured on the *same grid, same patches, same
terrain* — texture cannot explain a 2× gap between them. It is not that the
archive is corrupt either. **"21 looks" names a method, and the two methods do
not deliver the same number of looks.** The delivered product's 5–6 sits with
the spatial-average figure and its 6.8 ceiling, not with the sub-band figure.

**The operative number for everything downstream is therefore N ≈ 5, not 21.**

*One window of nine (the last, at the very end of the pass) is a clear outlier
at 1.50 / 4.03, and the medians above are taken over all nine regardless.*

**The sub-band arm falls short of its own ceiling, and three hypotheses failed
to explain it.** At 8.8–9.9 against a ceiling of 21, the obvious suspect was
spectral leakage from a hard rectangular band split. It was tested:

| sub-band variant | measured ENL |
|---|---|
| hard rectangular split | 8.76 |
| Hamming taper + 8-bin guard bands | **8.37** |
| powers equalised across looks | 9.39 |
| tapered *and* equalised | 6.96 |
| *ceiling implied by the measured per-look powers* | *12.81* |

**Tapering does not climb — it falls slightly. The leakage diagnosis is
rejected.** Equalising the looks recovers little, so unequal sub-band power is
not the main term either, even though the measured per-look powers cap the
achievable figure at 12.8 rather than 21. The residual gap between about 9 and
21 is **unexplained**, and no attempt is made here to explain it away.

Two things follow, and the second matters more than the first. **We have not
demonstrated that 21 independent looks are achievable on this data**, so no
claim to that effect is made anywhere. And **the conclusion does not depend on
it**: it rests on the spatial arm (4.4–4.5) matching the delivered product
(5.3–6.5) and its independently derived 6.77 ceiling, and on the sub-band arm
being roughly twice the spatial arm on identical grids, identical patches and
identical terrain — a gap that texture cannot produce.

### 7.5 Neighbouring pixels are not independent

Correlation of DN with itself at small lags, after removing each patch's mean:

| direction | lag 1 | lag 2 | lag 3 |
|---|---|---|---|
| azimuth (lines) | **+0.838** | +0.565 | +0.363 |
| range (samples) | **+0.576** | +0.476 | +0.396 |

The anisotropy is itself evidence about its own cause: azimuth is far more
correlated than range, and the product has 21 azimuth looks against 1 range
look. This is the processing, not the terrain, which has no reason to prefer the
azimuth axis of one particular pass. (These are an upper bound on the speckle
correlation, since sub-patch terrain structure survives the mean removal.)

### 7.6 The boxcar trap

CPR and DOP are not formed on raw pixels: the pipeline applies a 5 × 5 boxcar to
σ⁰ first. If pixels were independent that would multiply the looks by 25.
Measured, over the DN mask eroded by the boxcar half-width so no window reaches
a zero-fill pixel (2,337,086 → 2,294,084 px):

| channel | ENL raw | ENL after 5 × 5 | gain | if independent | variance understated | SD understated |
|---|---|---|---|---|---|---|
| LH | 5.83 | 13.72 | **2.35×** | 25× | **10.6×** | 3.26× |
| LV | 5.14 | 19.77 | **3.84×** | 25× | **6.5×** | 2.55× |

This generalises beyond this product and is the most transferable result here:
**any study that spatially averages a SAR image and assumes its looks scale with
pixel count is understating its noise by roughly an order of magnitude in
variance.** The correction requires measuring the pixel-to-pixel correlation,
which — as far as this project's literature sweep found — nobody does for lunar
radar, so nobody knows the size of their own error.

### 7.7 What that does to a CPR threshold

CPR is a **ratio** of two N-look intensities, so its sampling distribution is
`CPR · F(2N, 2N)`. Everything below follows from that and is reproducible from
`scipy.stats.f` alone.

| N | rel. SD | bias E[R]/CPR | FP at CPR 0.5 | 0.7 | 0.9 | true CPR for 95 % confidence above 1.0 |
|---|---|---|---|---|---|---|
| **5** | 0.775 | 1.250 | 14.48 % | 29.16 % | 43.55 % | **2.978** |
| **6** | 0.677 | 1.200 | 12.21 % | 27.31 % | 42.91 % | **2.687** |
| 9 | 0.519 | 1.125 | 7.55 % | 22.84 % | 41.28 % | 2.217 |
| 21 | 0.321 | 1.050 | 1.35 % | 12.59 % | 36.72 % | 1.671 |
| 38 | 0.234 | 1.027 | 0.14 % | 6.11 % | 32.36 % | 1.462 |

The threshold in use is CPR = 1.00. **At the measured N ≈ 5, a single pixel needs
a true CPR above 2.98 before it reads over 1.0 with 95 % confidence, and ordinary
rock at a true CPR of 0.7 crosses the threshold 29 % of the time.** At the
nominal 21 those figures are 1.67 and 12.6 %. The difference between the nominal
and the measured look count is the difference between a threshold that means
something and one that does not.

### 7.8 What is and is not novel here

The loose claim "nobody reports uncertainty on lunar CPR" is **false**, and is
not made anywhere in this project. The DFSAR instrument paper reports a
"~38 look average for each sampled location" over Peary crater and "an
approximate 1/N^1/2 … uncertainty in the CPR measurements of ±0.16"
(Bhiravarasu et al. 2021, *Planet. Sci. J.* **2**, 134). Four narrower statements
replace it, each separately defensible:

**(a) The published error bar uses the wrong statistic.** `1/sqrt(N)` is the
relative error of a *single channel*. CPR is a *ratio* of two, whose relative
standard deviation is `sqrt((2N-1) / (N(N-2)))`:

| N | 1/√N | correct ratio SD | ratio |
|---|---|---|---|
| 38 | 0.1622 | 0.2341 | **1.44×** |
| 21 | 0.2182 | 0.3206 | 1.47× |
| 6 | 0.4082 | 0.6770 | 1.66× |

**(b) It is computed from nominal looks.** §7.3–7.4 measure ENL on a DFSAR
product and find it 3–4× below nominal. Combined with (a), a published bar of
±0.16 may understate the true figure by roughly 3×.

*Calibration of this claim.* **ENL falling below nominal looks because of
azimuth oversampling is textbook in terrestrial SAR and is not presented here as
a discovered phenomenon.** What is ours is narrower and survives that: the first
measurement of ENL on a DFSAR product; a controlled experiment on the
single-look complex from the same pass that isolates the mechanism and rules out
texture; and the quantified consequence for a live scientific dispute. The verb
throughout is **measure and quantify**, never *discover*.

**(c) There is an uncorrected positive bias.** `E[R] = CPR · N/(N−1)`, because
the denominator is a random variable and `E[1/Y] > 1/E[Y]`. That is **+25 % at
N = 5** and pushes every estimate *toward* the threshold, in the direction that
manufactures detections. No lunar CPR study found applies this correction.

**(d) Three nulls survive the counterexample intact.** Nobody tests per-pixel
significance, reports a confidence interval on an ice area, or computes a
false-positive rate for CPR > 1.

**What cannot be claimed.** Our measured ENL is a property of *this* compact-pol
`sri` product from *this* pass. It cannot be transferred to Sinha et al.'s
full-polarimetric result — different acquisition mode, different processing
chain, different look configuration — and no statement here does so. The point
is narrower and harder to dismiss: **nobody has measured it for theirs either**,
so the uncertainty on a published lunar CPR detection is presently unknown
rather than small.

### 7.9 Two corrections to how these numbers may be used

Both of these constrain *our own* claims, not the literature's.

#### 7.9.1 A crater does not hold as many independent samples as it holds pixels

Any "the peak over an ice-free crater would reach X" argument is a
multiple-comparisons calculation, and computing it from raw pixel counts assumes
the pixels are independent. §7.5 shows they are not, and the field that is
actually thresholded is a 5 × 5 boxcar of σ⁰ on top of that. So the effective
count is measured, by integrating the two-dimensional autocorrelation of
`cpr_real.tif` itself over patches lying wholly inside the valid mask:

**A = 61.5 pixels per independent sample.** F2's **1,520 pixels of CPR are
therefore about 25 independent samples**, not 1,520.

Patches are mean-removed before the ACF, which suppresses the DC terrain level
and biases A slightly *low* — that is, biases the independent count *high*, so
the penalty derived from it errs against our own argument rather than for it.

Median peak over an ice-free F2, true CPR 0.7, as the median of the maximum of
*n* draws of `CPR · F(2N,2N)`:

| N | from 1,520 raw pixels | from 25 effective samples |
|---|---|---|
| 5 | 7.38 | **2.52** |
| 6 | 5.77 | **2.23** |
| 9 | 3.71 | **1.78** |
| 21 | 2.00 | **1.27** |

**The raw-pixel column overstates the penalty by roughly 3×, and quoting it
would be precisely the error this project exists to avoid.** Only the
right-hand column may be used.

#### 7.9.2a Why F(2N,2N) may not be applied to our own values

`R ~ CPR · F(2N, 2N)` holds for a ratio of two independent N-look **intensities**
— which is what published CPR, `σ_SC/σ_OC` from the Stokes vector, is. The
critique in §7.8 is aimed at those values and stands. It is **not** what this
build computes: the amplitude proxy `((√LH − √LV)/(√LH + √LV))²` is a different
functional form with a different sampling distribution, and applying F(2N,2N) to
it would be the same class of error the critique is about. Its distribution is
therefore obtained by Monte Carlo, below — which turned out to say something
considerably stronger than "different distribution".

#### 7.9.2 The quantity this build calls CPR is a channel-imbalance estimator

**This is the deepest result in the project, and it is stronger than the
0.0042610 ceiling recorded in §1.** The ceiling bounded the proxy's *magnitude*
under the DOP gate. This bounds its *information content*, everywhere,
unconditionally.

**The statement.** At equal channel powers, the amplitude proxy's population
value is **exactly zero for every value of CPR**. Not small — zero, identically,
as an algebraic fact about the quantity rather than a property of this scene. It
is a function of LH and LV alone, and the circular polarisation ratio lives in
the **H–V phase**, which taking magnitudes discards before the ratio is ever
formed. What remains responds to one thing only: the imbalance between the two
channels. **It is a channel-imbalance estimator carrying CPR's name.**

##### The experiment

`backend/scripts/cpr_significance.py`. Circular complex Gaussian draws at N
looks. The population CPR is set through the H–V correlation and the population
channel imbalance through the covariance diagonal, **independently**, so the two
can be moved one at a time — which is the whole design. Run at the swath's own
measured coherence, |ρ| = 0.9822 (§7.9.3), N = 5, 120,000 trials per row.

| true CPR | imbalance | Stokes median | Stokes p5 | p95 | **proxy median** | proxy p95 | proxy population |
|---|---|---|---|---|---|---|---|
| 0.30 | 0 dB | **0.300** | 0.233 | 0.387 | **0.00043** | 0.00434 | 0 |
| 0.70 | 0 dB | **0.700** | 0.563 | 0.869 | **0.00043** | 0.00432 | 0 |
| 1.00 | 0 dB | **1.000** | 0.806 | 1.239 | **0.00043** | 0.00438 | 0 |
| 1.50 | 0 dB | **1.500** | 1.203 | 1.866 | **0.00043** | 0.00435 | 0 |
| 0.70 | 1 dB | 0.700 | 0.563 | 0.869 | 0.00331 | 0.01224 | 0.00331 |
| 0.70 | 3 dB | 0.700 | 0.569 | 0.861 | **0.02922** | 0.04967 | 0.02924 |

**Read the last three columns down.** Across a factor of five in true CPR the
proxy's median is *constant to five decimal places*. Hold the CPR fixed and add
3 dB of channel imbalance and it moves by a factor of **68**, landing on its
population value to four decimals. The Stokes estimator, computed from the very
same draws, tracks the truth in every row.

##### Two independent routes to one conclusion

The algebra of §1 — `CPR_amp = tanh²(x/4)`, `DOP_amp = |tanh(x/2)|`, one degree
of freedom, ceiling 0.0042610 — and this simulation were derived separately and
agree. The proxy's non-zero median at zero imbalance is a pure **speckle noise
floor**: LH and LV differ by chance at finite looks and the proxy squares that
difference, so the floor is positive-definite and biased upward. That is the same
fact as the ceiling, reached from the sampling distribution instead of from the
identity. **Neither is quoted as confirming the other's method; they share no
step.**

##### One deliberate control, and why it is in the table

The CPR = 1.00 row is kept even though it adds no new physics. An early version
of this simulation had a sign error on `Im(C[0,1])` that **inverted** the Stokes
CPR — 0.30 read as 3.35. **CPR = 1.0 is its own reciprocal, so that row alone
cannot detect an inversion**, and had the table contained only it, the bug would
have shipped. Every other row disagreed immediately. The row stays as a standing
reminder that a test whose expected value is a fixed point of the failure mode is
not a test.

#### 7.9.3 The simulator, validated against the swath — a pre-registered failure

Predictions were committed in `docs/preregistration_proxy_validation.md` **before
this was run**, because a simulator nobody checked against data is not evidence,
and that applies to ours.

**P1 — the Monte Carlo should reproduce the analytic form.** To first order the
proxy is `χ²₁/(8N)` when the channels are independent. Predicted median 0.01137
and p95 0.09604 at N = 5; measured 0.01207 and 0.09995 — within 4 %. **Held**, at
N = 5, 14 and 20.

**P3 — the observed swath cannot be quieter than the speckle floor.** This was
the falsifiable one, and **it failed.**

| | pre-registered | measured |
|---|---|---|
| simulated floor p95 at N = 14–20 | 0.024–0.034 | 0.024–0.035 |
| observed p95, native grid | *above the floor* | **0.00508** |

The observed swath came out **five times quieter than its own speckle floor** —
the same impossibility, in the same direction, as the intensity reading of §7.2
putting the scene below the instrument's noise floor.

**Two candidate explanations, one wrong and one right.**

The first suspect was the grid. `cpr_real.tif` is 2048 × 2048 — the *resampled*
analysis product, not the native 2258 × 6618 — and resampling 6618 range samples
down to 2048 smooths by a further ~3.2×. Comparing it against a simulation at
native-grid N compares two different fields. So the native proxy was rebuilt from
the raw DN exactly as `process_real_sar_pipeline.py` forms it. **It made almost no
difference**: native p95 0.00508 against resampled 0.00478. The hypothesis was
tested and rejected.

The real cause was an omission in the simulator. **The measured LH/LV intensity
correlation over the swath is +0.9647.** CPR fixes only the *imaginary* part of
the H–V correlation; leaving the real part at zero — which the first version did
implicitly — makes the two channels as independent as the CPR allows, and so as
noisy as possible for a statistic built on their difference. With
`Var(δ₁ − δ₂) = 2(1 − r)/N`, a correlation of 0.96 lowers the floor by ~28×.

Supplying the **measured** |ρ| = √0.9647 = 0.9822 — measured, not fitted to close
the gap:

| | value |
|---|---|
| simulated floor p95, N = 14–20 | 0.00090 – 0.00133 |
| observed native p95 | **0.00508** |

**P3 now holds**, with the observed distribution sitting a factor of 5.6 above the
floor. That excess is real channel imbalance and terrain, which is a measurement
rather than an error. P2 holds likewise.

**What is honestly weaker after this.** The `(1 − r)` correction is first-order,
and at r = 0.96 the Monte Carlo departs from it by 5–10 % (0.00133 against
0.00121 predicted at N = 14) — so P1 passes in its independent-channel form and
not in its corrected form. And the correlation used is the *total* within-patch
correlation, which conflates speckle coherence with terrain shared between the
two channels; feeding it in as |ρ|² is an empirical calibration of the floor, not
a physical decomposition of it. Neither weakens §7.9.2, whose central claim —
population value identically zero at equal channel powers — holds at every
coherence, including zero.

**The pre-registered check earned its keep.** It was written to be capable of
failing, it failed, and what it caught was a real omission in our own simulator
rather than a problem with the data.

> **Had the prediction been written afterwards, the coherence term would never
> have been noticed.**

That is the whole justification for the habit. A simulator that disagrees with
the data by a factor of five is a discovery; a simulator tuned until it agrees,
and then written up, is nothing at all — and from the inside the two feel
identical unless the prediction was committed first.

## 8 · The 20 m DEM, and what it actually bought

### 8.1 The resample reversed direction, and the filter strength is a measurement

80 m → 25 m was a 3.2× **upsample**, where bilinear point-sampling is correct:
there is nothing between the posts to alias. 20 m → 25 m is a **downsample** of
f = 1.25, where it is wrong — `map_coordinates` interpolates, it does not
average, so content the 25 m grid cannot represent folds back instead of being
averaged away.

The two library conventions are four times apart and **neither is acceptable**.
Measured against an *ideal band-limited downsample* — a brick wall at the output
Nyquist, sampled onto the same 25 m grid, so both spectra live on one grid and no
cross-grid normalisation enters — over three windows of the real 20 m array:

| σ (source px) | passband loss ≥120 m | alias excess ≤65 m | worse of the two |
|---|---|---|---|
| `(f−1)/2` = 0.125 | −0.000 | **0.234** | 0.234 |
| `f/2` = 0.625 | **0.192** | −0.489 | 0.192 |
| **0.400 — shipped** | **0.042** | **0.031** | **0.042** |

**They fail in opposite directions.** `(f−1)/2` is indistinguishable from *no
filter* to four decimals in every column and every slope percentile — at f = 1.25
scipy truncates it to a three-tap kernel of centre weight ≈0.9999 — while the
unfiltered control runs **23.4 % hot in amplitude at Nyquist**, so the aliasing
is measured rather than assumed. `f/2` removes 19.2 % of real terrain at 120 m
and longer, which is the detail the 20 m product was fetched for.

σ = 0.400 is the **minimax**: it minimises the worse of the two failure modes, at
0.042 against 0.192 for the better convention — a 4.5× improvement. Reproduce
with `backend/scripts/choose_antialias_sigma.py`; recorded in
`docs/antialias_sigma.json` and in the DEM's provenance sidecar.

*Two defects in the first version of that measurement, both caught before the
verdict was used. A wavelength row fell outside the last frequency bin and a
`dict.get(..., [1,1,1])` default then supplied three **fabricated** 1.000s to the
verdict. And the control read 0.630 where it had to read 1.000, because two PSDs
on different grids were divided without normalising `|FFT|²` by `(dx/N)²` and the
window energy. The control now reads 1.000 at 400, 200 and 120 m, which is the
self-check that the method is sound.*

### 8.2 What the 1.85 GB bought — provenance, not resolution

Native frame, 25 m grid, 80 m source → 20 m source:

| | 80 m | 20 m | Δ |
|---|---|---|---|
| slope p50 | 9.343° | 9.563° | +2.4 % |
| slope p90 | 20.172° | 20.600° | +2.1 % |
| roughness p50 | 5.806 m | 5.948 m | +2.4 % |
| roughness p90 | 12.923 m | 13.077 m | +1.2 % |
| hazard p50 | 0.3355 | 0.3436 | +2.4 % |
| mean hazard | 0.3647 | 0.3726 | +2.2 % |
| slope > 15° | 25.161 % | 25.895 % | +0.73 pp |
| *critical hazard fraction* | *0.1146* | *0.1221* | *+6.5 %* |
| *slope max* | *62.787°* | *69.392°* | *+10.5 %* |

**The distribution shifted uniformly by about 2.4 %.** It is not that the tails
moved most: p50 +2.4 % against p90 +2.1 % is the same shift throughout. The two
larger numbers are *derived* and should not be read as detail gain —
`critical_hazard_fraction` moves 6.5 % because a 2 % shift amplifies at a
threshold crossing, and `slope max` is a single pixel.

**Why the gain is small, and it is not a disappointment.** The 25 m analysis grid
is the binding constraint, not the source posts. A 25 m grid cannot carry
anything below 50 m wavelength, and §8.1's measured filter low-passes at exactly
that Nyquist. So the 20 m product buys only the 50–160 m band — real, but modest
in any statistic taken on a 25 m grid.

**The real gain is provenance.** *"20 m native, low-passed and resampled to 25 m"*
is a clean statement. *"80 m native, bilinearly upsampled 3.2× to 25 m"* put a
caveat on **every** slope, roughness and hazard figure, and through them on every
landing criterion downstream. That caveat is now gone from the entire chain. That
is what the download bought, and claiming a detail gain the grid cannot carry
would be the opposite of the discipline this project is for.

**The 25 m grid stays.** The radar is natively 25 m. A 20 m grid would put real
20 m terrain under *upsampled* radar — trading one interpolation for a worse one.

### 8.3 The saturation problem had returned, in the request path

Roughness is a 5 × 5 window. On the 2048² serving grid the sample spacing is
**80.79 m**, so that window spans **~404 m** and measures *regional relief* — a
different physical quantity wearing the same name. `clip(roughness / 50)` then
pins at 1.0 and slope stops contributing to hazard at all.

`build_analysis.py` and `render_layers.py` — everything the UI reads — score on
the native 2258 × 6618 frame at 25 m and were never affected. But
`pradan_pipeline.process_real_dem`, which `mission_service` and the PDF use,
resized the DEM to the serving grid **first** and scored there.

**The precise statement is worth getting right, because it is a better sentence
than the loose one.** The bug existed and *could not reach the screen*. Phase 1
moved the UI onto the static analysis JSON, so the visible surface carried the
native, unsaturated numbers throughout — but the PDF report and any API consumer
were served saturated hazard, and would have been until someone looked. "The bug
existed" and "the bug existed and could not reach the screen" are different
claims, and only the second one is true here:

| hazard | p50 | p90 | p95 | p99 | pinned at 1.0 |
|---|---|---|---|---|---|
| resize-then-score *(was)* | 0.393 | 0.843 | 0.933 | **1.000** | **2.4143 %** |
| **score-then-average** *(now)* | 0.344 | 0.709 | 0.743 | 0.788 | **0.0000 %** |
| native reference | 0.344 | 0.721 | 0.744 | 0.788 | 0.0002 % |

The fix is the agreed one: score at 25 m, then **area-average the bounded 0–1
field** onto the serving grid — `INTER_AREA`, never `INTER_LINEAR`, which would
point-sample and reintroduce the aliasing. Averaging a bounded score is
meaningful in a way that averaging a DEM and re-differencing it is not.

`slope_max_deg` is carried **beside** `hazard_mean`, by a maximum filter sized to
the serving cell and then nearest-sampled, because an average hides the thing a
lander cares about: a cell that averages safe can still hold one impassable face.
Measured on the current frame, p50 11.36° against a cell-mean slope of 9.58°, and
the frame maximum of 69.39° survives the downsampling intact.

The 2048² table in the ingest log is now labelled **DIAGNOSTIC ONLY, DO NOT
QUOTE** with the reason inline, so it cannot be mistaken for a 25 m roughness.

### 8.4 One map, two scales, stated per layer

The horizon sweep runs on the LOLA polar array at 240 m effective and is **not**
rerun at 20 m: that array is 30400², 3.7 GB as float32, and 360 rotations of it
is not feasible. So after this phase the map draws **20 m-derived terrain beneath
an 80 m-derived shadow mask** — a 10× scale disparity, and the largest on the
map.

That is ordinary multi-scale practice and it is legitimate. It is not a footnote.
`layers.json` now carries a resolution record per layer, written by the same
script that renders the pixels, and the legend prints it:

| layer | native | effective | decimation |
|---|---|---|---|
| hillshade, dem_elevation, hazard_map | 20 m | 25 m | 1 |
| **illumination** | **80 m** | **240 m** | **3** |
| cpr_heatmap, dop_heatmap | 25 m | 25 m | 1 |

The field is optional in the TypeScript type so a manifest without it reads as
**absent** rather than defaulting to 25 m. Near-field horizon refinement at 20 m
is out of scope and was not started.

### 8.5 The Faustini floor, reported not tuned

From the new 20 m frame, relative to the label's own 1737400 m sphere:
min **−4250.8 m**, p01 −3933.0 m, p50 −821.1 m, max +1958.7 m.

The ingest prints its own prior — "expectation was −3 to −4 km" — as **NOT met**
and adjusts nothing. That prior came from a superseded handoff, not from a
published value, and p01 sits inside the band. The check that *can* fail is the
label-range reproduction in step 3.1, which passed with **residual 0** against a
0.5 m tolerance; this one cannot discriminate, because the old synthetic array
passed it too.

### 8.6 Evenly-spaced multi-azimuth hillshading degenerates to a slope map

A single-azimuth hillshade has a known weakness: faces pointing away from the
light shade identically to the flat ground beside them, so ridges running along
the light direction disappear. The standard remedy is to average several
azimuths. **Averaging *evenly-spaced* azimuths does not fix it — it destroys the
relief entirely, and this can be shown in one line.**

Horn's hillshade is

```
h(az) = cos(z)·cos(slope) + sin(z)·sin(slope)·cos(az − aspect)
```

Only the last term carries direction. Summing it over four azimuths 90° apart,
writing `a = −aspect`:

```
cos(0°+a) + cos(90°+a) + cos(180°+a) + cos(270°+a)
    = cos a + (−sin a) + (−cos a) + sin a
    = 0        exactly, for every aspect
```

The directional term vanishes identically. What survives is `cos(z)·cos(slope)`
— **a pure function of slope, with no aspect information at all.** The averaged
"hillshade" is a slope map wearing a hillshade's name.

Measured on this frame, at 100 m posts, against slope alone:

| scheme | contrast (std) | correlation with slope-only |
|---|---|---|
| single 315° | 0.0668 | −0.124 |
| **four evenly spaced, 315/45/135/225** | **0.0075** | **−0.950** |
| four across a 135° arc, 270/315/0/45 *(shipped)* | 0.0420 | −0.128 |
| ESRI-like 225/270/315/360, weights 3/3/1/3 | 0.0430 | −0.248 |

**−0.950 is the identity showing up in the data**, and the residual 0.0075 of
contrast is what is left after `cos(slope)` is stretched across the display
range. Nine times less contrast than the single sun it was meant to improve on.

The failure is also visible without any of this: the rendered layer's luminance
median went to **228 of 255 with 4.6 % pure white**, because a near-constant
field stretched to p2–p98 amplifies its own noise. The histogram check in §8.7
caught it as a brightness problem; the cause was three steps upstream.

**What ships is four azimuths across a 135° arc.** Confining them to less than a
half-turn leaves the directional sum non-zero, so the scheme keeps a single sun's
directional information (−0.128, identical) while filling the faces a single sun
leaves black. The single-azimuth path is kept behind
`render_layers.py --hillshade-azimuths 315`.

*This is a display choice and is recorded as one in `layers.json`. It says nothing
about where the Sun actually is: the real Sun here is within 1.54° of the horizon
and lights almost none of this frame, which is the Solar Illumination layer,
computed from horizons, and a different thing entirely.*

### 8.7 The base-map filter, measured on the rendered pixels

`mc.css` applies a CSS filter to the hillshade. Its setting is measured rather
than chosen: `backend/scripts/hillshade_histogram.py` reads the declaration out
of `mc.css`, applies it to the exported `hillshade.webp`, and reports the
luminance histogram. The rule is a post-filter median at or below ~190 and no
more than 1 % of pixels clipped at 255.

At the shipped `brightness(1.10)` the median was fine at 163, but **7.197 % of
the frame clipped to pure white** — a fourteenth of the map with its relief
gone. Walking brightness back with contrast held at 1.06:

| brightness | post-filter median | clipped at 255 |
|---|---|---|
| 1.10 | 163 | 7.197 % |
| 1.08 | 160 | 6.300 % |
| 1.04 | 154 | 4.472 % |
| 1.00 | 148 | 2.960 % |
| **0.98** | **145** | **0.000 %** |

`brightness(0.98)` is the first value that clears both rules and is what ships.

## 9 · Are the landing sites real terrain, or LOLA interpolation?

Phase 3's five best sites came back with slopes of 0.05–0.55° against a frame
median of 9.56°, hazards of 0.006–0.023 against 0.339, and roughnesses of
0.55–2.29 m against 5.95 m. **A slope of 0.05° on a 25 m grid means the surface
rises about 2 cm over 25 metres.** All five sit between −85.9° and −86.4°, the
equatorward edge of a frame running to −89.26°.

**There is a mechanism that would produce exactly that.** The DEM's own label
says so: *"The ground tracks are interpolated using the Generic Mapping Tools
programs `mapproject`, `blockmedian` and `surface`."* GMT `surface` is a
minimum-curvature spline — **smooth by construction wherever tracks are sparse**
— and LOLA track density falls away from the pole. **The product publishes no
per-pixel track-density or quality band**, so nothing in the file distinguishes a
measured cell from an interpolated one.

So two hypotheses predict the same site list: those are the flattest places, or
those are the emptiest places. Three tests separate them.

### 9.1 Roughness against latitude — suggestive, not decisive

| latitude | roughness p50 | slope p50 |
|---|---|---|
| −90.00 … −89.75 | 13.40 m | 20.75° |
| −89.00 … −88.75 | 6.22 m | 10.03° |
| −87.00 … −86.75 | 7.76 m | 12.24° |
| **−86.25 … −86.00** | **7.59 m** | **12.18°** |
| −85.25 … −85.00 | 2.49 m | 4.15° |

Correlation of roughness with latitude across 21 bands: **−0.498**; equatorward
of −86.5 the median roughness is 0.771× the poleward value. Latitude increases
equatorward, so a *negative* correlation is the artifact direction, and a mild
trend is present. **But it is not conclusive**: the poleward-most band is genuine
Shackleton-area relief and drags the fit by itself, and the bands where the sites
actually sit read 4.5–7.6 m — ordinary.

### 9.2 Where the ultra-smooth pixels are — decisive, and it exonerates the sites

Band medians answer "is the region smoother". The site list is built from
individual *pixels*, so the question is where the ultra-smooth pixels live.
Enrichment is the share of sub-1.2 m-roughness pixels in a band divided by that
band's share of area; 1.0 means they are spread exactly like area.

| latitude | enrichment |
|---|---|
| −85.25 … −85.00 | **3.65** |
| −85.00 … −84.75 | **2.98** |
| −88.50 … −88.25 | 1.87 |
| **−86.50 … −85.75 (all five sites)** | **0.59** |

**The artifact is real and it is not where the sites are.** The extreme
equatorward bands are enriched 3–3.7× in ultra-smooth pixels — the interpolation
signature, exactly as predicted. But in the band holding all five sites, smooth
pixels are **under**-represented at 0.59×. The sites are not drawn from the
suspect region.

### 9.3 Planarity — the test that separates flat from empty

A real crater floor carries metres of micro-relief about its mean plane over a
kilometre. A spline drawn between distant tracks does not. Fitting a plane to
each site's 2 km box, against 200 random boxes in the same frame (p05 **8.20 m**,
p50 20.91 m):

| site | latitude | plane-fit RMS | vs reference p05 | local rank |
|---|---|---|---|---|
| 1 | −86.2714 | 62.46 m | **7.62×** | 0.3 % |
| 2 | −86.4434 | 36.02 m | **4.39×** | 0.1 % |
| 3 | −86.0109 | 32.46 m | **3.96×** | 0.5 % |
| 4 | −86.2995 | 51.17 m | **6.24×** | 0.2 % |
| 5 | −85.8987 | 41.23 m | **5.03×** | 8.5 % |

Every site's neighbourhood is **3.9–7.6× further from a plane** than the
smoothest 5 % of the frame, and above the median. The *local rank* says the rest:
each site is smoother than 99.5 % of its own 2 km box, whose median roughness is
3.7–6.2 m. **These are small genuinely flat spots — crater floors — sitting
inside ordinary rough terrain, not regions where the data ran out.**

**Verdict: the sites are real.** The artifact exists in this product and is
measurable, but it lives at −85.25 to −84.75 and the site list does not draw from
there.

### 9.4 The guard, because it was luck and not design

Nothing in Phase 3 excluded the enriched bands — the other criteria happened to.
So each site now carries an `interpolation_check`: its 2 km plane-fit RMS, the
frame's reference p05, and a verdict. A site whose neighbourhood fits a plane
*better* than 95 % of the frame is marked **SUSPECT**, with the terrain figures
there called possibly unresolved rather than flat. **Marked, not dropped** — a
site excluded silently is a claim about the Moon; a site marked is a statement
about the data.

### 9.5 Why all five cluster in 0.55° of latitude

The physical cause is this project's own correction: max solar elevation is
`1.54° + (90 − |φ|)`, so 5.29° at −86.3° against 2.29° at −89.25°. Measured, the
illumination field follows it:

| latitude | illumination p50 | max solar elevation |
|---|---|---|
| −90.0 … −89.5 | 0.0295 | 1.79° |
| −88.5 … −88.0 | 0.0002 | 3.29° |
| −87.0 … −86.5 | 0.0591 | 4.79° |
| **−86.5 … −86.0** | **0.2677** | 5.29° |
| **−86.0 … −85.5** | **0.3184** | 5.79° |
| −85.0 … −84.5 | 0.1610 | 6.79° |

Correlation of illumination with latitude: **+0.544**. The band the sites occupy
is the illumination maximum of this frame — and it is a *local* maximum, not the
edge, which is why the sites cluster at −86 rather than at −84.8.

### 9.6 The score decomposition — the largest weight does the least work

| site | safety (w 0.50) | power (w 0.31) | access (w 0.19) |
|---|---|---|---|
| 1 | 0.492 (53 %) | 0.279 (30 %) | 0.159 (17 %) |
| 2 | 0.495 (54 %) | 0.278 (30 %) | 0.147 (16 %) |
| 3 | 0.497 (54 %) | 0.249 (27 %) | 0.169 (18 %) |
| 4 | 0.489 (54 %) | 0.280 (31 %) | 0.132 (15 %) |
| 5 | 0.488 (54 %) | 0.237 (26 %) | 0.173 (19 %) |

Safety carries the largest weight and **more than half of every score — and it
does none of the ranking.** Across the top five its term value ranges only
0.976–0.994, because `safety = 1 − hazard` and every candidate is already
near-perfectly safe; the term is saturated. Power ranges 0.758–0.896 and access
0.704–0.923. **The order of this list is decided by the two terms carrying
together less than half its weight.**

### 9.6a Safety is applied twice, and the second application is inert

The cause is structural, not accidental. **The criteria filter has already
removed every pixel with slope > 12°, roughness > 10 m or hazard > 0.50.** So
everything reaching the composite is safe by construction, and `1 − hazard` has
almost nothing left to separate:

| term | weight | min | max | **span** | role here |
|---|---|---|---|---|---|
| access | 0.188 | 0.704 | 0.924 | **0.219** | ranks the list |
| power | 0.312 | 0.759 | 0.896 | **0.137** | ranks the list |
| **safety** | **0.500** | 0.977 | 0.994 | **0.017** | **inert — a gate, not a discriminator** |

**The largest weight has the smallest span.** Safety enters the answer twice —
once as a hard gate, where it does all its work, and once as a weighted score,
where it can do none. That is the same double-counting fixed in Phase 1b, where
`scientific_value` carried only distance while distance had already been
subtracted: a quantity counted once where it bites and once where it cannot.

**The ranking of this list is determined by the power and access terms alone.**

**The weights are not retuned.** Reweighting to make safety "count" would be
threshold-tuning against one frame. The weight is defensible: on rougher terrain,
or a crater where the filter admits more marginal ground, safety would
discriminate. **Its inertness here is a measurement, not a flaw**, and the span
is reported beside the weight so a reader who sees "safety 0.50" cannot conclude
that safety drove the choice.



### 9.7 What "PSR km" does not mean

Every site reports a distance to the nearest permanently shadowed region, and it
will read as proximity to ice. It is not. **Candidate area in this frame is
0.00 km² — no pixel passes the ice criteria at all** — so no site here is near
detected ice, because nothing was detected. The figure is the distance to the
nearest **modelled** cold trap, from the Phase 2 horizon computation at 240 m
effective resolution. A cold trap is where ice *could* persist; that is a
different claim from where ice *is*. Each site now carries that sentence in its
own record.

## 10 · Traverse planning, and connectivity before distance

### 10.1 Connectivity is reported first, and that ordering is the point

A planning cell is impassable if **any** 25 m face inside it exceeds
`MAX_TRAVERSABLE_SLOPE_DEG` = 20°. That is the conservative rule and the correct
one — a rover meets the worst face in a cell, not its average — but `slope_max`
rises fast with cell size (p50 already 18.15° at 0.55 km cells), so at a coarse
planning resolution the graph can fragment on single steep faces.

**If it did, every `UNREACHABLE` would be reporting the cell size rather than the
Moon** — the same shape as the hazard saturation of §8.3, one level up. So
connectivity is measured and printed before a single route is computed, at two
resolutions:

| planning res | cells | passable | components | largest | sites inside it |
|---|---|---|---|---|---|
| 100 m | 932,856 | 81.32 % | 1,717 | 746,975 | **5 / 5** |
| 50 m | 3,735,861 | 85.92 % | 6,507 | 3,167,476 | **5 / 5** |

**The graph does not fragment.** All five sites lie in one component at both
resolutions, and that component holds 98.5 % of all passable cells at 100 m — the
other 1,716 components are small pockets walled in by steep ground. The passable
fraction moves 81.32 % → 85.92 % between the two resolutions, which is the
aggregation effect made visible rather than assumed away.

**The slope limit was not relaxed to reconnect anything**, because nothing needed
reconnecting; had it fragmented, the finer figures are what a reader would use to
tell terrain from quantisation.

### 10.2 What is quantised, and by how much

Planning runs at **100 m**. Every reported length is a multiple of 100 m, or
141.4 m diagonally, so a route reported as 4,180 m is **4,180 ± 50 m**. The
planner cannot resolve finer than one cell and does not pretend to.

Graph: 758,637 nodes, 5,806,726 directed edges, 8-connected, Dijkstra via
`scipy.sparse.csgraph`. Edge cost is ground length × (1 + 2 × mean hazard).
**Cost and length are tracked separately**: a cost is a planning quantity, a
length is a claim about the Moon.

### 10.3 The primary deliverable — and what the rover is driving to

**Candidate ice area in this frame is 0.00 km².** There is no measured ice target
anywhere here, so a traverse "to the ice" would be a route to something this
project did not find. The primary result is instead the route from each site to
the nearest **modelled cold trap** boundary — 206,967 cold-trap cells, 142,888 of
them passable — carrying the same caveat the site records do.

| site | length | climb | energy (J/kg) | cells | status |
|---|---|---|---|---|---|
| 1 | 3,273 m | 0.0 m | 1,330 | 30 | REACHABLE |
| 2 | 4,663 m | 46.9 m | 1,970 | 41 | REACHABLE |
| 3 | 2,207 m | 0.2 m | 897 | 21 | REACHABLE |
| 4 | 7,280 m | 47.6 m | 3,035 | 68 | REACHABLE |
| 5 | 1,641 m | 44.0 m | 738 | 17 | REACHABLE |

**This is the mission chain the project set out to demonstrate** — land here,
drive this far, spend this much — and it is honest only because the target's
status is stated: *a cold trap at 240 m effective resolution is where ice could
persist, not where ice is, and no radar detection supports it.*

The energy figure is marked **DERIVED** and is reported **per kilogram**, so no
rover mass is invented: `g_moon × (μ_roll × length + positive climb)` with
`g = 1.625 m/s²` and an **assumed** rolling resistance `μ_roll = 0.25`. That
coefficient is a stated assumption, not a measurement.

### 10.4 The pairwise matrix is the result; the tour is a demonstration

The site-to-site matrix shows the planner works between arbitrary pairs. **It is
not a mission plan.** Neither is the tour: no lander visits five sites, a lander
goes to one. The shortest tour (order 1 → 4 → 2 → 3 → 5, 76,025 m) is computed by
**exact enumeration** of all 4! permutations with the first site fixed — not a
heuristic, not annealing; for n ≤ 8 the optimum is cheap to prove. It is labelled
in the output and in `traverse.json` as a capability demonstration so nobody reads
it as a proposed concept of operations.

`UNREACHABLE` is an explicit state and never a distance of 0. A zero would read
as "no travel needed", which is the opposite of what it means.

### 10.5 The detour ratio, which is where the information is

A raw length says little. The ratio of route length to straight-line separation
says what the terrain does:

| pair | straight | route | ratio |
|---|---|---|---|
| 1–2 | 5,263 m | 5,638 m | **1.07** |
| 1–4 | 5,963 m | 6,404 m | **1.07** |
| 2–4 | 7,760 m | 8,408 m | **1.08** |
| 3–5 | 5,613 m | 6,153 m | **1.10** |
| 2–5 | 19,307 m | 59,877 m | **3.10** |
| 1–5 | 14,776 m | 58,923 m | **3.99** |
| 4–5 | 12,600 m | 65,327 m | **5.18** |
| 1–3 | 9,422 m | 54,106 m | **5.74** |
| 3–4 | 8,817 m | 60,510 m | **6.86** |

**The five sites are not one neighbourhood.** They fall into two groups — {1, 2,
4} and {3, 5} — internally connected at ratios of 1.07–1.10, and separated from
each other by 3.1–6.9×. Sites 1 and 3 are 9.4 km apart in a straight line and
54 km apart by rover. **A table of raw lengths would not show that**; the ratio
does, and it is a fact about this frame rather than about the planner.

*Asserted, not assumed: every route is at least its straight-line separation. A
path shorter than the Euclidean distance would mean the length accumulator or the
grid mapping is wrong, and the number would look entirely plausible while being
impossible.*

### 10.6 The routes are drawn, and the drawing is a gate

Until this pass the five routes existed only in `traverse.json`; the map showed
the API's demo-target path instead. They are now drawn from the artifact — every
one of the **177 waypoints**, at the planning cell centre, converted to the 25 m
raster grid by `planning.resolution_m / native_metres` read from the file rather
than written as `4`. Selecting a route flies the map to it, because five routes
spread over a 165 km frame do not fit the 40 km opening window and a route
off-screen answers nothing.

Three things are asserted at draw time, and each one exists because the quantity
it compares had no comparator before:

1. **The drawn route and the reported length are the same route.** The polyline
   is re-summed in the browser — `resolution_m` per orthogonal step,
   `resolution_m·√2` per diagonal — and must agree with `length_m` to 1 m. Two
   independent sums of one route is how the traverse coverage figure came to
   disagree with itself earlier in this project.
2. **The route starts where the site is.** Enforced in `plan_traverse.py` against
   `landing_sites.json`, to within one planning cell of great-circle distance —
   the check that would have caught the longitude convention error of §0, and
   did not exist until it had already happened. Measured: 25.0–55.8 m against a
   150 m tolerance.
3. **A site that passed `in_amplitude_mask` plots inside the measured ribbon.**
   Enforced in the map against the search's own per-criterion record.

**`UNREACHABLE` is drawn as nothing.** Not a faint line, not a dashed one: a
route that does not exist gets no geometry, and the panel prints the word.

The rover itself is an **illustration and carries no measurement**. There is no
rover mass, wheel geometry, speed or duty cycle anywhere in this project — which
is exactly why the energy figure is per kilogram — so the vehicle is a drawing
placed on a computed path, the traverse runs at a fixed 22 s end to end
regardless of length, and the panel says so beside the marker. Its position is
interpolated by **distance**, not by vertex index, because diagonal steps are
1.414× longer than orthogonal ones and index interpolation would put the marker
out of step with the odometer beside it.

## 11 · Detection statistics — the contribution

> **Read down a column: at N = 6 nothing clears the floor, by N = 38 everything
> does. The look count decides the answer, and it is not reported.**

That is this section's thesis, and it is the project's contribution. It accuses
nobody of being wrong, it is checkable by anyone in ten minutes with
`scipy.stats.f`, and the table it refers to is §11.3.

### 11.1 Per-pixel significance, at a named look count

Not *"is this value high"* but *"is it significantly above threshold"*, with the
confidence stated and the effective look count **named rather than assumed**. The
screened field carries **N = 13.72 (LH) to 19.77 (LV)** — measured in §7.3–7.6,
where the raw product's 5.83/5.14 looks are multiplied by the 5 × 5 boxcar's
**2.35–3.84×, not 25×**, because the pixels are correlated.

| N | relative SD | bias E[R]/CPR | 95 % single-pixel floor |
|---|---|---|---|
| 13.72 | 0.405 | 1.079 | **1.895** |
| 19.77 | 0.331 | 1.053 | **1.698** |

**A single pixel must read above 1.70–1.90 to be significantly above a threshold
of 1.00.** The swath's maximum is **0.0534** — short of the floor by a factor of
**35**. Zero of 2,337,086 measured pixels reach it.

*The raster is named for what it is.* Our proxy is **not** F(2N,2N)-distributed
(§7.9.2), so `cpr_significance.tif` is the ratio of the measured value to the
floor a **true** `σ_SC/σ_OC` would have to clear — not a p-value on our own
quantity. Conflating the two would be the error this section exists to identify.

### 11.2 Candidate area, with a confidence interval

**As far as this project's literature sweep found, the first ice-candidate area
in this literature reported with one.**

| | |
|---|---|
| candidate pixels | **0** of 2,337,086 measured |
| candidate area | **0.0000 km²** |
| 95 % Wilson interval | **[0.0000, 0.0024] km²** |

The measurement is zero, **and the data would not have distinguished anything up
to 0.0024 km² from zero.** That is a stronger statement than a bare zero, and a
more honest one: it says how large a real signal could have been and still
produced this observation.

**Wilson, not the normal approximation, and the reason matters.** At k = 0 the
normal interval is exactly **[0, 0]** — it would report a measured zero as
carrying *no uncertainty at all*, which is the single most misleading thing this
table could say. The zero is the case that most needs its interval, not the case
that can do without one.

### 11.3 The published detections against their own floors

Published CPR **is** `σ_SC/σ_OC`, a ratio of two N-look intensities, so it **is**
F(2N,2N)-distributed and the F machinery applies to these values — and not to
ours.

| feature | CPR | N=6 | N=9 | N=21 | N=38 | N=100 |
|---|---|---|---|---|---|---|
| *95 % single-pixel floor* | | *2.69* | *2.22* | *1.67* | *1.46* | *1.26* |
| F2 | 1.95 | no | no | **yes** | **yes** | **yes** |
| F3 | 1.60 | no | no | no | **yes** | **yes** |
| S1 | 1.45 | no | no | no | no | **yes** |
| H3 | 1.30 | no | no | no | no | **yes** |

**Read down a column, not across.** At N = 6 no published value clears a
single-pixel 95 % floor; by N = 38 all four do. **The look count decides the
answer, and it is not reported in the source.**

**Every assumption this rests on, listed rather than buried:**

1. Published CPR is `σ_SC/σ_OC` from the Stokes vector — stated in the source,
   not our inference.
2. **Their look count is not stated in the open text.** The table is therefore
   computed *across* a range of N, and no single floor is quoted for their data.
3. **Our measured ENL cannot be transferred to their product.** Ours is a
   compact-pol `sri` product from one pass; theirs is full-polarimetric L- and
   S-band from a different acquisition and processing chain. **The point is not
   that their N is ours — it is that nobody has measured theirs.**
4. These floors are for a **single pixel**. A detection averaged over many pixels
   has a lower floor, by roughly √n_eff — and n_eff, not n, because CPR pixels
   are correlated (§7.9.1 measures 61.5 px per independent sample in our field).
5. **No claim is made that any published detection is wrong.** The claim is that
   the floor is not reported alongside it, so a reader cannot tell.

### 11.4 The gate

`emit_provenance.assert_detection_area_has_interval` fails the build if
`candidate_area_km2` reaches the UI without an interval computed in the same run.
It checks that the interval exists, that it brackets the area, that it has
non-zero width, and that the two came from the same run rather than two.

**A measured zero is not exempt** — exempting it would remove the interval from
the only number this project actually reports. Verified by injection: removing
`docs/detection_statistics.json` fails the build with the reason, and restoring
it passes.

### 11.5 The probe — the null result made checkable rather than assertable

`0.0000 km²` is a claim a reader has to take on trust. The **criteria probe**
turns it into something they can check anywhere: click any point on the map and
it reports the measured CPR and DOP there, each against its own threshold, the
margin in both directions, and how far the reading falls below the §11.1
detection floor.

It was asked for as a way to "predict where ice spots exactly are", and **that
tool cannot honestly be built here** — there is nothing to predict, and §1 shows
the screen is empty *by construction* rather than by chance. A panel that output
"ice is here" would fabricate the single number this project exists not to
fabricate. What it does instead is stronger: it lets the emptiness be inspected
point by point instead of asserted once.

Four properties make it a measurement rather than a picture of one:

- **The values are shipped as values.** The rendered layers are colourised,
  clipped and lossy `.webp`; the colour map is not injective, so reading pixels
  back off the canvas would produce a number that looked measured and was not.
  `emit_probe_grid.py` writes float32 instead.
- **The decimation is stated in the header and repeated in the readout.** Every
  value is a block mean over 8×8 native 25 m pixels — a **200 m cell**, outlined
  on the map at the size the number actually covers, because a crosshair on the
  click point would imply the value belongs to that spot.
- **Absent is absent.** A cell with no measured radar reads `NaN`, and the panel
  prints `NO DATA — they are not zero and they are not low; they are absent`.
  All three coverage states are distinguished: measured radar, *pointed and
  returned integer zero* (56.11 % of ISRO's own swath mask), and never observed.
  Collapsing the middle case into either end would discard the two-mask model.
- **Nothing is restated.** The thresholds come from `config.py`, the floor and
  the look count from `detection_statistics.json`, and the algebraic ceiling is
  recomputed from the configured DOP threshold as `tanh²(artanh(d)/2)` rather
  than pasted as `0.0042610` — so if anyone moves the gate, the bound moves with
  it instead of quoting the old one beside the new one.

A representative reading inside the ribbon, at −86.3039°, 83.1289°:
`CPR 2.684 × 10⁻⁴` against a threshold of 1.00 — **3.7 × 10³ below it** — with
`DOP 0.0263` passing, and the panel explaining at that point, with that point's
own numbers, that DOP passing is precisely what caps CPR at 0.0042611. The same
cell is **7.1 × 10³ below** the 1.8946 detection floor.


---

*Sections 9, 10 and 11 are written: the site search, the traverse, and the
detection statistics. The Stokes derivation is Phase 5b and is not written,
because it is not computed — the complex `sli` products are on disk and not
ingested, and §1 states exactly what having them would change.*

<!-- BEGIN GENERATED STAMP -- do not edit by hand -->

## Provenance of the numbers in this document

Every measured figure quoted above is transcribed from an artifact on
disk. Those artifacts are digested here, so that a figure which has gone
stale is **detectable** rather than merely wrong —
`python backend/scripts/stamp_methods.py --check` fails the build when an
artifact has moved since this stamp was written, and names the sections
that were read from it.

**What this does not do.** It does not verify that any individual digit
was transcribed correctly; only generation could do that, and generating
this document would mean templating the prose that carries its reasoning.
It catches the failure that has actually occurred here — an artifact
changing underneath text that still quotes the old numbers.

Stamped at commit `432c085`.

| artifact | sha256 | sections |
|---|---|---|
| `data/pradan/lola/horizon_240m.provenance.json` | `f84a64b1ae849b27…` | §5.4, §5.6, §8.4 |
| `data/pradan/lola/ldem_frame_25m.provenance.json` | `3cca8d4243ef625b…` | §8.1, §8.2, §8.4 |
| `docs/antialias_sigma.json` | `f6a2ee114aaf9a56…` | §8.1 |
| `docs/cpr_significance.json` | `0c440b1811442128…` | §7.7, §7.9.1, §7.9.2, §7.9.3 |
| `docs/detection_statistics.json` | `6ba46058e1399689…` | §11.1, §11.2, §11.3 |
| `docs/enl.json` | `6057bd5d8ae62908…` | §7.1, §7.3, §7.5, §7.6 |
| `docs/landing_sites.json` | `6405581775517073…` | §9.6, §9.7 |
| `docs/psr_validation.json` | `082c71a40d2f8f8e…` | §5.10 |
| `docs/roughness_vs_latitude.json` | `ace9c0c9c9999d96…` | §9.1, §9.2 |
| `docs/rover_coverage.json` | `45e2b31fed3a7cf8…` | §6.5 |
| `docs/site_inspection.json` | `817b7a32b75980be…` | §9.3 |
| `docs/slc_multilook_control.json` | `85b3d66ff708ac67…` | §7.4 |
| `docs/solar_model_ab.json` | `c8c57b02601626d1…` | §5.3, §5.10 |
| `docs/traverse.json` | `6df4a099ee59aaab…` | §10.1, §10.2, §10.3, §10.4, §10.5 |
| `frontend/public/analysis/faustini.json` | `de1cfb3a0d650d75…` | §8.2, §8.3 |
| `frontend/public/analysis/probe_grid.json` | `848f0884f29b79ed…` | §11.5 |

<!-- END GENERATED STAMP -->
