# Data

**The code licence does not extend to the data.** `LICENSE` (MIT) covers the
software in this repository and nothing else. The satellite products this code
reads are owned by the agencies that produced them and carry their own terms,
which are reproduced below.

## This repository contains no Chandrayaan-2 or LOLA data

Not one raster, and not one byte of one. `data/` is gitignored in its entirety,
and two gates enforce it rather than trusting it:

- **C1** (`backend/scripts/check_repo_complete.py`) — no ISRO or LOLA product,
  and no raster of any kind, is tracked by git.
- **C7** (same script) — **no data or secret appears anywhere in git *history***.
  This is the check that matters before the repository is made public: a file
  committed once and deleted later is still in history, and deleting it now does
  nothing. C7 reads every path ever committed, not the current tree.

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
