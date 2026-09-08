"""
validate_psr_vs_lola.py -- our shadows against the LOLA team's own published ones.

    python backend/scripts/validate_psr_vs_lola.py

WHY THIS IS THE STRONGEST EVIDENCE IN THE PROJECT
--------------------------------------------------
Everything else in Phase 2 is an internal consistency argument: the algorithm
matches its own brute force, the projection has no offset, the closed form
matches sampling. None of that says the SHADOWS ARE RIGHT.

The LOLA team publishes its own permanently-shadowed masks and average
illumination rasters, from the same instrument, on the same PDS node, in the
same PDS3 .IMG + .LBL format, in the same south polar stereographic projection
on the same 1737.4 km sphere. So this is not an argument. It is a measurement
against the instrument team's own product, pixel for pixel, with no reprojection.

  LPSR_75S_120M_201608      binary permanent-shadow mask, 120 m/px, 75S -> pole
  AVGVISIB_75S_120M_201608  average solar visibility,     120 m/px, 75S -> pole

Both cover the whole DFSAR frame (outer corner -84.833). Downloaded from PDS
Geosciences (pds-geosciences.wustl.edu) because imbrium.mit.edu was unreachable;
identical products, same release.

A MASK IS CATEGORICAL
---------------------
LPSR is resampled to the frame with NEAREST NEIGHBOUR, never bilinear. An
interpolated boolean invents half-shadowed pixels and would quietly improve the
agreement it is supposed to be testing. AVGVISIB is continuous and is resampled
bilinearly, which is correct for it.

THE EXPECTATION, STATED BEFORE LOOKING
--------------------------------------
Agreement will not be 100 % and should not be. Ours is computed from 80 m posts
decimated to 240 m; theirs is 120 m and epoch-specific. Finer topography resolves
more small shadows, so A MODEST POSITIVE BIAS IN OUR PSR AREA IS EXPECTED AND
DEFENSIBLE; A LARGE ONE IS NOT. Against Mazarico et al. (2011) we already run
1.50x high poleward of 87.5S, and the leading suspect is that this model treats
the Sun as a POINT when its angular radius is ~0.25 deg -- large next to a
+/-1.54 deg subsolar band at grazing incidence, and biased toward over-shadowing.
So the prediction here is: we over-call PSR relative to LPSR, by a factor in the
same 1.2-1.6 range, with high recall and lower precision.
"""
from __future__ import annotations

import importlib.util
import json
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
ILLUM_DIR = LOLA_DIR / "illumination"
RAW = BASE_DIR / "data" / "pradan" / "raw" / "data" / "calibrated" / "20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
OUT = BASE_DIR / "docs" / "psr_validation.json"


def hr(t: str) -> None:
    print("\n" + "-" * 78)
    print(t)
    print("-" * 78)


def load_pds(stem: str):
    """A PDS3 polar raster, through the ingest's own label parser."""
    spec = importlib.util.spec_from_file_location(
        "_ingest_lola", BACKEND_DIR / "scripts" / "ingest_lola_polar_dem.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    lbl = ILLUM_DIR / f"{stem}.LBL"
    img = ILLUM_DIR / f"{stem}.IMG"
    if not (lbl.is_file() and img.is_file()):
        raise SystemExit(
            f"{stem} not in {ILLUM_DIR}. Fetch from\n"
            "  https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
            "lrolol_1xxx/extras/illumination/img/"
        )
    label = mod.read_label(lbl)
    g = mod.LolaGrid(label, img)
    conv = mod.solve_convention(g)
    if isinstance(conv, dict) and "chosen" in conv:
        g.base = conv["chosen"]
    mm = np.memmap(img, dtype=g.dtype, mode="r",
                   offset=g.data_offset_bytes, shape=(g.lines, g.samples))
    # PERMANENT_SHADOW = DN * SCALING_FACTOR + OFFSET, per the label's own NOTE.
    arr = np.asarray(mm, dtype=np.float32) * np.float32(g.scaling_factor) \
        + np.float32(g.value_offset)
    del mm
    return g, arr


def to_frame(g, arr, frame, shape, order):
    """Sample a polar PDS raster onto the DFSAR frame. `order` 0 = nearest."""
    from scipy.ndimage import map_coordinates
    base = {"zero_based": 0.0, "half_pixel": 0.5, "one_based": 1.0}[g.base]
    rows = np.arange(shape[0], dtype=np.float64)
    cols = np.arange(shape[1], dtype=np.float64)
    gx, gy = frame.pixel_to_xy(rows[:, None], cols[None, :])
    gx, gy = np.broadcast_arrays(gx, gy)
    line = g.lpo - gy / g.scale_m - base
    samp = g.spo + gx / g.scale_m - base
    return map_coordinates(arr.astype(np.float64), np.stack([line, samp]),
                           order=order, mode="nearest").astype(np.float32)


def main() -> int:
    from app.ingestion.horizon_frame import load_horizon
    from app.ingestion.sar_geometry import read_geotiff_frame

    shape = (2258, 6618)
    frame = read_geotiff_frame(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif",
                               RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml")
    # DERIVED from the frame's own GeoTIFF pixel size, not typed. The literal
    # 25.0 * 25.0 was correct for this frame and would have gone on being
    # correct right up until the grid changed, at which point every AREA in this
    # script would have been silently wrong while every count stayed right.
    # Asserted against the published value so this change provably moves no
    # number: it removes a trap without touching a result.
    cell_km2 = (frame.pixel_size_m[0] / 1000.0) * (frame.pixel_size_m[1] / 1000.0)
    assert abs(cell_km2 - 0.000625) < 1e-12, (
        f"frame pixel size {frame.pixel_size_m} gives a cell area of "
        f"{cell_km2:.12f} km2, not the 0.000625 km2 every published area in "
        f"this project was computed with. Areas would move; stop and reconcile.")

    hp = load_horizon(LOLA_DIR)
    proj = hp.to_frame(frame, shape)
    ours = proj["psr_mask"]
    ours_frac = proj["illumination_fraction"]

    hr("THE PREDICTION, MADE BEFORE LOOKING")
    print("  Ours is 80 m posts decimated to 240 m; theirs is 120 m, epoch-specific.")
    print("  Finer topography resolves more small shadows, and this model treats the")
    print("  Sun as a POINT (true angular radius ~0.25 deg, large next to a +/-1.54 deg")
    print("  band at grazing incidence) — both bias toward MORE shadow.")
    print("  PREDICTED (for the POINT-SUN model, before the finite disc shipped):")
    print("             we over-call PSR by roughly 1.2–1.6x, with high recall and")
    print("             lower precision. A large bias would not be defensible.")

    # ---------------------------------------------------------------- LPSR
    g_psr, a_psr = load_pds("LPSR_75S_120M_201608")
    hr("LPSR_75S_120M_201608 — the LOLA team's own permanent-shadow mask")
    print(f"  grid        {g_psr.lines} x {g_psr.samples} @ {g_psr.scale_m:g} m/px, "
          f"base {g_psr.base}")
    print(f"  values      min {a_psr.min():.4f}  max {a_psr.max():.4f}  "
          f"unique(first 6) {np.unique(a_psr)[:6]}")
    theirs_polar = a_psr > 0.5
    print(f"  PSR on their own grid: {int(theirs_polar.sum()):,} px  "
          f"{theirs_polar.sum() * (g_psr.scale_m / 1000.0) ** 2:,.0f} km²")

    theirs = to_frame(g_psr, a_psr, frame, shape, order=0) > 0.5
    print(f"  resampled to the frame with NEAREST NEIGHBOUR (a mask is categorical)")

    tp = int((ours & theirs).sum())
    fp = int((ours & ~theirs).sum())
    fn = int((~ours & theirs).sum())
    tn = int((~ours & ~theirs).sum())
    jac = tp / max(tp + fp + fn, 1)
    dice = 2 * tp / max(2 * tp + fp + fn, 1)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)

    hr("CONFUSION MATRIX over the DFSAR frame (14,943,444 px, 9,339.65 km²)")
    print(f"  {'':22}{'LPSR shadow':>16}{'LPSR lit':>16}")
    print(f"  {'ours shadow':22}{tp:>16,}{fp:>16,}")
    print(f"  {'ours lit':22}{fn:>16,}{tn:>16,}")
    print()
    print(f"  our PSR      {ours.sum() * cell_km2:10,.1f} km²")
    print(f"  their PSR    {theirs.sum() * cell_km2:10,.1f} km²")
    print(f"  ratio        {ours.sum() / max(int(theirs.sum()), 1):10.3f}x")
    print()
    print(f"  Jaccard (IoU) {jac:.4f}      Dice {dice:.4f}")
    print(f"  precision     {prec:.4f}      recall {rec:.4f}")
    print(f"  agreement     {(tp + tn) / ours.size:.4f}")

    # ------------------------------------------------------------ AVGVISIB
    g_vis, a_vis = load_pds("AVGVISIB_75S_120M_201608")
    hr("AVGVISIB_75S_120M_201608 — average SOLAR visibility, the continuous check")
    print(f"  grid        {g_vis.lines} x {g_vis.samples} @ {g_vis.scale_m:g} m/px")
    print(f"  values      min {a_vis.min():.4f}  max {a_vis.max():.4f}  "
          f"mean {a_vis.mean():.4f}")
    vis = to_frame(g_vis, a_vis, frame, shape, order=1)

    ok = np.isfinite(ours_frac) & np.isfinite(vis)
    x, y = ours_frac[ok].astype(np.float64), vis[ok].astype(np.float64)
    r = float(np.corrcoef(x, y)[0, 1])
    rms = float(np.sqrt(((x - y) ** 2).mean()))
    slope, icpt = np.polyfit(y, x, 1)
    print(f"\n  ours  mean {x.mean():.4f}  p50 {np.percentile(x, 50):.4f}  max {x.max():.4f}")
    print(f"  LOLA  mean {y.mean():.4f}  p50 {np.percentile(y, 50):.4f}  max {y.max():.4f}")
    print(f"\n  Pearson r    {r:.4f}")
    print(f"  rms diff     {rms:.4f}")
    print(f"  ours = {slope:.3f} x theirs + {icpt:.4f}")

    # A 2-D histogram, printed as text so it survives in a log.
    hr("2-D HISTOGRAM  (rows = ours, cols = LOLA AVGVISIB), % of frame")
    edges = np.linspace(0, max(x.max(), y.max()) + 1e-6, 9)
    H, _, _ = np.histogram2d(x, y, bins=[edges, edges])
    H = H / H.sum() * 100.0
    print("        " + "".join(f"{edges[j]:>7.2f}" for j in range(8)))
    for i in range(7, -1, -1):
        print(f"  {edges[i]:5.2f} " + "".join(
            f"{H[i, j]:7.2f}" if H[i, j] >= 0.01 else "      ·" for j in range(8)))

    # ------------------------------------------------- the sun-model A/B
    # Both arms come from ONE horizon, reach the frame through ONE mapping, and
    # have their masks re-derived by ONE rule. The only difference is rho.
    models = {t: (proj[f"psr_mask_r{t}"], proj[f"illumination_fraction_r{t}"])
              for t in sorted(hp.illumination_by_radius,
                              key=lambda s: float(s))}
    if len(models) > 1:
        hr("SOLAR-MODEL A/B — point Sun vs finite disc, both against LPSR")
        print("  Predictions were committed in docs/preregistration_solar_disc.md")
        print("  BEFORE this sweep finished. Measured values are reported against")
        print("  them below whether or not they land.\n")
        rows = {}
        for tag, (m, f) in models.items():
            ok2 = np.isfinite(f) & np.isfinite(vis)
            xx, yy = f[ok2].astype(np.float64), vis[ok2].astype(np.float64)
            sl, _ic = np.polyfit(yy, xx, 1)
            t_p = int((m & theirs).sum())
            f_p = int((m & ~theirs).sum())
            f_n = int((~m & theirs).sum())
            t_n = int((~m & ~theirs).sum())
            rows[tag] = {
                "solar_radius_deg": float(tag),
                "psr_km2": float(m.sum() * cell_km2),
                "ratio": m.sum() / max(int(theirs.sum()), 1),
                "jaccard": t_p / max(t_p + f_p + f_n, 1),
                "dice": 2 * t_p / max(2 * t_p + f_p + f_n, 1),
                "precision": t_p / max(t_p + f_p, 1),
                "recall": t_p / max(t_p + f_n, 1),
                "agreement": (t_p + t_n) / m.size,
                "avgvisib_r": float(np.corrcoef(xx, yy)[0, 1]),
                "avgvisib_slope": float(sl),
                "avgvisib_rms": float(np.sqrt(((xx - yy) ** 2).mean()))}
        tags = list(rows)
        name = {t: ("point Sun" if float(t) == 0.0 else f"disc r={t}°") for t in tags}
        print(f"  {'metric':>16}" + "".join(f"{name[t]:>14}" for t in tags))
        for k in ("psr_km2", "ratio", "jaccard", "dice", "precision", "recall",
                  "agreement", "avgvisib_r", "avgvisib_slope", "avgvisib_rms"):
            print(f"  {k:>16}" + "".join(f"{rows[t][k]:>14.4f}" for t in tags))

        # predicted vs measured, stated as it was pre-registered
        pred = {"ratio": ("~1.16", 1.301), "jaccard": ("up", 0.6732),
                "dice": ("up", 0.8047), "precision": ("up", 0.7115),
                "recall": ("down slightly", 0.9258), "avgvisib_r": ("up", 0.8925),
                "avgvisib_slope": ("up toward 1.0", 0.755),
                "avgvisib_rms": ("down", 0.0890)}
        disc = tags[-1]
        print(f"\n  {'metric':>16}{'point (was)':>13}{'predicted':>16}"
              f"{'measured':>11}{'held?':>8}")
        held = 0
        for k, (what, base) in pred.items():
            got = rows[disc][k]
            if what == "up":
                ok3 = got > base
            elif what.startswith("down"):
                ok3 = got < base
            elif what.startswith("up toward"):
                ok3 = base < got <= 1.05
            else:
                ok3 = abs(got - 1.16) <= 0.06
            held += ok3
            print(f"  {k:>16}{base:>13.4f}{what:>16}{got:>11.4f}"
                  f"{'YES' if ok3 else 'NO':>8}")
        print(f"\n  {held} of {len(pred)} predictions held.")
        better = (rows[disc]["jaccard"] > rows[tags[0]]["jaccard"]
                  and rows[disc]["precision"] > rows[tags[0]]["precision"])
        print("  DISC IMPROVES AGREEMENT — it ships." if better else
              "  DISC DOES NOT IMPROVE AGREEMENT — hypothesis REJECTED, point Sun ships.")
        (BASE_DIR / "docs/solar_model_ab.json").write_text(
            json.dumps({"models": rows, "disc_improves": bool(better)}, indent=2),
            encoding="utf-8")

    hr("VERDICT")
    over = ours.sum() / max(int(theirs.sum()), 1)
    print(f"  Predicted a modest positive bias of about 1.2–1.6x. Measured {over:.3f}x.")
    if over > 1.0:
        print("  Direction: WE OVER-CALL SHADOW, as predicted.")
    else:
        print("  Direction: WE UNDER-CALL SHADOW — the OPPOSITE of the prediction.")
    print(f"  Recall {rec:.3f} against precision {prec:.3f}: "
          f"{'high recall, lower precision — the predicted shape' if rec > prec else 'NOT the predicted shape'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_by": "backend/scripts/validate_psr_vs_lola.py",
        "reference_products": {
            "psr": "LPSR_75S_120M_201608",
            "illumination": "AVGVISIB_75S_120M_201608",
            "source": ("PDS Geosciences Node, lro-l-lola-3-rdr-v1/lrolol_1xxx/extras/"
                       "illumination/img/ (imbrium.mit.edu was unreachable)"),
            "resample": "PSR nearest-neighbour (categorical); AVGVISIB bilinear (continuous)",
        },
        "ours": {"psr_km2": float(ours.sum() * cell_km2),
                 "effective_metres_per_pixel": hp.effective_m,
                 "azimuths": hp.meta["azimuths"]},
        "theirs": {"psr_km2": float(theirs.sum() * cell_km2),
                   "metres_per_pixel": g_psr.scale_m},
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "jaccard": jac, "dice": dice, "precision": prec, "recall": rec,
        "area_ratio_ours_over_theirs": float(ours.sum() / max(int(theirs.sum()), 1)),
        "avgvisib": {"pearson_r": r, "rms": rms,
                     "fit_ours_vs_theirs": {"slope": float(slope), "intercept": float(icpt)}},
        "prediction": ("modest positive bias 1.2-1.6x, high recall and lower precision, "
                       "stated before looking. WRITTEN FOR THE POINT-SUN MODEL, where "
                       "it measured 1.301x and fell inside; the finite disc then "
                       "shipped and the ratio is 1.174x, just outside. Recorded as NOT "
                       "A HIT conservatively — arguably void rather than missed, since "
                       "it was scored against a model it does not describe."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
