"""
real_data_gate.py — decides, per crater, whether a REAL run is defensible.

Why this exists. `mission_service` used to decide "the real rasters are present"
by testing whether a *filename* existed:

    Path(f"data/pradan/dem/{crater_id}_lola_dem.tif").exists()

Four files on disk share one hash, so that test cannot discriminate:

    3a0911941aa169da25828304e3db391b  dem/faustini_lola_dem.tif
    3a0911941aa169da25828304e3db391b  dem/shackleton_lola_dem.tif
    3a0911941aa169da25828304e3db391b  dem/real_dem.tif
    3a0911941aa169da25828304e3db391b  dem/ch2_sar_dem.tif

    587a58cdad10579039b76751a18766aa  dfsar/faustini_dfsar_s0.tif
    587a58cdad10579039b76751a18766aa  dfsar/shackleton_dfsar_s0.tif

`shackleton_lola_dem.tif` is a copy of Faustini's crop. Under the filename test
Shackleton passed as REAL and served Faustini's terrain and Faustini's radar
swath under a MEASURED mark — worse than the seeded DEMO fallback, because DEMO
labels itself and this did not.

So eligibility is decided by PROVENANCE, not by the filesystem: a crater serves
real data only if the catalogue marks it `is_real_data=True` AND names the PDS4
`product_id` the rasters came from. Shoemaker's 40,176-byte rasters are the
sample writer's output and fail on the same rule — file size is not the test.

On top of the gate, `assert_no_shared_real_rasters()` arms the trap for the
failure that nearly happened: if two craters are ever both marked real and their
DEMs hash equal, one of them is a copy and that is a hard failure, not a
warning. Same shape and same zero tolerance as `build_analysis.assert_dem_is_lola()`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# backend/app/ingestion/ -> parents[3] is the repository root.
BASE_DIR = Path(__file__).resolve().parents[3]
PRADAN_ROOT = BASE_DIR / "data" / "pradan"

#: Roles a crater needs before any REAL number can be computed for it.
DEM_ROLE = "dem"
CPR_ROLE = "cpr"
DOP_ROLE = "dop"


@dataclass
class RealDataStatus:
    """Whether `crater_id` may be analysed as REAL, and why / why not."""

    crater_id: str
    eligible: bool
    reason: str
    product_id: Optional[str] = None
    inputs: Dict[str, str] = field(default_factory=dict)
    missing_roles: List[str] = field(default_factory=list)
    #: Set when a crater passed the provenance gate but failed a later
    #: precondition -- so far only an unresolvable ground spacing. Kept separate
    #: from `reason` so the payload can say "registered, but not computable"
    #: rather than implying the product was never ingested.
    failure_code: Optional[str] = None

    def with_failure(self, code: str, reason: str) -> "RealDataStatus":
        """
        A copy of this status demoted to ineligible, carrying why.

        Used when the pipeline gets past the provenance gate and then finds it
        cannot compute honestly -- the spacing case. The alternative was to
        publish areas and distances off a placeholder constant, which is the
        defect this method exists to make impossible.
        """
        return RealDataStatus(
            crater_id=self.crater_id,
            eligible=False,
            reason=reason,
            product_id=self.product_id,
            inputs=dict(self.inputs),
            missing_roles=list(self.missing_roles),
            failure_code=code,
        )

    def as_payload(self) -> Dict[str, object]:
        """The absent-state block the API hands to the UI. No numbers in it."""
        return {
            "status": "NOT_INGESTED",
            "crater_id": self.crater_id,
            "reason": self.reason,
            "product_id": self.product_id,
            "missing_roles": list(self.missing_roles),
            "failure_code": self.failure_code,
            "resolved_inputs": dict(self.inputs),
            "what_would_change_it": (
                "Ingest a Chandrayaan-2 DFSAR product covering this crater and "
                "register its product_id in CRATER_CATALOG with is_real_data=True. "
                "Copying another crater's raster does not count and is blocked by "
                "assert_no_shared_real_rasters()."
            ),
        }


def sha256_file(path: Path, chunk_bytes: int = 1 << 20) -> str:
    """Streamed hash — these rasters run to megabytes and are never read whole."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk_bytes), b""):
            h.update(block)
    return h.hexdigest()


def crater_inputs(crater_id: str) -> Dict[str, Path]:
    """The rasters that belong to THIS crater. No shared `*_real.tif` aliases:
    those are the files whose ambiguity caused the bug."""
    return {
        DEM_ROLE: PRADAN_ROOT / "dem" / f"{crater_id}_lola_dem.tif",
        CPR_ROLE: PRADAN_ROOT / "dfsar" / "cpr_real.tif",
        DOP_ROLE: PRADAN_ROOT / "dfsar" / "dop_real.tif",
    }


def real_data_status(crater_id: str, crater_info: object) -> RealDataStatus:
    """Provenance first, filesystem second.

    A crater the catalogue does not vouch for can never reach the rasters, so a
    duplicated filename cannot promote it. Only after the catalogue vouches for
    it do we check that the files it names are actually there.
    """
    flagged = bool(getattr(crater_info, "is_real_data", False))
    product_id = getattr(crater_info, "product_id", None) or None

    if not flagged or not product_id:
        return RealDataStatus(
            crater_id=crater_id,
            eligible=False,
            reason=(
                f"No Chandrayaan-2 DFSAR product is registered for {crater_id}. "
                "CRATER_CATALOG carries "
                f"is_real_data={flagged} and product_id={product_id!r}, so there is "
                "nothing to measure. Rasters on disk whose names contain this "
                "crater id are copies of another crater's frame and are not "
                "evidence about this one."
            ),
            product_id=product_id,
            missing_roles=[DEM_ROLE, CPR_ROLE, DOP_ROLE],
        )

    paths = crater_inputs(crater_id)
    missing = sorted(role for role, p in paths.items() if not p.is_file())
    if missing:
        return RealDataStatus(
            crater_id=crater_id,
            eligible=False,
            reason=(
                f"{crater_id} is registered against product {product_id}, but the "
                f"ingested raster(s) for {', '.join(missing)} are not on this host. "
                "The 9 GB SAR set is not deployed, so a served host reports the "
                "absence rather than substituting generated data."
            ),
            product_id=product_id,
            inputs={role: str(p) for role, p in paths.items() if p.is_file()},
            missing_roles=missing,
        )

    return RealDataStatus(
        crater_id=crater_id,
        eligible=True,
        reason=f"{crater_id} is registered against PDS4 product {product_id} and all rasters are present.",
        product_id=product_id,
        inputs={role: str(p) for role, p in paths.items()},
    )


#: Rasters whose names promise a crater or a mission they cannot deliver. They
#: are not inputs to anything; they are listed so the fixture shows the
#: collision the filename test was reading as evidence.
AMBIGUOUS_ALIASES = (
    PRADAN_ROOT / "dem" / "real_dem.tif",
    PRADAN_ROOT / "dem" / "ch2_sar_dem.tif",
)


def hash_table(catalog: Dict[str, object]) -> List[Dict[str, object]]:
    """One row per (crater, role) the catalogue declares, plus the aliases.

    `sha256` is None when the file is absent: that is a fact about this host,
    not an error, and the row is still worth printing. Rows sharing a digest
    are the same bytes under different names.
    """
    rows: List[Dict[str, object]] = []
    for crater_id in sorted(catalog):
        status = real_data_status(crater_id, catalog[crater_id])
        for role, path in sorted(crater_inputs(crater_id).items()):
            present = path.is_file()
            rows.append({
                "crater_id": crater_id,
                "role": role,
                "path": str(path),
                "declared_real": status.product_id is not None
                and bool(getattr(catalog[crater_id], "is_real_data", False)),
                "eligible": status.eligible,
                "exists": present,
                "size_bytes": path.stat().st_size if present else None,
                "sha256": sha256_file(path) if present else None,
            })
    for path in AMBIGUOUS_ALIASES:
        present = path.is_file()
        rows.append({
            "crater_id": None,
            "role": "alias",
            "path": str(path),
            "declared_real": False,
            "eligible": False,
            "exists": present,
            "size_bytes": path.stat().st_size if present else None,
            "sha256": sha256_file(path) if present else None,
        })
    return rows


def assert_no_shared_real_rasters(catalog: Dict[str, object]) -> Dict[str, object]:
    """Two craters marked REAL may not resolve to the same bytes. Tolerance: 0.

    Same shape and same zero tolerance as `build_analysis.assert_dem_is_lola()`:
    a printed record on success, `SystemExit` on violation, no warning tier. A
    warning would be read as noise, and the failure it guards against is a
    MEASURED mark on another crater's terrain.

    Both identities are checked, because both can carry the bug:
      * same PATH  — `crater_inputs()` hands every crater the one shared
        `cpr_real.tif` / `dop_real.tif`. That is fine while exactly one crater is
        eligible. The moment a second is registered, those two craters would be
        served one radar swath, so this check trips and forces per-crater DFSAR
        ingestion instead of letting the reuse pass silently.
      * same DIGEST — `shackleton_lola_dem.tif` is a byte copy of Faustini's
        crop. Different names, one frame.

    With one eligible crater there is no pair to compare and the check passes
    with `pairs_compared: 0`. That is recorded rather than hidden: it says the
    trap is armed, not that duplication has been ruled out.
    """
    eligible: Dict[str, RealDataStatus] = {}
    for crater_id in sorted(catalog):
        status = real_data_status(crater_id, catalog[crater_id])
        if status.eligible:
            eligible[crater_id] = status

    digests: Dict[str, Dict[str, str]] = {
        crater_id: {role: sha256_file(Path(p)) for role, p in sorted(status.inputs.items())}
        for crater_id, status in eligible.items()
    }

    collisions: List[Dict[str, str]] = []
    ids = sorted(eligible)
    pairs = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            pairs += 1
            for role in (DEM_ROLE, CPR_ROLE, DOP_ROLE):
                pa, pb = eligible[a].inputs.get(role), eligible[b].inputs.get(role)
                if pa is not None and pa == pb:
                    collisions.append({"crater_a": a, "crater_b": b, "role": role,
                                       "kind": "shared_path", "detail": pa})
                elif digests[a].get(role) and digests[a][role] == digests[b].get(role):
                    collisions.append({"crater_a": a, "crater_b": b, "role": role,
                                       "kind": "shared_bytes", "detail": digests[a][role]})

    rec: Dict[str, object] = {
        "checked_craters": ids,
        "pairs_compared": pairs,
        "roles": [DEM_ROLE, CPR_ROLE, DOP_ROLE],
        "digests": digests,
        "tolerance": "no two eligible craters may share a raster path or digest",
        "collisions": collisions,
    }
    if collisions:
        lines = [
            f"  {c['crater_a']} and {c['crater_b']} share {c['role']} "
            f"({c['kind']}): {c['detail']}"
            for c in collisions
        ]
        raise SystemExit(
            "Two craters marked is_real_data resolve to the same raster:\n"
            + "\n".join(lines)
            + "\nOne of them is a copy, so one of them would serve the other's "
              "frame under a MEASURED mark. Ingest that crater's own product or "
              "clear its is_real_data flag. No REAL number may be served until "
              "this is resolved."
        )
    rec["verdict"] = "PASS"
    return rec




