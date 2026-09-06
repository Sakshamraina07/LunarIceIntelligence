# Pre-registration — finite solar disc vs point Sun

**Written before the sweep finished. No result existed when this file was
committed.** The point of the exercise is that a prediction made after seeing
the answer is worth nothing, and the LPSR validation in Phase 2 already showed
this project can state a number in advance and be held to it.

## What is being tested

Phase 2 modelled the Sun as a **point**: a pixel is lit when the solar elevation
exceeds its horizon, `el > H`. LPSR_75S_120M's own label cites Mazarico et al.
(2011, *Icarus* **211**, 1066) for its method, and that paper models the **finite
solar disk** — it states that treating the Sun as a point source would put a grid
element in sunlight only "if its horizon elevation is lower than the Sun
location", and then does something else. So the product we validate against uses
the disc and we used a point. That is a known bias in a known direction: a point
Sun over-calls shadow, because it ignores the upper limb.

The disc enters in exactly one place, with angular radius `rho = 0.25 deg`:

```
lit when   el > H - rho
threshold  sin(H - rho) = (hz*cos(rho) - sin(rho)) / sqrt(1 + hz^2)
```

`rho = 0` reduces this to the point model exactly, so both models are swept off
**one** horizon in one pass and cannot drift apart.

## The predictions

A 4-azimuth calibration run showed the disc shedding **10.5 %** of the point-Sun
shadow mask. The current ratio against LPSR is 1.301x, so 1.301 x 0.895 ~ 1.16x.

| quantity | point Sun (measured, Phase 2) | predicted, finite disc |
|---|---|---|
| shadow ratio vs LPSR | 1.301x | **~1.16x** |
| Jaccard | 0.6732 | **up** |
| Dice | 0.8047 | **up** |
| precision | 0.7115 | **up** |
| recall | 0.9258 | **down slightly** |
| AVGVISIB Pearson r | 0.8925 | **up** |
| AVGVISIB slope | 0.755 | **up, toward 1.0** |
| AVGVISIB rms | 0.0890 | **down** |

Recall is predicted to fall because the disc removes shadow pixels, and some of
those removed pixels are ones LPSR also calls shadow. Trading a little recall for
more precision is the whole point of the correction; if precision does not rise,
the hypothesis has failed.

## The guardrail, stated in advance

**A residual over-call of roughly 1.1–1.2x is the expected endpoint, not a
failure.** Our posts are 80 m; LPSR's are 120 m. A finer grid resolves small
shadowed hollows that a coarser one averages away, so some over-call is a
property of the comparison and cannot be removed by improving the physics.

**The disc model is the last change.** No parameter will be tuned to push the
ratio toward 1.0. If a number lands short of its prediction, that is reported as
a number landing short of its prediction.

## What counts as a failure

If the disc model does **not** improve agreement with LPSR, it is rejected and
the point-Sun mask ships. A tested-and-rejected hypothesis is a result and is
recorded in `METHODS.md` either way. Both masks are kept in the sweep's `.npz`
(`psr_mask_r0`, `psr_mask_r0.25`) so the comparison can be re-measured from the
product rather than re-run on trust.
