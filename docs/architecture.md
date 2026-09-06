# System Architecture

*What actually runs, as of PRD Phase 8. No machine-learning component exists in
this project — see `ml-methodology.md`.*

## The two paths, and why there are two

```
  RASTERS ON DISK                    data/pradan/  (~9 GB, gitignored)
       |
       |  OFFLINE PRODUCERS (backend/scripts/) — run by rebuild_all.py
       |
       +-> ingest_lola_polar_dem.py   LOLA polar DEM -> this frame's 25 m grid
       +-> process_real_sar_pipeline.py  DFSAR L2 -> native cpr/dop/valid/footprint
       +-> build_analysis.py          THE NUMBERS -> public/analysis/<crater>.json
       +-> render_layers.py           THE PIXELS  -> public/layers/*.webp + layers.json
       +-> detection_statistics.py    significance + the confidence interval
       +-> search_landing_sites.py    Phase 3 sites -> public/analysis/landing_sites.json
       +-> plan_traverse.py           Phase 4 routes -> public/analysis/traverse.json
       |
       v
  frontend/  (Vite + React + Leaflet)   reads the STATIC artifacts above
       |
  backend/app/  (FastAPI)               the REQUEST path: /api/mission, the PDF
```

**The UI reads static artifacts, not the API.** That is deliberate and it is why
a bug in the request path once could not reach the screen (`METHODS.md` §8.3).
Because the same terrain quantity is then computed by two paths that share no
code, `assert_paths_agree.py` runs on every rebuild and fails the build if they
diverge — they have, twice.

## The gate chain

`rebuild_all.py` runs eight stages and **any non-zero exit stops the rebuild**,
so a build that would have shipped an unlabelled number fails before it reaches
disk. The gates are listed in `testing.md`.

## Rules that constrain the code

- No `rasterio`, no GDAL. numpy, scipy, cv2, PIL, tifffile only.
- Never `imread` a multi-gigabyte raster whole — `np.memmap` and windowed reads.
- PDS labels parsed as text, with units taken from the angle brackets.
- Every number reaching a screen carries `MEASURED` / `DERIVED` / `MODELLED` /
  `NO DATA`. `np.zeros_like` is not an absent state.
