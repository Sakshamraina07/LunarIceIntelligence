"""
slc_chain.py -- what is applied to the SLC before the Stokes vector is formed,
and what the instrument documentation says about polarimetric non-ideality.
(v18a referee reports, N7a and N7b; N7c, the ellipticity propagation, is
written into the same artifact by snr_control.py)

    python backend/scripts/slc_chain.py

N7a is read from stokes_from_slc.build_coherency and the SLI labels of both
passes, not typed: each item says whether it is applied and with what value.
N7b records what the DFSAR instrument paper states (Bhiravarasu et al. 2021,
PSJ 2:134; read in its arXiv HTML version 2104.14259v1, whose section
numbering is quoted) and what a search of every document in both bundles
found (handedness.py). Quotations are kept to short fragments; the section and
table are given so the source can be read in full.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runinfo import run_info  # noqa: E402
import stokes_from_slc as SFS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
OUT = BASE_DIR / "docs" / "slc_chain.json"
HAND = BASE_DIR / "docs" / "handedness.json"

INSTRUMENT_PAPER = {
    "citation": ("S. S. Bhiravarasu et al., 'Chandrayaan-2 Dual-frequency Synthetic Aperture Radar "
                 "(DFSAR): Performance Characterization and Initial Results', Planet. Sci. J. 2:134 (2021), "
                 "doi:10.3847/PSJ/abfdbf; read as arXiv:2104.14259v1 (HTML)"),
    "transmit_circular_sense": {
        "value": "left-hand circular (LHCP) is the default transmit setting of the hybrid-polarimetric mode",
        "fragment": "LHCP (Left Hand Circular Polarity on transmission) mode is the default setting",
        "where": "Sec. III.2, DFSAR pre-flight (lab) characterization",
        "note": "handedness verified in the lab with helical antennas of each sense (same section)"},
    "axial_ratio": {
        "spec_L_hybrid_db": 0.4, "spec_S_hybrid_db": 1.1,
        "where_spec": "Table 1 (top-level specifications)",
        "measured_min_L_db": 0.39,
        "fragment": "minimum axial ratio of 0.39 dB",
        "where_measured": "Sec. III.2 and Fig. 1 (axial ratio for the DFSAR modes)"},
    "isolation_crosstalk": {
        "cross_polarization_isolation": ">> 30 dB",
        "where": "Table 1",
        "calibration_note": ("cross-talk and channel imbalance are estimated iteratively in the "
                             "full-polarimetric calibration (Sec. III.4.2); a compact-pol L-band phase "
                             "correction of about 40 deg is reported in Sec. III.4.3"),
        "phase_stability": "co- and cross-pol phases stable within about +/-10 deg across acquisitions (Sec. III.4.2)"},
    "page_numbers": ("the arXiv HTML carries no page numbers; the PSJ article's pages are not given here "
                     "because they were not read"),
}


def chain_for(pid: str) -> dict:
    SFS.configure(pid)
    lab = SFS.label_fields()
    src_code = inspect.getsource(SFS.build_coherency)
    xml = (SFS.RAW / f"{SFS.STEM}_d_sli_xx_cp_xx_d18.xml").read_text(encoding="utf-8", errors="replace")
    bias = re.findall(r"<isda:polarization>(\w+)</isda:polarization>.*?<isda:bias_real>([^<]+)<.*?"
                      r"<isda:bias_imag>([^<]+)<", xml, re.S)
    nes = re.findall(r"<isda:polarization>(\w+)</isda:polarization>.*?<isda:nes0_coeff_1>([^<]+)<.*?"
                     r"<isda:nes0_coeff_0>([^<]+)<", xml, re.S)
    k_db = lab["calibration_constant_db"]
    return {
        "pass": pid, "product": f"{SFS.STEM}_d_sli_xx_cp_xx_d18",
        "K": {"applied": True, "value_db": k_db, "source": "SLI label isda:calibration_constant",
              "note": "the SLI label's value, not the SRI's 70.308868; common to both channels, cancels in CPR and DOP"},
        "G_per_channel": {"applied": True, "LH": lab["gain_imbalance"]["LH"], "LV": lab["gain_imbalance"]["LV"],
                          "how": "divides |E_H|^2 by G_LH^2, |E_V|^2 by G_LV^2 and <E_H E_V*> by G_LH G_LV "
                                 "(amplitude factors)"},
        "sin_theta": {"applied": True, "value": float(__import__("math").sin(__import__("math").radians(
            lab["incidence_angle_deg"]))), "theta_deg": lab["incidence_angle_deg"],
            "how": "one scalar from the label's incidence_angle, common to both channels: cancels in CPR and DOP"},
        "nesz_subtraction": {"applied": False,
                             "label_nes0_coefficients": {p_: {"coeff_1": float(a), "coeff_0": float(b)} for p_, a, b in nes},
                             "note": "the noise-corrected variant is a sensitivity run in snr_control.json"},
        "dc_bias": {"applied": False, "label_bias": {p_: {"real": float(a), "imag": float(b)} for p_, a, b in bias}},
        "crosstalk_or_phase_calibration": {
            "applied": False,
            "label_phase_orthogonality": lab["phase_orthogonality"],
            "label_phase_orthogonality_unit": "not stated in the label",
            "note": ("read and recorded, never applied; the measured inter-channel phase clusters at -88.3 deg "
                     "(stokes_from_slc.json::results.sign.phase_evidence), and a +/-5 deg rotation is propagated "
                     "in phase_gain_perturbation.json")},
        "averaging": {"order": "1. per-line |E|^2 and E_H E_V* ; 2. mean over 21 consecutive azimuth lines "
                               "(reshape; the label's azimuth_looks); 3. calibration scale; 4. 5 x 5 boxcar "
                               "on the three coherency elements (boxcar2d, edge padding); 5. Stokes, CPR, DOP",
                      "azimuth_samples": SFS.AZIMUTH_LOOKS, "boxcar": SFS.BOXCAR,
                      "boxcar_on": "the coherency elements, never on a ratio",
                      "verified_in_code": all(t in src_code for t in ("mean(axis=1)", "boxcar2d(hh)", "boxcar2d(hv.real)"))},
        "zero_samples": ("zero SLC samples enter the 21-line mean as zeros; a cell is used only where the boxcar'd "
                         "|E_H|^2, |E_V|^2 and S0 are positive (and SC, OC > 0 for CPR). Cells whose 5 x 5 window "
                         "holds zero samples are kept ('partial window'); snr_control.json tabulates them separately"),
    }


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    hand = json.loads(HAND.read_text(encoding="utf-8"))
    doc.update({
        "schema": "lunar-ice/slc-chain/1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "generator": "backend/scripts/slc_chain.py (N7a, N7b); snr_control.py (N7c, key 'ellipticity')",
        "seed": None, "seed_note": "no random draws",
        "chain": {pid: chain_for(pid) for pid in ("20200808", "20200305")},
        "instrument_paper": INSTRUMENT_PAPER,
        "bundle_search": {"source": "handedness.json",
                          "transmit_or_handedness_statement_found": hand["transmit_or_handedness_statement_found"],
                          "text_files_scanned": hand["search"]["text_files_scanned"],
                          "axial_ratio_or_isolation_in_bundles": False,
                          "terms_searched": ["axial", "isolation", "crosstalk", "cross-talk", "cross_talk",
                                             "ellipticity", "orthogonality", "transmit", "handed", "circular"],
                          "note": ("no label or document in either bundle states an axial ratio, ellipticity or "
                                   "isolation figure; the only polarimetric non-ideality field is "
                                   "isda:phase_orthogonality, one value per receive channel, unit not stated "
                                   "(this pass LH 1.074722, LV 0.467679)")},
        "run_info_chain": run_info()})
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    hand["instrument_paper"] = {k: INSTRUMENT_PAPER[k] for k in ("citation", "transmit_circular_sense")}
    hand["verdict_v18"] = ("the bundles state no transmit sense; the DFSAR instrument paper states LHCP as the "
                           "default hybrid-pol transmit (Sec. III.2). The physical check is unchanged: the adopted "
                           "180 deg reading puts 98.49 % of cells below CPR 1")
    HAND.write_text(json.dumps(hand, indent=2), encoding="utf-8")
    print(json.dumps(doc["chain"]["20200808"], indent=1)[:1500])
    print(f"  wrote {OUT.relative_to(BASE_DIR)}; updated {HAND.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
