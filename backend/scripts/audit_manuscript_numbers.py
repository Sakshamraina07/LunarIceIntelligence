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
DEFAULT_TEX = "Claude outputs/grsl/dfsar_detection_limits_submission.tex"

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


_SEG = re.compile(r"([^\[]*)((?:\[[^\]]*\])*)$")


def _split_path(path: str) -> list:
    """Dotted path, but a filter's value may itself contain dots or spaces
    ("records[?name=Cardanus E]"), so dots inside brackets do not split."""
    parts, depth, cur = [], 0, ""
    for ch in path.strip("."):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "." and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _match_all(elem, cond: str) -> bool:
    """`a=x&b=y`: every condition must hold (the grid artifacts are indexed by
    more than one field, e.g. population CPR and look count)."""
    return all(_match(elem, *c.split("=", 1)) for c in cond.split("&"))


def _match(elem, key: str, want: str) -> bool:
    if not isinstance(elem, dict) or key not in elem:
        return False
    v = elem[key]
    if isinstance(v, bool):
        return str(v).lower() == want.lower()
    if isinstance(v, (int, float)):
        try:
            return abs(float(v) - float(want)) < 1e-12
        except ValueError:
            return False
    return str(v) == want


def resolve(rel: str, path: str):
    """Every value a path names. `[*]` fans out over a list, `[a:b]` slices it,
    `[?field=value]` keeps the elements whose field equals value. Returns
    (values, fanned_out) -- a list, and whether the path named more than one
    element. None if any step is absent."""
    if rel not in _CACHE:
        _CACHE[rel] = load(rel)
    doc = _CACHE[rel]
    if doc is None:
        return None, False
    curs, fanned = [doc], False
    for part in _split_path(path):
        m = _SEG.fullmatch(part)
        name, brackets = m.group(1), m.group(2)
        nxt = []
        for c in curs:
            try:
                x = c[name] if name else c
            except (KeyError, TypeError):
                return None, fanned
            nxt.append(x)
        curs = nxt
        for b in re.findall(r"\[([^\]]*)\]", brackets):
            nxt = []
            for c in curs:
                if not isinstance(c, list):
                    return None, fanned
                if b == "*":
                    nxt.extend(c)
                    fanned = True
                elif ":" in b and not b.startswith("?"):
                    lo, hi = b.split(":")
                    nxt.extend(c[int(lo) if lo else None:int(hi) if hi else None])
                    fanned = True
                elif b.startswith("?"):
                    nxt.extend(e for e in c if _match_all(e, b[1:]))
                    fanned = True
                else:
                    try:
                        nxt.append(c[int(b)])
                    except (IndexError, ValueError):
                        return None, fanned
            curs = nxt
    return curs, fanned


def _num(cur):
    if isinstance(cur, bool):
        return None
    if isinstance(cur, (int, float)):
        return float(cur)
    if isinstance(cur, str):
        try:
            return float(cur.strip())
        except ValueError:
            return None
    return None


def artifact_value(rel: str, path: str):
    """Resolve a path to ONE number. A path that fans out must end in an
    aggregate -- `|min`, `|max`, `|median`, `|count` -- and a filter that
    selects exactly one element is that element. None if absent."""
    agg = None
    if "|" in path:
        path, agg = path.split("|", 1)
    vals, fanned = resolve(rel, path)
    if vals is None:
        return None
    if agg == "count":
        return float(len(vals))
    nums = [_num(v) for v in vals]
    if agg:
        nums = [x for x in nums if x is not None]
        if not nums:
            return None
        return {"min": min, "max": max,
                "median": lambda a: float(sorted(a)[len(a) // 2]) if len(a) % 2
                else 0.5 * (sorted(a)[len(a) // 2 - 1] + sorted(a)[len(a) // 2])}[agg](nums)
    if len(vals) != 1:
        return None
    cur = vals[0]
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
from manuscript_audit_table import (AUDIT, APPROX, DERIVED, QUANTIFIED,  # noqa: E402
                                    QUANTIFIER_EXEMPT, STRINGS)

#: The words that make a sentence a claim about every element of something.
QUANTIFIER = re.compile(r"\b(?:all|every|each|identical(?:ly)?|uniformly|none)\b", re.I)
#: A quantified sentence is audited only if it also carries a number -- a
#: digit or a spelled-out count ("all nine windows").
NUMBERISH = re.compile(r"(?<![\w.])\d+(?:\.\d+)?|\b(?:one|two|three|four|five|six|"
                       r"seven|eight|nine|ten|eleven|twelve|twenty|thirty|hundred)\b", re.I)


def flat_body(tex: str):
    """The manuscript body as one line (comments stripped, bibliography
    dropped), with an index back to source line numbers."""
    out, line_of = [], []
    for i, ln in enumerate(tex.split("\n"), 1):
        if r"\begin{thebibliography}" in ln:
            break
        t = re.sub(r"(?<!\\)%.*", "", ln) + " "
        out.append(t)
        line_of.extend([i] * len(t))
    return "".join(out), line_of


def sentence_at(flat: str, pos: int):
    """Naive sentence bounds: the nearest '. ' / '; ' / table row end."""
    lo = max(flat.rfind(". ", 0, pos), flat.rfind("\\\\", 0, pos), flat.rfind("? ", 0, pos))
    hi_c = [x for x in (flat.find(". ", pos), flat.find("\\\\", pos)) if x != -1]
    hi = min(hi_c) if hi_c else len(flat)
    return lo + 1, hi + 1


def quantified_scan(tex: str):
    """Every quantifier in a sentence that carries a number, and whether a
    QUANTIFIED row or a QUANTIFIER_EXEMPT entry claims it. Unclaimed ones are
    the finding: a new 'all'/'every' claim nobody has checked element-wise."""
    flat, line_of = flat_body(tex)
    start = flat.find(r"\begin{abstract}")
    hits = []
    for m in QUANTIFIER.finditer(flat, max(start, 0)):
        a, b = sentence_at(flat, m.start())
        sent = flat[a:b]
        clean = re.sub(r"\\(?:ref|cite|label)\{[^}]*\}", "", sent)
        if not NUMBERISH.search(clean):
            continue
        claimed_by = None
        for rid, anchor, *_ in QUANTIFIED:
            for am in re.finditer(anchor, sent):
                if abs((a + am.start()) - m.start()) <= 120 or a + am.start() <= m.start() <= a + am.end():
                    claimed_by = ("QUANTIFIED", rid)
        if claimed_by is None:
            for anchor, why in QUANTIFIER_EXEMPT:
                for am in re.finditer(anchor, sent):
                    if abs((a + am.start()) - m.start()) <= 120 or a + am.start() <= m.start() <= a + am.end():
                        claimed_by = ("EXEMPT", why)
        hits.append({"line": line_of[m.start()], "word": m.group(0),
                     "sentence": re.sub(r"\s+", " ", sent).strip()[:240],
                     "claimed_by": claimed_by})
    return hits


def check_quantified(values, test):
    """(ok, detail) for one test against every element."""
    kind = test[0]
    if kind == "count":
        return len(values) == test[1], f"{len(values)} elements, claim {test[1]}"
    if kind == "all_are":
        off = [v for v in values if v != test[1]]
        return (len(values) > 0 and not off), (
            f"{len(values)} elements; {len(off)} not '{test[1]}'"
            + (f": {sorted(set(map(str, off)))}" if off else ""))
    if kind == "none_are":
        off = [v for v in values if v == test[1]]
        return (len(values) > 0 and not off), f"{len(values)} elements; {len(off)} are '{test[1]}'"
    if kind == "yes_only_for_id":
        return (values.count("yes") == 1), (
            f"{values.count('yes')} 'yes' among {len(values)} (the id is checked "
            f"through counts.claims_yes)")
    nums = [_num(v) for v in values]
    if not nums or any(x is None for x in nums):
        return False, "absent or non-numeric element"
    if kind == "rounds_to":
        d = decimals(test[1])
        off = [x for x in nums if round(x, d) != round(float(test[1]), d)]
        return not off, f"{len(nums)} elements, {len(off)} do not round to {test[1]}" + (
            f": {[round(x, d + 3) for x in off]}" if off else "")
    if kind == "within":
        off = [x for x in nums if not (test[1] <= x <= test[2])]
        return not off, f"{len(nums)} elements in [{min(nums):.6g}, {max(nums):.6g}]; " \
                        f"{len(off)} outside [{test[1]}, {test[2]}]"
    if kind == "below":
        off = [x for x in nums if not x < test[1]]
        return not off, f"max {max(nums):.6g} vs < {test[1]}"
    if kind == "above":
        off = [x for x in nums if not x > test[1]]
        return not off, f"min {min(nums):.6g} vs > {test[1]}"
    if kind == "equals":
        off = [x for x in nums if x != test[1]]
        return not off, f"{len(nums)} elements, {len(off)} != {test[1]}"
    return False, f"unknown test {kind}"

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
    # A literal must appear as a WHOLE number, not as the prefix of a longer
    # one. Without these boundaries "6.2" was found inside "6.21" and the row
    # passed while the manuscript printed something else -- the specimen test
    # for the Table III look counts caught exactly that. The guard rejects a
    # match glued to a digit on either side, or one preceded by a decimal
    # point, which would make it the fractional tail of a larger number.
    lead, trail = r"(?<![0-9.])", r"(?![0-9])"
    hits = []
    for variant in (tex, normalise(tex), compact(tex)):
        for p in pats:
            for m in re.finditer(lead + "(?:" + p + ")" + trail, variant):
                hits.append(variant.count("\n", 0, m.start()) + 1)
    return sorted(set(hits))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", default=DEFAULT_TEX)
    ap.add_argument("--inject-quantified", action="store_true",
                    help=("prove the element-wise check catches what a median key "
                          "cannot: set ONE window's oversampling factor to 3.25 in "
                          "memory -- the median stays 3.10 -- and require the "
                          "quantified row to fail. Nothing is written."))
    args = ap.parse_args()
    if args.inject_quantified:
        rel = "docs/slc_multilook_control.json"
        _CACHE[rel] = load(rel)
        _CACHE[rel]["windows"][4]["oversampling_factor"] = 3.25
        _CACHE[rel]["windows"][4]["measured_bandwidth_hz"] = 1022.0

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

    # ---- "about X" rows ----------------------------------------------------
    print("\n  APPROXIMATE ('about X'), at the stated relative tolerance:")
    for cid, lit, rel, key, tol, section, note in APPROX:
        lines = appears(tex, lit)
        val = artifact_value(rel, key)
        if not lines:
            verdict = "ABSENT"
            absent.append((cid, lit, section))
        elif val is None:
            verdict = "NO SOURCE"
            nosource.append((cid, lit, section, f"{rel} has no key {key}"))
        else:
            ok = abs(val - float(lit)) <= tol * abs(float(lit))
            verdict = "PASS" if ok else "MISMATCH"
            if not ok:
                mismatch.append((cid, lit, val, rel, key, section))
        print(f"    {cid:<16} about {lit:<8} artifact {val if val is None else round(val, 4)!s:<10}"
              f" tol {tol:.0%}  {verdict}")
        rows.append({"id": cid, "printed": lit, "artifact": rel, "key": key,
                     "artifact_value": val, "verdict": verdict, "section": section,
                     "note": note, "tolerance_relative": tol, "tex_lines": lines})

    # ---- identifiers printed verbatim ---------------------------------------
    print("\n  STRINGS, printed verbatim:")
    tex_plain = tex.replace("\\_", "_")
    for cid, lit, rel, key, section, note in STRINGS:
        lines = [i for i, ln in enumerate(tex_plain.split("\n"), 1) if lit in ln]
        vals, _ = resolve(rel, key)
        val = vals[0] if vals and len(vals) == 1 and isinstance(vals[0], str) else None
        if not lines:
            verdict = "ABSENT"
            absent.append((cid, lit, section))
        elif val is None:
            verdict = "NO SOURCE"
            nosource.append((cid, lit, section, f"{rel} has no string key {key}"))
        else:
            ok = lit in val
            verdict = "PASS" if ok else "MISMATCH"
            if not ok:
                mismatch.append((cid, lit, val, rel, key, section))
        print(f"    {cid:<16} {verdict:<9} {lit}  <-  {rel}::{key} = {val}")
        rows.append({"id": cid, "printed": lit, "artifact": rel, "key": key,
                     "artifact_value": val, "verdict": verdict, "section": section,
                     "note": note, "tex_lines": lines})

    # ---- quantified claims, against every element ---------------------------
    print("\n  QUANTIFIED CLAIMS -- 'all', 'every', 'each', tested against EVERY element:")
    qrows, qfail = [], []
    flat_, _ = flat_body(tex)
    flat_one = re.sub(r"\s+", " ", flat_)
    for cid, anchor, checks, section, note in QUANTIFIED:
        present = re.search(anchor, flat_one) is not None
        details, ok_all = [], True
        if not present:
            verdict = "ABSENT"
        elif not checks:
            verdict, ok_all = "UNBACKED", False
            details.append("no artifact field records the elements this claim is about")
        else:
            for rel, key, test in checks:
                vals, _ = resolve(rel, key)
                if vals is None or (test[0] != "count" and not vals):
                    ok, det = False, f"{rel}::{key} absent"
                else:
                    ok, det = check_quantified(vals, test)
                details.append(f"{rel}::{key} {test[0]}: {det} -> {'ok' if ok else 'FAIL'}")
                ok_all &= ok
            verdict = "PASS" if ok_all else "FAIL"
        if verdict != "PASS":
            qfail.append((cid, verdict))
        print(f"    {cid:<24} {verdict:<9} ({section}) {note or ''}")
        for d in details:
            print(f"        {d}")
        qrows.append({"id": cid, "anchor": anchor, "verdict": verdict, "section": section,
                      "note": note, "details": details})

    scan = quantified_scan(tex)
    unchecked = [h for h in scan if h["claimed_by"] is None]
    print(f"\n  QUANTIFIER SCAN: {len(scan)} quantifier(s) in sentences that carry a number; "
          f"{sum(1 for h in scan if h['claimed_by'] and h['claimed_by'][0] == 'QUANTIFIED')} "
          f"checked element-wise, "
          f"{sum(1 for h in scan if h['claimed_by'] and h['claimed_by'][0] == 'EXEMPT')} exempt "
          f"with a reason, {len(unchecked)} UNCHECKED")
    for h in unchecked:
        print(f"    UNCHECKED L{h['line']} [{h['word']}] {h['sentence'][:200]}")

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
        "quantified": {"rows": qrows,
                       "counts": {v: sum(1 for r in qrows if r["verdict"] == v)
                                  for v in ("PASS", "FAIL", "UNBACKED", "ABSENT")},
                       "scan": scan, "unchecked": len(unchecked),
                       "rule": ("a claim about every element is tested against every "
                                "element; a median or a single row cannot pass it")},
    }
    if args.inject_quantified:
        med = artifact_value("docs/slc_multilook_control.json", "medians.oversampling_factor")
        q = next(r for r in qrows if r["id"] == "q_oversampling_nine")
        bw = next(r for r in rows if r["id"] == "bw_max")
        print("\n  INJECTION: window 4's oversampling factor set to 3.25 in memory")
        print(f"    the median key still reads {med:.4f} -> the old check would PASS")
        print(f"    q_oversampling_nine: {q['verdict']}   bw_min/bw_max row: {bw['verdict']}")
        caught = q["verdict"] == "FAIL"
        print(f"  {'INJECTION CAUGHT' if caught else 'INJECTION MISSED'} -- nothing written")
        return 0 if caught else 1
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
    if qfail or unchecked:
        print("\n  QUANTIFIED:")
        for cid, v in qfail:
            print(f"    {cid}: {v}")
        if unchecked:
            print(f"    {len(unchecked)} quantified sentence(s) claimed by no row")
    print("\n  wrote docs/manuscript_number_audit.json")
    print("  This is a REPORT. The manuscript is not edited here.")
    # A non-zero exit on anything a reader would have to be told: a printed
    # figure its artifact contradicts or cannot find, and a quantified claim
    # that fails on some element or that nobody has checked element by element.
    return 1 if (mismatch or absent or derived_bad or qfail or unchecked) else 0


if __name__ == "__main__":
    raise SystemExit(main())
