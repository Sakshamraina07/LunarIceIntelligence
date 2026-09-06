# Pre-registration — validating the Monte Carlo against the real swath

**Written and committed before the validation was run.** Every number below is a
prediction. The point of Phase 8 is that a simulator nobody checked against data
is not evidence, and that applies to ours.

## The open question

The Monte Carlo in `METHODS §7.9.2` gives the amplitude proxy a p95 of ≈ 0.10 at
N = 5 looks. The maximum proxy value actually observed anywhere in the swath is
**0.0534**. A simulated 95th percentile above the observed maximum would mean
the simulator is producing noise the instrument does not.

The resolution ought to be the look count. The proxy is not computed on raw
pixels: `process_real_sar_pipeline.py` applies a 5 × 5 boxcar to σ⁰ first, which
`METHODS §7.6` measures as worth **2.35× (LH) / 3.84× (LV)** more looks, taking
the raw ENL of 5.83 / 5.14 to **13.72 / 19.77**. So the screening field carries
an effective N near 14–20, not 5, and the simulated floor should fall by that
factor.

## The analytic prediction, which makes this a sharp bet

Write `LH = μ(1+δ₁)`, `LV = μ(1+δ₂)`. To first order in δ,

```
(√LH − √LV)/(√LH + √LV) ≈ (δ₁ − δ₂)/4       so     proxy ≈ (δ₁ − δ₂)²/16
```

With `Var(δ) = 1/N` per channel and the two roughly independent,
`Var(δ₁ − δ₂) = 2/N`, giving

```
proxy  ~  χ²₁ / (8N)
```

At N = 5 that predicts median **0.01137** and p95 **0.09604**. The Monte Carlo
already run measured **0.0115** and **0.096** — agreement to three decimals,
which is why the same form is trusted to predict the untested cases.

## Predictions

**P1 — the simulated proxy, at the measured effective N.** The Monte Carlo,
re-run at integer looks bracketing the measured 13.72 / 19.77:

| N | predicted median | predicted p95 |
|---|---|---|
| 14 | **0.00406** | **0.03430** |
| 20 | **0.00284** | **0.02401** |

The Monte Carlo should reproduce these to about 1 %, as it did at N = 5.

**P2 — the simulated p95 falls below the observed maximum.** At N = 14–20 the
simulated p95 (0.024–0.034) lands below the observed swath maximum of 0.0534.
The anomaly in the open flag is then explained by the look count alone, with
nothing else adjusted.

**P3 — the observed distribution must sit AT OR ABOVE the pure-noise floor.**
The simulation at zero channel imbalance is a *noise floor*: it is what the proxy
reads on a scene with no real LH/LV imbalance at all. Real terrain adds genuine
imbalance on top. So the observed distribution of `cpr_real.tif` over the valid
mask must be **at least as broad** as the simulated zero-imbalance distribution
at the same N. The excess, if any, is real channel imbalance and is a measurement
rather than an error.

**P4 — the observed distribution is enveloped once the measured imbalance is
supplied.** Feeding the scene's own measured median |10·log₁₀(LH/LV)| into the
simulation should bring the simulated distribution up to cover the observed one.

## What counts as failure

**If the observed p95 falls BELOW the simulated pure-noise p95 at the measured
effective N, the validation has failed.** A scene cannot be quieter than the
speckle floor of the instrument that recorded it — the same argument that
settled the amplitude/intensity question in §7.2. That would mean either the
measured ENL is wrong or the simulator is wrong, and it must be chased before
any significance layer is built.

**The significance layer will not be built on an unvalidated simulator.** If P3
fails, Phase 8 stops until it is understood.

## What is not being predicted

The observed distribution's exact shape. Real terrain imbalance has no reason to
be Gaussian, and no prediction is made about it beyond the one-sided bound in P3.
