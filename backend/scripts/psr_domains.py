"""
psr_domains.py -- every PSR area this project can quote, with its denominator.

WHY THIS EXISTS
---------------
The horizon runs on the full 608 x 608 km LOLA polar array. Its PSR total is
26,900 km2 -- which is 2.88x the ENTIRE DFSAR frame (9,339.65 km2). That number
is a diagnostic about the polar cap, not a property of this scene, and putting it
anywhere near the analysis JSON would be nonsense of exactly the kind this
project exists to stop.

An area without its domain is as defective as a number without its provenance
mark. So every figure here is printed with the denominator it is a fraction OF,
and the one that reaches the UI is named explicitly.

    python backend/scripts/psr_domains.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

LOLA_DIR = BASE_DIR / "data" / "pradan" / "lola"
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
R_MOON = 1737400.0


def main() -> int:
    from app.ingestion.horizon_frame import load_horizon
    from app.ingestion.sar_geometry import read_geotiff_frame

    hp = load_horizon(LOLA_DIR)
    eff = hp.effective_m
    cell_polar = (eff / 1000.0) ** 2
    psr = hp.psr_mask
    n_l, n_s = psr.shape

    # Latitude of every polar cell, from the same closed form the sweep used.
    cy, cx = (n_l - 1) / 2.0, (n_s - 1) / 2.0
    yy, xx = np.mgrid[0:n_l, 0:n_s].astype(np.float32)
    rho = np.hypot(xx - cx, yy - cy) * np.float32(eff)
    lat = np.degrees(2.0 * np.arctan(rho / (2.0 * R_MOON)) - np.pi / 2.0)

    print("=" * 78)
    print("  PSR AREA BY DOMAIN — every figure with the denominator it belongs to")
    print("=" * 78)
    print(f"  horizon product   {hp.path.name}   {n_l} x {n_s} @ {eff:g} m")
    print(f"  azimuths          {hp.meta['azimuths']}")
    print(f"  subsolar band     {hp.meta.get('subsolar_latitude_range_deg')} deg, "
          f"integrated in closed form")
    print(f"  decimation        {hp.decimation}x from {hp.native_m:g} m posts "
          f"-> {eff:g} m effective")
    print()

    rows = []

    def add(label, mask, domain_mask, note):
        a = float(mask.sum()) * cell_polar
        d = float(domain_mask.sum()) * cell_polar
        rows.append((label, a, d, (a / d * 100 if d else float("nan")), note))

    everything = np.ones_like(psr, dtype=bool)
    add("full 608 x 608 km array", psr, everything,
        "DIAGNOSTIC ONLY — never reaches the UI")
    add("inscribed 80S circle", psr & (lat <= -80.0), lat <= -80.0,
        "the product's nominal coverage")
    add("poleward of 87.5S", psr & (lat <= -87.5), lat <= -87.5,
        "Mazarico et al. 2011 comparison band")

    # The frame, through the validated projection.
    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    shape = (2258, 6618)
    proj = hp.to_frame(frame, shape)
    # DERIVED from the frame's own GeoTIFF pixel size, not typed. The literal
    # 25.0 * 25.0 was correct for this frame and would have gone on being
    # correct right up until the grid changed, at which point every AREA in this
    # script would have been silently wrong while every count stayed right.
    # Asserted against the published value so this change provably moves no
    # number: it removes a trap without touching a result.
    cell_frame = (frame.pixel_size_m[0] / 1000.0) * (frame.pixel_size_m[1] / 1000.0)
    assert abs(cell_frame - 0.000625) < 1e-12, (
        f"frame pixel size {frame.pixel_size_m} gives a cell area of "
        f"{cell_frame:.12f} km2, not the 0.000625 km2 every published area in "
        f"this project was computed with. Areas would move; stop and reconcile.")
    psr_frame = proj["psr_mask"]
    frame_km2 = shape[0] * shape[1] * cell_frame
    psr_frame_km2 = float(psr_frame.sum()) * cell_frame

    print(f"  {'domain':<28} {'PSR km²':>12} {'of domain km²':>15} {'%':>7}   note")
    print("  " + "-" * 92)
    for label, a, d, pct, note in rows:
        print(f"  {label:<28} {a:12,.1f} {d:15,.1f} {pct:6.2f}%   {note}")
    print(f"  {'DFSAR frame (THE UI VALUE)':<28} {psr_frame_km2:12,.1f} "
          f"{frame_km2:15,.1f} {psr_frame_km2 / frame_km2 * 100:6.2f}%   "
          f"resampled to 25 m; psr_mask re-derived")
    print()
    print(f"  The full-array figure is {rows[0][1] / frame_km2:.2f}x the entire frame.")
    print(f"  Only PSR ∩ frame = {psr_frame_km2:,.1f} km² may appear in faustini.json.")

    # Mazarico anchor.
    maz_ours = rows[2][1]
    print()
    print("-" * 78)
    print("  SANITY ANCHOR — Mazarico et al. 2011 (LPI Volatiles abstract 6007)")
    print("-" * 78)
    print(f"  published, poleward of 87.5S at 240 m/px     3,660 km²  (20.3 % of 18,060 km²)")
    print(f"  ours,      poleward of 87.5S at {eff:g} m/px  {maz_ours:7,.0f} km²  "
          f"({rows[2][3]:.1f} % of {rows[2][2]:,.0f} km²)")
    print(f"  ratio ours/published                          {maz_ours / 3660.0:.2f}x")
    print("  Mazarico note their own figure is larger than earlier work (2,751 km²).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
