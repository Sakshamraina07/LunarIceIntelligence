"""
Regression tests for the provenance gate.

These lock the bug that nearly shipped. Four DEM files on this host share one
digest, and one of them is named `shackleton_lola_dem.tif`:

    a5e4ed4bb7248831...  dem/faustini_lola_dem.tif
    a5e4ed4bb7248831...  dem/shackleton_lola_dem.tif
    a5e4ed4bb7248831...  dem/real_dem.tif
    a5e4ed4bb7248831...  dem/ch2_sar_dem.tif

The old eligibility test was `Path(f".../{crater_id}_lola_dem.tif").exists()`,
which cannot tell those four apart, so Shackleton served Faustini's terrain and
Faustini's radar swath under a MEASURED mark. `test_shackleton_is_not_eligible`
fails if that path is ever reintroduced.
"""

import copy

import pytest

from app.demo.lunar_generator import CRATER_CATALOG
from app.ingestion.real_data_gate import (
    CPR_ROLE,
    DEM_ROLE,
    DOP_ROLE,
    assert_no_shared_real_rasters,
    crater_inputs,
    hash_table,
    real_data_status,
)


def test_faustini_is_eligible():
    """The one crater with a registered PDS4 product."""
    status = real_data_status("faustini", CRATER_CATALOG["faustini"])
    assert status.eligible is True
    assert status.product_id == "ch2_sar_ncxl_20200808t201154198_d_sri_xx_cp_xx_d18"
    assert set(status.inputs) == {DEM_ROLE, CPR_ROLE, DOP_ROLE}
    assert status.missing_roles == []


def test_shackleton_is_not_eligible_despite_a_matching_filename():
    """The regression. `shackleton_lola_dem.tif` exists and is a byte copy."""
    path = crater_inputs("shackleton")[DEM_ROLE]
    assert path.is_file(), "precondition: the ambiguous copy is still on this host"

    status = real_data_status("shackleton", CRATER_CATALOG["shackleton"])
    assert status.eligible is False
    assert status.product_id is None
    assert status.missing_roles == [DEM_ROLE, CPR_ROLE, DOP_ROLE]
    assert "is_real_data=False" in status.reason


def test_shoemaker_is_not_eligible_and_size_is_not_the_test():
    """40,176 bytes is the sample writer's output, but the gate never looks."""
    status = real_data_status("shoemaker", CRATER_CATALOG["shoemaker"])
    assert status.eligible is False
    assert status.product_id is None


def test_unknown_crater_is_not_eligible():
    """A crater absent from the catalogue cannot be promoted by anything."""
    status = real_data_status("cabeus", None)
    assert status.eligible is False
    assert status.missing_roles == [DEM_ROLE, CPR_ROLE, DOP_ROLE]


def test_absent_state_payload_carries_no_numbers():
    """`as_payload()` must not smuggle a measurement into the refusal."""
    payload = real_data_status("shackleton", CRATER_CATALOG["shackleton"]).as_payload()
    assert payload["status"] == "NOT_INGESTED"

    def _numeric(value) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    assert not any(_numeric(v) for v in payload.values())


def test_identity_check_passes_on_the_real_catalogue():
    record = assert_no_shared_real_rasters(CRATER_CATALOG)
    assert record["collisions"] == []
    assert record["checked_craters"] == ["faustini"]
    # One eligible crater means no pair exists to compare. Recorded, not hidden:
    # the trap is armed, duplication is not ruled out.
    assert record["pairs_compared"] == 0


def test_identity_check_is_a_hard_failure_when_two_craters_share_bytes():
    """Negative control. Zero tolerance means SystemExit, not a warning."""
    catalog = copy.deepcopy(CRATER_CATALOG)
    catalog["shackleton"].is_real_data = True
    catalog["shackleton"].product_id = "ch2_sar_pretend_20200808"

    with pytest.raises(SystemExit) as excinfo:
        assert_no_shared_real_rasters(catalog)

    message = str(excinfo.value)
    assert "shared_bytes" in message
    assert "faustini" in message and "shackleton" in message


def test_hash_table_exposes_the_collision():
    """The fixture behind the report: rows sharing a digest are one frame."""
    rows = hash_table(CRATER_CATALOG)
    dems = {
        r["path"]: r["sha256"]
        for r in rows
        if r["role"] in (DEM_ROLE, "alias") and r["exists"]
    }
    digests = list(dems.values())
    assert len(digests) > len(set(digests)), "expected at least one duplicated DEM"
