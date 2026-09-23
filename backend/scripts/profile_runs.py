"""
profile_runs.py -- wall time and peak memory of the major analyses. (M16)

    python backend/scripts/profile_runs.py [--only NAME ...]

Each analysis runs in a FRESH Python process, through runpy, exactly as its
own command line would run it; when it returns, the same process reports its
wall time and peak working set (runinfo.py: GetProcessMemoryInfo on Windows,
ru_maxrss elsewhere). Running an analysis regenerates its artifact with its
recorded seed, so the artifact is unchanged apart from its timestamp.

The analyses that already record their own run_info (the third-review
scripts) are read from their artifacts rather than re-run; the two longest
(enl_benchmark.py, enl_interval_validation.py) are listed with the figure
their own run recorded, or marked not re-measured.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "runtime_profile.json"

#: (name, script, argv) -- re-run here
RUN = [
    ("process_real_sar_pipeline", "backend/scripts/process_real_sar_pipeline.py", []),
    ("detection_statistics", "backend/scripts/detection_statistics.py", []),
    ("dop_exclusion", "backend/scripts/dop_exclusion.py", []),
    ("bootstrap_enl", "backend/scripts/bootstrap_enl.py", []),
    ("slc_multilook_control", "backend/scripts/slc_multilook_control.py", ["--windows", "9"]),
    ("mechanism_controls", "backend/scripts/mechanism_controls.py", []),
]
#: (name, artifact) -- their own run recorded run_info
RECORDED = [
    ("stokes_from_slc", "docs/stokes_from_slc.json"),
    ("phase_gain_perturbation (same run)", "docs/phase_gain_perturbation.json"),
    ("dop_sampling_bias", "docs/dop_sampling_bias.json"),
    ("dop_sampling_bias -> joint_calibration", "docs/joint_calibration.json"),
    ("calibration_example", "docs/calibration_example.json"),
    ("enl_interval_validation", "docs/enl_interval_validation.json"),
    ("mechanism_spec", "docs/mechanism_spec.json"),
    ("enl_generality_full", "docs/enl_L_20200305_full.json"),
    ("enl_benchmark (not re-run; hours at 200 replicates x B = 2000)", "docs/enl_benchmark.json"),
    ("f2_maximum", "docs/f2_maximum.json"),
]

WRAP = r"""
import json, runpy, sys
sys.path.insert(0, r"{scripts}")
sys.argv = {argv!r}
import runinfo
rc = 0
try:
    runpy.run_path(r"{script}", run_name="__main__")
except SystemExit as e:
    rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
print("@@RUNINFO@@" + json.dumps({{**runinfo.run_info(), "exit": rc}}))
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    rows = []
    for name, script, argv in RUN:
        if args.only and name not in args.only:
            continue
        code = WRAP.format(scripts=str(BASE_DIR / "backend" / "scripts"),
                           script=str(BASE_DIR / script), argv=[script] + argv)
        print(f"  running {name} ...", flush=True)
        p = subprocess.run([sys.executable, "-c", code], cwd=BASE_DIR, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        line = [ln for ln in p.stdout.splitlines() if ln.startswith("@@RUNINFO@@")]
        info = json.loads(line[-1][len("@@RUNINFO@@"):]) if line else {"error": p.stderr[-400:]}
        rows.append({"analysis": name, "command": " ".join(["python", script] + argv),
                     "measured_here": True, **info})
        print(f"    wall {info.get('wall_s')} s, peak {info.get('peak_rss_mb')} MB, "
              f"exit {info.get('exit')}", flush=True)
    for name, art in RECORDED:
        p = BASE_DIR / art
        info = None
        if p.is_file():
            info = json.loads(p.read_text(encoding="utf-8")).get("run_info")
        rows.append({"analysis": name, "artifact": art, "measured_here": False,
                     **(info or {"note": "not re-run in this pass; the artifact records "
                                         "no run_info"})})
    OUT.write_text(json.dumps({
        "schema": "lunar-ice/runtime-profile/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/profile_runs.py",
        "method": ("each analysis in a fresh process via runpy; wall time from process "
                   "start, peak working set from the operating system (runinfo.py)"),
        "rows": rows}, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
