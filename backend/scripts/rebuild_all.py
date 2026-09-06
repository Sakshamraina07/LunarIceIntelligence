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
    3. incidence_audit.py           is the incidence raster an incidence angle?
    4. incidence_mask.py            the Bragg-domain criterion, or its refusal
    5. build_analysis.py            the numbers  -> public/analysis/<crater>.json
    6. render_layers.py             the pixels   -> public/layers/*.webp + layers.json
    7. detection_statistics.py      the floor and the confidence interval
    8. emit_probe_grid.py           the measured field, readable point by point
    9. emit_provenance.py           docs/PROVENANCE.md, AND the marks gate
   10. assert_paths_agree.py        the API and the static analysis, compared
   11. assert_pdf_agrees_with_analysis.py  the report vs the artifacts it renders
   12. stamp_methods.py --check     METHODS against the artifacts it quotes

FIVE OF THESE ARE GATES, NOT REPORTS, and each exits non-zero rather than
printing a warning:

  * step 6 computes the interval step 8 refuses to ship a detection area without;
  * step 8 fails if any value reaches the UI unmarked, marked MODELLED, or absent
    without a reason;
  * step 9 fails if the API and the static analysis disagree on a terrain
    quantity they both report -- they have diverged twice;
  * step 10 fails if the PDF prints a figure the artifacts do not contain -- it
    printed five deleted landing sites and an invented rover energy for months,
    because nothing checked it;
  * step 11 fails if an artifact moved after a figure was transcribed from it into
    METHODS, and names which sections to re-read.

Step 7 is here for the same reason step 5 is: it reads the same native rasters
as step 4, so leaving it out would put an older copy of the measured field under
a live map.

STEPS 1 AND 2 ARE SKIPPABLE, AND USUALLY SHOULD BE. They read multi-gigabyte
products and take minutes; steps 3-12 take seconds to a couple of minutes and are
the ones that change when the analysis changes. `--skip-ingest` runs 3-12 only.
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
                        run("1/12 · ingest_lola_polar_dem.py",
                            [py, str(SCRIPTS / "ingest_lola_polar_dem.py")])))
        timings.append(("2 · DFSAR pipeline",
                        run("2/12 · process_real_sar_pipeline.py",
                            [py, str(SCRIPTS / "process_real_sar_pipeline.py")])))

    # BEFORE the analysis, which reads its artifact to build the Bragg-domain
    # criterion row. Running it after would leave the criterion describing the
    # previous run's geometry.
    # The audit decides whether the mask may be computed at all, so it runs
    # first. It is not optional: the mask refuses without it.
    timings.append(("3 · incidence audit",
                    run("3/12 · incidence_audit.py — is the raster an incidence angle?",
                        [py, str(SCRIPTS / "incidence_audit.py")])))
    timings.append(("4 · local incidence",
                    run("4/12 · incidence_mask.py — the Bragg-domain criterion",
                        [py, str(SCRIPTS / "incidence_mask.py")])))
    timings.append(("5 · analysis",
                    run("5/12 · build_analysis.py — the numbers",
                        [py, str(SCRIPTS / "build_analysis.py"), args.crater])))
    timings.append(("6 · layers",
                    run("6/12 · render_layers.py — the pixels",
                        [py, str(SCRIPTS / "render_layers.py")])))
    # Must precede the provenance gate: that gate now REFUSES to ship a detection
    # area without its confidence interval, and this is what computes it.
    timings.append(("7 · detection statistics",
                    run("7/12 · detection_statistics.py — significance, and the CI",
                        [py, str(SCRIPTS / "detection_statistics.py")])))
    # The probe reads the SAME native rasters the analysis does, at a stated
    # decimation. If it is not rebuilt here it becomes a second, older copy of
    # the measured field sitting under a live map -- which is precisely the
    # failure mode this file exists to prevent. It runs after detection
    # statistics because it copies the floor and the look count out of them.
    timings.append(("8 · probe grid",
                    run("8/12 · emit_probe_grid.py — the measured field, point by point",
                        [py, str(SCRIPTS / "emit_probe_grid.py")])))
    # The joint screen at every threshold pair. It reads the same native arrays
    # build_analysis just read, so it runs after it and before the gates that
    # compare the two.
    timings.append(("8b · sweep grid",
                    run("8b/12 · emit_sweep_grid.py — the screen at every threshold pair",
                        [py, str(SCRIPTS / "emit_sweep_grid.py"),
                         "--crater", args.crater])))
    timings.append(("8c · sweep discriminates",
                    run("8c/12 · assert_sweep_grid_discriminates.py — G17",
                        [py, str(SCRIPTS / "assert_sweep_grid_discriminates.py"),
                         "--crater", args.crater])))
    timings.append(("9 · provenance gate",
                    run("9/12 · emit_provenance.py — docs/PROVENANCE.md, and the marks gate",
                        [py, str(SCRIPTS / "emit_provenance.py"), args.crater])))
    # The API and the static analysis compute terrain by two paths that share no
    # code, and they have diverged twice. The second time the UI was correct and
    # only the PDF was wrong, which is the worst shape for a bug to have: looking
    # at the app does not reveal it.
    timings.append(("10 · cross-path gate",
                    run("10/12 · assert_paths_agree.py — API vs static analysis",
                        [py, str(SCRIPTS / "assert_paths_agree.py"),
                         "--crater", args.crater])))
    # The report is a rendering of the artifacts just rebuilt, so it is checked
    # against them here rather than at tag time.
    timings.append(("11 · PDF vs analysis",
                    run("11/12 · assert_pdf_agrees_with_analysis.py — the report's figures",
                        [py, str(SCRIPTS / "assert_pdf_agrees_with_analysis.py"),
                         "--crater", args.crater])))
    timings.append(("12 · METHODS staleness",
                    run("12/12 · stamp_methods.py --check — METHODS vs its artifacts",
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
