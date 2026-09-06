# Lunar Ice Intelligence

### Screening Chandrayaan-2 DFSAR over the Moon's south pole for water ice — and reporting what the data can and cannot support

**Project type:** Final year engineering capstone
**Domain:** Planetary remote sensing · radar polarimetry · SAR detection statistics · GIS · path planning
**Stack:** FastAPI + numpy/scipy backend, Vite + React + Leaflet frontend. No GDAL, no rasterio, no machine learning.

---

## What this is

An end-to-end, fully provenance-marked go/no-go pipeline over one real
Chandrayaan-2 DFSAR pass and real LOLA topography. **Every number on screen
carries a mark — `MEASURED`, `DERIVED` or `NO DATA` — and the build fails if one
does not.**

**The headline result is a null result with a proof.** The screen returns
0.0000 km² of candidate ice, 95 % CI [0.0000, 0.0024] km², and the reason is
closed-form rather than empirical: with CPR derived from amplitude alone it is a
strictly increasing function of DOP, so `CPR > 1.00 AND DOP < 0.13` is
arithmetically empty. That is not a failure to find ice. It is a measurement of
what this product can decide.

**And you do not have to take that on trust.** The map carries a probe: click
anywhere and it reports the measured CPR and DOP at that point, each against its
threshold, and how far below the detection floor the reading falls. It is not a
predictor — there is nothing to predict — but it turns the null from something
asserted into something checkable, everywhere in the frame.

## Three findings about detection limits

**1. The quantity everyone calls CPR, computed from amplitude, is not CPR.**
Monte Carlo at the measured look count: across a true CPR range of 0.30 → 1.50
its median moves **0.00043**, while 3 dB of channel imbalance at unchanged CPR
moves it by a factor of **68**. The circular polarisation ratio lives in the H–V
*phase*, and taking magnitudes discards it. It is a channel-imbalance estimator
carrying CPR's name. (`docs/METHODS.md` §7.9.2)

**2. The equivalent number of looks is 5–6, not the nominal 21** — and forming
21 looks from the single-look complex two different ways gives 4.5 and 9.9, so
*"21 looks" names a method, not a count*. As far as this project's literature
sweep found, this is the first ENL measured on a DFSAR product. (§7.3–7.4)

**3. The look count decides whether a published detection clears its own
significance floor, and it is not reported.**

| feature | CPR | N=6 | N=9 | N=21 | N=38 | N=100 |
|---|---|---|---|---|---|---|
| *95 % floor* | | *2.69* | *2.22* | *1.67* | *1.46* | *1.26* |
| F2 | 1.95 | no | no | **yes** | yes | yes |
| H3 | 1.30 | no | no | no | no | **yes** |

Read *down* a column. This accuses nobody of being wrong; it says the floor is
not reported, so a reader cannot tell. (§11.3)

## What it actually computes

| | |
|---|---|
| **shadow** | horizon computation over the full 2533² LOLA polar array, 360 azimuths, finite solar disc — validated against the LOLA team's own published PSR mask at **Jaccard 0.714** |
| **terrain** | LOLA `LDEM_80S_20M`, 20 m native, low-passed with a **measured** anti-alias σ and carried onto the 25 m DFSAR grid |
| **radar** | Chandrayaan-2 DFSAR L-band compact-pol, one pass, **15.64 %** of the frame returned amplitude |
| **landing sites** | argmax of a six-criterion search over all **14,943,444** native 25 m pixels, each with per-criterion evidence and an interpolation verdict |
| **traverse** | Dijkstra at a stated 100 m planning resolution, connectivity reported **before** any distance, `UNREACHABLE` an explicit state — all **177 waypoints** drawn on the map, each one hoverable |
| **the probe** | click any point and read the **measured** CPR and DOP there against their thresholds and the detection floor — a 200 m block mean, labelled as one, with `NO DATA` where the radar returned nothing |

## Quick start

```bash
npm run dev                                  # frontend, http://localhost:3000
npm run backend                              # FastAPI, http://127.0.0.1:8000
python -u backend/scripts/rebuild_all.py --skip-ingest    # regenerate everything
python -u backend/scripts/verify_all.py      # every gate, mapped to PRD section 6
```

The ~9 GB of Chandrayaan-2 and LOLA rasters are gitignored. **Without them the
app reports `NOT_INGESTED` and serves no numbers at all** — not zeros, which
would be a measurement claim. There is no demo or synthetic fallback on any
serving path.

## The report

`GET /api/report/pdf/{crater}` renders the PDF **from the same four artifacts the
mission screen reads** — it computes nothing of its own. Every figure carries a
provenance mark, because a reader holding a printout cannot hover a number to
find out where it came from.

It did not use to. Until this pass the report was generated from the on-demand
backend's legacy payload and printed **five landing sites that Phase 3 had
deleted** — one marked RECOMMENDED — beside a rover traverse of 18.06 km and
3,137.5 Wh for an invented 30 kg vehicle, while the screen reported NO DATA for
the same quantity. `assert_pdf_agrees_with_analysis.py` now reads the rendered
bytes and fails the build on any figure that is not in the artifacts.

## Verification

`verify_all.py` runs ten gates and maps each to a statement in PRD section 6.
Five of them also run on every rebuild, and any non-zero exit stops the build.
Each was verified by making it fail on purpose — including five cases where the
verification apparatus itself turned out to be wrong (`docs/METHODS.md` §0).

## Documentation

| document | what it holds |
|---|---|
| [`docs/METHODS.md`](docs/METHODS.md) | **the single methodological record** — 11 sections, every measured figure under a staleness stamp over 16 artifacts |
| [`docs/PROVENANCE.md`](docs/PROVENANCE.md) | generated, not written: every value, its mark, its source raster and the line that produced it |
| [`docs/assumptions.md`](docs/assumptions.md) | the register of what is **not** measured |
| [`docs/testing.md`](docs/testing.md) | the gates, and what each refuses to let ship |
| [`docs/architecture.md`](docs/architecture.md) | what actually runs |
| [`PRD.md`](PRD.md) | the specification. The only active one — `docs/handoffs/` holds nine superseded ones |

`docs/ml-methodology.md`, `docs/experiments.md` and `docs/rover-planning.md` are
stubs. They described code that was deleted, and are kept only to say so.

## What was removed, and why it matters

A Random Forest reporting `P(ice) = 0.96` was deleted in Phase 0: it was trained
on labels generated by `np.random.uniform`, so it modelled a random number
generator. It was the most impressive-looking number in the application and the
least real. **Deleting it is one of this project's findings.**
