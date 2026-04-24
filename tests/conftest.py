from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mesh2urdf.main import app


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    """FastAPI TestClient for the full app."""
    return TestClient(app)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to the tests/fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def cube_stl_path(fixtures_dir: Path) -> Path:
    """Path to the cube STL fixture."""
    return fixtures_dir / "cube.stl"


@pytest.fixture(scope="session")
def cube_obj_path(fixtures_dir: Path) -> Path:
    """Path to the cube OBJ fixture."""
    return fixtures_dir / "cube.obj"
