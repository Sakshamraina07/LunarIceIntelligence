"""
audit_manuscript_numbers.py -- every load-bearing number in the manuscript,
against the artifact it claims to come from.

    python backend/scripts/audit_manuscript_numbers.py [--tex PATH]

WHY
---
`METHODS.md` has a numeric-literal coverage checker (G8). The MANUSCRIPT does
not, and that asymmetry is exactly how a stale figure survives: 4.52 and 9.95
were quoted from a nine-window run whose artifact had been overwritten by a
five-window run, and nothing compared the two.

THIS READS THE .tex READ-ONLY. It never writes to it, and it must not: the
manuscript is edited elsewhere and a second editor would fork it. The output is
a report -- `docs/manuscript_number_audit.json` -- naming, for every audited
figure, the artifact and key it resolves to and whether it agrees.

WHAT A VERDICT MEANS
  PASS       the number appears in the .tex AND matches the artifact value at
             the precision printed
  MISMATCH   it appears, and the artifact says something else. A finding.
  NO SOURCE  it appears, and no artifact on disk carries it. Also a finding --
             a number with nothing behind it is the defect, not an inconvenience
  ABSENT     the audit expected it in the .tex and did not find it. Usually
             means the manuscript rewrote a sentence; still reported, because a
             silently vanished figure is a change nobody reviewed
  DERIVED    arithmetic from other audited figures; the arithmetic is checked
             here and the inputs are audited on their own rows
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
#: The comment-stripped build is what a reviewer receives, so it is what is
#: audited; `..._full.tex` is the master and is checked with --tex.
DEFAULT_TEX = "Claude outputs/dfsar_detection_limits_submission.tex"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def load(rel: str):
    p = BASE_DIR / rel
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


_CACHE: dict = {}


def artifact_value(rel: str, path: str):
    """Resolve a dotted/indexed path inside an artifact. None if absent."""
    if rel not in _CACHE:
        _CACHE[rel] = load(rel)
    doc = _CACHE[rel]
    if doc is None:
        return None
    cur = doc
    for part in path.strip(".").split("."):
        m = re.fullmatch(r"([^\[]*)\[(\d+)\]", part)
        try:
            if m:
                if m.group(1):
                    cur = cur[m.group(1)]
                cur = cur[int(m.group(2))]
            else:
                cur = cur[part]
        except (KeyError, IndexError, TypeError):
            return None
    if isinstance(cur, bool):
        return None
    if isinstance(cur, (int, float)):
        return float(cur)
    # Labels are transcribed as strings, so "21" and "3321.641156" are values.
    # Refusing to coerce them reported real sources as NO SOURCE.
    if isinstance(cur, str):
        try:
            return float(cur.strip())
        except ValueError:
            return None
    return None


# The table itself lives in manuscript_audit_table.py: one row per printed
# figure, naming the artifact and the key it must come from. It is the part a
# reviewer argues with, so it is a file they can read without reading this one.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from manuscript_audit_table import AUDIT, DERIVED  # noqa: E402

def decimals(lit: str) -> int:
    lit = re.sub(r"[,\s]", "", lit)
    if "e" in lit.lower():
        return 12
    return len(lit.split(".")[1]) if "." in lit else 0


def normalise(tex: str) -> str:
    """Strip LaTeX digit separators so 120\\,000 and 2,337,086 are findable.

    Replaced with a SPACE, not deleted, so offsets stay usable for line numbers
    and so adjacent tokens cannot fuse into a number that is not in the text.
    """
    out = re.sub(r"(?<=\d)\\,(?=\d)", " ", tex)
    out = re.sub(r"(?<=\d),(?=\d\d\d)", " ", out)
    out = re.sub(r"(?<=\d)\{,\}(?=\d)", "   ", out)
    return out


def compact(tex: str) -> str:
    """The same text with digit-group separators DELETED, so that a literal
    written 2,337,086 here is found in a source that writes 2\\,337\\,086.

    The space form above cannot do it, and that gap made the audit report
    ABSENT for six-figure counts the manuscript prints on every other page.
    Deletion is safe *between digits only*: what LaTeX renders as one number is
    exactly what collapses here, and nothing else does.
    """
    return re.sub(r"(?<=\d)(?:\\,|\{,\}|,|\s|~)(?=\d)", "", tex)


def appears(tex: str, lit: str) -> list:
    """Line numbers where the literal appears, tolerating LaTeX spacing.

    Every variant preserves newlines, so a hit's line number is the same in all
    of them and they are searched independently -- the earlier version
    concatenated the variants and reported line numbers past the end of the
    file for anything matched in the second copy.
    """
    bare = lit.replace(",", "")
    pats = [re.escape(lit), re.escape(bare)]
    if "e-" in bare:
        mant, exp = bare.split("e-")
        pats.append(re.escape(mant) + r"\s*\\times\s*10\^\{?-\s*" + exp.lstrip("0"))
        pats.append(re.escape(mant) + r"[^0-9]{0,20}10\^\{?-" + exp.lstrip("0"))
    hits = []
    for variant in (tex, normalise(tex), compact(tex)):
        for p in pats:
            for m in re.finditer(p, variant):
                hits.append(variant.count("\n", 0, m.start()) + 1)
    return sorted(set(hits))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=DEFAULT_TEX)
    args = ap.parse_args()

    tex_path = BASE_DIR / args.tex
    if not tex_path.is_file():
        print(f"  MANUSCRIPT NOT FOUND: {tex_path}")
        return 1
    tex = tex_path.read_text(encoding="utf-8", errors="replace")

    print("=" * 100)
    print(f"MANUSCRIPT NUMBER AUDIT — {args.tex} (READ-ONLY)")
    print("=" * 100)
    print(f"  {'id':<18}{'printed':>12}{'artifact value':>18}  {'verdict':<10} source")
    print("  " + "-" * 96)

    rows, mismatch, nosource, absent = [], [], [], []
    for cid, lit, rel, key, section, note in AUDIT:
        lines = appears(tex, lit)
        val = artifact_value(rel, key) if rel and key else None
        if not lines:
            verdict = "ABSENT"
            absent.append((cid, lit, section))
        elif rel is None:
            verdict = "NO SOURCE"
            nosource.append((cid, lit, section, note))
        elif val is None:
            verdict = "NO SOURCE"
            nosource.append((cid, lit, section,
                             f"{rel} has no key {key}"))
        else:
            try:
                # a literal may be written with either separator -- "120 000"
                # is one number, and parsing it as text was reporting a row
                # that agreed exactly as a MISMATCH
                printed = float(re.sub(r"[,\s]", "", lit))
            except ValueError:
                printed = None
            if printed is None:
                ok = False
            elif "e" in lit.lower():
                # SIGNIFICANT FIGURES, not decimal places. Comparing 4.261e-3 at
                # twelve decimals against 0.004261082862785302 called a correct
                # figure a MISMATCH -- the audit was wrong, not the manuscript.
                sig = len(lit.lower().split("e")[0].replace(".", "").lstrip("0"))
                ok = (printed == 0 and float(val) == 0) or (
                    float(val) != 0
                    and round(float(val),
                              sig - 1 - int(math.floor(math.log10(abs(float(val))))))
                    == printed)
            else:
                d = decimals(lit)
                # A fraction stored 0..1 and printed as a percentage is the same
                # measurement, not a second source.
                ok = (round(float(val), d) == round(printed, d)
                      or round(float(val) * 100.0, d) == round(printed, d))
            verdict = "PASS" if ok else "MISMATCH"
            if not ok:
                mismatch.append((cid, lit, val, rel, key, section))
        shown = "—" if val is None else f"{val:.6g}"
        src = f"{rel}::{key}" if rel else (note or "")
        print(f"  {cid:<18}{lit:>12}{shown:>18}  {verdict:<10} {src}")
        rows.append({"id": cid, "printed": lit, "artifact": rel, "key": key,
                     "artifact_value": val, "verdict": verdict,
                     "section": section, "note": note,
                     "tex_lines": lines})

    print("\n  DERIVED arithmetic:")
    derived_bad = []
    for cid, printed, fn, tol in DERIVED:
        got = fn()
        ok = abs(got - printed) <= tol
        print(f"    {cid:<16} printed {printed:<14g} computed {got:<20.10g} "
              f"{'ok' if ok else 'MISMATCH'}")
        if not ok:
            derived_bad.append((cid, printed, got))

    out = {
        "schema": "lunar-ice/manuscript-audit/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "computed_by": "backend/scripts/audit_manuscript_numbers.py",
        "manuscript": args.tex,
        "manuscript_is_read_only": True,
        "n_audited": len(rows),
        "counts": {"PASS": sum(1 for r in rows if r["verdict"] == "PASS"),
                   "MISMATCH": len(mismatch), "NO SOURCE": len(nosource),
                   "ABSENT": len(absent)},
        "rows": rows,
        "derived_checks_failed": derived_bad,
    }
    (BASE_DIR / "docs" / "manuscript_number_audit.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")

    print(f"\n  {out['counts']}")
    if mismatch:
        print("\n  MISMATCH:")
        for cid, lit, val, rel, key, sec in mismatch:
            print(f"    {cid} (§{sec}): manuscript {lit}, {rel}::{key} = {val}")
    if nosource:
        print("\n  NO SOURCE:")
        for cid, lit, sec, why in nosource:
            print(f"    {cid} (§{sec}): {lit} — {why}")
    if absent:
        print("\n  ABSENT from the .tex:")
        for cid, lit, sec in absent:
            print(f"    {cid} (§{sec}): {lit}")
    print("\n  wrote docs/manuscript_number_audit.json")
    print("  This is a REPORT. The manuscript is not edited here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
