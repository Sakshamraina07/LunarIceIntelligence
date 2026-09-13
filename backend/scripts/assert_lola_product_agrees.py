"""
assert_lola_product_agrees.py -- G24. Two LOLA products, never confused.

    python backend/scripts/assert_lola_product_agrees.py [--inject WHICH]

WHY
---
METHODS section 3 said the frame DEM was `LDEM_80S_80M` at 80 m native posts,
resampled onto the 25 m grid. It is `LDEM_80S_20M` at 20 m. Section 3 was
describing the product Phase 8 replaced, and was never updated -- so the document
contradicted itself, section 3 saying 80 and section 8 saying 20, and a reader
checking the resolution got a different answer depending which section they
opened.

**THERE ARE TWO LOLA PRODUCTS AND THEY ARE NOT INTERCHANGEABLE:**

    frame DEM        LDEM_80S_20M   20 m native -> 25 m grid
                     ldem_frame_25m.provenance.json
    horizon / PSR    LDEM_80S_80M   80 m native -> 240 m, block mean
                     horizon_240m.provenance.json

Both figures are correct for their own product. The defect is quoting one for the
other, which is how a true sentence becomes false by being moved.

WHAT IT ASSERTS
  1. the pipeline reads the frame DEM's post spacing from its provenance file
     rather than holding a literal
  2. every document that names the frame DEM's product or post spacing states
     what that provenance file states
  3. the horizon's own 80 m is not rewritten to match -- a gate that forced one
     number everywhere would replace one conflation with another
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
FRAME = BASE_DIR / "data" / "pradan" / "lola" / "ldem_frame_25m.provenance.json"
HORIZON = BASE_DIR / "data" / "pradan" / "lola" / "horizon_240m.provenance.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

#: Documents that describe the FRAME DEM. Each is searched for a sentence
#: naming a LOLA product together with a post spacing; that pair must match the
#: frame provenance file. Sentences about the horizon product are excluded by
#: name below rather than by hoping they do not match.
DOCS = ["README.md", "docs/METHODS.md", "docs/viva.md",
        "docs/scientific-methodology.md", "docs/assumptions.md"]

#: Contexts where 80 m / LDEM_80S_80M is CORRECT because it is the horizon
#: product. Matched on the line, so a line mentioning horizon, illumination,
#: PSR, azimuth sweep or 240 m is understood to be about that product.
HORIZON_CONTEXT = re.compile(
    r"horizon|illuminat|PSR|permanent|azimuth|240\s*m|block mean|2533", re.I)

INJECTIONS = ("wrongdoc", "literal", "flattened")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    print("=" * 78)
    print("G24 — the frame DEM's product and post spacing, read not remembered")
    print("=" * 78)

    for f in (FRAME, HORIZON):
        if not f.is_file():
            print(f"  GATE FAIL — {f.relative_to(BASE_DIR)} is absent.")
            return 1
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    horizon = json.loads(HORIZON.read_text(encoding="utf-8"))

    sp = frame.get("source_product")
    f_product = (sp.get("img") if isinstance(sp, dict) else sp) or ""
    f_product = Path(str(f_product)).stem
    f_native = float(frame["native_metres_per_pixel"])
    f_grid = float(frame["output_metres_per_pixel"])
    h_native = float(horizon["native_metres_per_pixel"])

    if args.inject == "flattened":
        print("  --inject flattened: the horizon's 80 m rewritten to the frame's 20\n")
        h_native = f_native

    print(f"  frame DEM    {f_product}  {f_native:g} m native -> {f_grid:g} m grid")
    print(f"  horizon      LDEM_80S_80M  {h_native:g} m native -> "
          f"{horizon['effective_metres_per_pixel']:g} m")

    bad: list[str] = []

    # 3. the two must stay distinct
    if abs(h_native - f_native) < 1e-9:
        bad.append("the horizon and frame products now report the same native post "
                   "spacing. They are different products (80 m and 20 m); forcing "
                   "one number everywhere replaces one conflation with another.")

    # 1. the pipeline reads it
    build = (BASE_DIR / "backend" / "scripts" / "build_analysis.py").read_text(
        encoding="utf-8")
    if args.inject == "literal":
        print("  --inject literal: the pipeline holds the post spacing as a literal\n")
        build = build.replace('NATIVE_POST_M = float(DEM_PROV["native_metres_per_pixel"])',
                              "NATIVE_POST_M = 20.0")
    if not re.search(r'NATIVE_POST_M\s*=\s*float\(DEM_PROV\[', build):
        bad.append("build_analysis.py no longer reads native_metres_per_pixel from "
                   "the provenance file. A literal here is the fourth spacing "
                   "constant in this project to go stale behind a rename.")
    else:
        print("  pipeline     reads native_metres_per_pixel from the provenance file")

    # 2. every document agrees, excluding lines that are about the horizon
    prod_pat = re.compile(r"LDEM_80S_(\d+)M")
    for rel in DOCS:
        p = BASE_DIR / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if args.inject == "wrongdoc" and rel == "README.md":
            print("  --inject wrongdoc: README renamed to the horizon product\n")
            text = text.replace("LDEM_80S_20M", "LDEM_80S_80M", 1)
        for i, line in enumerate(text.splitlines(), 1):
            if HORIZON_CONTEXT.search(line):
                continue
            m = prod_pat.search(line)
            if not m:
                continue
            # a product named on a line that also states a grid of 25 m is a
            # claim about the frame DEM
            if not re.search(r"25\s*m|native", line, re.I):
                continue
            named = f"LDEM_80S_{m.group(1)}M"
            if named != f_product:
                bad.append(f"{rel}:{i} names {named} for the frame DEM; "
                           f"{FRAME.name} says {f_product}  |  {line.strip()[:72]}")

    print()
    if args.inject:
        if bad:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            for b in bad:
                print(f"    {b}")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}).")
        return 1

    if bad:
        print("  GATE FAIL")
        for b in bad:
            print(f"    - {b}")
        return 1
    print("  GATE PASS — the frame DEM's product and post spacing are read from")
    print("  its provenance file, every document naming them agrees, and the")
    print("  horizon product keeps its own distinct 80 m.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
