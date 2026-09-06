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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the stamp instead of writing it; exit 1 if stale")
    args = ap.parse_args()

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
        print("\n  GATE PASS — every watched artifact matches its stamp.")
        return 0

    body = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", text, flags=re.S).rstrip()
    METHODS.write_text(body + "\n\n" + render(digests, head_commit()), encoding="utf-8")
    n_absent = sum(1 for v in digests.values() if v is None)
    print(f"stamped {len(digests)} artifacts into METHODS.md "
          f"({n_absent} absent) at commit {head_commit()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
