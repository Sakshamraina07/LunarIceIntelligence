"""
v21_carryover_checks.py -- the V20 carry-overs of the v21 work order (W3.2),
recomputed from stored artifacts. Draws nothing.

    python backend/scripts/v21_carryover_checks.py

1. "a coherence-aware estimate differs by 2 %" (39.2 against 40.0):
   tail_calibration_ci.json::logratio_model_coherence_aware.results.20200808_64px.{coherence_aware,standard}.N_hat_train_halves.median.
2. "subtracting the noise in any of the variants run changes F2's selections by at most
   14 % (50 to 43) and no disc rate by more than 1.1 points", over ALL variants in
   snr_control.json: v20_reconciliation.variants_f2 and variants_disc_rates (the nominal
   and beta-0 noise subtractions at constant and range-linear level, the valid-fraction
   normalisation, the projection of non-positive-definite cells, the 3 and 6 dB floors)
   and the top-level f2 / discs_by_variant (which also carry the ellipticity variants,
   NOT noise subtractions). Reported separately so the sentence is tested on the set it
   names and on the whole set.
3. "the 11 dB margin marked nominal": calibration_example.json::scene_example.margin_above_floor_db.
Output docs/v21_carryover_checks.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "v21_carryover_checks.json"


def load(n):
    return json.loads((BASE_DIR / "docs" / n).read_text(encoding="utf-8"))


def main() -> int:
    tc = load("tail_calibration_ci.json")["logratio_model_coherence_aware"]["results"]["20200808_64px"]
    a, s = tc["coherence_aware"]["N_hat_train_halves"]["median"], tc["standard"]["N_hat_train_halves"]["median"]
    c1 = {"coherence_aware_median": a, "standard_median": s, "relative_difference_percent": 100 * (s - a) / s,
          "source": "tail_calibration_ci.json::logratio_model_coherence_aware.results.20200808_64px.*.N_hat_train_halves.median",
          "note": "both medians are over the training halves of the 109 blocks (the standard one is 40.0, not the 39.4 of the whole blocks)"}
    sn = load("snr_control.json")
    rc = sn["v20_reconciliation"]
    # the variants of the reconciliation (nominal/beta0, constant/linear, floors ...)
    f2 = {k: v for k, v in rc["variants_f2"].items()}
    f2_sel = {}
    for k, v in f2.items():
        if isinstance(v, dict):
            x = v.get("20200808", v)
            if isinstance(x, dict) and "published_rule_selects" in x:
                f2_sel[k] = x["published_rule_selects"]
    base = f2_sel.get("base", 50)
    noise_keys = [k for k in f2_sel if k.startswith(("nc_", "legacy"))]
    def pct(k):
        return 100 * (f2_sel[k] - base) / base
    rates = {}
    dr = rc["variants_disc_rates"]
    for k, v in dr.items():
        rates[k] = {kk: (vv["ge1"]["rate"] * 100 if isinstance(vv, dict) and "ge1" in vv else None) for kk, vv in (v if isinstance(v, dict) else {}).items()}
    def maxdiff(keys):
        out = {}
        for cls in ("20200808_outside", "20200808_inside", "20200305_outside", "20200305_inside"):
            vals = [rates[k].get(cls) for k in keys if rates.get(k, {}).get(cls) is not None]
            b = rates.get("base", {}).get(cls)
            if vals and b is not None:
                out[cls] = {"base_percent": b, "min_percent": min(vals), "max_percent": max(vals),
                            "max_abs_change_points": max(abs(x - b) for x in vals)}
        return out
    allk = [k for k in rates if k != "base"]
    # pooled-class rates (all passes) from the top-level discs_by_variant
    top = {}
    for var, d in sn["discs_by_variant"].items():
        k_in = sum(d[c]["ge1"]["k"] for c in d if c.endswith("_inside")); n_in = sum(d[c]["ge1"]["n"] for c in d if c.endswith("_inside"))
        k_out = sum(d[c]["ge1"]["k"] for c in d if c.endswith("_outside")); n_out = sum(d[c]["ge1"]["n"] for c in d if c.endswith("_outside"))
        top[var] = {"sunlit_percent": 100 * k_out / n_out, "shadowed_percent": 100 * k_in / n_in}
    b = top["base"]
    c2 = {"f2_selected_by_reconciliation_variant": f2_sel, "f2_base": base,
          "f2_change_percent_noise_subtraction_variants": {k: pct(k) for k in noise_keys},
          "f2_max_abs_change_percent_noise_subtraction": max(abs(pct(k)) for k in noise_keys) if noise_keys else None,
          "f2_max_abs_change_percent_every_reconciliation_variant": max(abs(pct(k)) for k in f2_sel),
          "f2_selected_top_level_variants": {k: v["published_rule_selects"] for k, v in sn["f2"].items()},
          "f2_max_abs_change_percent_top_level_including_ellipticity": max(abs(100 * (v["published_rule_selects"] - 50) / 50) for v in sn["f2"].values()),
          "disc_rates_reconciliation_variants_ge1_percent": rates,
          "max_change_points_noise_subtraction_variants": maxdiff([k for k in allk if k.startswith(("nc_", "legacy"))]),
          "max_change_points_every_reconciliation_variant": maxdiff(allk),
          "pooled_disc_rates_top_level_variants_percent": top,
          "pooled_max_abs_change_points_sunlit": max(abs(v["sunlit_percent"] - b["sunlit_percent"]) for v in top.values()),
          "pooled_max_abs_change_points_shadowed": max(abs(v["shadowed_percent"] - b["shadowed_percent"]) for v in top.values()),
          "pooled_max_abs_change_points_noise_and_floor_variants": max(
              max(abs(v["sunlit_percent"] - b["sunlit_percent"]), abs(v["shadowed_percent"] - b["shadowed_percent"]))
              for k, v in top.items() if not k.startswith("ellipticity"))}
    ce = load("calibration_example.json")["scene_example"]
    c3 = {"margin_above_floor_db": ce["margin_above_floor_db"], "nesz_LH_db": ce["nesz_LH_db"],
          "amplitude_reading_with_G_db": ce["amplitude_reading_with_G_db"],
          "note": "the margin is relative to the label's NOMINAL nes0; the coherence bound says the nominal level overstates the noise "
                  "(band_s.json::noise_scan: 1.80 % of cells violate |C_HV|^2 <= C_HH C_VV at the nominal level against 0.022 % at 10 dB)"}
    doc = {"schema": "lunar-ice/v21-carryover-checks/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
           "generator": "backend/scripts/v21_carryover_checks.py", "seed": None, "seed_note": "draws nothing",
           "coherence_aware_differs_by_2_percent": c1, "noise_variants": c2, "margin_11_db_nominal": c3,
           "run_info": run_info()}
    OUT.write_text(json.dumps(doc, indent=2, default=float), encoding="utf-8")
    print(f"  1. aware {a:.2f} vs standard {s:.2f}: {c1['relative_difference_percent']:.2f} %")
    print(f"  2. F2 max change, noise-subtraction variants {c2['f2_max_abs_change_percent_noise_subtraction']:.1f} %, every reconciliation variant "
          f"{c2['f2_max_abs_change_percent_every_reconciliation_variant']:.1f} %, top-level incl. ellipticity {c2['f2_max_abs_change_percent_top_level_including_ellipticity']:.1f} %")
    print(f"     pooled disc rates: max change sunlit {c2['pooled_max_abs_change_points_sunlit']:.2f}, shadowed {c2['pooled_max_abs_change_points_shadowed']:.2f} points "
          f"(noise and floors only: {c2['pooled_max_abs_change_points_noise_and_floor_variants']:.2f})")
    print(f"  3. margin {c3['margin_above_floor_db']} dB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
