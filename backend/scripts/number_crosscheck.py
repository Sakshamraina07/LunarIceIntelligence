"""
number_crosscheck.py -- the second, independent net over the manuscript's
numbers.

    python backend/scripts/number_crosscheck.py [--tex PATH] [--list-unmatched]

WHY A SECOND ONE
----------------
`audit_manuscript_numbers.py` maps each load-bearing figure to a NAMED KEY and
compares it there. That is the strong check, and it has one weakness: it only
sees the rows somebody wrote down. A literal that entered the manuscript and
was never added to the table is invisible to it.

This net is the opposite shape. It takes EVERY numeric literal in the body text
and asks whether ANY number anywhere in the artifacts rounds to it. That is a
much weaker statement about any single figure -- a coincidence in a 240 000-value
haystack proves nothing -- so it is not a gate. What it is good for is the
residue: the literals that match nothing at all. Each of those is either a
closed form, a value from the literature, a label field, or a number with
nothing behind it, and the last kind is what this exists to surface.

Ported from the reference `Claude outputs/hygiene/number_crosscheck.py`, whose
paths pointed at a sandbox that does not exist here; the matching rule is
unchanged.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEX = "Claude outputs/grsl/dfsar_detection_limits_submission.tex"
OUT = BASE_DIR / "docs" / "number_crosscheck.json"
JSON_DIRS = ["docs", "frontend/public/analysis", "data/pradan/dfsar"]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def flatten(o, prefix, out):
    if isinstance(o, dict):
        for k, v in o.items():
            flatten(v, f"{prefix}.{k}", out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            flatten(v, f"{prefix}[{i}]", out)
    elif isinstance(o, bool):
        pass
    elif isinstance(o, (int, float)) and math.isfinite(o):
        out.append((float(o), prefix))
    elif isinstance(o, str):
        for m in re.finditer(r"-?\d+\.\d+(?:[eE]-?\d+)?", o):
            out.append((float(m.group()), prefix + ":str"))


#: `2\,337\,086` is ONE number. The reference pattern knew only the comma form,
#: so every LaTeX-spaced count arrived as three orphan tokens ("337", "086")
#: that match nothing and read as findings.
NUM_RE = re.compile(
    r"(?<![\w.])("
    r"\d{1,3}(?:\\,\d{3})+"
    r"|\d{1,3}(?:,\d{3})+"
    r"|\d+\.\d+(?:\\times\s*10\^\{-?\d+\}|e-?\d+)?"
    r"|\d+"
    r")(?![\w])")


def parse(tok: str) -> float:
    # \, first: stripping bare commas first would leave a dangling backslash
    t = tok.replace("\\,", "").replace(",", "")
    t = re.sub(r"\\times\s*10\^\{(-?\d+)\}", r"e\1", t)
    return float(t)


def sig_digits(tok: str) -> int:
    t = re.sub(r"\\times10\^\{-?\d+\}|e-?\d+", "", tok).replace(",", "").lstrip("0")
    t = t.replace(".", "")
    return max(len(t.lstrip("0")), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=DEFAULT_TEX)
    ap.add_argument("--list-unmatched", action="store_true")
    args = ap.parse_args()

    vals = []
    for d in JSON_DIRS:
        for f in sorted(glob.glob(str(BASE_DIR / d / "**" / "*.json"), recursive=True)):
            try:
                flatten(json.loads(Path(f).read_text(encoding="utf-8")),
                        Path(f).name, vals)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  skip {f}: {exc}", file=sys.stderr)

    tex_path = BASE_DIR / args.tex
    if not tex_path.is_file():
        print(f"  MANUSCRIPT NOT FOUND: {tex_path}")
        return 1
    lines = tex_path.read_text(encoding="utf-8", errors="replace").splitlines()

    print("=" * 78)
    print(f"NUMBER CROSS-CHECK — {args.tex} against every artifact number")
    print("=" * 78)
    print(f"  {len(vals):,} numbers loaded from {len(JSON_DIRS)} artifact trees")

    seen: dict = {}
    in_bib = False
    for i, ln in enumerate(lines, 1):
        s = re.sub(r"(?<!\\)%.*", "", ln)
        # `$2\,337\,086\to2\,294\,084$` -- the control word runs into the digit
        # that follows it, and the word-boundary lookbehind then starts the
        # match three characters late. Binary relations are separated here;
        # \times is left alone because the scientific-notation form needs it.
        s = re.sub(r"\\(?:to|pm|ge|le|geq|leq|approx|sim|cdot)(?![a-zA-Z])", " ", s)
        if r"\bibitem" in s or r"\begin{thebibliography}" in s:
            in_bib = True
        if in_bib:
            continue
        for m in NUM_RE.finditer(s):
            tok = m.group(0)
            if re.fullmatch(r"\d{1,2}", tok):        # section and list numbering
                continue
            if re.fullmatch(r"(19|20)\d\d", tok):    # years
                continue
            seen.setdefault(tok, []).append(i)

    def matches(x: float, tok: str):
        if x == 0:
            return None
        if "\\times" in tok or "e-" in tok:
            # scientific notation: compare at the MANTISSA's precision, which
            # is what the reader can check. Without this the two-figure forms
            # (8.6e-5) could match nothing at all and read as unsourced.
            rel_tol = 0.5 * 10.0 ** (-(sig_digits(tok) - 1))
            dec = None
        else:
            rel_tol = 0.005 if sig_digits(tok) >= 3 else None
            dec = len(tok.split(".")[1]) if "." in tok else None
        for v, where in vals:
            if v == 0:
                continue
            if dec is not None and abs(round(v, dec) - x) < 10 ** (-dec) * 0.51:
                return where
            # a sign difference is a convention, not a missing source
            if rel_tol is not None and abs(abs(v) - abs(x)) / abs(x) < rel_tol:
                return where
        return None

    rows = []
    for tok, ls in sorted(seen.items(), key=lambda kv: kv[1][0]):
        rows.append((tok, ls, matches(parse(tok), tok)))
    ok = [r for r in rows if r[2]]
    no = [r for r in rows if not r[2]]

    print(f"  {len(rows)} distinct literals in body text; {len(ok)} found in an "
          f"artifact; {len(no)} without a match")
    print("\n  NO ARTIFACT MATCH — each is a closed form, a literature value, a")
    print("  label field, or a number with nothing behind it:")
    for tok, ls, _ in no:
        print(f"    {tok:>16}  lines {ls[:8]}")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/number-crosscheck/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/number_crosscheck.py",
        "manuscript": args.tex,
        "artifact_numbers_loaded": len(vals),
        "artifact_trees": JSON_DIRS,
        "rule": ("a literal matches if some artifact value rounds to it at the "
                 "printed precision, or agrees to 0.5 % relative with >= 3 "
                 "significant digits. Deliberately loose: this is a net for "
                 "literals nobody mapped, not a check on any one figure"),
        "not_a_gate": ("a match here is weak evidence; audit_manuscript_numbers.py "
                       "is the strong check, and this only catches what that "
                       "table has not been told about"),
        "distinct_literals": len(rows),
        "matched": len(ok),
        "unmatched": len(no),
        "unmatched_rows": [{"literal": t, "lines": l} for t, l, _ in no],
        "matched_rows": [{"literal": t, "lines": l, "example_key": w} for t, l, w in ok],
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
