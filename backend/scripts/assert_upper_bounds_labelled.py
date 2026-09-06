"""
assert_upper_bounds_labelled.py -- a bound may not be quoted as a rate.

    python backend/scripts/assert_upper_bounds_labelled.py [--inject]

WHY
---
The false-positive rates in METHODS 7.7 come from `CPR * F(2N,2N)`, which assumes
the two circular channels are INDEPENDENT. Section 7.10 shows, from Putrevu et
al. 2023's own Byrgius C dispersion, that they are correlated at |rho|^2 >= 0.36
-- and correlation between numerator and denominator narrows a ratio, so every
one of those rates is an UPPER BOUND rather than a rate.

"29.16 % of ordinary rock crosses the threshold" and "up to 29.16 % of ordinary
rock crosses the threshold" are different claims. The first is not supported and
the second is. The difference is one phrase, which is exactly the kind of thing
that survives one edit and is gone by the third -- METHODS 0, first pattern, in a
number rather than a caption.

So it is enforced. Every occurrence of a bounded figure anywhere in the tracked
sources must carry its qualifier within the same sentence.

WHAT COUNTS AS "THE SAME SENTENCE"
----------------------------------
A window of characters either side, not a real sentence parser: prose here spans
line breaks, markdown table cells and Python string concatenation, and a parser
that mis-splits those would fail on formatting rather than on meaning. The window
is generous in the direction that makes the gate WEAKER, so a pass is a real
pass; anything it lets through would need the qualifier to be more than 400
characters away, which is far enough that a reader would not connect them either.

AND IT SCANS SOURCE TEXT, NOT RENDERED STRINGS. A qualifier split across a Python
string concatenation -- `"... an upper "` on one line and `"bound of 29.16 %"` on
the next -- reads correctly at runtime and is invisible here, because the
substring "upper bound" never appears in the file. That happened once, in
assert_incidence_geometry.py, and the fix was to reword the source rather than to
teach this file to parse Python. The cost is a false FAILURE, never a false pass,
which is the right direction for a gate to be wrong in.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# ── the bounded figures, and the words that qualify them ────────────────────
#
# Each entry is (pattern, what it is, the phrases any one of which qualifies it).
# Adding a row here is how a new bound gets protected; the alternative is
# remembering, which is what this file exists to replace.
BOUNDED = [
    (r"29\.16\s*%",
     "false-positive rate at true CPR 0.7, N = 5 — an upper bound because it "
     "assumes independent circular channels (7.10), AND the wrong look count "
     "for this screen: the threshold touches the boxcar-smoothed field at "
     "N = 13.72, not the raw product's 5.83 (7.7)",
     ("upper bound", "upper-bound", "up to", "at most")),
    (r"17\.79\s*%",
     "false-positive rate at true CPR 0.7 at the OPERATING POINT N = 13.72 "
     "(METHODS 7.7) — still an upper bound, for the same reason (7.10)",
     ("upper bound", "upper-bound", "up to", "at most")),
    (r"3\.74\s*%",
     "false-positive rate at true CPR 0.5 at the operating point (METHODS 7.7) "
     "— an upper bound",
     ("upper bound", "upper-bound", "up to", "at most")),
]

SEARCH_ROOTS = ["docs", "backend", "frontend/src", "PRD.md", "README.md"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build",
             "docs/handoffs", "docs/evidence", "docs/gate6", "docs/gate10"}
SUFFIXES = {".py", ".ts", ".tsx", ".md", ".json", ".css", ".mjs"}
WINDOW = 400


def files():
    for root in SEARCH_ROOTS:
        p = BASE_DIR / root
        if p.is_file():
            yield p
            continue
        for f in p.rglob("*"):
            if not f.is_file() or f.suffix not in SUFFIXES:
                continue
            rel = f.relative_to(BASE_DIR).as_posix()
            if any(part in SKIP_DIRS for part in rel.split("/")):
                continue
            if any(rel.startswith(d + "/") for d in SKIP_DIRS):
                continue
            yield f


def scan(extra: list[tuple[Path, str]] | None = None):
    """Returns a list of (path, line_no, figure, context) for unlabelled hits."""
    bad = []
    docs = [(f, f.read_text(encoding="utf-8", errors="replace")) for f in files()]
    if extra:
        docs += extra
    for path, text in docs:
        for pat, what, qualifiers in BOUNDED:
            for m in re.finditer(pat, text):
                lo = max(0, m.start() - WINDOW)
                hi = min(len(text), m.end() + WINDOW)
                ctx = text[lo:hi].lower()
                if any(q in ctx for q in qualifiers):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                bad.append((path, line, m.group(0), what,
                            text[max(0, m.start() - 90):m.end() + 90]
                            .replace("\n", " ")))
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", action="store_true",
                    help="prove the gate fails on an unlabelled quotation")
    args = ap.parse_args()

    print("=" * 78)
    print("UPPER BOUNDS — a bound may not be quoted as a rate")
    print("=" * 78)
    for pat, what, qs in BOUNDED:
        print(f"  /{pat}/  {what}")
        print(f"    qualifies if any of {qs} appears within {WINDOW} characters")

    extra = None
    if args.inject:
        # A sentence of exactly the kind this gate exists to stop, in a file that
        # does not exist. If the gate passes on this, it is not a gate.
        #
        # BUILT, NOT WRITTEN. Spelling the figure out here would put an
        # unlabelled occurrence in a tracked source file, and the gate would then
        # fail on its own test fixture on every ordinary run -- which it did, the
        # first time this was written. A gate that cries wolf gets waved through.
        extra = [(Path("<injected>"),
                  f"Ordinary rock crosses the CPR threshold {29.16:.2f} % of the "
                  "time, so the screen cannot be trusted.")]
        print("\n  --inject: one unlabelled quotation of the bounded figure")

    bad = scan(extra)
    n_files = sum(1 for _ in files())
    print(f"\n  scanned {n_files} files under {', '.join(SEARCH_ROOTS)}")

    if bad:
        print(f"\n  UNLABELLED: {len(bad)}")
        for path, line, fig, what, ctx in bad:
            rel = path if path.name == "<injected>" else path.relative_to(BASE_DIR)
            print(f"    {rel}:{line}  {fig}")
            print(f"      {what}")
            print(f"      ...{ctx.strip()}...")

    if args.inject:
        if bad:
            print("\n  INJECTION CAUGHT. The gate works.")
            return 0
        print("\n  INJECTION NOT CAUGHT. The gate does not do what it says.")
        return 1

    if bad:
        print("\n  GATE FAIL — a bounded figure is quoted as if it were a rate.")
        print("  Add the qualifier, or remove the figure. METHODS 7.10.")
        return 1

    print("  GATE PASS — every occurrence carries its qualifier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
