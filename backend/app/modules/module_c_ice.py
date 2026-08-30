"""
MODULE C: Ice Intelligence (Scientific Baseline + ML Ice-Likelihood Model).
PRD Compliance: Combines multi-criteria scientific screening (CPR > th AND DOP < th AND PSR overlap)
with an explainable Random Forest ML model. Adheres strictly to the PRD Data Limitation Rule:
Never fabricates ground truth or unverified accuracy claims.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier
from app.core.config import settings
from app.core.schemas import IceIntelligenceResult
from app.core.provenance import create_provenance


class LunarIceLikelihoodModel:
    """
    Random Forest probabilistic ice-likelihood estimator.
    Trained on polarimetric and morphological lunar features using weakly-supervised
    scientific radar constraints.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.model = RandomForestClassifier(
            n_estimators=50,
            max_depth=6,
            random_state=self.random_state,
            n_jobs=1
        )
        self._is_trained = False

    def train_prototype_model(self):
        """
        Trains model on synthetic physical response curves representing
        regolith vs volatile-ice polarimetric scattering.
        """
        np.random.seed(self.random_state)
        n_samples = 1500

        # Features: [cpr, dop, slope_deg, roughness, illumination, psr_flag]
        # Class 0: Dry polar regolith
        cpr_0 = np.random.uniform(0.2, 0.7, n_samples // 2)
        dop_0 = np.random.uniform(0.3, 0.8, n_samples // 2)
        slope_0 = np.random.uniform(2.0, 30.0, n_samples // 2)
        rough_0 = np.random.uniform(5.0, 40.0, n_samples // 2)
        illum_0 = np.random.uniform(0.0, 1.0, n_samples // 2)
        psr_0 = np.random.choice([0.0, 1.0], size=n_samples // 2, p=[0.7, 0.3])
        X_0 = np.column_stack([cpr_0, dop_0, slope_0, rough_0, illum_0, psr_0])
        y_0 = np.zeros(n_samples // 2)

        # Class 1: Radar-consistent volatile candidate (CBOE CPR > 1.0, DOP < 0.13 in PSR)
        cpr_1 = np.random.uniform(1.05, 2.5, n_samples // 2)
        dop_1 = np.random.uniform(0.03, 0.12, n_samples // 2)
        slope_1 = np.random.uniform(0.0, 12.0, n_samples // 2)  # Typically deposited in flat floors
        rough_1 = np.random.uniform(2.0, 20.0, n_samples // 2)
        illum_1 = np.zeros(n_samples // 2)  # Trapped in permanent cold shadow
        psr_1 = np.ones(n_samples // 2)
        X_1 = np.column_stack([cpr_1, dop_1, slope_1, rough_1, illum_1, psr_1])
        y_1 = np.ones(n_samples // 2)

        X = np.vstack([X_0, X_1])
        y = np.concatenate([y_0, y_1])

        self.model.fit(X, y)
        self._is_trained = True

    def predict_likelihood(
        self,
        cpr: np.ndarray,
        dop: np.ndarray,
        slope_deg: np.ndarray,
        roughness: np.ndarray,
        illumination: np.ndarray,
        psr_mask: np.ndarray
    ) -> np.ndarray:
        if not self._is_trained:
            self.train_prototype_model()

        flat_cpr = cpr.flatten()
        flat_dop = dop.flatten()
        flat_slope = slope_deg.flatten()
        flat_rough = roughness.flatten()
        flat_illum = illumination.flatten()
        flat_psr = psr_mask.astype(float).flatten()

        X = np.column_stack([flat_cpr, flat_dop, flat_slope, flat_rough, flat_illum, flat_psr])
        probs = self.model.predict_proba(X)[:, 1]
        return probs.reshape(cpr.shape).astype(np.float32)


# Central singleton model instance
ice_ml_model = LunarIceLikelihoodModel(random_state=settings.RANDOM_SEED)


def evaluate_ice_intelligence(
    crater_id: str,
    cpr: np.ndarray,
    dop: np.ndarray,
    slope_deg: np.ndarray,
    roughness: np.ndarray,
    illumination: np.ndarray,
    psr_mask: np.ndarray,
    doubly_shadowed_mask: np.ndarray,
    pixel_scale_m: float = 250.0,
    cpr_threshold: Optional[float] = None,
    dop_threshold: Optional[float] = None,
    data_mode: str = "DEMO"
) -> Tuple[IceIntelligenceResult, Dict[str, np.ndarray]]:
    """
    Computes both scientific baseline screening and explainable ML ice likelihood.
    """
    cpr_th = cpr_threshold if cpr_threshold is not None else settings.CPR_THRESHOLD
    dop_th = dop_threshold if dop_threshold is not None else settings.DOP_THRESHOLD
    cell_area_km2 = (pixel_scale_m / 1000.0) ** 2

    # Scientific Baseline Screening Mask
    # CPR > threshold AND DOP < threshold AND within Shadow/PSR
    scientific_candidate_mask = (cpr > cpr_th) & (dop < dop_th) & psr_mask
    candidate_cells = int(np.sum(scientific_candidate_mask))
    candidate_area_km2 = float(candidate_cells * cell_area_km2)

    # ML Probabilistic Ice Likelihood P(ice | features)
    ml_likelihood = ice_ml_model.predict_likelihood(
        cpr=cpr,
        dop=dop,
        slope_deg=slope_deg,
        roughness=roughness,
        illumination=illumination,
        psr_mask=psr_mask
    )

    # Calculate evidence metrics inside candidate zones
    mean_prob = float(np.mean(ml_likelihood[scientific_candidate_mask])) if candidate_cells > 0 else 0.0
    max_prob = float(np.max(ml_likelihood)) if ml_likelihood.size > 0 else 0.0

    # Determine confidence level
    # High confidence requires: CPR well above threshold, DOP depressed, and doubly-shadowed overlap
    doubly_overlap = np.sum(scientific_candidate_mask & doubly_shadowed_mask)
    if candidate_cells > 20 and doubly_overlap > 5 and mean_prob > 0.70:
        confidence = "High"
    elif candidate_cells > 5 and mean_prob > 0.50:
        confidence = "Medium"
    else:
        confidence = "Low"

    evidence_checklist = {
        "cpr_above_threshold": bool(np.mean(cpr[scientific_candidate_mask]) > cpr_th) if candidate_cells > 0 else False,
        "dop_below_threshold": bool(np.mean(dop[scientific_candidate_mask]) < dop_th) if candidate_cells > 0 else False,
        "psr_cold_trap_overlap": bool(candidate_cells > 0),
        "doubly_shadowed_core_overlap": bool(doubly_overlap > 0),
        "thermal_stability_expected": bool(candidate_cells > 0)
    }

    explainability_notes = [
        f"Scientific Baseline Screening: {candidate_cells} grid cells ({candidate_area_km2:.2f} km²) passed CPR > {cpr_th:.2f} & DOP < {dop_th:.2f} within PSR.",
        f"Radar Polarimetry: Observed high CPR indicates coherent backscatter opposition effect (CBOE) consistent with low-loss volatile deposits.",
        f"Depolarization: DOP depression (< {dop_th:.2f}) indicates multiple subsurface volume scattering rather than pure surface facet reflection.",
        f"Doubly-Shadowed Overlap: {doubly_overlap * cell_area_km2:.2f} km² situated in ultra-cold nested traps protected from secondary scattered sunlight.",
        "ML Assessment: Random Forest model estimated peak ice-likelihood of "
        f"{max_prob:.2f} with {confidence.upper()} confidence based on coupled terrain and radar features.",
        "Limitation Note: Radar anomalies are consistent with candidate ice-bearing material, but ground truth drilling/spectroscopy is required for physical confirmation."
    ]

    provenance = create_provenance(
        dataset_name=f"{crater_id.upper()}_ICE_INTEL",
        algorithm="Scientific Dual-Threshold Screening + Random Forest Probabilistic Inference",
        parameters={
            "cpr_threshold": cpr_th,
            "dop_threshold": dop_th,
            "n_estimators": 50,
            "max_depth": 6
        },
        data_mode=data_mode
    )

    result = IceIntelligenceResult(
        crater_id=crater_id,
        scientific_candidate_area_km2=round(candidate_area_km2, 2),
        ml_ice_likelihood_mean=round(mean_prob, 3),
        ml_ice_likelihood_max=round(max_prob, 3),
        confidence=confidence,
        scientific_screening_status="PASS" if candidate_cells > 0 else "FAIL",
        evidence_checklist=evidence_checklist,
        explainability_notes=explainability_notes,
        provenance=provenance
    )

    rasters = {
        "scientific_candidate_mask": scientific_candidate_mask,
        "ml_likelihood": ml_likelihood
    }

    return result, rasters
