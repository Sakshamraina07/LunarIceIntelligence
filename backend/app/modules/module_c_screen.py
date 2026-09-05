"""
MODULE C (live): the ice CRITERIA SCREEN.

This replaces `module_c_ice.evaluate_ice_intelligence` as the wired
implementation. `module_c_ice.py` is still on disk, with a header explaining
why it is unwired; nothing imports it.

WHAT CHANGED AND WHY
--------------------
The previous Module C produced two things: a criteria mask, and a Random Forest
probability P(ice). The probability was the problem. The model was fitted to
`np.random.uniform` labels with a fixed seed, and its positive class was defined
as CPR in 1.05-2.5 — a range this product cannot reach at all, because its peak
CPR over the whole measured swath is 0.0534. Every probability it emitted was an
extrapolation from fabricated examples, and one of its six input features was
the illumination proxy, itself invented. It was not retrained on better
synthetic labels, because better synthetic labels are still synthetic.

What remains is the part that was always measured:

    candidate = (cpr > CPR_THRESHOLD) & (dop < DOP_THRESHOLD) & measured

Two thresholds from `config.py`, applied to calibrated radar. No model, no
seed, nothing to extrapolate.

THE PSR TERM IS ALSO GONE, AND THAT IS DELIBERATE
-------------------------------------------------
The old mask ANDed in `psr_mask`, which comes from the illumination proxy —
`hillshade(sun 1.5°) * elev_norm**1.3`, an invented brightness expression that
darkens 77 % of the frame. Intersecting with it did not discriminate a cold
trap; it multiplied by a large arbitrary mask while making a MEASURED-marked
area partly modelled. The shadow criteria are reported separately and read
UNAVAILABLE until the Phase 2 horizon computation exists.

EVIDENCE CHECKLIST TRI-STATE
----------------------------
`evidence_checklist` values are `True` / `False` / `None`. `None` means the
criterion could not be evaluated in this build — it is not a failure. Collapsing
"never tested" into "tested and failed" is the same class of error as reporting
a placeholder where a measurement belongs.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional

from app.core.config import settings
from app.core.schemas import IceIntelligenceResult
from app.core.provenance import create_provenance

#: Why P(ice) is absent rather than zero. Referenced, not retyped, so the API
#: and the static analysis cannot drift into two different explanations.
ML_WITHDRAWN = (
    "WITHDRAWN. The Random Forest was fitted to np.random.uniform labels (seed 42) whose positive "
    "class was defined as CPR 1.05-2.5, a range this amplitude-only product cannot reach — peak CPR "
    "over the measured swath is 0.0534. Every prediction was therefore an extrapolation from "
    "fabricated examples, and one of its six features was the invented illumination proxy. Unwired in "
    "PRD Phase 1C; not retrained, because better synthetic labels are still synthetic."
)

SHADOW_WITHHELD = (
    "Withheld: this build has no horizon computation, only a brightness proxy that darkens 77 % of "
    "the frame. Phase 2 replaces it."
)

THERMAL_WITHHELD = (
    "Withheld: no thermal product is on disk and no thermal model runs here. The previous "
    "implementation returned True whenever the candidate count was non-zero, which restated the "
    "screening result rather than testing a temperature."
)


def screen_ice_criteria(
    crater_id: str,
    cpr: np.ndarray,
    dop: np.ndarray,
    spacing_m: Tuple[float, float],
    measured_mask: Optional[np.ndarray] = None,
    cpr_threshold: Optional[float] = None,
    dop_threshold: Optional[float] = None,
    *,
    data_mode: str,
) -> Tuple[IceIntelligenceResult, Dict[str, np.ndarray]]:
    """
    The measured two-criterion screen.

    `spacing_m` is (metres_per_line, metres_per_sample) for the grid the rasters
    are on; the candidate area is cells x sy x sx and nothing else.

    `measured_mask` restricts the screen to cells that carry radar. When it is
    omitted the whole grid is treated as measured, which is only correct for a
    grid that has no padding in it.
    """
    cpr_th = cpr_threshold if cpr_threshold is not None else settings.CPR_THRESHOLD
    dop_th = dop_threshold if dop_threshold is not None else settings.DOP_THRESHOLD
    cell_area_km2 = (spacing_m[0] / 1000.0) * (spacing_m[1] / 1000.0)

    measured = (np.ones(cpr.shape, dtype=bool) if measured_mask is None
                else np.asarray(measured_mask, dtype=bool))

    cpr_pass = (cpr > cpr_th) & measured
    dop_pass = (dop < dop_th) & measured
    candidate_mask = cpr_pass & dop_pass

    candidate_cells = int(np.sum(candidate_mask))
    candidate_area_km2 = float(candidate_cells * cell_area_km2)
    measured_cells = int(np.sum(measured))

    peak_cpr = float(np.max(cpr[measured])) if measured_cells else 0.0
    median_dop = float(np.median(dop[measured])) if measured_cells else 0.0

    # Confidence describes the SCREEN, not a probability. It can reach every
    # level it names; the previous implementation could never report anything
    # but "Low" because its Medium and High branches both required mean_prob
    # from the withdrawn model.
    if candidate_cells == 0:
        confidence = "Low"
    elif candidate_cells * cell_area_km2 >= 1.0:
        confidence = "High"
    else:
        confidence = "Medium"

    evidence_checklist: Dict[str, Optional[bool]] = {
        "cpr_above_threshold": bool(peak_cpr > cpr_th),
        "dop_below_threshold": bool(median_dop < dop_th),
        "psr_cold_trap_overlap": None,
        "doubly_shadowed_core_overlap": None,
        "thermal_stability_expected": None,
    }

    if candidate_cells > 0:
        headline = (
            f"Criteria screen: {candidate_cells:,} cells ({candidate_area_km2:.4f} km²) of "
            f"{measured_cells:,} measured pass CPR > {cpr_th:.2f} AND DOP < {dop_th:.2f}."
        )
    else:
        headline = (
            f"Criteria screen: NULL RESULT. No cell of the {measured_cells:,} measured passes both "
            f"CPR > {cpr_th:.2f} and DOP < {dop_th:.2f}. Peak CPR is {peak_cpr:.4f}, "
            f"{cpr_th / max(peak_cpr, 1e-9):.0f}x below the threshold."
        )

    explainability_notes = [
        headline,
        f"CPR criterion: {int(cpr_pass.sum()):,} of {measured_cells:,} measured cells "
        f"({float(cpr_pass.sum()) / max(measured_cells, 1) * 100:.3f} %) exceed {cpr_th:.2f}.",
        f"DOP criterion: {int(dop_pass.sum()):,} of {measured_cells:,} measured cells "
        f"({float(dop_pass.sum()) / max(measured_cells, 1) * 100:.3f} %) fall below {dop_th:.2f}. "
        "A depressed DOP is consistent with volume scattering, but on its own it does not "
        "discriminate ice from fine dry regolith.",
        f"Shadow criteria: {SHADOW_WITHHELD}",
        f"Thermal criterion: {THERMAL_WITHHELD}",
        f"P(ice): {ML_WITHDRAWN}",
        "Limitation: a radar screen cannot confirm ice. Ground truth by drilling or spectroscopy is "
        "required, and this build derives CPR from amplitude alone rather than from the Stokes S3 "
        "phase term the CBOE threshold refers to.",
    ]

    provenance = create_provenance(
        dataset_name=f"{crater_id.upper()}_ICE_SCREEN",
        algorithm="Dual-threshold polarimetric criteria screen (no classifier)",
        parameters={
            "cpr_threshold": cpr_th,
            "dop_threshold": dop_th,
            "mask": "(cpr > cpr_th) & (dop < dop_th) & measured_mask",
            "spacing_m": [float(spacing_m[0]), float(spacing_m[1])],
            "measured_cells": measured_cells,
            "classifier": "none — see ml_model_status",
        },
        data_mode=data_mode,
    )

    result = IceIntelligenceResult(
        crater_id=crater_id,
        scientific_candidate_area_km2=round(candidate_area_km2, 4),
        ml_ice_likelihood_mean=None,
        ml_ice_likelihood_max=None,
        ml_model_status=ML_WITHDRAWN,
        confidence=confidence,
        scientific_screening_status="PASS" if candidate_cells > 0 else "FAIL",
        evidence_checklist=evidence_checklist,
        explainability_notes=explainability_notes,
        provenance=provenance,
    )

    rasters = {
        "scientific_candidate_mask": candidate_mask,
        "cpr_pass_mask": cpr_pass,
        "dop_pass_mask": dop_pass,
    }

    return result, rasters
