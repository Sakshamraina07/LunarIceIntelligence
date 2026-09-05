"""
pytest configuration for the backend.

The only thing this does is opt the test session into the synthetic environment
generator. `app/demo/lunar_generator.py` refuses to run without this flag so
that a serving path can never fabricate a mission (Step 10, handoff V10.3):
production returns an explicit NOT_INGESTED payload instead.

Tests are the one place seeded rasters are legitimate. `test_pipeline.py` drives
shackleton / shoemaker / faustini end to end through modules A-G, and
`test_rover.py::test_anisotropic_spacing_changes_reported_distance` needs a grid
whose spacing it controls. Both want a deterministic environment, not a
measurement, so both get one here and nowhere else.
"""

import os

from app.demo.lunar_generator import DEMO_GENERATOR_ENV_FLAG

os.environ[DEMO_GENERATOR_ENV_FLAG] = "1"
