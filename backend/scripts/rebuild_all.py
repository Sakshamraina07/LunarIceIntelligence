"""
rebuild_all.py -- regenerate the imagery and the numbers in ONE command.

    python backend/scripts/rebuild_all.py [--crater faustini] [--skip-ingest]

WHY THIS EXISTS (PRD section 3)
-------------------------------
The map and the stat panel are produced by different scripts reading the same
rasters. Run one without the other and they describe different data -- which is
exactly what happened once already: `render_layers.py` was changed to call
`module_d_terrain.compute_hazard_score` while the layer caption in `config.ts`
still described the 0.6/0.4 blend it used to have, so the picture and the number
disagreed and nothing failed.

So the ordering is expressed here rather than in a reviewer's memory:

    1. ingest_lola_polar_dem.py     LOLA polar DEM -> this frame's 25 m grid
    2. process_real_sar_pipeline.py DFSAR L2 -> native cpr / dop / valid / footprint
    3. build_analysis.py            the numbers  -> public/analysis/<crater>.json
    4. render_layers.py             the pixels   -> public/layers/*.webp + layers.json
    5. emit_provenance.py           docs/PROVENANCE.md, AND the marks gate

Step 5 is a GATE, not a report. It exits non-zero if any value reaches the UI
unmarked, if any value is marked MODELLED, or if an absent value carries no
reason -- so a rebuild that would have shipped an unlabelled number fails here
instead of on screen.

STEPS 1 AND 2 ARE SKIPPABLE, AND USUALLY SHOULD BE. They read multi-gigabyte
products and take minutes; steps 3-5 take seconds and are the ones that change
when the analysis changes. `--skip-ingest` runs 3-5 only.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
# ── console encoding ────────────────────────────────────────────────────────
# The Windows console is cp1252 by default, and a single unencodable character
# in a progress line raises UnicodeEncodeError and kills a 30-minute run at
# minute 28. Reconfiguring here rather than relying on PYTHONIOENCODING means it
# cannot be forgotten by whoever launches the script. errors="replace" because a
# diagnostic print must never be the thing that fails a computation.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SCRIPTS = Path(__file__).resolve().parent


def run(label: str, argv: list[str]) -> float:
    """Run one stage. A non-zero exit stops the whole rebuild."""
    print("\n" + "=" * 78)
    print(f"  {label}")
    print(f"  $ {' '.join(argv)}")
    print("=" * 78, flush=True)
    t0 = time.time()
    proc = subprocess.run(argv, cwd=str(BASE_DIR))
    dt = time.time() - t0
    if proc.returncode != 0:
        raise SystemExit(
            f"\nREBUILD ABORTED at '{label}' (exit {proc.returncode}) after {dt:.1f}s.\n"
            "Nothing downstream has run, so the analysis and the layers on disk are "
            "still the consistent pair the previous rebuild produced."
        )
    print(f"\n  -- {label} ok ({dt:.1f}s)")
    return dt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--crater", default="faustini",
                    help="crater id to build the analysis for (default: faustini)")
    ap.add_argument("--skip-ingest", action="store_true",
                    help="skip the two raster-ingest stages; rebuild only the "
                         "analysis, the layers and the provenance document")
    args = ap.parse_args()

    py = sys.executable
    timings: list[tuple[str, float]] = []

    if args.skip_ingest:
        print("  --skip-ingest: stages 1 and 2 not run. The native rasters on disk "
              "are reused as-is.")
    else:
        timings.append(("1 · LOLA ingest",
                        run("1/5 · ingest_lola_polar_dem.py",
                            [py, str(SCRIPTS / "ingest_lola_polar_dem.py")])))
        timings.append(("2 · DFSAR pipeline",
                        run("2/5 · process_real_sar_pipeline.py",
                            [py, str(SCRIPTS / "process_real_sar_pipeline.py")])))

    timings.append(("3 · analysis",
                    run("3/5 · build_analysis.py — the numbers",
                        [py, str(SCRIPTS / "build_analysis.py"), args.crater])))
    timings.append(("4 · layers",
                    run("4/5 · render_layers.py — the pixels",
                        [py, str(SCRIPTS / "render_layers.py")])))
    timings.append(("5 · provenance gate",
                    run("5/6 · emit_provenance.py — docs/PROVENANCE.md, and the marks gate",
                        [py, str(SCRIPTS / "emit_provenance.py"), args.crater])))
    # The API and the static analysis compute terrain by two paths that share no
    # code, and they have diverged twice. The second time the UI was correct and
    # only the PDF was wrong, which is the worst shape for a bug to have: looking
    # at the app does not reveal it.
    timings.append(("6 · cross-path gate",
                    run("6/7 · assert_paths_agree.py — API vs static analysis",
                        [py, str(SCRIPTS / "assert_paths_agree.py"),
                         "--crater", args.crater])))
    timings.append(("7 · METHODS staleness",
                    run("7/7 · stamp_methods.py --check — METHODS vs its artifacts",
                        [py, str(SCRIPTS / "stamp_methods.py"), "--check"])))

    print("\n" + "=" * 78)
    print("  REBUILD COMPLETE — the imagery and the numbers describe the same data")
    print("=" * 78)
    for label, dt in timings:
        print(f"    {label:24s} {dt:7.1f}s")
    print(f"\n    analysis   frontend/public/analysis/{args.crater}.json")
    print( "    layers     frontend/public/layers/")
    print( "    provenance docs/PROVENANCE.md")
    print( "\n  Next: node frontend/scripts/verify_v8_view.mjs  (needs the dev server up)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
