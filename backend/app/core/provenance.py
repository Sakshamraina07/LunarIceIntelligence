"""
Data Provenance and Reproducibility Tracking.
Ensures every calculated scientific product traces back to its exact inputs,
algorithms, parameters, and random seeds.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.core.schemas import ProvenanceMetadata
from app.core.config import settings


def create_provenance(
    dataset_name: str,
    algorithm: str,
    parameters: Dict[str, Any],
    data_mode: Optional[str] = None,
    source: str = "Chandrayaan-2 Remote Sensing Archive (ISRO/PRADAN / LOLA PDS)",
    model_version: str = "v2.0-scientific"
) -> ProvenanceMetadata:
    return ProvenanceMetadata(
        dataset_name=dataset_name,
        data_source=source if (data_mode or settings.DATA_MODE) == "REAL" else "Deterministic Lunar South Polar Simulator (Fixed Seed)",
        data_mode=data_mode or settings.DATA_MODE,
        algorithm=algorithm,
        parameters=parameters,
        model_version=model_version,
        random_seed=settings.RANDOM_SEED,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
