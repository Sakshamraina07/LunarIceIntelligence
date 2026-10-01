# Data

**The code licence does not extend to the data.** `LICENSE` (MIT) covers the
software in this repository and nothing else. The satellite products this code
reads are owned by the agencies that produced them and carry their own terms,
which are reproduced below.

## What this repository contains, and what it does not

**It contains no Chandrayaan-2 or LOLA source product** (no raster, PDS4 label, single-look complex file, or per-cell or per-pixel
value table), **and no layer file, tile or screenshot that renders a DFSAR-derived quantity at a pixel size finer than 200 m.**
It does contain: code; derived numerical results (`docs/*.json`, per-disc and per-block summaries, histograms); the manuscript's
figures; coarse aggregate layers of about 200 m and coarser (`frontend/public/analysis/probe_grid.bin`, 200 m cells of 8 x 8 block
means, and the `*.preview.webp` previews, about 258 m/px); LOLA-only map layers (hillshade, elevation, hazard, illumination)
rendered on a 25 m grid from the public NASA PDS LOLA product; and interface screenshots in `docs/evidence/` that draw LOLA relief
and single-cell probe read-outs, with no CPR or DOP layer on the map. **ISRO keeps the copyright in the Chandrayaan-2 data**; nothing
here transfers any right in it.

**What was removed.** The two 25 m CPR and DOP layer files, the CPR and DOP map-tile pyramid (zoom 0 to 3, 27.6 to 80.8 m per
pixel) and the application screenshots that showed the CPR or DOP proxy at map zoom (28.6 to 144 m per pixel) were removed from the
tree and from every branch and tag, by two history rewrites (V24 and V25). `docs/removed_native_renderings.json` keeps what is needed
to know they existed and to recognise a local copy: path, git blob id, sha256, size, pixel size and first commit, and no pixel
value. The author holds the files locally; they are not published, and gate G28 (checks C1, C8 and C8b) fails if one is tracked,
is anywhere in history by name or by blob id, or differs from its recorded sha256.

**Two exceptions are stated here rather than left implicit, and they are NOT removed.**
(1) `docs/propagation_ddop_map.png`, a delta-DOP perturbation map of about 125 m per pixel (a derived field of a calibration
ablation), is on GitHub but is `export-ignore`d, so it is not in the release archive or the Zenodo record.
(2) `paper/fig_scene.pdf`, a manuscript figure, has a panel (b) of the sample CPR at 25 m bins over a 12 x 3.8 km window; the
figure is in the repository and in the release archive. Neither meets the 200 m rule, and the author has not yet decided them.

`data/` is gitignored in its entirety, `docs/selected_cells_v21.json` (per-cell values) and the two native-resolution layer files
(`frontend/public/layers/cpr_heatmap.webp`, `dop_heatmap.webp`) are gitignored and local only, and gates enforce it rather than trusting it:

- **C1** (`backend/scripts/check_repo_complete.py`) — no ISRO or LOLA product, no raster of any kind, no per-cell table
  and no native-resolution DFSAR layer is tracked by git.
- **C7** (same script) — **no data or secret appears anywhere in git *history***.
  This is the check that matters before the repository is made public: a file
  committed once and deleted later is still in history, and deleting it now does
  nothing. C7 reads every path ever committed, not the current tree.

The GitHub release archive (and so the Zenodo record) is code and results only: `.gitattributes` marks `frontend/public/layers/` and
`probe_grid.bin` `export-ignore`.

`docs/data_provenance.json` records exactly which files the analysis read — name,
size, SHA-256, and the label fields that identify each product — so a reader can
obtain the same products and confirm they have the same bytes, without this
repository ever having distributed them.

## Chandrayaan-2 DFSAR — ISRO

Obtained from **PRADAN**, the ISRO Science Data Archive
(`https://pradan.issdc.gov.in/ch2/`), free of charge on registration.

Product used: `urn:isro:isda:ch2_cho:sar_calibrated` —
`ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18` and the corresponding
`sli` bundle, plus `ch2_sar_ncxl_20200305t114902885_*` for the generality check.

**ISRO's terms, quoted verbatim from
`https://pradan.issdc.gov.in/ch2/disclaimer.xhtml`:**

> "CH-2 data sharing is open and free of charge for non-profit scientific use"

> the data "remains the property of ISRO"

> users "do not have the right to copy, lease or loan the satellite data without
> the prior permission of ISRO/ DOS"

> no commercial use, "defined as that involving the sale or resale of data, as
> well as data derived there from"

**What that means for anyone reusing this repository.** You may take the code
under MIT. You may not take the data from here, because it is not here. To
reproduce the analysis you must obtain the products from PRADAN yourself, under
ISRO's terms, and those terms bind you directly rather than through this
repository.

Note the breadth of the commercial-use clause: it reaches "data derived there
from". The derived artifacts under `docs/` and `frontend/public/analysis/` are
measurements computed from ISRO products, so anyone contemplating a commercial
use should treat that clause as applying to them and seek ISRO's permission.
The MIT licence on the code does not and cannot override it.

## LOLA — NASA PDS

`LDEM_80S_20M` (frame DEM, 20 m native) and `LDEM_80S_80M` (horizon computation,
80 m native), both `LRO-L-LOLA-4-GDR-V1.0` V2.0, together with
`LPSR_75S_120M_201608` and `AVGVISIB_75S_120M_201608`, from the **NASA Planetary
Data System**, Geosciences Node
(`https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/`).

NASA PDS data are in the public domain and carry no licence restriction. The PDS
asks that the instrument team and the data set be cited; this work cites Smith et
al. for LOLA and names the data set identifiers in the manuscript's Data
Availability section.

## Citing

See `CITATION.cff`. The Zenodo record (`.zenodo.json`) lists the DFSAR and LOLA
identifiers as related identifiers so that the data this work used is
discoverable from the software record, without the software record containing it.
