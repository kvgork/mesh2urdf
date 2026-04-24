"""Unit tests for the primitive fitting engine.

All meshes are created with trimesh.creation so tests have exact ground truth.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh
import trimesh.creation

from mesh2urdf.core.primitive_fitter import (
    fit_box,
    fit_cylinder,
    fit_sphere,
    scale_primitive,
)

# ---------------------------------------------------------------------------
# fit_box
# ---------------------------------------------------------------------------


def test_fit_box_unit_cube() -> None:
    """Unit cube at origin: size must be [1,1,1], center [0.5,0.5,0.5]."""
    mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    # trimesh.creation.box is centered at origin → translate so bounds are [0,1]
    mesh.apply_translation([0.5, 0.5, 0.5])

    spec = fit_box(mesh)

    assert spec.type == "box"
    assert spec.dimensions["size_x"] == pytest.approx(1.0, abs=1e-9)
    assert spec.dimensions["size_y"] == pytest.approx(1.0, abs=1e-9)
    assert spec.dimensions["size_z"] == pytest.approx(1.0, abs=1e-9)
    assert spec.origin_xyz[0] == pytest.approx(0.5, abs=1e-9)
    assert spec.origin_xyz[1] == pytest.approx(0.5, abs=1e-9)
    assert spec.origin_xyz[2] == pytest.approx(0.5, abs=1e-9)
    assert spec.origin_rpy == [0.0, 0.0, 0.0]


def test_fit_box_empty_mesh_raises() -> None:
    """fit_box must raise ValueError on an empty mesh."""
    empty = trimesh.Trimesh()
    with pytest.raises(ValueError, match="empty"):
        fit_box(empty)


# ---------------------------------------------------------------------------
# fit_sphere
# ---------------------------------------------------------------------------


def test_fit_sphere() -> None:
    """Icosphere of radius 0.5: fitted radius must be within 2%."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=0.5)
    spec = fit_sphere(mesh)

    assert spec.type == "sphere"
    assert spec.dimensions["radius"] == pytest.approx(0.5, rel=0.02)
    # Center should be near origin.
    assert np.linalg.norm(spec.origin_xyz) == pytest.approx(0.0, abs=0.02)


def test_fit_sphere_fallback() -> None:
    """Dense icosphere (>100k verts) must still return a valid result via fallback."""
    mesh = trimesh.creation.icosphere(subdivisions=7, radius=1.0)
    # subdivisions=7 typically yields ~163 840 vertices.
    assert mesh.vertices.shape[0] > 100_000, "Fixture not dense enough — adjust subdivisions"

    spec = fit_sphere(mesh)

    assert spec.type == "sphere"
    assert spec.dimensions["radius"] > 0.0
    assert len(spec.origin_xyz) == 3


# ---------------------------------------------------------------------------
# fit_cylinder
# ---------------------------------------------------------------------------


def test_fit_cylinder() -> None:
    """Z-axis cylinder (r=0.3, h=1.0): radius and length within 5%."""
    mesh = trimesh.creation.cylinder(radius=0.3, height=1.0, sections=64)
    spec = fit_cylinder(mesh)

    assert spec.type == "cylinder"
    assert spec.dimensions["radius"] == pytest.approx(0.3, rel=0.05)
    assert spec.dimensions["length"] == pytest.approx(1.0, rel=0.05)
    # Axis is Z → rpy should be [0,0,0] (degenerate parallel case).
    assert spec.origin_rpy == pytest.approx([0.0, 0.0, 0.0], abs=1e-9)


# ---------------------------------------------------------------------------
# scale_primitive
# ---------------------------------------------------------------------------


def test_scale_primitive_box() -> None:
    """Box scaled by margin=0.10 must have each dimension grown by factor 1.10."""
    mesh = trimesh.creation.box(extents=[2.0, 3.0, 4.0])
    spec = fit_box(mesh)
    scaled = scale_primitive(spec, margin=0.10)

    assert scaled.dimensions["size_x"] == pytest.approx(spec.dimensions["size_x"] * 1.10, rel=1e-9)
    assert scaled.dimensions["size_y"] == pytest.approx(spec.dimensions["size_y"] * 1.10, rel=1e-9)
    assert scaled.dimensions["size_z"] == pytest.approx(spec.dimensions["size_z"] * 1.10, rel=1e-9)


def test_scale_preserves_origin() -> None:
    """Scaling must not change origin_xyz or origin_rpy for any primitive type."""
    box_mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    sphere_mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    cyl_mesh = trimesh.creation.cylinder(radius=0.3, height=1.0)

    for spec in [fit_box(box_mesh), fit_sphere(sphere_mesh), fit_cylinder(cyl_mesh)]:
        scaled = scale_primitive(spec, margin=0.15)
        assert scaled.origin_xyz == pytest.approx(spec.origin_xyz, abs=1e-12)
        assert scaled.origin_rpy == pytest.approx(spec.origin_rpy, abs=1e-12)


def test_scale_sphere() -> None:
    """Sphere radius scaled correctly."""
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    spec = fit_sphere(mesh)
    scaled = scale_primitive(spec, margin=0.20)
    assert scaled.dimensions["radius"] == pytest.approx(spec.dimensions["radius"] * 1.20, rel=1e-9)


def test_scale_cylinder() -> None:
    """Cylinder radius and length both scaled."""
    mesh = trimesh.creation.cylinder(radius=0.3, height=1.0)
    spec = fit_cylinder(mesh)
    scaled = scale_primitive(spec, margin=0.05)
    assert scaled.dimensions["radius"] == pytest.approx(spec.dimensions["radius"] * 1.05, rel=1e-9)
    assert scaled.dimensions["length"] == pytest.approx(spec.dimensions["length"] * 1.05, rel=1e-9)


def test_scale_unknown_type_raises() -> None:
    """scale_primitive must raise ValueError for an unknown primitive type."""
    from mesh2urdf.models.schema import PrimitiveSpec

    # Bypass Literal validation to test runtime guard.
    spec = PrimitiveSpec.model_construct(
        type="capsule",
        dimensions={"radius": 1.0},
        origin_xyz=[0.0, 0.0, 0.0],
        origin_rpy=[0.0, 0.0, 0.0],
    )
    with pytest.raises(ValueError, match="Unknown"):
        scale_primitive(spec, margin=0.1)


# ---------------------------------------------------------------------------
# Optional / exploratory
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Phase 2.5: rotated cylinder orientation recovery not yet implemented")
def test_fit_cylinder_rotated() -> None:  # pragma: no cover
    """Rotate a Z-cylinder 45 degrees about Y; verify rpy recovers orientation."""
    mesh = trimesh.creation.cylinder(radius=0.3, height=1.0, sections=64)
    angle = np.pi / 4
    rot = trimesh.transformations.rotation_matrix(angle, [0, 1, 0])
    mesh.apply_transform(rot)
    spec = fit_cylinder(mesh)
    # The pitch (rpy[1]) should be approximately ±45°.
    assert abs(spec.origin_rpy[1]) == pytest.approx(angle, abs=0.05)
