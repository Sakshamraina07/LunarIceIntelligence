"""
handedness.py -- does any label say which circular polarization DFSAR
transmits? If not, the physical check. (v17a referee report, P7)

    python backend/scripts/handedness.py

1. Every PDS4 label (*.xml) and every other text document in both bundles,
   and the text members of the bundle zips, are scanned for a transmit
   polarization or handedness statement: transmit, handed(ness), right/left
   circular, RHC/LHC, RCP/LCP, circular. Every hit is quoted verbatim with
   its file and line. The label's own polarization fields are listed
   separately (they name the RECEIVE channels, LH and LV).
2. The physical check, per pass, over every matched complex-product cell:
   the median Stokes CPR and the fraction of cells with CPR < 1 under each of
   the two admissible sign conventions, S3 = +2 Im<E_H E_V*> (0 deg) and
   S3 = -2 Im<E_H E_V*> (180 deg). Single-bounce-dominated lunar terrain has
   CPR < 1 over most cells, so the reading under which most cells fall below
   1 is the physical one; the manuscript's convention is 180 deg.
"""
from __future__ import annotations

import json
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "handedness.json"
ROOTS = [BASE_DIR / "data/pradan/raw", BASE_DIR / "data/generality/20200305"]
TEXT_EXT = {".xml", ".lbl", ".txt", ".htm", ".html", ".md", ".cat", ".fmt"}
PAT = re.compile(r"transmit|handed|right[\s_-]*circular|left[\s_-]*circular|\bRHC\b|\bLHC\b|"
                 r"\bRCP\b|\bLCP\b|circular", re.I)
POL_FIELD = re.compile(r"<isda:(polarization|polarisation|num_polarizations|imaging_mode|"
                       r"polarization_mode|pol_mode|transmit[^>]*)>([^<]*)<", re.I)


def scan_text(name: str, text: str, hits: list, fields: dict) -> None:
    for i, ln in enumerate(text.splitlines(), 1):
        if PAT.search(ln):
            hits.append({"file": name, "line": i, "text": ln.strip()})
        for m in POL_FIELD.finditer(ln):
            fields.setdefault(m.group(1), set()).add(m.group(2).strip())


def main() -> int:
    t0 = time.time()
    hits, fields, scanned, zips = [], {}, [], []
    for root in ROOTS:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in TEXT_EXT:
                scan_text(str(p.relative_to(BASE_DIR)), p.read_text(encoding="utf-8", errors="replace"),
                          hits, fields)
                scanned.append(str(p.relative_to(BASE_DIR)))
            elif p.is_file() and p.suffix.lower() == ".zip":
                try:
                    z = zipfile.ZipFile(p)
                    n = 0
                    for mname in z.namelist():
                        if Path(mname).suffix.lower() in TEXT_EXT:
                            scan_text(f"{p.relative_to(BASE_DIR)}::{mname}",
                                      z.read(mname).decode("utf-8", errors="replace"), hits, fields)
                            n += 1
                    zips.append({"zip": str(p.relative_to(BASE_DIR)), "text_members_scanned": n})
                except zipfile.BadZipFile:
                    zips.append({"zip": str(p.relative_to(BASE_DIR)), "error": "not a valid zip archive"})
    specific = [h for h in hits if re.search(r"transmit|handed|right[\s_-]*circular|left[\s_-]*circular|"
                                             r"\bRHC\b|\bLHC\b|\bRCP\b|\bLCP\b", h["text"], re.I)]
    # de-duplicate identical quotations (the ncxl / ncxs labels and the zips repeat them)
    uniq = {}
    for h in hits:
        uniq.setdefault(h["text"], []).append(f"{h['file']}:{h['line']}")
    statement = bool(specific)
    print(f"  scanned {len(scanned)} text files and {len(zips)} zips; {len(hits)} hits "
          f"({len(uniq)} distinct lines); transmit / handedness statements: {len(specific)}")
    for t, where in uniq.items():
        print(f"    \"{t[:160]}\"  ({len(where)} x)")

    phys = {}
    for pid in ("20200808", "20200305"):
        SFS.configure(pid)
        hh, vv, hv, _ = SFS.build_coherency(0)
        s0 = hh + vv
        m = (hh > 0) & (vv > 0) & (s0 > 0)
        s3 = 2.0 * hv.imag
        del hv
        out = {}
        for deg, sgn in ((0, 1.0), (180, -1.0)):
            a, b = s0 - sgn * s3, s0 + sgn * s3
            ok = m & (a > 0) & (b > 0)
            cpr = a[ok] / b[ok]
            out[f"{deg}_deg"] = {"convention": f"S3 = {'+' if sgn > 0 else '-'}2 Im<E_H E_V*>",
                                 "cells": int(ok.sum()), "median_cpr": float(np.median(cpr)),
                                 "fraction_cpr_lt_1": float((cpr < 1.0).mean())}
        out["physical_reading"] = min(("0_deg", "180_deg"), key=lambda k: out[k]["median_cpr"])
        phys[pid] = out
        print(f"  {pid}: 0 deg median {out['0_deg']['median_cpr']:.4f} (CPR<1 on "
              f"{100 * out['0_deg']['fraction_cpr_lt_1']:.2f} %); 180 deg median "
              f"{out['180_deg']['median_cpr']:.4f} (CPR<1 on {100 * out['180_deg']['fraction_cpr_lt_1']:.2f} %)",
              flush=True)
        del hh, vv, s0, m, s3
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/handedness/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/handedness.py", "seed": None, "seed_note": "no random draws",
        "search": {"roots": [str(r.relative_to(BASE_DIR)) for r in ROOTS],
                   "text_files_scanned": len(scanned), "files": scanned, "zips": zips,
                   "pattern": PAT.pattern},
        "transmit_or_handedness_statement_found": statement,
        "statements_verbatim": specific,
        "all_hits_distinct": [{"text": t, "occurrences": w} for t, w in uniq.items()],
        "label_polarization_fields": {k: sorted(v) for k, v in fields.items()},
        "physical_check": phys,
        "verdict": ("a transmit handedness statement exists; quoted verbatim" if statement else
                    "NO LABEL OR DOCUMENT IN EITHER BUNDLE STATES THE TRANSMIT POLARIZATION OR ITS "
                    "HANDEDNESS; the physical check decides the sign"),
        "run_info": {**run_info(), "wall_s": round(time.time() - t0, 1)}}, indent=2), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
