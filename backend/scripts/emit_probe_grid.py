"""
emit_probe_grid.py -- the numbers behind the map, readable at any point.

    python -u backend/scripts/emit_probe_grid.py [--decimate 8]

WHY THIS EXISTS
---------------
The Ice Criteria screen asserts a verdict -- 0.00 km2 -- and shows the criteria
that produced it, but there was no way to point at a place and ask what the
criteria say THERE. That is the difference between a conclusion and an
instrument, and a reader should be able to check the conclusion anywhere.

WHAT IT IS NOT
--------------
IT IS NOT A PREDICTOR AND THERE IS NOTHING TO PREDICT. Candidate area in this
frame is 0.0000 km2 and METHODS 1 proves that screen is empty BY CONSTRUCTION:
with CPR from amplitude alone, DOP < 0.13 caps CPR at 0.0042610, so no pixel can
satisfy both criteria whatever the terrain. A tool that output "ice is here"
would be inventing the one number this project exists not to invent.

What this emits is the MEASURED VALUE AT EVERY POINT, so the emptiness can be
inspected rather than taken on trust.

DECIMATION IS STATED, NOT HIDDEN
--------------------------------
The native field is 2258 x 6618 float32 -- 60 MB per channel, which no browser
should fetch. This block-MEANS by `--decimate` (default 8, so 200 m cells) and
says so in the header and in the readout. A probe reporting a block mean while
implying a pixel value would be a caption that stopped tracking its own
computation.

Channels are packed little-endian float32, row-major, in the order named by
`channels` in the JSON header. NaN marks a cell with no measured radar -- an
absent state, not a zero.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

NATIVE = BASE_DIR / "data" / "pradan" / "native"
LOLA_DIR = BASE_DIR / "data" / "pradan" / "lola"
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT_BIN = BASE_DIR / "frontend" / "public" / "analysis" / "probe_grid.bin"
OUT_HDR = BASE_DIR / "frontend" / "public" / "analysis" / "probe_grid.json"


def block_mean(a: np.ndarray, k: int, mask: np.ndarray | None = None) -> np.ndarray:
    """Mean over k x k blocks. Where `mask` is given, the mean is over MASKED
    pixels only and a block with none returns NaN -- so a cell outside the
    amplitude ribbon reads as ABSENT rather than as a zero averaged in."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    rs = lambda x: x[:h, :w].reshape(h // k, k, w // k, k)
    if mask is None:
        return rs(a.astype(np.float64)).mean(axis=(1, 3)).astype(np.float32)
    m = rs(mask.astype(np.float64))
    s = rs(np.where(mask, a, 0.0).astype(np.float64))
    n = m.sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(n > 0, s.sum(axis=(1, 3)) / np.maximum(n, 1), np.nan)
    return out.astype(np.float32)


def main() -> int:
    from app.core.config import settings as cfg
    from app.ingestion.horizon_frame import load_horizon
    from app.ingestion.sar_geometry import read_geotiff_frame

    ap = argparse.ArgumentParser()
    ap.add_argument("--decimate", type=int, default=8)
    args = ap.parse_args()
    k = max(1, args.decimate)

    cpr = np.asarray(tifffile.imread(str(NATIVE / "cpr_native.tif")), dtype=np.float32)
    dop = np.asarray(tifffile.imread(str(NATIVE / "dop_native.tif")), dtype=np.float32)
    valid = np.asarray(tifffile.imread(str(NATIVE / "valid_native.tif"))) > 0
    fp = np.asarray(tifffile.imread(str(NATIVE / "footprint_native.tif"))) > 0
    dem = np.asarray(tifffile.imread(str(NATIVE / "dem_native.tif")), dtype=np.float32)

    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    hp = load_horizon(LOLA_DIR)
    proj = hp.to_frame(frame, cpr.shape)
    illum = np.nan_to_num(proj["illumination_fraction"], nan=0.0).astype(np.float32)
    psr = proj["psr_mask"]

    print("=" * 78)
    print("PROBE GRID — the measured values, readable at any point on the map")
    print("=" * 78)
    print(f"  native {cpr.shape[0]} x {cpr.shape[1]} at 25 m")
    print(f"  decimate {k}x  ->  cells of {25 * k:g} m, STATED in the header and")
    print(f"  in the readout, because a probe reporting a block mean while implying")
    print(f"  a pixel value would be a caption that stopped tracking its computation.\n")

    ch = {
        # CPR and DOP are averaged over MEASURED pixels only. A block with no
        # radar returns NaN: absent, not zero.
        "cpr": block_mean(cpr, k, valid),
        "dop": block_mean(dop, k, valid),
        # Coverage fractions, so the probe can say WHICH of the three states a
        # place is in: measured, pointed-at but silent, or never observed.
        "amplitude_fraction": block_mean(valid.astype(np.float32), k),
        "pointed_fraction": block_mean(fp.astype(np.float32), k),
        "psr_fraction": block_mean(psr.astype(np.float32), k),
        "illumination": block_mean(illum, k),
        "elevation_m": block_mean(dem, k),
    }
    names = list(ch)
    ny, nx = ch["cpr"].shape
    buf = np.stack([ch[n] for n in names]).astype("<f4")
    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BIN.write_bytes(buf.tobytes(order="C"))

    n_meas = int(np.isfinite(ch["cpr"]).sum())
    print(f"  {len(names)} channels x {ny} x {nx} = {buf.nbytes / 1e6:.2f} MB")
    print(f"  cells with measured radar: {n_meas:,} of {ny * nx:,} "
          f"({100 * n_meas / (ny * nx):.2f} %)")
    for n in names:
        a = ch[n]
        f = np.isfinite(a)
        print(f"    {n:20s} min {np.nanmin(a):>12.5g}  max {np.nanmax(a):>12.5g}  "
              f"finite {f.mean() * 100:5.1f} %")

    ds = json.loads((BASE_DIR / "docs" / "detection_statistics.json")
                    .read_text(encoding="utf-8"))
    hdr = {
        "schema": "probe_grid/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/emit_probe_grid.py",
        "shape": [ny, nx], "channels": names, "dtype": "float32-le",
        "decimation": k, "cell_metres": 25.0 * k,
        "native_metres": 25.0, "native_shape": list(cpr.shape),
        "nan_means": "no measured radar in this cell — an absent state, not a zero",
        "decimation_note": (f"Every value is the MEAN over a {k}x{k} block of 25 m "
                            f"pixels ({25.0 * k:g} m cell), taken over measured pixels "
                            f"only. It is not a pixel value and the readout says so."),
        "thresholds": {"cpr": float(cfg.CPR_THRESHOLD), "dop": float(cfg.DOP_THRESHOLD)},
        # The closed-form cap, recomputed here from the CONFIGURED DOP threshold
        # rather than pasted as 0.0042610. If anyone moves DOP_THRESHOLD the
        # probe's ceiling moves with it; a literal would keep quoting the old
        # bound beside the new gate and look like it had been checked.
        #   CPR_amp = tanh^2(x/4), DOP_amp = |tanh(x/2)|, x = ln(LH/LV)
        #   => DOP < d caps CPR at tanh^2(artanh(d)/2).   METHODS section 1.
        "algebraic_ceiling": {
            "cpr_cap": float(np.tanh(np.arctanh(cfg.DOP_THRESHOLD) / 2.0) ** 2),
            "under_dop_below": float(cfg.DOP_THRESHOLD),
            "identity": "CPR_amp = tanh^2(x/4), DOP_amp = |tanh(x/2)|, x = ln(LH/LV)",
            "note": ("One degree of freedom, not two. The screening rule pushes |x| "
                     "up and down on the same axis, so satisfying DOP bounds CPR "
                     "from above and the pass set is empty for any terrain."),
            "source": "METHODS.md section 1",
        },
        "not_a_predictor": (
            "This is a readout of MEASURED values, not a prediction of where ice is. "
            "Candidate area in this frame is 0.0000 km2 and the screen is empty BY "
            "CONSTRUCTION: with CPR from amplitude alone, DOP < 0.13 caps CPR at "
            "0.0042610, so no pixel can satisfy both criteria whatever the terrain. "
            "See METHODS.md section 1."),
        # READ, NOT RESTATED. The floor and the look count belong to Phase 8 and
        # are copied out of its artifact, so the probe cannot drift away from the
        # table that produced them -- METHODS section 0, first pattern.
        "detection_floor": {
            "value": ds["per_pixel_significance"]["floor_at_low_N"],
            "confidence": ds["per_pixel_significance"]["confidence"],
            "looks": ds["effective_looks"]["screened_field"]["lh"],
            "source": "docs/detection_statistics.json :: per_pixel_significance",
            "note": ("A single pixel must read above this to be significantly above "
                     f"the CPR threshold of {ds['per_pixel_significance']['threshold']} "
                     f"at the measured look count "
                     f"(N = {ds['effective_looks']['screened_field']['lh']}). "
                     "METHODS.md section 11.1."),
            "caveat": ds["per_pixel_significance"]["caveat"],
        },
        "candidate_area": {
            "area_km2": ds["candidate_area"]["area_km2"],
            "ci_km2": ds["candidate_area"]["ci_km2"],
            "confidence": ds["candidate_area"]["confidence"],
            "method": ds["candidate_area"]["method"],
        },
    }
    OUT_HDR.write_text(json.dumps(hdr, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT_BIN.relative_to(BASE_DIR)}")
    print(f"  wrote {OUT_HDR.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
