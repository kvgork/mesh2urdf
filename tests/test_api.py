from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_healthz(test_client: TestClient) -> None:
    resp = test_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_serves_index(test_client: TestClient) -> None:
    resp = test_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_mesh_load_endpoint(test_client: TestClient, cube_stl_path: Path) -> None:
    with open(cube_stl_path, "rb") as f:
        resp = test_client.post(
            "/api/mesh/load",
            files={"file": ("cube.stl", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "mesh_id" in data
    assert data["face_count"] == 12
    assert data["vertex_count"] > 0


def test_upload_obj_cube(test_client: TestClient, cube_obj_path: Path) -> None:
    with open(cube_obj_path, "rb") as f:
        resp = test_client.post(
            "/api/mesh/load",
            files={"file": ("cube.obj", f, "application/octet-stream")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "mesh_id" in data
    assert data["vertex_count"] > 0
    assert data["face_count"] > 0


def test_mesh_metadata_endpoint(test_client: TestClient, cube_stl_path: Path) -> None:
    # First upload
    with open(cube_stl_path, "rb") as f:
        upload_resp = test_client.post(
            "/api/mesh/load",
            files={"file": ("cube.stl", f, "application/octet-stream")},
        )
    assert upload_resp.status_code == 200
    mesh_id = upload_resp.json()["mesh_id"]

    # Then fetch metadata
    resp = test_client.get(f"/api/mesh/{mesh_id}")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["mesh_id"] == mesh_id
    assert meta["face_count"] == 12
    assert "bounds" in meta
    assert "centroid" in meta


def test_mesh_metadata_404(test_client: TestClient) -> None:
    resp = test_client.get("/api/mesh/does-not-exist")
    assert resp.status_code == 404


def test_mesh_load_bad_extension(test_client: TestClient) -> None:
    resp = test_client.post(
        "/api/mesh/load",
        files={"file": ("model.txt", b"not a mesh", "text/plain")},
    )
    assert resp.status_code == 400


def test_mesh_load_bad_content(test_client: TestClient) -> None:
    resp = test_client.post(
        "/api/mesh/load",
        files={"file": ("model.stl", b"garbage bytes not a real stl", "application/octet-stream")},
    )
    assert resp.status_code == 400
