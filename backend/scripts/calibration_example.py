"""
calibration_example.py -- the incidence factor is applied once, with a worked example.

    python backend/scripts/calibration_example.py

WHY (third review, M3)
----------------------
Section III-A writes l = DN^2 sin(theta_inc) / (K G^2), K = 10^(K_dB/10), with
K_dB = 70.308868 from the ortho label and G the per-channel gain imbalance.
The reviewer asks two things of the repository: that sin(theta_inc) is applied
EXACTLY ONCE on the ortho-rectified product, and that the product is not
already incidence-normalized; and a worked example with the exact inputs.

WHAT IS TESTED, AND HOW
-----------------------
1. The production code path, empirically. The pipeline boxcars the calibrated
   intensities before forming CPR, and a spatially varying weight does not
   commute with a boxcar -- so zero, one and two applications of sin(theta)
   produce DIFFERENT boxcar'd fields. Recomputing the pipeline's stored
   rasters from the raw DN under each hypothesis and comparing identifies how
   many times the stored output applied it:
     * s0_real.tif  -- S0 = box(sigma0_LH) + box(sigma0_LV), resampled to the
                       analysis grid; absolute, so it also checks K and G
     * cpr_native.tif -- CPR_a on the native grid; K cancels, sin does not
2. Every sin(theta) in the tracked scripts, listed by file and role, so a
   second application elsewhere would be visible.
3. The label, for any declaration that the DN are already normalized.

What is NOT decidable here: whether ISRO's processor applied an incidence
normalization BEFORE writing the DN. The label declares none, and no product
layer records one; the data cannot separate a normalization from terrain
backscatter's own incidence dependence. That is stated, not assumed.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
for p in (BACKEND_DIR, Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from runinfo import run_info  # noqa: E402

RAW = BASE_DIR / "data/pradan/raw/data/calibrated/20200808"
STEM = "ch2_sar_ncxl_20200808t201154198"
LABEL = RAW / f"{STEM}_d_sri_xx_cp_xx_d18.xml"
S0_STORED = BASE_DIR / "data/pradan/dfsar/s0_real.tif"
CPR_STORED = BASE_DIR / "data/pradan/native/cpr_native.tif"
OUT = BASE_DIR / "docs" / "calibration_example.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def db(x: float) -> float:
    return 10.0 * math.log10(x)


def label_value(xml: str, tag: str, nth: int = 0) -> float:
    vals = re.findall(rf"<isda:{tag}[^>]*>([^<]+)</isda:{tag}>", xml)
    return float(vals[nth])


def main() -> int:
    import cv2
    from app.ingestion.sar_geometry import parse_calibration

    xml = LABEL.read_text(encoding="utf-8", errors="replace")
    cal = parse_calibration(LABEL)
    k_db = float(cal["calibration_constant_db"])
    k_lin = 10.0 ** (k_db / 10.0)
    g = {c: float(cal["channels"][c]["gain_imbalance"]) for c in ("LH", "LV")}
    theta_label = label_value(xml, "incidence_angle")
    nesz = {"LH": label_value(xml, "nes0_coeff_0", 0), "LV": label_value(xml, "nes0_coeff_0", 1)}

    lh = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lh_d18.tif")).astype(np.float64)
    lv = tifffile.imread(str(RAW / f"{STEM}_d_sri_xx_cp_lv_d18.tif")).astype(np.float64)
    inc = tifffile.imread(str(RAW / f"{STEM}_d_sri_in_cp_xx_d18.tif")).astype(np.float64)
    amp = (lh > 0) & (lv > 0)
    med = {"LH": float(np.median(lh[amp])), "LV": float(np.median(lv[amp]))}
    theta_raster_med = float(np.median(inc[amp]))

    print("=" * 78)
    print("CALIBRATION — sin(theta_inc) applied once, and a worked example (M3)")
    print("=" * 78)
    print(f"  label: K_dB {k_db} dB -> K = {k_lin:.6e}; G_LH {g['LH']}, G_LV {g['LV']}; "
          f"theta {theta_label} deg")
    print(f"  median DN over {int(amp.sum()):,} amplitude pixels: LH {med['LH']:.0f}, "
          f"LV {med['LV']:.0f}; median incidence-raster value {theta_raster_med:.3f} deg")

    # ---- 1. the scene-level example Section III-A prints ---------------------
    st = math.sin(math.radians(theta_label))
    scene = {}
    for reading, p in (("amplitude", 2), ("intensity", 1)):
        for with_g in (False, True):
            val = med["LH"] ** p * st / (k_lin * (g["LH"] ** 2 if with_g else 1.0))
            scene[f"{reading}_reading{'_with_G' if with_g else '_without_G'}_db"] = db(val)
    scene["nesz_LH_db"] = db(nesz["LH"])
    scene["nesz_LV_db"] = db(nesz["LV"])
    for k, v in scene.items():
        print(f"    {k:<40} {v:+.2f} dB")
    printed = {"amplitude_reading_db": -20.3, "intensity_reading_db": -47.6, "nesz_db": -31.5}
    reproduces = {
        "amplitude": {"without_G": round(scene["amplitude_reading_without_G_db"], 1) == -20.3,
                      "with_G": round(scene["amplitude_reading_with_G_db"], 1) == -20.3},
        "intensity": {"without_G": round(scene["intensity_reading_without_G_db"], 1) == -47.6,
                      "with_G": round(scene["intensity_reading_with_G_db"], 1) == -47.6}}
    print(f"  the manuscript prints -20.3 / -47.6 dB: reproduced WITHOUT G "
          f"({reproduces['amplitude']['without_G']}/{reproduces['intensity']['without_G']}), "
          f"WITH G ({reproduces['amplitude']['with_G']}/{reproduces['intensity']['with_G']})")

    # ---- 2. one pixel through the production equation ------------------------
    ys, xs = np.nonzero(amp & (lh == med["LH"]))
    cy, cx = np.array(lh.shape) // 2
    i = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
    py, px = int(ys[i]), int(xs[i])
    th = float(inc[py, px])
    pix = {"line": py, "sample": px, "DN_LH": float(lh[py, px]), "DN_LV": float(lv[py, px]),
           "theta_inc_raster_deg": th, "sin_theta": math.sin(math.radians(th))}
    for c, dn in (("LH", pix["DN_LH"]), ("LV", pix["DN_LV"])):
        s = dn ** 2 * pix["sin_theta"] / (k_lin * g[c] ** 2)
        pix[f"sigma0_{c}_linear"] = s
        pix[f"sigma0_{c}_db"] = db(s)
    print(f"  pixel ({py}, {px}): DN {pix['DN_LH']:.0f}/{pix['DN_LV']:.0f}, theta "
          f"{th:.4f} deg -> sigma0 LH {pix['sigma0_LH_db']:+.3f} dB, LV {pix['sigma0_LV_db']:+.3f} dB")

    # ---- 3. how many times did the stored output apply sin(theta)? ----------
    k = np.ones((5, 5), np.float32) / 25.0
    sin_r = np.sin(np.deg2rad(inc)).astype(np.float32)
    lh32, lv32 = lh.astype(np.float32), lv.astype(np.float32)
    code_path = {}
    stored_s0 = tifffile.imread(str(S0_STORED)).astype(np.float64) if S0_STORED.is_file() else None
    stored_cpr = tifffile.imread(str(CPR_STORED)).astype(np.float64) if CPR_STORED.is_file() else None
    eroded = cv2.erode(amp.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    for n_app in (0, 1, 2):
        w = sin_r ** n_app if n_app else np.float32(1.0)
        bl = cv2.filter2D(lh32 ** 2 * w / np.float32(k_lin * g["LH"] ** 2), -1, k)
        bv = cv2.filter2D(lv32 ** 2 * w / np.float32(k_lin * g["LV"] ** 2), -1, k)
        row = {}
        if stored_s0 is not None:
            s0 = cv2.resize((bl + bv).astype(np.float32), (stored_s0.shape[1], stored_s0.shape[0]),
                            interpolation=cv2.INTER_AREA).astype(np.float64)
            ok = stored_s0 > 0
            rel = np.abs(s0[ok] / stored_s0[ok] - 1.0)
            row["s0_real_rel_diff"] = {"median": float(np.median(rel)), "p99": float(np.percentile(rel, 99)),
                                       "max": float(rel.max()), "n": int(ok.sum())}
        if stored_cpr is not None:
            sh, sv = np.sqrt(np.maximum(bl, 0)), np.sqrt(np.maximum(bv, 0))
            cpr = 0.5 * (sh - sv) ** 2 / (0.5 * (sh + sv) ** 2 + 1e-8)
            d = np.abs(cpr[eroded] - stored_cpr[eroded])
            row["cpr_native_abs_diff"] = {"median": float(np.median(d)), "max": float(d.max()),
                                          "n": int(eroded.sum())}
        code_path[f"{n_app}_applications"] = row
        print(f"  {n_app} x sin(theta): "
              + "  ".join(f"{k_}: median {v['median']:.2e} max {v['max']:.2e}"
                          for k_, v in row.items()))
    # the hypothesis the stored rasters match
    best = min(code_path, key=lambda h: code_path[h].get("cpr_native_abs_diff", {}).get("max", 1e9))
    matched = best == "1_applications"
    print(f"  stored rasters match: {best}  ->  {'applied exactly once' if matched else 'NOT once'}")

    # ---- 4. every sin(theta) in the tracked scripts ----------------------------
    uses = []
    for f in sorted((BASE_DIR / "backend").rglob("*.py")):
        rel = f.relative_to(BASE_DIR).as_posix()
        if rel.endswith("calibration_example.py"):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"(?:np|math)\.sin\((?:np\.deg2rad|math\.radians)\((?:inc|inc_deg|lab\[)", line):
                uses.append({"file": rel, "line": n, "code": line.strip()[:110]})
    roles = {
        "backend/scripts/process_real_sar_pipeline.py": "PRODUCTION: DN^2 x sin / (K G^2), once, before the boxcar",
        "backend/scripts/sanity_check_sar.py": "diagnostic replica of the production equation",
        "backend/scripts/cpr_significance.py": "native-grid proxy recomputation; same single application",
        "backend/scripts/incidence_audit.py": "ablation: with and without, never twice",
        "backend/scripts/propagation_percentiles.py": "ablation: with and without, never twice",
        "backend/scripts/measure_enl.py": "scene sigma0 at the label's theta, for the NESZ comparison",
        "backend/scripts/stokes_from_slc.py": "SLC calibration at the label's theta; common, cancels in ratios",
        "backend/scripts/enl_benchmark.py": "SLC arm calibration at the label's theta; common, cancels",
    }
    for u in uses:
        u["role"] = roles.get(u["file"], "UNCLASSIFIED -- inspect")
    unclassified = [u for u in uses if u["role"].startswith("UNCLASSIFIED")]

    # ---- 5. what the label declares ------------------------------------------
    kw = sorted(set(m.group(0).lower() for m in re.finditer(
        r"sigma0|sigma_0|beta0|beta_0|gamma0|gamma_0|normali[sz]\w*|radiometric\w*|"
        r"incidence_correct\w*|terrain_correct\w*", xml, re.I)))
    label_decl = {"normalization_keywords_found": kw,
                  "processing_level": re.search(r"<processing_level>([^<]+)<", xml).group(1),
                  "declares_normalization": bool(kw)}
    print(f"  label normalization keywords: {kw or 'none'}")

    OUT.write_text(json.dumps({
        "schema": "lunar-ice/calibration-example/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/calibration_example.py",
        "review_item": "M3",
        "product": LABEL.name,
        "equation": "sigma0_X = DN_X^2 sin(theta_inc) / (K G_X^2), K = 10^(K_dB/10)",
        "inputs": {"K_db": k_db, "K_db_unit": "dB", "K_lin": k_lin, "G": g,
                   "theta_label_deg": theta_label,
                   "theta_raster_median_over_amplitude_deg": theta_raster_med,
                   "median_DN": med, "nesz_linear": nesz,
                   "amplitude_pixels": int(amp.sum())},
        "scene_example": {
            "definition": ("the median LH DN over the amplitude mask at the label's "
                           "incidence, as Section III-A's NESZ comparison states it"),
            **scene, "manuscript_prints": printed,
            "reproduced_by": reproduces,
            "note": ("the printed -20.3 and -47.6 dB are reproduced WITHOUT the gain "
                     "G_LH = 1.018442; with it the amplitude reading is "
                     f"{scene['amplitude_reading_with_G_db']:.2f} dB and the intensity "
                     f"reading {scene['intensity_reading_with_G_db']:.2f} dB. The "
                     "0.16 dB changes neither margin to the -31.5 dB floor.")},
        "pixel_example": pix,
        "incidence_applied_once": {
            "method": ("recompute the pipeline's stored rasters from the raw DN with "
                       "sin(theta) applied 0, 1 and 2 times; the boxcar makes the "
                       "three distinguishable"),
            "stored": [str(S0_STORED.relative_to(BASE_DIR)).replace("\\", "/"),
                       str(CPR_STORED.relative_to(BASE_DIR)).replace("\\", "/")],
            "comparison": code_path, "matches": best,
            "verdict": "PASS" if matched else "FAIL"},
        "sin_theta_in_code": {"uses": uses, "unclassified": len(unclassified)},
        "label_declaration": label_decl,
        "not_decidable": ("whether ISRO applied an incidence normalization before "
                          "writing the DN: the label declares none (no sigma0/beta0/"
                          "gamma0 or normalization field) and no layer records one; "
                          "terrain backscatter's own incidence dependence cannot be "
                          "separated from a normalization in the data"),
        "run_info": run_info(),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}")
    return 0 if matched and not unclassified else 1


if __name__ == "__main__":
    raise SystemExit(main())
