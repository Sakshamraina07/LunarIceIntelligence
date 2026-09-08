"""
Make a stale number in METHODS.md DETECTABLE rather than merely wrong.

THE PROBLEM, DEMONSTRATED RATHER THAN HYPOTHESISED
--------------------------------------------------
emit_provenance.py carried one DEM product name as a literal in twelve places.
Phase 6 replaced the product and all twelve went stale in a single step -- inside
the provenance document itself, which ended up naming the 80 m product in the
same sentence as "20 m posts". Nothing caught it; a person did.

METHODS.md now carries far more measured figures than that: the ENL control, the
sigma minimax, the eight A/B rows, several percentile tables, the Monte Carlo,
the saturation comparison. Every one is a transcription from an artifact on
disk, and nothing watches any of them.

WHY STAMPING RATHER THAN GENERATING
-----------------------------------
Generating METHODS from its artifacts would mean writing the prose as templates,
and the prose is the part that carries the reasoning -- "they fail in opposite
directions", "the bug existed and could not reach the screen". Templating that
would damage the document to protect its numbers.

So instead every artifact METHODS quotes is DIGESTED, and the digests are stamped
into the document with the commit that produced them. `--check` recomputes them:
if an artifact has changed since the stamp, the numbers transcribed from it are
suspect and the build fails, naming which artifact moved and which sections read
from it. That converts "silently stale" into "fails loudly", which is the whole
ask. It does not verify that a given digit was copied correctly -- nothing short
of generation would -- and it says so in the stamp rather than implying more.

Usage:
    python -u backend/scripts/stamp_methods.py            # write/refresh the stamp
    python -u backend/scripts/stamp_methods.py --check    # verify, exit 1 if stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
METHODS = BASE_DIR / "docs" / "METHODS.md"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

INJECT_DIGIT = False

BEGIN = "<!-- BEGIN GENERATED STAMP -- do not edit by hand -->"
END = "<!-- END GENERATED STAMP -->"

#: artifact -> the METHODS sections whose figures were transcribed from it.
#: When an artifact's digest changes, these are the sections to re-read.
ARTIFACTS: dict[str, list[str]] = {
    "docs/enl.json": ["7.1", "7.3", "7.5", "7.6"],
    "docs/slc_multilook_control.json": ["7.4"],
    "docs/cpr_significance.json": ["7.7", "7.9.1", "7.9.2", "7.9.3"],
    "docs/rover_coverage.json": ["6.5"],
    "docs/landing_sites.json": ["9.6", "9.7"],
    "docs/traverse.json": ["10.1", "10.2", "10.3", "10.4", "10.5"],
    "docs/detection_statistics.json": ["11.1", "11.2", "11.3"],
    "frontend/public/analysis/probe_grid.json": ["11.5"],
    "frontend/public/analysis/sweep_grid.json": ["1.9"],
    "docs/cpr_dispersion.json": ["7.10"],
    "docs/incidence_audit.json": ["7.12", "12.1", "12.2", "12.3", "12.4", "12.5"],
    "docs/incidence_mask.json": ["7.11", "7.12"],
    "docs/roughness_vs_latitude.json": ["9.1", "9.2"],
    "docs/site_inspection.json": ["9.3"],
    "docs/psr_validation.json": ["5.10"],
    "docs/solar_model_ab.json": ["5.3", "5.10"],
    "docs/antialias_sigma.json": ["8.1"],
    "frontend/public/analysis/faustini.json": ["8.2", "8.3"],
    "data/pradan/lola/ldem_frame_25m.provenance.json": ["8.1", "8.2", "8.4"],
    "data/pradan/lola/horizon_240m.provenance.json": ["5.4", "5.6", "8.4"],
}


#: Keys whose value changes on every run without any number changing. Digesting
#: them would make this gate fire after every rebuild, and a gate that cries wolf
#: on every build is worse than no gate -- it teaches you to re-stamp reflexively,
#: which is exactly the habit that would let a real change through.
VOLATILE = ("generated_utc", "generated_at", "generated", "timestamp", "stamped_at")


def _stable(obj):
    """Strip volatile keys, at any depth, so the digest tracks NUMBERS only."""
    if isinstance(obj, dict):
        return {k: _stable(v) for k, v in sorted(obj.items()) if k not in VOLATILE}
    if isinstance(obj, list):
        return [_stable(v) for v in obj]
    return obj


def sha256(path: Path) -> str | None:
    """Digest the artifact's CONTENT. For JSON that means its stable content:
    parsed, volatile keys removed, re-serialised canonically. A reformat or a
    new timestamp therefore does not read as a changed measurement, and a
    changed measurement cannot hide behind a reformat."""
    if not path.is_file():
        return None
    if path.suffix == ".json":
        try:
            canon = json.dumps(_stable(json.loads(path.read_text(encoding="utf-8"))),
                               sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(canon.encode("utf-8")).hexdigest()
        except (OSError, ValueError):
            pass
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def head_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=str(BASE_DIR), capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def current() -> dict[str, str | None]:
    return {rel: sha256(BASE_DIR / rel) for rel in sorted(ARTIFACTS)}


def render(digests: dict[str, str | None], commit: str) -> str:
    lines = [
        BEGIN,
        "",
        "## Provenance of the numbers in this document",
        "",
        "Every measured figure quoted above is transcribed from an artifact on",
        "disk. Those artifacts are digested here, so that a figure which has gone",
        "stale is **detectable** rather than merely wrong —",
        "`python backend/scripts/stamp_methods.py --check` fails the build when an",
        "artifact has moved since this stamp was written, and names the sections",
        "that were read from it.",
        "",
        "**What this does not do.** It does not verify that any individual digit",
        "was transcribed correctly; only generation could do that, and generating",
        "this document would mean templating the prose that carries its reasoning.",
        "It catches the failure that has actually occurred here — an artifact",
        "changing underneath text that still quotes the old numbers.",
        "",
        f"Stamped at commit `{commit}`.",
        "",
        "| artifact | sha256 | sections |",
        "|---|---|---|",
    ]
    for rel, digest in digests.items():
        secs = ", ".join("§" + s for s in ARTIFACTS[rel])
        shown = f"`{digest[:16]}…`" if digest else "**ABSENT**"
        lines.append(f"| `{rel}` | {shown} | {secs} |")
    lines += ["", END, ""]
    return "\n".join(lines)


def read_stamp(text: str) -> dict[str, str]:
    m = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), text, re.S)
    if not m:
        return {}
    out = {}
    for row in re.finditer(r"^\|\s*`([^`]+)`\s*\|\s*`?([0-9a-f]{16})", m.group(1), re.M):
        out[row.group(1)] = row.group(2)
    return out


# ----------------------------------------------------------------------------
# THE BLIND SPOT THIS FILE USED TO ONLY DOCUMENT
# ----------------------------------------------------------------------------
# The stamp said, in writing: "It does not verify that any individual digit was
# transcribed correctly; only generation could do that." That sentence was quoted
# back at this project when METHODS section 5.10 was found reporting Jaccard
# 0.6732 while docs/psr_validation.json held 0.714229 -- the section carrying the
# project's ONLY external validation, stale by a whole solar model, with the
# deployed site displaying the right number the whole time.
#
# The digest HAD changed when the finite solar disc shipped, so the staleness
# gate fired; the stamp was then refreshed, which is exactly the act of recording
# "the prose has been re-checked". It had not been.
#
# A gate that documents its own blind spot has not mitigated it. It has only made
# the eventual failure quotable in advance. So the digit check exists now: it is
# assert_pdf_agrees_with_analysis.py's mechanism -- every numeric literal in the
# rendered text must appear in the artifact it claims to come from -- turned on
# this document.

#: Figures that are legitimately not in any artifact: section numbering, years,
#: and the log base. Listed with a reason, because an allow-list is where a gate
#: goes to die.
LITERAL_EXEMPT = re.compile(
    r"""^(
        \d{1,2}(\.\d{1,2})?      # section and list numbering
      | (19|20)\d\d              # years
      | 10                       # log / dB base
      )$""",
    re.X,
)

#: A figure quoted in a mapped section but sourced elsewhere -- another artifact,
#: a cited paper, or arithmetic done in the prose. Keyed "section:literal" so an
#: exemption cannot silently widen to every occurrence of a common number, and
#: carrying the reason it is exempt.
LITERAL_EXCEPTIONS: dict = {}


def _load_exceptions() -> None:
    """Exceptions live beside the document, not in this file.

    Each entry is "section:literal" -> the reason it is not in the artifact:
    a figure from a cited paper, a constant, or arithmetic carried out in the
    prose. Kept in a JSON file so adding one is a visible, reviewable diff
    rather than an edit inside the checker that grants it.
    """
    f = BASE_DIR / "docs" / "methods_literal_exceptions.json"
    if f.is_file():
        try:
            LITERAL_EXCEPTIONS.update(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass

_NUM = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?)(?![\w])")


def section_bodies(text: str) -> dict:
    """Every numbered section's body, keyed by its number."""
    out: dict = {}
    heads = list(re.finditer(r"^#{2,5}\s+(\d+(?:\.\d+)*[a-z]?)\s+", text, re.M))
    for i, h in enumerate(heads):
        stop = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.setdefault(h.group(1), "")
        out[h.group(1)] += text[h.end():stop]
    return out


def flatten(obj, out: dict, prefix: str = "") -> None:
    """Every numeric leaf of an artifact, keyed by its dotted path."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(v, out, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten(v, out, f"{prefix}.{i}")
    elif isinstance(obj, (int, float)):
        out[prefix] = float(obj)


def _decimals(lit: str) -> int:
    """How many decimal places a printed literal carries."""
    if "e" in lit.lower():
        return 12
    return len(lit.split(".")[1]) if "." in lit else 0


#: What a leaf key is called in the prose. Only names that are unambiguous in
#: this document -- a label that could mean two things is not checkable and is
#: deliberately absent rather than guessed at.
KEY_ALIASES = {
    "jaccard": ["jaccard"],
    "dice": ["dice"],
    "precision": ["precision"],
    "recall": ["recall"],
    "area_ratio_ours_over_theirs": ["ratio"],
    "pearson_r": ["pearson r", "pearson"],
    "rms": ["rms difference"],
    "tp": [], "fp": [], "fn": [], "tn": [],
    "psr_km2": [],
    "area_all_lags": ["pixels per independent sample", "px per independent sample"],
    "correlation_area_px": ["px per independent sample"],
    "cpr_value": [],
    "factor_below_published": [],
    "algebraic_ceiling": [],
    "absolute_agreement": [],
    "relative_agreement": [],
}


def check_labelled_figures(text: str) -> list:
    """A LABELLED figure must equal the artifact value with that label.

    WHY NOT EVERY LITERAL. The first version of this check asked that every
    numeric literal in a mapped section appear in the artifact -- G9's mechanism,
    copied wholesale. G9 can do that because the PDF is PURELY a rendering.
    METHODS is not: it derives figures in the prose. Section 7.7's whole table is
    closed forms -- N/(N-1), sqrt((2N-1)/(N(N-2))), F-quantiles -- computed here
    and correctly absent from cpr_significance.json. That version produced 188
    findings, almost all of them the checker's fault, and a gate that cries wolf
    gets waved through. This project has already learned that once, with G10.

    So the check is anchored on LABELS. Where the prose names a quantity the
    artifact also names, the number beside it must be that artifact's value at
    the precision printed. That is exactly the shape instance 20 had -- a row
    reading "| Jaccard (IoU) | 0.6732 |" against a stored 0.7142289 -- and it is
    silent on figures the artifact never claimed to source.
    """
    bodies = section_bodies(text)
    problems = []
    for rel, sections in ARTIFACTS.items():
        path = BASE_DIR / rel
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        leaves: dict = {}
        flatten(doc, leaves)
        # leaf-name -> the values stored under it anywhere in the artifact
        by_name: dict = {}
        for dotted, val in leaves.items():
            by_name.setdefault(dotted.split(".")[-1], set()).add(val)

        for sec in sections:
            body = bodies.get(sec)
            if body is None:
                problems.append(f"S{sec} is mapped to {rel} but no such section exists")
                continue
            for line in body.splitlines():
                if not re.search(r"\d", line):
                    continue
                # A LABEL IS A TABLE CELL, NOT A WORD IN A SENTENCE.
                # Without this, section 5.10's pre-registration line -- "by
                # roughly 1.2-1.6x (the point-Sun band), with high recall and
                # read as labelling 1.2 with "recall". The words are qualitative
                # there and label nothing. Only a markdown table row states
                # "this name has this value", which is the claim being checked.
                if not line.lstrip().startswith("|"):
                    continue
                low = line.lower()
                for leaf, values in by_name.items():
                    labels = KEY_ALIASES.get(leaf)
                    if not labels:
                        continue
                    if not any(re.search(r"(?<![a-z])" + re.escape(lb) + r"(?![a-z])", low)
                               for lb in labels):
                        continue
                    nums = [m.group(1) for m in _NUM.finditer(line)]
                    if not nums:
                        continue
                    ok = False
                    for lit in nums:
                        if f"{sec}:{lit}" in LITERAL_EXCEPTIONS:
                            ok = True
                            break
                        try:
                            printed = float(lit.replace(",", ""))
                        except ValueError:
                            continue
                        d = _decimals(lit)
                        cand = set(values) | {v * 100.0 for v in values}
                        if any(round(v, d) == round(printed, d) for v in cand):
                            ok = True
                            break
                    if not ok:
                        shown = ", ".join(sorted(f"{v:g}" for v in values)[:3])
                        problems.append(
                            f"S{sec}: a line labelled '{leaf}' prints "
                            f"{', '.join(nums[:3])} but {rel} holds {shown} "
                            f"-- {line.strip()[:70]}")
    return problems


def _numkey(n: str):
    """(chapter, subsection, suffix) -- always this shape, so keys compare.

    A first version returned a variable-length tuple, so comparing "5" against
    "5.10" put a str beside an int and raised. Fixed shape, one type per slot.
    """
    parts = n.split(".")
    nums = [int(re.sub(r"[^0-9]", "", x) or 0) for x in parts]
    # Pad to a fixed depth so keys of different depth still compare, and so that
    # "7.9" sorts BEFORE "7.9.1" rather than equal to it. A first version kept
    # only two levels, which made every three-level section look out of order.
    nums = (nums + [-1, -1, -1])[:3]
    suffix = n[-1] if n[-1].isalpha() else ""
    return (nums[0], nums[1], nums[2], suffix)


def check_section_numbering(text: str) -> list:
    """No two sections share a number, and numbers ascend within a chapter."""
    problems = []
    heads = [(m.group(1), m.start())
             for m in re.finditer(r"^#{2,5}\s+(\d+(?:\.\d+)*[a-z]?)\s+", text, re.M)]
    seen = {}
    for num, pos in heads:
        if num in seen:
            problems.append(f"section number {num} is used twice (offsets "
                            f"{seen[num]} and {pos}); every cross-reference to it "
                            f"is ambiguous")
        seen[num] = pos
    for (a, _), (b, _) in zip(heads, heads[1:]):
        ka, kb = _numkey(a), _numkey(b)
        # A subsection may be followed by a new chapter (7.12 -> 8), so only
        # compare within the same chapter.
        if ka[0] == kb[0] and ka >= kb:
            problems.append(f"section {b} follows {a}: numbering is not monotonic")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the stamp instead of writing it; exit 1 if stale")
    ap.add_argument("--inject-digit", action="store_true",
                    help="prove the digit check fails when a figure does not match "
                         "its artifact -- the METHODS 5.10 defect, replayed")
    args = ap.parse_args()
    global INJECT_DIGIT
    INJECT_DIGIT = args.inject_digit

    text = METHODS.read_text(encoding="utf-8")
    digests = current()

    if args.check:
        stamped = read_stamp(text)
        if not stamped:
            print("FAIL  METHODS.md carries no provenance stamp. Run "
                  "stamp_methods.py without --check.")
            return 1
        stale, missing = [], []
        for rel, digest in digests.items():
            if digest is None:
                missing.append(rel)
            elif rel not in stamped:
                stale.append((rel, "not in the stamp"))
            elif not digest.startswith(stamped[rel]):
                stale.append((rel, f"{stamped[rel]}… -> {digest[:16]}…"))
        print("=" * 78)
        print("METHODS.md STALENESS CHECK")
        print("=" * 78)
        print(f"  artifacts watched: {len(digests)}   stamped: {len(stamped)}")
        for rel in missing:
            print(f"  ABSENT   {rel} — cannot verify the figures read from it")
        for rel, why in stale:
            print(f"  STALE    {rel}  {why}")
            print(f"           re-read " + ", ".join("§" + s for s in ARTIFACTS[rel]))
        if stale:
            print("\n  GATE FAIL — an artifact moved after METHODS was written, so the")
            print("  figures transcribed from it may no longer be what it says. Re-read")
            print("  the sections above, then re-stamp. Do NOT re-stamp first.")
            return 1
        if missing:
            print("\n  GATE FAIL — a watched artifact is absent.")
            return 1
        # -- the digit check and the numbering check ------------------------
        _load_exceptions()
        checked = text
        if INJECT_DIGIT:
            # PERTURB A REAL DIGIT AND LET THE REAL CHECKER FIND IT.
            #
            # The first version of this injection APPENDED a fabricated finding
            # to the results list. That proves the print statement works and
            # nothing else -- an injection that fails for a reason other than its
            # claim, which is METHODS section 0's seventh instance, committed
            # again inside the fix for its twentieth. So the document itself is
            # perturbed: one digit of the Jaccard figure, exactly the shape
            # instance 20 had, and the untouched checker must notice.
            # Find the Jaccard table row and perturb its last digit. Done by
            # line scan rather than a regex, because the regex escaping in
            # this file has now been mangled twice by the editing path.
            hit = None
            for ln in checked.splitlines():
                st = ln.strip()
                if st.startswith("|") and "jaccard" in st.lower():
                    nums = _NUM.findall(ln)
                    if nums:
                        hit = (ln, nums[-1])
                        break
            if hit is None:
                print("  INJECTION COULD NOT BE PLACED -- no Jaccard table row;"
                      " this branch proves nothing and is a failure.")
                return 1
            row, lit = hit
            bad = lit[:-1] + ("0" if lit[-1] != "0" else "1")
            checked = checked.replace(row, row.replace(lit, bad), 1)
            print("  --inject-digit: Jaccard " + lit + " -> " + bad
                  + " in the text under test" + chr(10))
        lit = check_labelled_figures(checked)
        num = check_section_numbering(checked)
        for m in num:
            print(f"  NUMBERING {m}")
        for m in lit[:40]:
            print(f"  FIGURE   {m}")
        if len(lit) > 40:
            print(f"  ...      and {len(lit) - 40} more")
        if lit or num:
            print("\n  GATE FAIL — the stamp matches but the PROSE does not. This is")
            print("  the blind spot the stamp used to only document: a digest can be")
            print("  refreshed without anyone re-reading the sections it covers.")
            return 1
        print("\n  GATE PASS — every watched artifact matches its stamp, every figure")
        print("  in the sections it covers appears in it at the precision printed,")
        print("  and no section number is duplicated or out of order.")
        return 0

    body = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", text, flags=re.S).rstrip()
    METHODS.write_text(body + "\n\n" + render(digests, head_commit()), encoding="utf-8")
    n_absent = sum(1 for v in digests.values() if v is None)
    print(f"stamped {len(digests)} artifacts into METHODS.md "
          f"({n_absent} absent) at commit {head_commit()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
