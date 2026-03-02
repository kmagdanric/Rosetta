"""Shared test fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_ssot_dir(tmp_path):
    """Create a temporary SSOT directory for tests."""
    ssot_dir = tmp_path / "ssot"
    (ssot_dir / "hypotheses").mkdir(parents=True)
    (ssot_dir / "data_registry").mkdir(parents=True)
    return ssot_dir
