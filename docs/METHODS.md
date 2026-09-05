# METHODS

The actual method behind each number, with the numbers. `PROVENANCE.md` says
*what* every value is and where it came from; this says *how*, and what each
method can and cannot support.

Sections are added as phases land. Anything not listed here is not yet computed,
and `PROVENANCE.md` names the phase that will compute it.

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

**Measured consequence.** The full sweep was run both ways over the same array:

| sun model | PSR over the 7600² array |
|---|---|
| naive, `el ∈ [0°, 1.54°]` for every pixel | 65,398 km² |
| **per-pixel, `sin(el) = sin φ sin δ + cos φ cos δ cos H`** | **26,900 km²** |

The naive figure is 2.4× the corrected one and 5× the published ~13,000 km²
south of 80°S (Mazarico et al. 2011). It would have been this phase's headline
number, and nothing about it would have looked wrong.

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

---

*Sections 6 (site search), 7 (traverse) and 8 (Stokes derivation) arrive with
Phases 3, 4 and 5b.*
