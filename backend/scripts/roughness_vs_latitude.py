"""
Is the smoothest ground in this frame real terrain, or LOLA interpolation?

THE SUSPICION, AND WHY IT IS NOT PARANOIA
------------------------------------------
Phase 3's five best landing sites came back with slopes of 0.05-0.55 deg against
a frame median of 9.56 deg, and hazards of 0.006-0.023 against a median of 0.339.
Site 3's slope of 0.05 deg on a 25 m grid means the surface rises about 2 cm over
25 metres. That is flatter than almost anything real on the Moon.

All five sit between -85.9 and -86.4 deg, on the EQUATORWARD EDGE of a frame that
runs to -89.26. LOLA GDRs are gridded from laser tracks whose density is highest
at the pole and falls away from it, and a grid cell with no track through it is
an interpolation between distant ones -- which is smooth by construction.

So there are two hypotheses that predict the same site list:
  A. those places really are the flattest ground in the frame;
  B. those places have the fewest LOLA shots, and the search found the smoothest
     INTERPOLATION rather than the smoothest TERRAIN.

THE TEST
--------
Bin the whole frame by latitude and plot roughness and slope against it.

Real geology has no reason to get monotonically smoother toward one edge of an
arbitrary radar swath. Track density does exactly that. If roughness falls
steadily as |latitude| decreases, hypothesis B is live and the site list is an
artifact map. If roughness is flat or noisy against latitude, the sites are real
and their latitude clustering has some other cause.

The test is cheap, it is one plot, and it can be run by anyone.

Usage:
    python -u backend/scripts/roughness_vs_latitude.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import uniform_filter

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

NATIVE = BASE_DIR / "data/pradan/native"
RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
R_MOON = 1737400.0


def main() -> int:
    from app.ingestion.sar_geometry import read_geotiff_frame

    dem = np.asarray(tifffile.imread(str(NATIVE / "dem_native.tif")), dtype=np.float32)
    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    lines, samples = dem.shape

    # Latitude per pixel, from the frame's own projection. South polar
    # stereographic: rho -> colatitude, exactly as compute_horizon does it.
    rows = np.arange(lines, dtype=np.float64)[:, None]
    cols = np.arange(samples, dtype=np.float64)[None, :]
    gx, gy = frame.pixel_to_xy(rows, cols)
    gx, gy = np.broadcast_arrays(gx, gy)
    rho = np.hypot(gx, gy)
    lat = -(90.0 - np.degrees(2.0 * np.arctan(rho / (2.0 * R_MOON))))

    sy, sx = 25.0, 25.0
    dy, dx = np.gradient(dem.astype(np.float64), sy, sx)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    m = uniform_filter(dem.astype(np.float64), size=5)
    rough = np.sqrt(np.maximum(0.0, uniform_filter(dem.astype(np.float64) ** 2, size=5) - m * m))

    print("=" * 78)
    print("ROUGHNESS AND SLOPE vs LATITUDE — is the smooth ground real?")
    print("=" * 78)
    print(f"  frame {lines} x {samples} at 25 m, latitude "
          f"{lat.min():.3f} to {lat.max():.3f} deg")
    print(f"  frame medians: slope {np.median(slope):.3f} deg, "
          f"roughness {np.median(rough):.3f} m\n")

    edges = np.arange(np.floor(lat.min() * 4) / 4, np.ceil(lat.max() * 4) / 4 + 0.25, 0.25)
    print(f"  {'lat band':>16}{'px':>12}{'slope p50':>11}{'rough p50':>11}"
          f"{'rough p90':>11}{'slope p90':>11}")
    rows_out = []
    for i in range(len(edges) - 1):
        sel = (lat >= edges[i]) & (lat < edges[i + 1])
        n = int(sel.sum())
        if n < 20000:
            continue
        sl, ro = slope[sel], rough[sel]
        r = {"lat_lo": float(edges[i]), "lat_hi": float(edges[i + 1]), "pixels": n,
             "slope_p50": float(np.median(sl)), "slope_p90": float(np.percentile(sl, 90)),
             "rough_p50": float(np.median(ro)), "rough_p90": float(np.percentile(ro, 90))}
        rows_out.append(r)
        print(f"  {edges[i]:>7.2f}..{edges[i+1]:<7.2f}{n:>12,}"
              f"{r['slope_p50']:>11.3f}{r['rough_p50']:>11.3f}"
              f"{r['rough_p90']:>11.3f}{r['slope_p90']:>11.3f}")

    # Monotonicity: does roughness fall steadily toward the equatorward edge?
    lo = [r for r in rows_out if r["lat_hi"] <= -87.0]
    hi = [r for r in rows_out if r["lat_lo"] >= -86.5]
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    if lo and hi:
        rl = float(np.median([r["rough_p50"] for r in lo]))
        rh = float(np.median([r["rough_p50"] for r in hi]))
        sl_ = float(np.median([r["slope_p50"] for r in lo]))
        sh = float(np.median([r["slope_p50"] for r in hi]))
        print(f"  poleward of -87.0 :  roughness p50 {rl:6.3f} m   slope p50 {sl_:6.3f} deg")
        print(f"  equatorward of -86.5: roughness p50 {rh:6.3f} m   slope p50 {sh:6.3f} deg")
        print(f"  ratio equatorward/poleward: roughness {rh / max(rl, 1e-9):.3f}, "
              f"slope {sh / max(sl_, 1e-9):.3f}")
        lats = np.array([0.5 * (r["lat_lo"] + r["lat_hi"]) for r in rows_out])
        rr = np.array([r["rough_p50"] for r in rows_out])
        corr = float(np.corrcoef(lats, rr)[0, 1])
        # SIGN. Latitude runs -90 (pole) to -84.8 (equatorward edge), so it
        # INCREASES equatorward. Roughness falling equatorward is therefore a
        # NEGATIVE correlation. The first version of this script tested
        # `corr > 0.6` and would have reported "no artifact" for a perfect
        # artifact -- the fifth instance of the verification apparatus being
        # wrong, recorded as such in METHODS section 0.
        print(f"\n  correlation of roughness p50 with latitude across "
              f"{len(rows_out)} bands: {corr:+.3f}")
        print("  Latitude increases EQUATORWARD, so a NEGATIVE correlation")
        print("  means smoother toward the equatorward edge -- the artifact.")
        if corr < -0.6 and rh < 0.7 * rl:
            print("\n  ARTIFACT SIGNATURE PRESENT at frame scale.")
        elif corr < -0.3:
            print(f"\n  A MILD equatorward smoothing trend is present "
                  f"({corr:+.3f}, ratio {rh / max(rl, 1e-9):.3f}).")
            print("  Not conclusive alone: the poleward-most band is genuine")
            print("  Shackleton-area relief and drags the trend by itself. The")
            print("  decisive question is where the ULTRA-SMOOTH pixels are.")
        else:
            print("\n  NO equatorward smoothing trend at frame scale.")
    # ---- THE DIRECT TEST ---------------------------------------------
    # Band medians answer "is the REGION smoother". The site list is built
    # from individual PIXELS, so what matters is where the ultra-smooth
    # pixels live. Clustered equatorward beyond what the medians explain =
    # interpolation. Spread like area = real flat ground.
    print("\n" + "=" * 78)
    print("WHERE ARE THE ULTRA-SMOOTH PIXELS? the site list is built from these")
    print("=" * 78)
    site_rough = 1.2
    smooth = rough <= site_rough
    print(f"  roughness <= {site_rough:g} m: {int(smooth.sum()):,} px "
          f"({smooth.mean() * 100:.3f} % of the frame)")
    print()
    print(f"  {'lat band':>16}{'% of area':>12}{'% of smooth':>14}{'enrichment':>12}")
    enrich = []
    for i2 in range(len(edges) - 1):
        sel = (lat >= edges[i2]) & (lat < edges[i2 + 1])
        n = int(sel.sum())
        if n < 20000:
            continue
        a = n / lat.size
        b = int((smooth & sel).sum()) / max(int(smooth.sum()), 1)
        e = b / a if a > 0 else float("nan")
        enrich.append({"lat_lo": float(edges[i2]), "area_frac": a,
                       "smooth_frac": b, "enrichment": e})
        print(f"  {edges[i2]:>7.2f}..{edges[i2+1]:<7.2f}{a * 100:>11.2f}%"
              f"{b * 100:>13.2f}%{e:>12.2f}")
    print()
    print("  Enrichment 1.0 = smooth pixels spread exactly like area.")
    print("  Values >> 1 in the equatorward bands would be the artifact.")
    sb = [e for e in enrich if -86.5 <= e["lat_lo"] < -85.75]
    if sb:
        se = float(np.mean([e["enrichment"] for e in sb]))
        print(f"\n  enrichment where all five sites sit (-86.5..-85.75): {se:.2f}")

    (BASE_DIR / "docs/roughness_vs_latitude.json").write_text(
        json.dumps({"bands": rows_out, "smooth_enrichment": enrich,
                    "smooth_threshold_m": site_rough}, indent=2), encoding="utf-8")
    print("\n  wrote docs/roughness_vs_latitude.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
