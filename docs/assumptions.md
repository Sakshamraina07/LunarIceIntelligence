# Assumptions and limitations

*Every assumption that a number in this project rests on. Measurements are in
`METHODS.md`; this is the register of what is **not** measured.*

## Thresholds taken from the literature, not derived here

| constant | value | source |
|---|---|---|
| `CPR_THRESHOLD` | 1.00 | Sinha et al. 2026, doi 10.1038/s44453-026-00038-9 |
| `DOP_THRESHOLD` | 0.13 | same |
| `MAX_TRAVERSABLE_SLOPE_DEG` | 20° | rover tilt limit, engineering convention |
| `CRITICAL_LANDING_SLOPE_DEG` | 12° | landing convention |
| `CRITICAL_LANDING_ROUGHNESS_M` | 10 m | display convention, stated as one |
| `CRITICAL_LANDING_HAZARD` | 0.50 | display convention, stated as one |

**Their thresholds were derived from full-polarimetric data; this build has
compact-pol.** `METHODS.md` §6.3–6.4 explains why the CPR values are not
comparable at all.

## Assumed constants, with no measurement behind them

| quantity | value | where it enters |
|---|---|---|
| rolling resistance μ | 0.25 | the traverse energy proxy, §10.3 |
| lunar surface gravity | 1.625 m/s² | same — this one is a published constant |
| solar angular radius | 0.25° | the finite-disc illumination model, §5.3 |
| hillshade sun altitude | 30° | a **display** choice, not a solar model, §8.6 |
| contour interval | 250 m | a display choice, §8.6 |

The energy proxy is reported **per kilogram** so that no rover mass is invented.

## What is not measured at all

- **No temperature.** No Diviner product is on disk and no thermal model runs.
  "Thermal stability" is inferred from illumination geometry alone and is marked
  DERIVED for that reason.
- **No boulder count.** There is no OHRC product for this frame, so the hazard
  blend is slope + roughness renormalised, with the boulder weight zeroed rather
  than fed an unmeasured zero.
- **No ice.** Candidate area is **0.0000 km²**, and **no interval is reported on
  it** (corrected 2026-09-16; METHODS §11.2). The screen's firing rate is zero
  algebraically for every admissible input, so the zero carries no sampling
  uncertainty for an interval to express. The effective-sample count stands as a
  measurement — **38 050** = 2,337,086 px / 61.42 px per independent sample
  (§7.9.1) — and the two superseded intervals are kept, labelled, in
  `detection_statistics.json::candidate_area.withdrawn_interval`.
- **No one-sided critical value for the published values**, because their look
  count is not stated in the open text (§11.3).

## Limitations that bound every result here

1. **One pass.** Everything radar rests on a single DFSAR acquisition,
   2020-08-08, orbit 4265. 15.64 % of the frame returned amplitude.
2. **Compact-pol, not full-pol.** The Stokes S3 phase term is absent, so the CPR
   proxy measures channel imbalance and not CPR at all (§7.9.2). This is the
   project's central limitation and its central finding.
3. **The shadow mask is 80 m-derived at 240 m effective**, drawn under 20 m-derived
   terrain — a 10× scale disparity, stated per layer in `layers.json` (§8.4).
4. **LOLA GDRs are interpolated** with GMT `surface` and publish no per-pixel
   quality band. Sites carry an `interpolation_check` verdict for this reason
   (§9.4).
5. **The traverse target is a modelled cold trap**, not detected ice — there is
   no detected ice in this frame to drive to (§10.3).
