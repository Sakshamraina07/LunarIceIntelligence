"""
assert_withdrawn_claims_absent.py -- G19. A withdrawn claim stays withdrawn.

    python backend/scripts/assert_withdrawn_claims_absent.py [--list] [--inject WHICH]

WHY
---
This project has withdrawn eight specific claims after measuring them wrong. Each
was true-looking, each reached a document or a screen, and each is recorded in
METHODS section 0. A withdrawal is only a withdrawal if the claim cannot come
back, and prose is copied forward: a sentence deleted from one file survives in a
tag message, a commit body, a README, or the next draft of the same section.

ANCHOR ON THE CLAIM, NEVER ON THE NUMBER
----------------------------------------
An earlier ad-hoc version of this scan rejected the bare string "8.75". That
figure is the FABRICATED base candidate-ice area that PRD Phase 1B deleted -- and
it is ALSO the measured width of the amplitude ribbon (8.75 km), which appears
correctly in three source files today, and it is ALSO the look count derivable
from Fa & Cai 2013's published CPR moments, which is about to become a correct,
load-bearing figure in a new external-validation section.

    A scan that fires on a bare number will either block correct work or be
    disabled, and both are worse than a scan that names what it forbids.

So every term below is anchored on the WORDS THAT MADE THE CLAIM WRONG -- the
surrounding assertion, not the digits. `--list` prints each term with the exact
sentence it is protecting against, because a forbidden pattern whose reason is
not written down becomes a pattern nobody dares delete and nobody understands.
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

#: (id, pattern, the sentence it protects against, why it is withdrawn)
#:
#: Each pattern must match the CLAIM. None of them may match a bare figure: a
#: number is evidence, and the same number is usually correct somewhere else.
WITHDRAWN = [
    ("pdf-local-only",
     r"(?is)pdf[^.]{0,120}verifiable\s+locally\s+only"
     r"|verifiable\s+locally\s+only[^.]{0,120}pdf"
     r"|report[^.]{0,80}\bcan(?:not|'t)\s+be\s+(?:produced|generated)[^.]{0,40}deployed",
     '"The PDF report is verifiable LOCALLY ONLY."',
     "Disproved by the deployed host: GET /api/report/pdf/faustini returns HTTP "
     "200 and a 12,356-byte report. The report renders committed artifacts and "
     "needs no rasters. METHODS 0, instance 18."),

    ("report-409-in-production",
     r"(?is)/report/pdf[^.]{0,80}returns?\s+(?:HTTP\s*)?409\s+in\s+production"
     r"|409\s+in\s+production[^.]{0,80}report",
     '"/report/pdf/faustini returns 409 in production, by design."',
     "Same withdrawal. The 409 path is real but fires on ABSENT ARTIFACTS, not "
     "on absent rasters, and no deployed host is in that state."),

    ("ceiling-hit-exactly",
     r"(?is)ceiling[^.]{0,40}hit\s+exactly|hit\s+exactly[^.]{0,40}ceiling",
     '"the ceiling, hit exactly"',
     "It is not exact. Measured crossing 0.004261057358235121 against algebraic "
     "0.004261082862785302 -- 5.985e-06 relative. Six-figure agreement between a "
     "measurement and a closed form is the stronger claim; 'exactly' is what a "
     "copied number looks like. METHODS 1.4."),

    ("psr-point-sun-current",
     r"(?is)jaccard[^\n]{0,40}0\.6732"
     r"|(?:ratio|over-?call)[^.\n]{0,60}1\.301\s*[x×][^.\n]{0,40}(?:lpsr|their|published)",
     '"Jaccard 0.6732 ... ratio 1.301x" quoted as the current agreement.',
     "Those are the POINT-SUN run. The finite solar disc shipped and the "
     "validation was re-run: Jaccard 0.714229, ratio 1.174153. The old figures "
     "are legitimate as the 'before' side of the A/B and are forbidden only as "
     "the current result. METHODS 0, instance 20."),

    ("operative-look-count-5",
     r"(?is)operative[^.]{0,60}\bN\s*(?:≈|~|=)\s*5\b"
     r"|\bN\s*(?:≈|~|=)\s*5\b[^.]{0,60}(?:for\s+)?everything\s+downstream",
     '"The operative number for everything downstream is therefore N ~ 5."',
     "The threshold touches the boxcar-smoothed field, whose measured ENL is "
     "13.72. N ~ 5 is a true fact about the DELIVERED PRODUCT and is forbidden "
     "only as the downstream operating point. METHODS 7.4 and 7.7."),

    ("fabricated-base-area",
     r"(?is)base[_ ]?area(?:_km2)?[^.\n]{0,40}8\.75"
     r"|8\.75[^.\n]{0,40}base\s+candidate\s+ice\s+area",
     '"base_area_km2: float = Query(8.75, ...)" -- a candidate-ice-area '
     'baseline with no origin, scaled into a sensitivity curve.',
     "Deleted in PRD Phase 1B with run_sensitivity_sweep. NOTE THE ANCHOR: the "
     "bare figure 8.75 is CORRECT elsewhere -- the amplitude ribbon is 8.75 km "
     "wide, and 8.75 is derivable as a look count from Fa & Cai 2013's published "
     "CPR moments. Only the base-area claim is forbidden."),

    ("psr-brightness-proxy",
     r"(?is)(?:psr|permanent(?:ly)?[ _]shadow\w*)[^.]{0,80}"
     r"(?:illumination\s*<\s*0\.05|brightness\s+threshold)"
     r"|sun_altitude_deg\s*[=:]\s*1\.5",
     '"psr_mask = (illumination < 0.05)" from a hillshade at a capped 1.5 deg '
     'solar altitude.',
     "METHODS 5.3 measures that model wrong by up to 4.4x: elevation at latitude "
     "phi reaches 1.54 + (90 - |phi|), 6.71 deg at this frame's edge. Deleted; "
     "the served path reads the horizon product or refuses. METHODS 5.1a."),

    ("preregistration-conflation",
     r"(?is)8\s*of\s*8[^.]{0,120}(?:1\.2\s*[-–—]\s*1\.6|area[ _]ratio|band)"
     r"|(?:1\.2\s*[-–—]\s*1\.6)[^.]{0,120}8\s*of\s*8",
     '"...the eight-row prediction for that comparison ... 8 of 8 held", read '
     'as the score for the 1.2-1.6x area-ratio band.',
     "Two different pre-registrations. The 8-of-8 scores the solar-disc A/B and "
     "is TRUE. The band is scored separately as NOT A HIT at 1.174x. Forbidden "
     "only as one claim. METHODS 5.10."),
]

#: A hit is EXCUSED when retraction language sits within RETRACTION_WINDOW
#: characters of it.
#:
#: THE SCAN FORBIDS ASSERTING A CLAIM, NOT MENTIONING ONE. Without this, its
#: first run flagged nine hits and every one was a TOMBSTONE -- the docstring in
#: assert_pdf_refuses_without_rasters.py recording that the claim was false, the
#: comment in module_g_volume.py marking the deleted constant, PRD's own table of
#: what Phase 1B removed, METHODS 5.10 explaining the conflation. A project that
#: records its withdrawals in prose CANNOT have a scan that fires on the record.
#:
#: Same shape as G9's negative lookbehind on RECOMMENDED: a check that fires on
#: its own disclaimer is a check that gets waved through.
RETRACTION_MARKERS = (
    "withdraw", "was false", "is false", "used to", "no longer", "deleted",
    "superseded", "previously", "corrected", "disproved", "not the current",
    "was here", "tombstone", "removed", "retract", "instance", "wrong",
    "defect", "first version", "earlier",
    # Narrow past-tense markers. "pre-registered" was tried here and removed:
    # a LIVE conflation of the two pre-registrations would use that exact word,
    # and it excused the very claim it was meant to let through -- the marker
    # list defeating the injection is the same failure as a gate defeating its
    # own fixture. These name the BASELINE column of the solar-disc A/B, where
    # the point-Sun figures legitimately live as the "was" side.
    "as it was", "point (was)", "(was)", "baseline",
    "point-sun", "point sun", "not a hit", "true and stays", "delivered product",
    "forbidden only", "protects against", "arguably void", "this said",
    "phase 1b", "computed nothing", "with no origin",
)
RETRACTION_WINDOW = 320

#: A hit is also excused when the sentence NEGATES the claim. "Permanent shadow
#: is not a brightness threshold" states the correct position and matched the
#: pattern for asserting the wrong one; a scan that cannot read a negation would
#: force the documentation to stop denying the thing it withdrew.
NEGATIONS = (" is not ", " are not ", " never ", " cannot ", " no longer ",
             " rather than ", " instead of ", " not a ", " not the ")
NEGATION_WINDOW = 90


SEARCH_ROOTS = ["docs", "backend", "frontend/src", "PRD.md", "README.md"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build",
             "docs/handoffs", "docs/evidence", "docs/gate6", "docs/gate10"}
SUFFIXES = {".py", ".ts", ".tsx", ".md", ".json", ".css", ".mjs"}

#: This file necessarily contains every forbidden pattern, as patterns. So does
#: METHODS section 0, which is the register that records them. Both are excluded
#: BY PATH, and the exclusion is narrow and named -- an exclusion by content
#: would be a hole any file could climb through.
SELF = {"backend/scripts/assert_withdrawn_claims_absent.py"}

#: DEFECT REGISTERS: sections whose JOB is to quote the claim being withdrawn.
#: Scoped to a file AND a heading, never to a whole file, so a register cannot
#: become a place to park a live claim. Each carries the reason it is a register.
REGISTERS = {
    "docs/METHODS.md": (
        r"^## 0 ", r"^## 1 ",
        "section 0 is the defect register; it must be able to quote a withdrawn "
        "claim in order to record it"),
    "PRD.md": (
        r"^### 1\.2 What is NOT real", r"^### 1\.3 ",
        "PRD 1.2 is the as-found defect table -- 'What is NOT real and still "
        "reaches a screen' -- and every row exists to state the defect verbatim"),
}


def files():
    for root in SEARCH_ROOTS:
        p = BASE_DIR / root
        if p.is_file():
            yield p
            continue
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if not f.is_file() or f.suffix not in SUFFIXES:
                continue
            rel = f.relative_to(BASE_DIR).as_posix()
            if any(part in SKIP_DIRS for part in rel.split("/")):
                continue
            if any(rel.startswith(d + "/") for d in SKIP_DIRS):
                continue
            if rel in SELF:
                continue
            yield f


def scan(extra=None):
    hits = []
    docs = [(f, f.read_text(encoding="utf-8", errors="replace")) for f in files()]
    if extra:
        docs += extra
    for path, text in docs:
        rel = (path.as_posix() if path.name.startswith("<")
               else path.relative_to(BASE_DIR).as_posix())
        # METHODS section 0 is the defect register: it must be able to QUOTE a
        # withdrawn claim in order to record it. The exclusion is scoped to that
        # section, not to the file.
        body = text
        reg = REGISTERS.get(rel)
        if reg:
            start_pat, end_pat, _why = reg
            ms = re.search(start_pat, text, re.M)
            me = re.search(end_pat, text, re.M)
            if ms and me and me.start() > ms.start():
                # Blank the register span, preserving offsets so reported line
                # numbers stay true to the file.
                body = (text[:ms.start()]
                        + " " * (me.start() - ms.start())
                        + text[me.start():])
        for cid, pat, sentence, why in WITHDRAWN:
            for hit in re.finditer(pat, body):
                lo = max(0, hit.start() - RETRACTION_WINDOW)
                hi = min(len(body), hit.end() + RETRACTION_WINDOW)
                window = body[lo:hi].lower()
                if any(mk in window for mk in RETRACTION_MARKERS):
                    continue  # a record of the withdrawal, not the claim
                near = body[max(0, hit.start() - NEGATION_WINDOW):
                            hit.end() + NEGATION_WINDOW].lower()
                if any(ng in near for ng in NEGATIONS):
                    continue  # the sentence denies the claim
                line = body.count(chr(10), 0, hit.start()) + 1
                ctx = body[max(0, hit.start() - 70):hit.end() + 70]
                ctx = ctx.replace(chr(10), " ")
                hits.append((rel, line, cid, sentence, why, ctx))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print every term with the sentence it protects against")
    ap.add_argument("--inject", help="a claim id to re-introduce, proving the "
                                     "scan fails on it")
    args = ap.parse_args()

    print("=" * 78)
    print("G19 — a withdrawn claim stays withdrawn")
    print("=" * 78)

    if args.list:
        print(f"  {len(WITHDRAWN)} terms. Each is anchored on the CLAIM, never on a")
        print("  figure: the same number is usually correct somewhere else.\n")
        for cid, pat, sentence, why in WITHDRAWN:
            print(f"  [{cid}]")
            print(f"    protects against : {sentence}")
            print(f"    why withdrawn    : {why}")
            print(f"    pattern          : {pat[:96]}{'...' if len(pat) > 96 else ''}")
            print()
        return 0

    extra = None
    if args.inject:
        match = [w for w in WITHDRAWN if w[0] == args.inject]
        if not match:
            print(f"  no such claim id: {args.inject}")
            print(f"  known: {', '.join(w[0] for w in WITHDRAWN)}")
            return 1
        cid, _, sentence, _ = match[0]
        print(f"\n  --inject {cid}: re-introducing the withdrawn sentence\n")
        extra = [(Path(f"<injected:{cid}>"), _SPECIMENS[cid])]

    hits = scan(extra)

    if args.inject:
        got = {h[2] for h in hits}
        if args.inject in got:
            print(f"  INJECTION CAUGHT ({args.inject}). The gate works.")
            for rel, line, cid, sentence, why, ctx in hits:
                if cid == args.inject:
                    print(f"    {rel}:{line}  ...{ctx.strip()}...")
            return 0
        print(f"  INJECTION NOT CAUGHT ({args.inject}). The gate does not do what "
              f"it says.")
        return 1

    if hits:
        print(f"\n  {len(hits)} withdrawn claim(s) present:\n")
        for rel, line, cid, sentence, why, ctx in hits:
            print(f"  {rel}:{line}  [{cid}]")
            print(f"    protects against: {sentence}")
            print(f"    ...{ctx.strip()}...")
        print("\n  GATE FAIL — a claim this project withdrew is back in a tracked")
        print("  source. Run --list for what each term forbids and why.")
        return 1

    print(f"  scanned {sum(1 for _ in files())} files under "
          f"{', '.join(SEARCH_ROOTS)}")
    print(f"  {len(WITHDRAWN)} withdrawn claims, none present.")
    print("\n  GATE PASS — every withdrawn claim stays withdrawn, and every term")
    print("  names a claim rather than a figure.")
    return 0


#: One sentence per claim, BUILT so that this file's own specimens do not trip
#: the scan on an ordinary run -- the mistake G10's first version made, failing
#: on its own test fixture until the payload was constructed rather than spelled.
_SPECIMENS = {
    "pdf-local-only":
        "The PDF report is " + "verifiable locally only" + " on a developer machine.",
    "report-409-in-production":
        "So /report/pdf/faustini returns " + "409 in production" + ", by design.",
    "ceiling-hit-exactly":
        "Highest CPR observed is the " + "ceiling, hit exactly" + " as predicted.",
    "psr-point-sun-current":
        "| Jaccard (IoU) | " + f"{0.6732:.4f}" + " |",
    "operative-look-count-5":
        "The " + "operative" + " number for " + "everything downstream" + " is "
        "therefore N " + "= 5" + ", not 21.",
    "fabricated-base-area":
        "base_area_km2 defaults to " + f"{8.75:.2f}" + " square kilometres.",
    "psr-brightness-proxy":
        "psr_mask = (" + "illumination < 0.05" + ") over the hillshade.",
    "preregistration-conflation":
        "We pre-registered " + "1.2-1.6" + "x and the prediction held "
        + "8 of 8" + ".",
}


if __name__ == "__main__":
    raise SystemExit(main())
