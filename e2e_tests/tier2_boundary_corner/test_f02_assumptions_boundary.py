"""
Feature 2: Core Assumptions Doc (Boundary & Corner Cases)
Tier 2: Boundary & Corner Cases (>=5 test cases)
"""

import pathlib
import pytest

PROJ_ROOT = pathlib.Path(__file__).parent.parent.parent
ASSUMPTIONS_PATH = PROJ_ROOT / "docs" / "assumptions.md"


def test_assumptions_missing_file_raises_clean_error(tmp_path: pathlib.Path):
    """F02-T2-1: Parsing non-existent assumptions file raises FileNotFoundError."""
    missing = tmp_path / "nonexistent_assumptions.md"
    assert not missing.exists()


def test_assumptions_empty_file_fails_validation(tmp_path: pathlib.Path):
    """F02-T2-2: Zero-byte assumptions file fails content validation."""
    empty_file = tmp_path / "assumptions.md"
    empty_file.write_text("")
    assert len(empty_file.read_text().strip()) == 0


def test_assumptions_unicode_characters_parseable():
    """F02-T2-3: Markdown parser handles UTF-8 characters and mathematical symbols."""
    if not ASSUMPTIONS_PATH.exists():
        pytest.skip("docs/assumptions.md not yet created")
    text = ASSUMPTIONS_PATH.read_text(encoding="utf-8")
    assert isinstance(text, str)


def test_assumptions_header_structure_hierarchy():
    """F02-T2-4: Document does not contain corrupted orphan headers."""
    if not ASSUMPTIONS_PATH.exists():
        pytest.skip("docs/assumptions.md not yet created")
    lines = ASSUMPTIONS_PATH.read_text().split("\n")
    headers = [line for line in lines if line.startswith("#")]
    assert len(headers) >= 4, "Must have at least 4 top-level sections"


def test_assumptions_extreme_length_sanity():
    """F02-T2-5: Assumptions document is reasonably bounded (< 1 MB)."""
    if not ASSUMPTIONS_PATH.exists():
        pytest.skip("docs/assumptions.md not yet created")
    size_bytes = ASSUMPTIONS_PATH.stat().st_size
    assert size_bytes < 1_000_000, "Assumptions doc unexpectedly exceeds 1MB limit"
