"""Integration tests for the POST /api/primitive/fit endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh
from fastapi.testclient import TestClient

from mesh2urdf.core.mesh_cache import clear_cache, put_mesh
from mesh2urdf.main import app


@pytest.fixture
def client() -> TestClient:
    """TestClient with a clean cache for each test."""
    clear_cache()
    return TestClient(app)


@pytest.fixture
def cube_mesh_id() -> str:
    """Store a unit cube in the mesh cache and return its mesh_id."""
    clear_cache()
    mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    return put_mesh(mesh)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_fit_box_via_api(client: TestClient, cube_mesh_id: str) -> None:
    """Upload cube → POST /api/primitive/fit with type=box → 200 with dimensions."""
    resp = client.post(
        "/api/primitive/fit",
        json={"mesh_id": cube_mesh_id, "primitive_type": "box"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "box"
    assert "size_x" in data["dimensions"]
    assert "size_y" in data["dimensions"]
    assert "size_z" in data["dimensions"]
    assert len(data["origin_xyz"]) == 3
    assert len(data["origin_rpy"]) == 3


def test_fit_sphere_via_api(client: TestClient, cube_mesh_id: str) -> None:
    """Fitting a sphere to the cube mesh must return a valid PrimitiveSpec."""
    resp = client.post(
        "/api/primitive/fit",
        json={"mesh_id": cube_mesh_id, "primitive_type": "sphere"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "sphere"
    assert "radius" in data["dimensions"]
    assert data["dimensions"]["radius"] > 0.0


def test_fit_cylinder_via_api(client: TestClient, cube_mesh_id: str) -> None:
    """Fitting a cylinder via the API must return valid radius and length."""
    resp = client.post(
        "/api/primitive/fit",
        json={"mesh_id": cube_mesh_id, "primitive_type": "cylinder"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "cylinder"
    assert data["dimensions"]["radius"] > 0.0
    assert data["dimensions"]["length"] > 0.0


def test_fit_box_via_stl_upload(client: TestClient, cube_stl_path: Path) -> None:
    """Full round-trip: upload STL → fit box → check dimensions.size present."""
    with open(cube_stl_path, "rb") as f:
        upload_resp = client.post(
            "/api/mesh/load",
            files={"file": ("cube.stl", f, "application/octet-stream")},
        )
    assert upload_resp.status_code == 200
    mesh_id = upload_resp.json()["mesh_id"]

    fit_resp = client.post(
        "/api/primitive/fit",
        json={"mesh_id": mesh_id, "primitive_type": "box"},
    )
    assert fit_resp.status_code == 200
    data = fit_resp.json()
    assert data["type"] == "box"
    assert "size_x" in data["dimensions"]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_fit_unknown_mesh(client: TestClient) -> None:
    """Unknown mesh_id must return HTTP 404."""
    resp = client.post(
        "/api/primitive/fit",
        json={"mesh_id": "00000000-0000-0000-0000-000000000000", "primitive_type": "box"},
    )
    assert resp.status_code == 404


def test_fit_invalid_type(client: TestClient, cube_mesh_id: str) -> None:
    """Invalid primitive_type 'banana' must return 400 or 422."""
    resp = client.post(
        "/api/primitive/fit",
        json={"mesh_id": cube_mesh_id, "primitive_type": "banana"},
    )
    assert resp.status_code in {400, 422}
