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

Their peak CPR of 1.95 is **127× our maximum** — and **this is not a
contradiction**. Our CPR is the amplitude-only ratio, which §1 proves cannot
exceed 0.0042611 wherever DOP < 0.13 and cannot reach 1.95 anywhere by
construction. Different polarimetric mode, different quantity. The comparison
becomes meaningful only after Phase 5b recovers true Stokes CPR — at which point
it becomes a direct test against a specific published claim on a specific 1.1 km
crater, which is a far stronger position than a general improvement.

---

*Sections 7 (site search), 8 (traverse) and 9 (Stokes derivation) arrive with
Phases 3, 4 and 5b.*
