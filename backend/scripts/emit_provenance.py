"""
emit_provenance.py -- generate docs/PROVENANCE.md from the analysis asset.

    python backend/scripts/emit_provenance.py [crater_id ...]

WHY THIS IS GENERATED AND NOT WRITTEN
-------------------------------------
This document is the one a reviewer is handed: every number the mission screen
can display, what produced it, and what its limitation is. Fifty-four rows typed
by hand stop being evidence the moment Phase 2 lands and PSR area becomes real --
they become prose that used to be true. So the table is emitted from the SAME
`frontend/public/analysis/<crater>.json` the UI reads, and regenerating it is one
command.

IT IS ALSO A GATE, NOT A REPORT
-------------------------------
SIX assertions run before anything is written, and each one exits non-zero.
Every one of them was verified by injecting the violation it guards against:

  1. NO VALUE MAY REACH THE UI UNMARKED. A missing `provenance` field is a
     build failure, not a blank cell.
  2. NO VALUE MAY BE MARKED `MODELLED`. This is the machine-checkable proof that
     the random-label Random Forest no longer reaches a screen. It is asserted
     precisely BECAUSE the expected count is zero: a count printed in a report
     can drift back up unnoticed, an assertion cannot. If a genuinely modelled
     quantity is ever added -- the Phase 2 illumination fraction is the obvious
     candidate -- this assertion is the thing that forces a deliberate decision
     about how it is labelled, which is the point.
  3. AN ABSENT VALUE MUST CARRY A REASON. `value: null` with no `reason` renders
     as a bare em dash, which is indistinguishable from a layout bug.
  4. THE MARK MUST BE ONE OF THE FOUR. An unrecognised string would render a
     badge that no longer means what the legend says it means.
  5. A VALUE MUST LIE IN THE RANGE ITS UNIT ALLOWS. See assert_units(): Phase 1
     shipped a correctly-measured, correctly-marked, correctly-traced value to
     the screen as "0.897 %" for a surface that is 89.7 % traversable. Provenance
     discipline does not catch a unit error. This does.
  6. THE AMPLITUDE-ONLY ICE SCREEN MUST RETURN EXACTLY ZERO. See
     assert_amplitude_screen_is_empty(): while CPR is derived from amplitude
     alone it is a strictly increasing function of DOP, so "CPR > a AND DOP < b"
     is empty for every a above tanh^2(artanh(b)/2). A non-zero candidate area
     under those conditions is arithmetically impossible and is therefore a bug,
     never a discovery.

THE `RESOLVED BY` COLUMN
------------------------
Fourteen of the fifty-four values are UNAVAILABLE. Without a column naming the
phase that fills each one, the document reads as fourteen gaps. With it, it reads
as fourteen dated items -- which is what they are. The mapping is declared in
RESOLVED_BY below and is keyed on the value name, so a value that is neither
resolved nor deliberately permanent shows up as UNSCHEDULED rather than being
quietly omitted.
"""
from __future__ import annotations

import json
import sys
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

ANALYSIS_DIR = BASE_DIR / "frontend" / "public" / "analysis"
OUT = BASE_DIR / "docs" / "PROVENANCE.md"

MEASURED = "MEASURED"
MODELLED = "MODELLED"
DERIVED = "DERIVED"
UNAVAILABLE = "UNAVAILABLE"

#: Which phase fills each currently-absent value. Keyed by value name, longest
#: prefix wins. `None` means permanently absent in this project (see §5 of the
#: PRD, "out of scope"), which is a different statement from "not yet".
RESOLVED_BY = {
    "psr_area_km2": "Phase 2 — horizon computation over the full LDEM_80S_80M array",
    "doubly_shadowed_area_km2": "Phase 2 — sky-view factor restricted to lit horizon",
    "mean_illumination_fraction": "Phase 2 — per-pixel lit fraction over a 360° solar azimuth sweep",
    "thermal_stability_k": "Phase 2 — DERIVED from illumination; no thermal product is on disk",
    "landing_site": "Phase 3 — per-pixel six-criterion search over the native frame",
    "landing_site_score": "Phase 3",
    "landing_sites_evaluated": "Phase 3",
    "rover_traverse_km": "Phase 4 — Dijkstra over a slope-and-hazard cost surface",
    "rover_energy_wh": "Phase 4",
    "rover_mean_hazard": "Phase 4",
    "ablation_runs": "Phase 4 — replan with each hazard weight zeroed in turn",
    "p_ice_max": "NEVER — withdrawn, not deferred. No ground-truth ice label exists in this project.",
    "p_ice_mean": "NEVER — withdrawn, not deferred.",
    "boulder_risk": "NEVER in this build — no optical product; WEIGHT_BOULDER = 0 (PRD §5)",
}

#: Which raster each value is read from. Keyed by prefix, longest match wins.
SOURCE_RASTER = {
    "cpr": "native/cpr_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask)",
    "dop": "native/dop_native.tif (Chandrayaan-2 DFSAR L2, amplitude mask)",
    "screening": "native/cpr_native.tif + native/dop_native.tif",
    "candidate": "native/cpr_native.tif + native/dop_native.tif",
    "criteria": "native/cpr_native.tif + native/dop_native.tif",
    "measured_area": "native/valid_native.tif",
    "pointed_area": "native/footprint_native.tif (ISRO sri_ma)",
    "slope": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "max_slope": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "mean_slope": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "safe_slope": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "landable_slope": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "roughness": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "mean_roughness": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "hazard": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "mean_hazard": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "critical_hazard": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "min_elevation": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "max_elevation": "native/dem_native.tif = LOLA LDEM_80S_80M V2.0",
    "conservative_volume": "derived from candidate area — no raster of its own",
    "expected_volume": "derived from candidate area — no raster of its own",
    "upper_volume": "derived from candidate area — no raster of its own",
}


def longest_prefix(table: dict, key: str, default: str) -> str:
    best = None
    for prefix in table:
        if key.startswith(prefix) and (best is None or len(prefix) > len(best)):
            best = prefix
    return table[best] if best else default


def generator_line(key: str, src_lines: list[str]) -> str:
    """The build_analysis.py line that emits this value, found by search."""
    needle = '"%s": val(' % key
    for i, line in enumerate(src_lines, 1):
        if needle in line:
            return "build_analysis.py:%d" % i
    return "build_analysis.py (line not located)"


def one_line(text: str, limit: int = 240) -> str:
    """Collapse a reason or note onto one Markdown table cell."""
    t = " ".join(str(text or "").split()).replace("|", "\\|")
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def assert_marks(doc: dict, crater: str) -> dict:
    """The three gates. Each exits non-zero rather than writing a document."""
    values = doc.get("values") or {}
    counts = {MEASURED: 0, MODELLED: 0, DERIVED: 0, UNAVAILABLE: 0}

    unmarked = [k for k, v in values.items() if not v.get("provenance")]
    if unmarked:
        raise SystemExit(
            "PROVENANCE GATE FAILED (%s): %d value(s) reach the UI with no mark: %s\n"
            "A number without a defensible mark does not ship. Fix build_analysis.py."
            % (crater, len(unmarked), ", ".join(sorted(unmarked)))
        )

    unknown = sorted({v["provenance"] for v in values.values()} - set(counts))
    if unknown:
        raise SystemExit(
            "PROVENANCE GATE FAILED (%s): unrecognised mark(s) %s. The legend is "
            "MEASURED / MODELLED / DERIVED / UNAVAILABLE." % (crater, unknown)
        )

    for v in values.values():
        counts[v["provenance"]] += 1

    if counts[MODELLED]:
        modelled = sorted(k for k, v in values.items() if v["provenance"] == MODELLED)
        raise SystemExit(
            "PROVENANCE GATE FAILED (%s): %d value(s) marked MODELLED: %s\n"
            "This assertion exists because the expected count is ZERO -- it is the "
            "machine-checkable proof that the random-label Random Forest no longer "
            "reaches a screen. If a genuinely modelled quantity is being added, that "
            "is a deliberate decision: change this assertion, and say so in the PRD."
            % (crater, counts[MODELLED], ", ".join(modelled))
        )

    silent = [k for k, v in values.items() if v.get("value") is None and not v.get("reason")]
    if silent:
        raise SystemExit(
            "PROVENANCE GATE FAILED (%s): %d absent value(s) carry no reason: %s\n"
            "An em dash with no explanation is indistinguishable from a layout bug."
            % (crater, len(silent), ", ".join(sorted(silent)))
        )

    assert_units(doc, crater)
    assert_amplitude_screen_is_empty(doc, crater)
    return counts


def assert_units(doc: dict, crater: str) -> None:
    """
    GATE 5 -- a value's UNIT is part of its contract.

    Phase 1 shipped `safe_slope_fraction` to the screen as "0.897 %" for a
    surface that is 89.7 % traversable. That value was measured, correctly
    marked MEASURED, and correctly traced to the raster it came from -- and it
    was still wrong, because the component rendered a fraction as a percentage
    without scaling it. Provenance discipline does not catch a unit error. Only
    the browser pass caught it, and a browser pass is not run on every rebuild.

    So the ranges are asserted here, where they are cheap and automatic:

        unit "%"        value must lie in [0, 100]
        unit ""  + a name ending _fraction   value must lie in [0, 1]
        unit "km²"      value must not exceed the frame area
        unit "°"        value must lie in [0, 90] for a slope

    These are deliberately loose. They cannot catch a wrong number; they catch a
    number that is not even in the right space, which is the class of error that
    survived every other check in this file.
    """
    values = doc.get("values") or {}
    frame_km2 = float((doc.get("grid") or {}).get("frame_area_km2") or 0.0)
    bad = []

    for key, rec in values.items():
        v = rec.get("value")
        if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        unit = (rec.get("unit") or "").strip()

        if unit == "%" and not (0.0 <= v <= 100.0):
            bad.append((key, v, unit, "a percentage must lie in [0, 100]"))
        elif unit == "" and key.endswith("_fraction") and not (0.0 <= v <= 1.0):
            bad.append((key, v, unit, "a _fraction must lie in [0, 1]"))
        elif unit == "km²" and frame_km2 and v > frame_km2 * 1.000001:
            bad.append((key, v, unit,
                        "exceeds the %.2f km² frame — an area inside the frame cannot" % frame_km2))
        elif unit == "°" and "slope" in key and not (0.0 <= v <= 90.0):
            bad.append((key, v, unit, "a slope in degrees must lie in [0, 90]"))

    if bad:
        lines = "\n".join("    %-28s %-16r unit %-4r  %s" % (k, v, u, why) for k, v, u, why in bad)
        raise SystemExit(
            "PROVENANCE GATE FAILED (%s): %d value(s) are outside the range their unit allows:\n%s\n"
            "A correct number rendered in the wrong units is no better than an invented one."
            % (crater, len(bad), lines)
        )


def assert_amplitude_screen_is_empty(doc: dict, crater: str) -> None:
    """
    GATE 6 -- the amplitude-only ice screen is EMPTY BY CONSTRUCTION.

    While CPR is formed from amplitude alone, CPR and DOP are two
    reparameterisations of one channel ratio x = ln(lh/lv):

        cpr = tanh²(x/4)        dop = |tanh(x/2)|        cpr = tanh²(artanh(dop)/2)

    so DOP < dop_th places a hard ceiling tanh²(artanh(dop_th)/2) on achievable
    CPR. With dop_th = 0.13 that ceiling is 0.0042611, and the configured
    CPR_THRESHOLD of 1.00 is 235x above it. The conjunction cannot be satisfied
    by any pixel, of any terrain, from any instrument.

    Therefore a non-zero candidate area under those conditions is arithmetically
    impossible, and if one ever appears it is a BUG -- a broken mask, a swapped
    threshold, a changed CPR source that nothing else noticed -- and never a
    discovery. This gate is what makes that distinction automatic instead of
    depending on somebody remembering the algebra.

    See docs/METHODS.md for the derivation and the numerical verification.
    """
    ident = doc.get("cpr_dop_identity")
    if not ident:
        return  # a crater built before the identity was recorded; nothing to assert
    if ident.get("cpr_source") != "amplitude-only":
        return  # Phase 5b landed: CPR and DOP are independent again, gate retires

    if not ident.get("screen_is_empty_by_construction"):
        return  # threshold is at or below the ceiling; a non-zero area is legitimate

    area = ((doc.get("values") or {}).get("candidate_area_km2") or {}).get("value")
    if area not in (0, 0.0):
        raise SystemExit(
            "PROVENANCE GATE FAILED (%s): candidate_area_km2 = %r, but the screen is EMPTY BY\n"
            "CONSTRUCTION and the only arithmetically possible value is exactly 0.0.\n\n"
            "  CPR source        %s\n"
            "  DOP < %-14g implies CPR < %.7f  (ceiling)\n"
            "  CPR_THRESHOLD     %-14g = %.0fx the ceiling\n\n"
            "cpr and dop are both monotone in x = ln(lh/lv) here, so 'cpr > a AND dop < b' is\n"
            "one condition pushing |x| up and another pushing it down on the SAME axis. A\n"
            "non-zero area means something upstream broke — a mask, a threshold, or the CPR\n"
            "source itself — not that ice was found. Investigate before shipping."
            % (crater, area, ident.get("cpr_source"), ident.get("dop_threshold"),
               ident.get("implied_cpr_ceiling"),
               (doc.get("thresholds") or {}).get("cpr_threshold"),
               ident.get("threshold_over_ceiling_ratio") or 0.0)
        )


def render(crater: str, doc: dict, counts: dict, src_lines: list[str]) -> str:
    values = doc["values"]
    grid = doc["grid"]
    amp = doc["masks"]["amplitude"]
    th = doc["thresholds"]

    rows = []
    for key in values:
        rec = values[key]
        mark = rec["provenance"]
        absent = rec.get("value") is None
        shown = "—" if absent else str(rec["value"])
        unit = rec.get("unit") or ""
        if unit and not absent:
            shown = "%s %s" % (shown, unit)

        if absent:
            raster = "—"
            resolved = longest_prefix(RESOLVED_BY, key, "**UNSCHEDULED** — no phase claims this")
            limitation = one_line(rec.get("reason"))
        else:
            raster = longest_prefix(SOURCE_RASTER, key, "—")
            resolved = "—"
            limitation = one_line(rec.get("note") or "—")

        rows.append((key, shown, mark, generator_line(key, src_lines), raster, limitation, resolved))

    order = {MEASURED: 0, DERIVED: 1, MODELLED: 2, UNAVAILABLE: 3}
    rows.sort(key=lambda r: (order[r[2]], r[0]))

    out = []
    w = out.append
    w("# PROVENANCE — every number the mission screen can display\n")
    w("**GENERATED FILE. Do not edit by hand.**\n")
    w("```")
    w("python backend/scripts/emit_provenance.py")
    w("```")
    w("")
    w("Emitted from `frontend/public/analysis/%s.json`, which is the same asset the" % crater)
    w("UI reads — so this table cannot describe a different run than the one on screen.")
    w("The emitter fails the build if any value reaches the UI unmarked, if any value")
    w("is marked `MODELLED`, or if an absent value carries no reason.\n")
    w("---\n")
    w("## The scene\n")
    w("| | |")
    w("|---|---|")
    w("| Crater | %s |" % doc["crater_name"])
    w("| Centre | %.2f°, %.2f° |" % (doc["latitude_deg"], doc["longitude_deg"]))
    w("| Instrument | %s |" % doc["instrument"])
    w("| Product | `%s` |" % (doc.get("product_id") or "—"))
    w("| Observed | %s |" % ((doc.get("observation_date") or "—")[:10]))
    w("| Frame | %d × %d @ %g m/px = %s km² |"
      % (grid["lines"], grid["samples"], grid["metres_per_pixel"],
         "{:,.0f}".format(grid["frame_area_km2"])))
    w("| Measured swath | %s km² (%.3f %% of frame) — every MEASURED radar figure uses this mask only |"
      % ("{:,.2f}".format(amp["area_km2"]), amp["fraction"] * 100))
    w("| Thresholds | CPR > %g, DOP < %g — read from %s, **not retuned** |"
      % (th["cpr_threshold"], th["dop_threshold"], th["source"]))
    w("| Generated | %s |" % doc["generated_utc"])
    w("")
    w("## Mark counts\n")
    w("| Mark | Count | Meaning |")
    w("|---|---:|---|")
    w("| `MEASURED` | %d | An observation, or a direct geometric consequence of one. |" % counts[MEASURED])
    w("| `DERIVED` | %d | An assumption model applied on top of a measured quantity. |" % counts[DERIVED])
    w("| `MODELLED` | %d | **Asserted zero.** A non-zero count fails the build — see the emitter. |" % counts[MODELLED])
    w("| `UNAVAILABLE` | %d | Cannot be computed honestly yet. Each names the phase that fills it. |" % counts[UNAVAILABLE])
    w("| **Unmarked** | **0** | Asserted. A number with no defensible mark does not ship. |")
    w("")
    w("`MODELLED = 0` is the load-bearing row. It is the machine-checkable statement")
    w("that no output of the random-label Random Forest reaches a screen: the model was")
    w("fitted to `np.random.uniform` labels whose positive class was CPR 1.05–2.5, a")
    w("range this amplitude-only product cannot reach, so every probability it produced")
    w("was an extrapolation from fabricated examples. It is unwired, not retrained.\n")
    w("---\n")
    w("## Every value\n")
    w("| Value | Shown | Mark | Computed at | Source raster | Limitation / reason | Resolved by |")
    w("|---|---|---|---|---|---|---|")
    for key, shown, mark, line, raster, limitation, resolved in rows:
        w("| `%s` | %s | `%s` | `%s` | %s | %s | %s |"
          % (key, shown, mark, line, raster, limitation, resolved))
    w("")
    w("---\n")
    w("## Evidence checklist — the five named criteria\n")
    w("| Criterion | Measured | vs threshold | Verdict | Mark |")
    w("|---|---|---|---|---|")
    for e in doc["evidence"]:
        m = "—" if e["measured"] is None else str(e["measured"])
        t = "—" if e["threshold"] is None else "%s %s" % (e["comparison"], e["threshold"])
        verdict = "PASS" if e["passed"] else ("**WITHHELD**" if e["provenance"] == UNAVAILABLE else "FAIL")
        w("| %s | %s (%s) | %s | %s | `%s` |"
          % (e["label"], m, e["measured_label"], t, verdict, e["provenance"]))
    w("")
    w("> %s\n" % one_line(doc["verdict"]["criteria_note"], 600))
    w("> **%s**\n" % one_line(doc["verdict"]["null_result_caveat"], 600))
    w("---\n")
    ident = doc.get("cpr_dop_identity")
    if ident and ident.get("cpr_source") == "amplitude-only":
        w("## Why the ice screen is empty — an identity, not a measurement\n")
        w("This build forms both polarimetric quantities from the same two smoothed")
        w("amplitudes, so with `x = ln(lh/lv)`:\n")
        w("```")
        w("cpr = %s   dop = %s" % (ident["cpr_of_x"], ident["dop_of_x"]))
        w("=>  cpr = %s" % ident["cpr_from_dop"])
        w("```")
        w("")
        w("They are not two observables — they are **two reparameterisations of one**")
        w("**channel ratio**, %d degree of freedom between them. So `DOP < %g` places a hard"
          % (ident["degrees_of_freedom"], ident["dop_threshold"]))
        w("ceiling on achievable CPR:\n")
        w("| | |")
        w("|---|---|")
        w("| Ceiling implied by the DOP gate | **CPR < %.7f** |" % ident["implied_cpr_ceiling"])
        w("| Highest CPR observed where DOP passes | %.7f |" % (ident["max_cpr_where_dop_passes"] or 0.0))
        w("| Configured `CPR_THRESHOLD` | %g — **%.0f× the ceiling** |"
          % ((doc["thresholds"]["cpr_threshold"]), ident["threshold_over_ceiling_ratio"]))
        w("| Identity verified over | %s pixels |" % "{:,}".format(ident["verified_over_pixels"]))
        w("| max\\|residual\\| · rms · Pearson r | %.3e · %.3e · %.12f |"
          % (ident["max_abs_residual"], ident["rms_residual"], ident["pearson_r"]))
        w("")
        w("%s\n" % ident["consequence"])
        w("%s\n" % ident["what_fixes_it"])
        w("---\n")
    w("## Sensitivity — measured, not scaled\n")
    w("Each row re-thresholds the native arrays and counts pixels, so every area is a")
    w("measurement. Marked `●` is the configured operating point.\n")
    for axis in ("cpr_threshold", "dop_threshold"):
        blk = doc["sensitivity"][axis]
        w("### %s (baseline %g)\n" % (axis.replace("_", " "), blk["baseline"]))
        w("| Threshold | Pixels | Area km² | Volume m³ |")
        w("|---|---:|---:|---:|")
        for r in blk["rows"]:
            mark = " ●" if r["is_configured_value"] else ""
            w("| %g%s | %s | %.4f | %s |"
              % (r["threshold"], mark, "{:,}".format(r["candidate_px"]),
                 r["candidate_area_km2"], "{:,.0f}".format(r["volume_m3"])))
        w("")
    w("> %s\n" % one_line(doc["sensitivity"]["note"], 700))
    w("---\n")
    w("## Volume tiers — assumptions carried as data\n")
    w("| Tier | Assumed depth | Assumed pore fraction | Volume | Rate |")
    w("|---|---:|---:|---:|---:|")
    for t in doc["volume_tiers"]:
        w("| %s | %g m | %g | %s m³ | %s m³ per km² |"
          % (t["tier"], t["assumed_depth_m"], t["assumed_pore_fraction"],
             "{:,.0f}".format(t["volume_m3"]), "{:,.0f}".format(t["volume_m3_per_km2"])))
    w("")
    w("---\n")
    w("## What each stage can show\n")
    w("| # | Stage | Status | Basis |")
    w("|---:|---|---|---|")
    for s in doc["steps"]:
        w("| %d | %s | `%s` | %s |" % (s["n"], s["title"], s["status"], one_line(s["basis"], 300)))
    w("")
    return "\n".join(out) + "\n"


def main() -> int:
    craters = sys.argv[1:] or ["faustini"]
    src_lines = (BASE_DIR / "backend" / "scripts" / "build_analysis.py").read_text(
        encoding="utf-8").splitlines()

    chunks = []
    for crater in craters:
        path = ANALYSIS_DIR / f"{crater}.json"
        if not path.is_file():
            raise SystemExit(
                f"{path} missing. Nothing can be documented for {crater}. Run:\n"
                f"    python backend/scripts/build_analysis.py {crater}"
            )
        doc = json.loads(path.read_text(encoding="utf-8"))
        counts = assert_marks(doc, crater)
        chunks.append(render(crater, doc, counts, src_lines))
        print(f"  {crater:12s} {sum(counts.values()):3d} values  "
              f"MEASURED {counts[MEASURED]}  DERIVED {counts[DERIVED]}  "
              f"MODELLED {counts[MODELLED]}  UNAVAILABLE {counts[UNAVAILABLE]}  "
              f"unmarked 0  -> gates PASS")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n\n".join(chunks), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(BASE_DIR)}  ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
