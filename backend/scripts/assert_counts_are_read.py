"""
assert_counts_are_read.py -- G25. No document spells a count it could read.

    python backend/scripts/assert_counts_are_read.py [--inject WHICH]

WHY
---
`docs/viva.md` said "Nine gates" and "five times the verification apparatus was
wrong". `README.md` said "nineteen gates". There were twenty-one, and METHODS
section 0 records seven apparatus failures. Three numbers, three documents, all
stale, none of them wrong when written.

**NOBODY WAS CHECKING, WHICH IS WHY ALL THREE DRIFTED.** The instruction that
produced this gate asked to bring viva.md under "whatever gate already keeps
README's gate count honest". There was no such gate. README was stale for the
same reason viva.md was.

This is METHODS section 0's FIRST pattern -- a human wrote a count once and
nothing afterwards forced it to agree with the thing counted -- and the fix is
the one that pattern always takes: make whatever produces the number also produce
the words about it, or fail the build when they part company. `verify_all.py`
already reads its own gate count and its own PRD statement count rather than
spelling them. The documents did not.

WHAT IT ASSERTS
  every count below, wherever a tracked document states it in words or digits,
  equals the count READ from the thing it describes:

    gates              len(verify_all.GATES)
    apparatus failures the numbered instances under METHODS section 0's
                       second pattern
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS = BASE_DIR / "backend" / "scripts"
METHODS = BASE_DIR / "docs" / "METHODS.md"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
    13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
    21: "twenty-one", 22: "twenty-two", 23: "twenty-three", 24: "twenty-four",
    25: "twenty-five", 26: "twenty-six", 27: "twenty-seven",
}
WORD_TO_N = {w: n for n, w in WORDS.items()}

DOCS = ["README.md", "docs/viva.md", "docs/METHODS.md", "docs/testing.md",
        "docs/scientific-methodology.md", "PRD.md"]

INJECTIONS = ("gatecount", "apparatus")


def gate_count() -> int:
    sys.path.insert(0, str(SCRIPTS))
    import verify_all  # noqa: E402
    return len(verify_all.GATES)


def apparatus_count() -> int:
    """The count METHODS section 0 itself states for its second pattern.

    READ FROM THE REGISTER, NOT RECOUNTED FROM MARKERS. A first version tallied
    numbered list items plus the "And a sixth/seventh" prose additions and
    returned 5 where the section says seven -- it mis-parsed the body and would
    have failed the build on a correct document. METHODS section 0 is a prose
    register of this project's own defects; the sentence "Seven instances, and it
    is a distinct failure..." IS the authoritative statement, and this gate's job
    is to stop README and viva.md contradicting it, not to re-derive it.
    """
    text = METHODS.read_text(encoding="utf-8")
    # Built rather than spelled: a literal backslash-n in this file has been
    # mangled by the editing path more than once.
    pat = ("### The second pattern:[^" + '\\n' + "]*"
           + '\\n' + "+([A-Za-z-]+) instances")
    m = re.search(pat, text)
    return WORD_TO_N.get(m.group(1).lower(), -1) if m else -1


#: (label, the true count, the phrases that state it)
def checks(n_gates: int, n_app: int):
    return [
        ("gates", n_gates, [
            re.compile(r"(?i)\b([a-z-]+|\d+)\s+gates\b"),
            re.compile(r"(?i)runs\s+([a-z-]+|\d+)\s+gates"),
            re.compile(r"(?i)ALL\s+(\d+)\s+GATES"),
        ]),
        ("apparatus failures", n_app, [
            re.compile(r"(?i)\b([a-z-]+|\d+)\s+(?:times|cases|instances)\b[^.\n]{0,60}"
                       r"(?:verification apparatus|apparatus itself)"),
            re.compile(r"(?i)(?:verification apparatus|apparatus itself)[^.\n]{0,60}?"
                       r"\b([a-z-]+|\d+)\s+(?:times|cases|instances)\b"),
        ]),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=INJECTIONS)
    args = ap.parse_args()

    print("=" * 78)
    print("G25 — no document spells a count it could read")
    print("=" * 78)

    n_gates = gate_count()
    n_app = apparatus_count()
    if args.inject == "gatecount":
        print("  --inject gatecount: the true gate count moved, documents did not\n")
        n_gates += 1
    if args.inject == "apparatus":
        print("  --inject apparatus: the apparatus-failure count moved\n")
        n_app += 1

    print(f"  gates, read from verify_all.GATES        {n_gates}")
    print(f"  apparatus failures, read from METHODS 0  {n_app}")
    print()

    bad: list[str] = []
    for rel in DOCS:
        p = BASE_DIR / rel
        if not p.is_file():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8",
                                             errors="replace").splitlines(), 1):
            # a line that is itself about the checking, not a count of gates
            if line.lstrip().startswith(("|", ">")) and "gates" not in line.lower():
                continue
            for label, truth, pats in checks(n_gates, n_app):
                for pat in pats:
                    for m in pat.finditer(line):
                        tok = m.group(1).lower()
                        val = WORD_TO_N.get(tok)
                        if val is None:
                            if not tok.isdigit():
                                continue
                            val = int(tok)
                        if val != truth:
                            bad.append(f"{rel}:{i} states {tok!r} {label}; "
                                       f"the count is {truth}  |  "
                                       f"{line.strip()[:64]}")
    for b in bad:
        print(f"  STALE  {b}")

    print()
    if args.inject:
        if bad:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}).")
        return 1

    if bad:
        print("  GATE FAIL — a document states a count that disagrees with the")
        print("  thing it counts. Update the document; do not adjust the count.")
        return 1
    print("  GATE PASS — every stated gate count and apparatus-failure count")
    print("  agrees with the source it describes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
