"""
local_cells.py -- docs/selected_cells_v21.json is LOCAL ONLY. (V23b)

The file holds, for every cell the published rule selects (and F2's signal cells) in four passes, the
cell's grid index, sample CPR, sample DOP, local N-hat, minimum SNR and PSR flag: about 52 000
per-cell values at known positions of Chandrayaan-2 products. Per-cell values from an ISRO product are
not published with this repository, so the file is gitignored and is NOT tracked. It is a deterministic
product of `backend/scripts/v21_extract.py`, which reads the author's local SLCs.

`ensure()` is what the scripts that read it call first:
  * the file exists            -> True (read it);
  * absent, local rasters exist -> `v21_extract.py` is run (about 5-6 minutes, writes the file at its
                                    current path and docs/disc_table_v21.json), then True;
  * absent, no local rasters    -> prints `REQUIRES LOCAL DATA` with what is missing and returns False.
                                    The caller exits non-zero: nothing is computed from a missing file,
                                    and nothing passes because the file is missing.
The tracked summaries that carry the same results are docs/n_sensitivity_real.json and
docs/second_pass_s_v21.json, which are what the gates and the manuscript audit read.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PATH = BASE_DIR / "docs" / "selected_cells_v21.json"
#: the SLCs v21_extract.py reads (the L-band pass-1 SLI is enough to say the local raster is present)
RASTERS = (BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808",
           BASE_DIR / "data" / "generality" / "20200305" / "data" / "calibrated" / "20200305")


def rasters_present() -> bool:
    return all(d.is_dir() and any(d.glob("*_sli_*.tif")) for d in RASTERS)


def ensure() -> bool:
    if PATH.is_file():
        return True
    if rasters_present():
        print(f"  {PATH.name} is not present; regenerating it from the local rasters (v21_extract.py) ...", flush=True)
        r = subprocess.run([sys.executable, str(BASE_DIR / "backend" / "scripts" / "v21_extract.py")], cwd=str(BASE_DIR))
        return r.returncode == 0 and PATH.is_file()
    print("  REQUIRES LOCAL DATA: docs/selected_cells_v21.json (per-cell values from Chandrayaan-2 products; gitignored, not in the repository).")
    print("  It is rebuilt by backend/scripts/v21_extract.py from the local SLCs under data/pradan/raw/ and data/generality/20200305/, which are absent here.")
    print("  The tracked results are docs/n_sensitivity_real.json and docs/second_pass_s_v21.json; nothing was computed.")
    return False
