# Pre-registration 02 — is the attained ENL fraction set by the resampling ratio?

**Written and committed BEFORE any third product is selected or downloaded.**
Nothing in this file may be edited after a product is fetched. If it turns out to
be wrong, it stays as written and the failure is recorded beside it, as
pre-registration 01 was (METHODS §7.4a).

---

## 1 · What failed, and what this replaces

Pre-registration 01 (`4aba4cd`, `docs/enl_predictions.json`) predicted that

```
measured ENL  ≈  azimuth_looks / (PRF / total_processed_azimuth_bandwidth)
```

It failed. Across eight multilooked measurements the **bound** held in 8 of 8,
but the **attained fraction** — measured ÷ ceiling — spans a factor of 7.65,
from 0.121 to 0.926. Doubling the declared azimuth looks *lowered* the measured
ENL. METHODS §7.4a records this and deliberately does not explain it.

This pre-registration tests one of the three candidates listed there as
UNTESTED, chosen for a stated reason and before any new data exists.

## 2 · The hypothesis

**The largest single difference between the two products is how far the output
grid is resampled relative to the resolution actually achieved.** Ours writes a
25 m grid from 19.99 × 26.73 m resolution; the 2020-03-05 product writes a 90 m
grid from 74.95 × 49.61 m. Interpolating onto a grid finer than the resolution
correlates neighbouring pixels, and correlated neighbours reduce the effective
number of independent samples — which is what ENL measures.

Define, from label fields only:

```
r  =  output_pixel_spacing  /  sqrt(input_resolution_across × input_resolution_along)
```

- ours: 25 / sqrt(19.986164 × 26.729926) = 25 / 23.1147 = **1.0816**
- 2020-03-05: 90 / sqrt(74.948115 × 49.611630) = 90 / 60.9836 = **1.4758**

**HYPOTHESIS: the attained fraction `f = measured ENL / predicted ceiling` is a
decreasing function of `r`.** A grid coarser than the resolution (`r > 1`)
averages independent looks together and should attain more of its ceiling; a
grid finer than the resolution (`r < 1`) interpolates and should attain less.

**NOTE THE DIRECTION, BECAUSE IT IS AGAINST US.** The two products we hold have
`r` = 1.08 and 1.48, and the *higher* `r` attained the *lower* fraction (0.165
vs 0.759 on L-band LV). So the hypothesis as stated is **already contradicted by
the two points in hand** if the relationship is monotonic decreasing in the naive
direction. It is written this way on purpose: the naive reading of "coarser grid,
more independent samples" predicts the opposite of what we see, and that is the
thing worth testing rather than quietly reversing.

## 3 · The functional form to be tested

For each product and channel, with `f` the attained fraction and `r` as above:

1. **Sign test (primary).** Spearman rank correlation between `r` and `f` across
   all products and channels measured. The hypothesis predicts **ρ_s < 0**.
2. **Magnitude (secondary).** Ordinary least squares of `f` on `r`. Reported
   with its slope, intercept and R², but **not** used to decide pass or fail.

## 4 · Product selection rule — by label fields alone, before measurement

A third product qualifies if and only if, read from its PDS4 label **before any
raster is opened**:

| field | required value |
|---|---|
| `product_type` | `L2-SELENOREF` |
| `processing_level` | `Calibrated` |
| `frequency_band` | `L` (the S-band file of the same pass is measured too) |
| `num_polarizations` | `2`, with `polarization` ∈ {LH, LV} |
| `imaging_mode` | `STRIPMAP` |
| `azimuth_looks`, `total_processed_azimuth_bandwidth`, `pulse_repetition_frequency`, `output_pixel_spacing`, `input_resolution_across`, `input_resolution_along` | all present |
| **`r`** | **outside [1.03, 1.53]**, i.e. beyond the span the two held products already cover, so the point extends the range rather than duplicating it |

**The first product in the archive listing that satisfies every row is the one
measured.** Not the closest to the hypothesis, not the one with the most
appealing `r`. If the first qualifying product's measurement is unwelcome it is
still the measurement.

If no product with `r` outside [1.03, 1.53] exists in the archive, that is
recorded as "the archive does not contain the test" and the hypothesis stays
untested. It is not softened to fit what is available.

## 5 · The numeric band committed to

With `r₃` the third product's ratio, and `f₃` its L-band LH attained fraction:

- **`r₃ > 1.53`** (a coarser grid than either held product) → predicted
  **`f₃ < 0.165`**, below the lowest fraction yet measured.
- **`r₃ < 1.03`** (a finer grid) → predicted **`f₃ > 0.926`**, above the highest
  fraction yet measured.

Both bands are stated as strict inequalities and both are extrapolations beyond
the observed range. That is deliberate: a band that contains the existing points
is not a test.

## 6 · The criterion for calling it failed

The hypothesis is **FAILED** if any one of these holds:

1. **Sign.** Spearman ρ_s between `r` and `f` over all measured products and
   channels is **≥ 0**.
2. **Band.** `f₃` falls outside the band in §5 for the `r₃` actually obtained.
3. **Ordering.** The third product's `f₃` does not sit on the correct side of
   *both* held products, given its `r₃`.

Any single failure is a failure. There is no partial credit and no re-scoring
against a revised form. If it fails, METHODS gains a subsection recording that,
written the way §7.4a was: prediction first, proof of an unchanged estimator
second, measurement third, verdict fourth, no post-hoc explanation.

## 7 · What this cannot establish even if it passes

`n = 3`, one instrument, one product line, one processor version. A confirmed
sign would say the resampling ratio is *associated* with the attained fraction
across three acquisitions of Chandrayaan-2 DFSAR. It would not isolate it from
pulse bandwidth or lag-1 correlation, which co-vary with it in the products we
hold and are not controlled by this design.

---

*Committed before any third product was selected or downloaded. The measurement
that scores it does not exist at the time of this commit.*
