from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mesh2urdf.core.mesh_cache import clear_cache, get_mesh, put_mesh
from mesh2urdf.core.mesh_loader import load_mesh, mesh_to_response

# ---------------------------------------------------------------------------
# load_mesh tests
# ---------------------------------------------------------------------------


def test_load_stl_cube(cube_stl_path: Path) -> None:
    data = cube_stl_path.read_bytes()
    mesh = load_mesh(data, "cube.stl")
    # ASCII STL duplicates vertices per facet: 12 faces * 3 = 36 raw vertices
    assert len(mesh.vertices) >= 8
    assert len(mesh.faces) == 12


def test_load_obj_cube(cube_obj_path: Path) -> None:
    data = cube_obj_path.read_bytes()
    mesh = load_mesh(data, "cube.obj")
    assert len(mesh.vertices) == 8
    assert len(mesh.faces) == 12


def test_reject_garbage_bytes() -> None:
    with pytest.raises((ValueError, Exception)):
        load_mesh(b"not a mesh at all!!!", "bad.stl")


def test_reject_unsupported_format() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        load_mesh(b"some bytes", "model.ply")


def test_finite_vertices(cube_stl_path: Path) -> None:
    data = cube_stl_path.read_bytes()
    mesh = load_mesh(data, "cube.stl")
    assert np.isfinite(mesh.vertices).all()


def test_mesh_to_response_shapes(cube_obj_path: Path) -> None:
    data = cube_obj_path.read_bytes()
    mesh = load_mesh(data, "cube.obj")
    resp = mesh_to_response(mesh, "test-id")

    assert resp["mesh_id"] == "test-id"
    assert resp["vertex_count"] * 3 == len(resp["vertices"])
    assert resp["face_count"] * 3 == len(resp["indices"])
    assert len(resp["bounds"]) == 2
    assert len(resp["centroid"]) == 3


# ---------------------------------------------------------------------------
# mesh_cache tests
# ---------------------------------------------------------------------------


def test_cache_put_get(cube_obj_path: Path) -> None:
    clear_cache()
    data = cube_obj_path.read_bytes()
    mesh = load_mesh(data, "cube.obj")

    mesh_id = put_mesh(mesh)
    assert isinstance(mesh_id, str) and len(mesh_id) > 0

    retrieved = get_mesh(mesh_id)
    assert retrieved is not None
    assert len(retrieved.vertices) == len(mesh.vertices)


def test_cache_miss_returns_none() -> None:
    result = get_mesh("nonexistent-id-00000000")
    assert result is None


def test_cache_put_unique_ids(cube_obj_path: Path) -> None:
    data = cube_obj_path.read_bytes()
    mesh = load_mesh(data, "cube.obj")
    id1 = put_mesh(mesh)
    id2 = put_mesh(mesh)
    assert id1 != id2
