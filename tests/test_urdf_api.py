"""Integration tests for the /api/urdf/export endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from lxml import etree as ET

from mesh2urdf.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _minimal_payload(robot_name: str = "robot") -> dict:
    return {
        "robot_name": robot_name,
        "links": [
            {
                "name": "base",
                "mesh_filename": "base.stl",
                "primitive": {
                    "type": "box",
                    "dimensions": {"size_x": 0.2, "size_y": 0.1, "size_z": 0.05},
                    "origin": {"xyz": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
                },
                "collision_margin": 0.05,
                "origin_xyz": [0.0, 0.0, 0.0],
                "origin_rpy": [0.0, 0.0, 0.0],
            }
        ],
        "joints": [],
    }


def _two_link_payload() -> dict:
    return {
        "robot_name": "robot",
        "links": [
            {
                "name": "base",
                "mesh_filename": "base.stl",
                "primitive": {
                    "type": "box",
                    "dimensions": {"size_x": 0.2, "size_y": 0.1, "size_z": 0.05},
                    "origin": {"xyz": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
                },
                "collision_margin": 0.05,
                "origin_xyz": [0.0, 0.0, 0.0],
                "origin_rpy": [0.0, 0.0, 0.0],
            },
            {
                "name": "arm",
                "mesh_filename": "arm.stl",
                "primitive": {
                    "type": "sphere",
                    "dimensions": {"radius": 0.05},
                    "origin": {"xyz": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]},
                },
                "collision_margin": 0.0,
                "origin_xyz": [0.0, 0.0, 0.1],
                "origin_rpy": [0.0, 0.0, 0.0],
            },
        ],
        "joints": [
            {
                "name": "j1",
                "type": "fixed",
                "parent": "base",
                "child": "arm",
                "origin_xyz": [0.0, 0.0, 0.1],
                "origin_rpy": [0.0, 0.0, 0.0],
                "axis": None,
                "limit": None,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_export_valid_payload_returns_200(client: TestClient) -> None:
    resp = client.post("/api/urdf/export", json=_minimal_payload())
    assert resp.status_code == 200


def test_export_content_type_is_xml(client: TestClient) -> None:
    resp = client.post("/api/urdf/export", json=_minimal_payload())
    assert "xml" in resp.headers["content-type"].lower()


def test_export_content_disposition_header(client: TestClient) -> None:
    resp = client.post("/api/urdf/export", json=_minimal_payload())
    cd = resp.headers.get("content-disposition", "")
    assert "robot.urdf" in cd
    assert "attachment" in cd


def test_export_body_parses_as_xml(client: TestClient) -> None:
    resp = client.post("/api/urdf/export", json=_minimal_payload())
    root = ET.fromstring(resp.content)
    assert root.tag == "robot"


def test_export_robot_name_in_xml(client: TestClient) -> None:
    resp = client.post("/api/urdf/export", json=_minimal_payload("my_bot"))
    root = ET.fromstring(resp.content)
    assert root.get("name") == "my_bot"


def test_export_two_links_one_joint(client: TestClient) -> None:
    resp = client.post("/api/urdf/export", json=_two_link_payload())
    assert resp.status_code == 200
    root = ET.fromstring(resp.content)
    assert len(root.findall("link")) == 2
    assert len(root.findall("joint")) == 1


# ---------------------------------------------------------------------------
# Validation error paths (422)
# ---------------------------------------------------------------------------


def test_export_empty_links_returns_422(client: TestClient) -> None:
    payload = {"robot_name": "robot", "links": [], "joints": []}
    resp = client.post("/api/urdf/export", json=payload)
    assert resp.status_code == 422


def test_export_joint_unknown_parent_returns_422(client: TestClient) -> None:
    payload = _minimal_payload()
    payload["joints"] = [
        {
            "name": "j1",
            "type": "fixed",
            "parent": "nonexistent",
            "child": "base",
            "origin_xyz": [0.0, 0.0, 0.0],
            "origin_rpy": [0.0, 0.0, 0.0],
            "axis": None,
            "limit": None,
        }
    ]
    resp = client.post("/api/urdf/export", json=payload)
    assert resp.status_code == 422


def test_export_joint_unknown_child_returns_422(client: TestClient) -> None:
    payload = _minimal_payload()
    payload["joints"] = [
        {
            "name": "j1",
            "type": "fixed",
            "parent": "base",
            "child": "missing",
            "origin_xyz": [0.0, 0.0, 0.0],
            "origin_rpy": [0.0, 0.0, 0.0],
            "axis": None,
            "limit": None,
        }
    ]
    resp = client.post("/api/urdf/export", json=payload)
    assert resp.status_code == 422


def test_export_revolute_missing_axis_returns_422(client: TestClient) -> None:
    payload = _two_link_payload()
    # Replace fixed joint with revolute that has no axis
    payload["joints"] = [
        {
            "name": "j1",
            "type": "revolute",
            "parent": "base",
            "child": "arm",
            "origin_xyz": [0.0, 0.0, 0.0],
            "origin_rpy": [0.0, 0.0, 0.0],
            "axis": None,
            "limit": {"lower": -1.57, "upper": 1.57, "effort": 10.0, "velocity": 1.0},
        }
    ]
    resp = client.post("/api/urdf/export", json=payload)
    assert resp.status_code == 422
