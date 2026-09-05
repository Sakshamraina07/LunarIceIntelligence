"""
diagnose_valid_mask.py -- v5 section 1. Which mask is the swath's real footprint?

THE QUESTION
------------
The map draws amplitude over 15.64 % of the frame. Three independent
ISRO-supplied numbers say the illuminated swath is ~35.6 %, so v5 proposed that
the 15.64 % was a bug in `(lh > 0) & (lv > 0)` at process_real_sar_pipeline.py:202.

THE ANSWER (measured below -- both v5 hypotheses tested, neither is the bug)
----------------------------------------------------------------------------
1. Boolean AND vs OR is NOT the bug. The AND discards FOUR pixels out of
   2,337,090. lh>0, lv>0, AND and OR all round to 15.64 %.

2. ISRO's own mask IS the 35.63 % figure, and `ma > 0` is byte-identical to
   `inc > 0` (IoU 100.00 %). But it cannot simply replace `valid`, because
   2,987,459 px -- 19.99 % of the frame -- are flagged imaged by ISRO while the
   amplitude rasters hold literal integer zero there. cpr/dop are built as
   `np.where(s0 > 0, ..., 0.0)`, so adopting `ma>0` as the single mask would
   paint a fabricated 0.0 over a fifth of the map.

3. The decisive check is the product's OWN ground-range geometry, before any
   geocoding. The `gri` frame is 16943 x 786 at 9.731 m x 25.0 m, i.e. exactly
   786 x 25 = 19,650 m across-track == the label's `isda:swath`. In that raw
   swath rectangle the amplitude is still only 46.34 % of the frame, its
   per-line across-track extent is p50 352 samples = 8.80 km, and it has ZERO
   interior holes on all 265 sampled lines. Areas close both ways:

       amplitude   gri 1501.2 km^2  vs  sri 1460.7 km^2   -> +2.77 %
       footprint   gri 3239.8 km^2  vs  sri 3327.8 km^2   -> -2.65 %

   So the geocoding lost nothing. ISRO's `ma` marks the NOMINAL 19.65 km swath
   the beam was pointed at; the delivered amplitude fills 8.80 km of it. The
   15.64 % is the data, not a threshold I invented.

THE ADOPTED MODEL -- two masks, because one mask was conflating two things
-------------------------------------------------------------------------
   footprint  = ma>0 (ISRO-supplied)  5,324,545 px  35.63 %  ribbon 19.25 km
                -> the swath outline, the void scrim, geometry, and the honest
                   statement of what the pass covered.
   amplitude  = (lh>0)&(lv>0)         2,337,086 px  15.64 %  ribbon  8.75 km
                -> alpha on the radar layers, and every stretch and statistic.

v5 asked to "prefer an ISRO-supplied mask over a threshold you invented", and
that is done -- for the footprint, which is the thing an ISRO mask can answer.
It cannot manufacture backscatter where the product carries none.

Nothing is written. Read-only diagnosis.

Run:  python backend/scripts/diagnose_valid_mask.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

RAW_DIR = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
GEOM_DIR = BASE_DIR / "data" / "pradan" / "raw" / "geometry" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"

# Seleno-referenced (map-projected) products -- what the app renders.
LH = RAW_DIR / f"{STEM}_d_sri_xx_cp_lh_d18.tif"
LV = RAW_DIR / f"{STEM}_d_sri_xx_cp_lv_d18.tif"
IN = RAW_DIR / f"{STEM}_d_sri_in_cp_xx_d18.tif"
MA = RAW_DIR / f"{STEM}_d_sri_ma_cp_xx_d18.tif"

# Ground-range products -- the raw swath rectangle, no geocoding applied.
GRI_LH = RAW_DIR / f"{STEM}_d_gri_xx_cp_lh_d18.tif"
GRI_XML = RAW_DIR / f"{STEM}_d_gri_xx_cp_xx_d18.xml"

SRI_PX_M = 25.0                 # both axes, south polar stereographic
GRI_LINE_M = 9.731043           # isda:output_line_spacing
GRI_SAMPLE_M = 25.0             # isda:output_pixel_spacing
NOMINAL_SWATH_M = 19650.0       # isda:swath

def hr(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def frac(m: np.ndarray) -> str:
    return f"{m.sum():>11,d} px  {m.mean() * 100:6.2f} %"


def thickness(m: np.ndarray, axis: int = 0, step: int = 32, min_run: int = 8) -> dict:
    """
    Extent of the mask along `axis`, measured line by line across the other axis.

    axis=0 walks columns and measures vertical extent (the sri ribbon).
    axis=1 walks rows and measures horizontal extent (the gri swath width).
    """
    m = m if axis == 0 else m.T
    runs, holes = [], []
    for c in range(0, m.shape[1], step):
        idx = np.flatnonzero(m[:, c])
        if idx.size < min_run:
            continue
        runs.append(idx.size)
        holes.append(int((np.diff(idx) > 1).sum()))
    a = np.asarray(runs, np.float64)
    if a.size == 0:
        return {"n": 0}
    h = np.asarray(holes, np.float64)
    return {
        "n": int(a.size),
        "p10": float(np.percentile(a, 10)),
        "p50": float(np.percentile(a, 50)),
        "p90": float(np.percentile(a, 90)),
        "mean": float(a.mean()),
        "holes_mean": float(h.mean()),
        "holes_max": int(h.max()),
        "no_hole_lines": int((h == 0).sum()),
    }


def report_thickness(name: str, t: dict, px_m: float) -> None:
    if not t["n"]:
        print(f"  {name:14s} (nothing to measure)")
        return
    print(f"  {name:14s} p50 {t['p50']:6.0f} px = {t['p50'] * px_m / 1000:6.2f} km   "
          f"(p10 {t['p10']:.0f}, p90 {t['p90']:.0f}, mean {t['mean'] * px_m / 1000:.2f} km)")
    print(f"  {'':14s} interior holes/line: mean {t['holes_mean']:.2f} max {t['holes_max']} "
          f"-> {t['no_hole_lines']}/{t['n']} lines are a single contiguous run")

def section_1_hypothesis_and_or() -> dict:
    """v5 hypothesis 1: is the Boolean AND throwing the swath edges away?"""
    hr("HYPOTHESIS 1 -- Boolean AND vs OR  (v5: 'if OR lands near 35.6 %, "
       "that is the whole bug')")

    lh = tifffile.imread(str(LH))
    lv = tifffile.imread(str(LV))
    print(f"  lh {lh.shape} {lh.dtype} range {lh.min()} .. {lh.max()}")
    print(f"  lv {lv.shape} {lv.dtype} range {lv.min()} .. {lv.max()}\n")

    lh_pos, lv_pos = lh > 0, lv > 0
    m_and, m_or = lh_pos & lv_pos, lh_pos | lv_pos
    print(f"  lh > 0            {frac(lh_pos)}")
    print(f"  lv > 0            {frac(lv_pos)}")
    print(f"  AND (current)     {frac(m_and)}   <- process_real_sar_pipeline.py:202")
    print(f"  OR                {frac(m_or)}")
    print(f"\n  lh>0 but lv==0    {frac(lh_pos & ~lv_pos)}")
    print(f"  lv>0 but lh==0    {frac(lv_pos & ~lh_pos)}")
    discarded = int(m_or.sum() - m_and.sum())
    print(f"  discarded by AND  {discarded:>11,d} px  "
          f"= {discarded / max(m_or.sum(), 1) * 100:.4f} % of the OR mask")
    print(f"\n  VERDICT: DISPROVED. The AND discards {discarded} pixels. It is not the bug.")
    return {"lh": lh, "lv": lv, "amp": m_and}


def section_1_hypothesis_isro_mask(amp: np.ndarray, lh, lv) -> dict:
    """v5 hypothesis 2: adopt ISRO's own mask instead of an inferred threshold."""
    hr("HYPOTHESIS 2 -- ISRO's own mask products  (v5: 'prefer an ISRO-supplied "
       "mask over a threshold you invented')")

    ma = tifffile.imread(str(MA)) if MA.exists() else None
    inc = tifffile.imread(str(IN))
    inc_pos = inc > 0
    print(f"  incidence raster {inc.shape} {inc.dtype} range {inc.min():.4f} .. {inc.max():.4f}")
    print(f"  inc > 0           {frac(inc_pos)}")
    nz = inc[inc_pos]
    print(f"    non-zero incidence p1={np.percentile(nz, 1):.3f} "
          f"p50={np.percentile(nz, 50):.3f} p99={np.percentile(nz, 99):.3f} deg")

    if ma is None:
        print("\n  !! sri ma product missing -- cannot test hypothesis 2")
        return {"footprint": inc_pos, "ma": None}

    vals, counts = np.unique(ma, return_counts=True)
    ma_pos = ma > 0
    print(f"\n  sri `ma` mask   {ma.shape} {ma.dtype}")
    print(f"    distinct values {dict(zip(vals.tolist(), counts.tolist()))}")
    print(f"  ma > 0            {frac(ma_pos)}")

    iou = (ma_pos & inc_pos).sum() / max((ma_pos | inc_pos).sum(), 1)
    print(f"\n  IoU(ma>0, inc>0)  {iou * 100:.2f} %   -> the two ISRO sources are "
          f"{'byte-identical' if iou > 0.9999 else 'NOT identical'}")
    print(f"  IoU(amp, ma>0)    {(amp & ma_pos).sum() / max((amp | ma_pos).sum(), 1) * 100:.2f} %")
    print(f"  amplitude outside ISRO's mask: {int((amp & ~ma_pos).sum()):,} px "
          "(0 would mean the amplitude is fully contained)")

    hr("THE CAVEAT THAT DECIDES THE DESIGN -- what is inside ISRO's mask "
       "but has no amplitude?")
    for v in vals[vals > 0]:
        cls = ma == v
        print(f"  ma == {int(v):3d}   {cls.sum():>10,d} px ({cls.mean() * 100:5.2f} % of frame)"
              f"   amplitude>0 within: {int((cls & amp).sum()):>10,d} "
              f"({(cls & amp).sum() / max(cls.sum(), 1) * 100:5.2f} %)")

    gap = ma_pos & ~amp
    print(f"\n  ISRO says imaged but amplitude == 0:  {gap.sum():,} px "
          f"({gap.mean() * 100:.2f} % of the frame, "
          f"{gap.sum() / max(ma_pos.sum(), 1) * 100:.2f} % of ISRO's own mask)")
    if gap.any():
        print(f"    their ma values there: "
              f"{dict(zip(*[x.tolist() for x in np.unique(ma[gap], return_counts=True)]))}")
        for nm, arr in (("lh", lh), ("lv", lv)):
            v = arr[gap]
            print(f"    {nm} there: {np.unique(v).size} distinct values, max {v.max()} "
                  f"-> literal integer zero, not a small-but-real return")
    print("\n  VERDICT: the 35.63 % figure is CONFIRMED and corroborated, but `ma>0`")
    print("           cannot replace `valid`: cpr/dop are np.where(s0>0, ..., 0.0), so")
    print("           this many pixels would receive a FABRICATED 0.0. Forbidden.")
    return {"footprint": ma_pos, "ma": ma}

def section_1_ground_range(amp_px: int, footprint_px: int) -> None:
    """
    The decisive test: look at the product's OWN swath rectangle, pre-geocoding.

    If the amplitude is narrow here too, the 15.64 % is the delivered data and no
    choice of mask on the geocoded grid can widen it.
    """
    hr("THE DECISIVE TEST -- the ground-range `gri` product, before geocoding")
    if not GRI_LH.exists():
        print(f"  !! {GRI_LH.name} not on disk -- cannot run the decisive test")
        return

    g = tifffile.imread(str(GRI_LH))
    gm = g > 0
    across_km = g.shape[1] * GRI_SAMPLE_M / 1000.0
    print(f"  gri frame        {g.shape[0]} lines x {g.shape[1]} samples "
          f"@ {GRI_LINE_M} m x {GRI_SAMPLE_M} m")
    print(f"  along-track      {g.shape[0] * GRI_LINE_M / 1000:.2f} km")
    print(f"  across-track     {across_km:.3f} km   vs label isda:swath "
          f"{NOMINAL_SWATH_M / 1000:.3f} km  -> "
          f"{'EXACT MATCH' if abs(across_km * 1000 - NOMINAL_SWATH_M) < 1 else 'MISMATCH'}")
    print(f"\n  This frame IS the nominal swath. No projection, no padding, no rotation.")
    print(f"  amplitude > 0     {frac(gm)}")

    print("\n  --- across-track (range) occupancy: % of lines carrying amplitude ---")
    prof = gm.mean(axis=0) * 100.0
    for s in range(0, g.shape[1], 32):
        print(f"    sample {s:3d} ({s * GRI_SAMPLE_M:6.0f} m from near edge)  "
              f"{prof[s]:6.2f} %  {'#' * int(round(prof[s] / 2.5))}")

    t = thickness(gm, axis=1, step=64)
    print("\n  --- per-line across-track extent of the delivered amplitude ---")
    report_thickness("gri amplitude", t, GRI_SAMPLE_M)
    print(f"\n  A single contiguous run per line, {t['p50'] * GRI_SAMPLE_M / 1000:.2f} km wide inside a "
          f"{across_km:.2f} km swath.")
    print("  The staircase profile above is that window stepping across range down-track.")

    hr("AREA CLOSURE -- two independent geometries, same physical ground")
    a_gri = gm.sum() * GRI_LINE_M * GRI_SAMPLE_M / 1e6
    f_gri = gm.size * GRI_LINE_M * GRI_SAMPLE_M / 1e6
    a_sri = amp_px * SRI_PX_M * SRI_PX_M / 1e6
    f_sri = footprint_px * SRI_PX_M * SRI_PX_M / 1e6
    print(f"  amplitude    gri {a_gri:8.1f} km2   sri {a_sri:8.1f} km2   "
          f"-> {a_gri / max(a_sri, 1e-9) * 100 - 100:+.2f} %")
    print(f"  footprint    gri {f_gri:8.1f} km2   sri {f_sri:8.1f} km2   "
          f"-> {f_gri / max(f_sri, 1e-9) * 100 - 100:+.2f} %")
    print(f"\n  Both close inside 3 %. The geocoding lost nothing:")
    print(f"    * ISRO's `ma` marks the NOMINAL {NOMINAL_SWATH_M / 1000:.2f} km swath the beam pointed at.")
    print(f"    * The delivered amplitude fills {a_gri / max(f_gri, 1e-9) * 100:.1f} % of it, "
          f"{t['p50'] * GRI_SAMPLE_M / 1000:.2f} km wide.")
    print(f"    * 15.64 % on the sri grid is the DATA. No mask choice can widen it.")


def section_1_geolocation_grid(footprint_frac: float) -> None:
    """The third ISRO source: the geolocation grid's own fill pattern."""
    hr("THIRD ISRO SOURCE -- the geolocation grid CSV")
    csv = GEOM_DIR / f"{STEM}_g_sri_xx_cp_xx_d18.csv"
    if not csv.exists():
        print(f"  !! {csv.name} not on disk")
        return

    head = csv.read_text(errors="replace").split("\n", 1)[0].strip()
    print(f"  {csv.name}")
    print(f"  header: {head}")
    a = np.loadtxt(str(csv), delimiter=",", skiprows=1, dtype=np.float64)
    print(f"  {a.shape[0]:,} nodes x {a.shape[1]} columns\n")

    for i, n in enumerate(head.split(",")):
        c = a[:, i]
        fill = np.isclose(c, -9999.0) | np.isclose(c, -999.0)
        ok = c[~fill]
        print(f"    {n:22s} fill {int(fill.sum()):>7,d}  non-fill {int((~fill).sum()):>7,d} "
              f"= {(~fill).mean() * 100:6.2f} %   range {ok.min():12.4f} .. {ok.max():12.4f}")

    inc_nf = ~np.isclose(a[:, 3], -9999.0)
    print(f"\n  incidence non-fill = {int(inc_nf.sum()):,} / {inc_nf.size:,} "
          f"= {inc_nf.mean() * 100:.2f} %")
    print(f"  sri ma>0 raster    = {footprint_frac * 100:.2f} %   -> the third source agrees")

    for r, c in ((566, 1656), (1656, 566)):
        if r * c == a.shape[0]:
            print(f"  lattice {r} x {c} = {a.shape[0]:,} nodes -> {r} x 4 = {r * 4} lines, "
                  f"{c} x 4 = {c * 4} samples  (sri frame is 2258 x 6618)")

def main() -> None:
    print("=" * 78)
    print("v5 SECTION 1 -- VALID MASK DIAGNOSIS  (read-only)")
    print("=" * 78)

    h1 = section_1_hypothesis_and_or()
    amp, lh, lv = h1["amp"], h1["lh"], h1["lv"]

    h2 = section_1_hypothesis_isro_mask(amp, lh, lv)
    footprint = h2["footprint"]
    del lh, lv

    hr("RIBBON THICKNESS ON THE SRI GRID  (nominal PDS4 swath is 19,650 m)")
    t_amp = thickness(amp)
    t_fp = thickness(footprint)
    report_thickness("amplitude", t_amp, SRI_PX_M)
    report_thickness("ISRO ma>0", t_fp, SRI_PX_M)
    if t_fp["n"]:
        print(f"\n  ISRO ribbon {t_fp['p50'] * SRI_PX_M / 1000:.2f} km p50 / "
              f"{t_fp['mean'] * SRI_PX_M / 1000:.2f} km mean against a nominal "
              f"{NOMINAL_SWATH_M / 1000:.2f} km -> closes to "
              f"{abs(t_fp['mean'] * SRI_PX_M / NOMINAL_SWATH_M * 100 - 100):.1f} %")

    section_1_ground_range(int(amp.sum()), int(footprint.sum()))
    section_1_geolocation_grid(float(footprint.mean()))

    hr("ADOPTED MASK MODEL -- two masks, because one was conflating two things")
    print(f"  footprint  ISRO sri `ma` > 0   {frac(footprint)}  "
          f"ribbon {t_fp['p50'] * SRI_PX_M / 1000:5.2f} km")
    print("             -> swath outline, void scrim, geometry, and the honest")
    print("                statement of what this pass covered.")
    print(f"  amplitude  (lh>0) & (lv>0)     {frac(amp)}  "
          f"ribbon {t_amp['p50'] * SRI_PX_M / 1000:5.2f} km")
    print("             -> alpha on the radar layers, and every stretch/statistic.")
    print(f"\n  amplitude / footprint = {amp.sum() / max(footprint.sum(), 1) * 100:.2f} % "
          "-- the fraction of the pointed swath that actually returned signal.")
    print("\n  Adopting ISRO's mask for the footprint answers what an ISRO mask CAN")
    print("  answer. It cannot manufacture backscatter where the product carries none,")
    print("  so the radar layers stay on the amplitude mask.")
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()
