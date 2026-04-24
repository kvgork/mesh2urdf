"""Unit tests for urdf_generator.py.

Tests cover:
- _fmt_xyz formatting
- Single link XML structure
- Mesh filename prefix
- Collision primitive scaling
- Joint serialisation (revolute emits axis+limit, fixed omits them)
- Validation errors (no links, cycle, dangling refs, missing axis)
"""

from __future__ import annotations

import pytest
from lxml import etree as ET

from mesh2urdf.core.urdf_generator import _fmt_xyz, _validate_request, generate_urdf
from mesh2urdf.models.schema import JointSpec, LinkSpec, PrimitiveSpec, URDFExportRequest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_box_spec(
    name: str = "base",
    mesh_filename: str = "base.stl",
    margin: float = 0.0,
) -> LinkSpec:
    return LinkSpec(
        name=name,
        mesh_filename=mesh_filename,
        primitive=PrimitiveSpec(
            type="box",
            dimensions={"size_x": 0.2, "size_y": 0.1, "size_z": 0.05},
            origin_xyz=[0.0, 0.0, 0.025],
            origin_rpy=[0.0, 0.0, 0.0],
        ),
        collision_margin=margin,
        origin_xyz=[0.0, 0.0, 0.0],
        origin_rpy=[0.0, 0.0, 0.0],
    )


def _make_fixed_joint(name: str, parent: str, child: str) -> JointSpec:
    return JointSpec(
        name=name,
        type="fixed",
        parent=parent,
        child=child,
        origin_xyz=[0.0, 0.0, 0.1],
        origin_rpy=[0.0, 0.0, 0.0],
        axis=None,
        limit=None,
    )


def _make_revolute_joint(name: str, parent: str, child: str) -> JointSpec:
    return JointSpec(
        name=name,
        type="revolute",
        parent=parent,
        child=child,
        origin_xyz=[0.0, 0.0, 0.1],
        origin_rpy=[0.0, 0.0, 0.0],
        axis=[0.0, 0.0, 1.0],
        limit={"lower": -1.57, "upper": 1.57, "effort": 10.0, "velocity": 1.0},
    )


# ---------------------------------------------------------------------------
# _fmt_xyz
# ---------------------------------------------------------------------------


def test_fmt_xyz_basic() -> None:
    result = _fmt_xyz([1.0, 2.0, 3.14159265])
    assert result == "1.000000 2.000000 3.141593"


def test_fmt_xyz_zeros() -> None:
    result = _fmt_xyz([0.0, 0.0, 0.0])
    assert result == "0.000000 0.000000 0.000000"


def test_fmt_xyz_wrong_length() -> None:
    with pytest.raises(ValueError, match="Expected 3 values"):
        _fmt_xyz([1.0, 2.0])


# ---------------------------------------------------------------------------
# generate_urdf — single link
# ---------------------------------------------------------------------------


def test_single_link_root_tag() -> None:
    req = URDFExportRequest(robot_name="my_robot", links=[_make_box_spec()])
    xml_bytes = generate_urdf(req)
    root = ET.fromstring(xml_bytes)
    assert root.tag == "robot"
    assert root.get("name") == "my_robot"


def test_single_link_xml_declaration() -> None:
    req = URDFExportRequest(robot_name="robot", links=[_make_box_spec()])
    xml_bytes = generate_urdf(req)
    assert xml_bytes.startswith(b"<?xml")


def test_single_link_name() -> None:
    req = URDFExportRequest(robot_name="robot", links=[_make_box_spec(name="arm")])
    root = ET.fromstring(generate_urdf(req))
    links = root.findall("link")
    assert len(links) == 1
    assert links[0].get("name") == "arm"


def test_single_link_mesh_filename_prefix() -> None:
    req = URDFExportRequest(robot_name="robot", links=[_make_box_spec(mesh_filename="part.stl")])
    root = ET.fromstring(generate_urdf(req))
    mesh_el = root.find(".//visual/geometry/mesh")
    assert mesh_el is not None
    assert mesh_el.get("filename") == "meshes/part.stl"


def test_single_link_collision_has_box() -> None:
    req = URDFExportRequest(robot_name="robot", links=[_make_box_spec()])
    root = ET.fromstring(generate_urdf(req))
    box_el = root.find(".//collision/geometry/box")
    assert box_el is not None


def test_collision_margin_applied() -> None:
    """Collision box size should be (1 + margin) * original dimensions."""
    margin = 0.10
    req = URDFExportRequest(robot_name="robot", links=[_make_box_spec(margin=margin)])
    root = ET.fromstring(generate_urdf(req))
    box_el = root.find(".//collision/geometry/box")
    assert box_el is not None
    sizes = [float(v) for v in box_el.get("size").split()]
    expected = [0.2 * 1.1, 0.1 * 1.1, 0.05 * 1.1]
    for got, exp in zip(sizes, expected):
        assert got == pytest.approx(exp, rel=1e-5)


# ---------------------------------------------------------------------------
# generate_urdf — joints
# ---------------------------------------------------------------------------


def test_two_links_fixed_joint() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base"), _make_box_spec("arm", "arm.stl")],
        joints=[_make_fixed_joint("j1", "base", "arm")],
    )
    root = ET.fromstring(generate_urdf(req))
    joints = root.findall("joint")
    assert len(joints) == 1
    j = joints[0]
    assert j.get("name") == "j1"
    assert j.get("type") == "fixed"
    assert j.find("parent").get("link") == "base"
    assert j.find("child").get("link") == "arm"


def test_fixed_joint_omits_axis_and_limit() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base"), _make_box_spec("arm", "arm.stl")],
        joints=[_make_fixed_joint("j1", "base", "arm")],
    )
    root = ET.fromstring(generate_urdf(req))
    j = root.find("joint")
    assert j.find("axis") is None
    assert j.find("limit") is None


def test_revolute_joint_has_axis_and_limit() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base"), _make_box_spec("arm", "arm.stl")],
        joints=[_make_revolute_joint("j1", "base", "arm")],
    )
    root = ET.fromstring(generate_urdf(req))
    j = root.find("joint")
    assert j.find("axis") is not None
    assert j.find("axis").get("xyz") == "0.000000 0.000000 1.000000"
    lim = j.find("limit")
    assert lim is not None
    assert float(lim.get("lower")) == pytest.approx(-1.57, rel=1e-4)
    assert float(lim.get("upper")) == pytest.approx(1.57, rel=1e-4)


def test_revolute_joint_xml_parses() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base"), _make_box_spec("arm", "arm.stl")],
        joints=[_make_revolute_joint("j1", "base", "arm")],
    )
    xml_bytes = generate_urdf(req)
    # Should parse without raising
    root = ET.fromstring(xml_bytes)
    assert root is not None


# ---------------------------------------------------------------------------
# _validate_request
# ---------------------------------------------------------------------------


def test_validate_empty_links_raises() -> None:
    req = URDFExportRequest(robot_name="robot", links=[])
    with pytest.raises(ValueError, match="at least one link"):
        _validate_request(req)


def test_validate_dangling_parent_raises() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base")],
        joints=[_make_fixed_joint("j1", "nonexistent", "base")],
    )
    with pytest.raises(ValueError, match="unknown parent"):
        _validate_request(req)


def test_validate_dangling_child_raises() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base")],
        joints=[_make_fixed_joint("j1", "base", "nonexistent")],
    )
    with pytest.raises(ValueError, match="unknown child"):
        _validate_request(req)


def test_validate_cycle_raises() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[
            _make_box_spec("A"),
            _make_box_spec("B", "b.stl"),
            _make_box_spec("C", "c.stl"),
        ],
        joints=[
            _make_fixed_joint("j_ab", "A", "B"),
            _make_fixed_joint("j_bc", "B", "C"),
            _make_fixed_joint("j_ca", "C", "A"),
        ],
    )
    with pytest.raises(ValueError, match="[Cc]ycle"):
        _validate_request(req)


def test_validate_revolute_without_axis_raises() -> None:
    req = URDFExportRequest(
        robot_name="robot",
        links=[_make_box_spec("base"), _make_box_spec("arm", "arm.stl")],
        joints=[
            JointSpec(
                name="j1",
                type="revolute",
                parent="base",
                child="arm",
                origin_xyz=[0.0, 0.0, 0.0],
                origin_rpy=[0.0, 0.0, 0.0],
                axis=None,
            )
        ],
    )
    with pytest.raises(ValueError, match="requires an axis"):
        _validate_request(req)
