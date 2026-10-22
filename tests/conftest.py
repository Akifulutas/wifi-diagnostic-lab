"""
Pytest global fixtures for BLL test suite.
"""

from __future__ import annotations

import pathlib
import pytest

PROJ_ROOT = pathlib.Path(__file__).parent.parent
SCHEMAS_DIR = PROJ_ROOT / "docs" / "schemas"


@pytest.fixture
def proj_root() -> pathlib.Path:
    return PROJ_ROOT


@pytest.fixture
def schemas_dir() -> pathlib.Path:
    return SCHEMAS_DIR


@pytest.fixture(autouse=True)
def clean_mock_state():
    """Ensure mock simulation state is reset between test executions."""
    from bll.platform.backends import MockSimulationBackend
    MockSimulationBackend._STATE_FILE.unlink(missing_ok=True)
    MockSimulationBackend._CLASS_IS_SETUP = False
    yield
    MockSimulationBackend._STATE_FILE.unlink(missing_ok=True)
    MockSimulationBackend._CLASS_IS_SETUP = False
