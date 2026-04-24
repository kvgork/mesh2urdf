"""Primitive fitting engine for trimesh.Trimesh objects.

Provides AABB box fit, minimum bounding sphere, PCA-based cylinder fit,
and a uniform scaling helper for collision margin expansion.
"""

from __future__ import annotations

import numpy as np
import trimesh
import trimesh.nsphere
from scipy.spatial.transform import Rotation

from mesh2urdf.models.schema import PrimitiveSpec


def fit_box(mesh: trimesh.Trimesh) -> PrimitiveSpec:
    """Fit an axis-aligned bounding box to the mesh.

    The box is the tightest AABB in mesh-local coordinates.
    If the mesh is pre-rotated the AABB will be loose (known limitation).

    Args:
        mesh: Input trimesh object.

    Returns:
        PrimitiveSpec of type "box" with size and center.

    Raises:
        ValueError: If the mesh has no vertices.
    """
    if len(mesh.vertices) == 0:
        raise ValueError("empty mesh")

    bmin, bmax = mesh.bounds  # each is shape (3,)
    center = ((bmin + bmax) / 2.0).tolist()
    size = (bmax - bmin).tolist()

    return PrimitiveSpec(
        type="box",
        dimensions={"size_x": size[0], "size_y": size[1], "size_z": size[2]},
        origin={"xyz": center, "rpy": [0.0, 0.0, 0.0]},
    )


def fit_sphere(mesh: trimesh.Trimesh) -> PrimitiveSpec:
    """Fit a minimum bounding sphere to the mesh.

    Uses trimesh.nsphere.minimum_nsphere for meshes with <= 100 000 vertices
    (Welzl algorithm).  Falls back to trimesh's approximate bounding sphere
    for denser meshes or if minimum_nsphere raises.

    Args:
        mesh: Input trimesh object.

    Returns:
        PrimitiveSpec of type "sphere" with radius and center.

    Raises:
        ValueError: If the mesh has no vertices.
    """
    if len(mesh.vertices) == 0:
        raise ValueError("empty mesh")

    if mesh.vertices.shape[0] > 100_000:
        sphere = mesh.bounding_sphere.primitive
        center = list(map(float, sphere.center))
        radius = float(sphere.radius)
    else:
        try:
            center_arr, radius = trimesh.nsphere.minimum_nsphere(mesh.vertices)
            center = list(map(float, center_arr))
            radius = float(radius)
        except Exception:
            sphere = mesh.bounding_sphere.primitive
            center = list(map(float, sphere.center))
            radius = float(sphere.radius)

    return PrimitiveSpec(
        type="sphere",
        dimensions={"radius": radius},
        origin={"xyz": center, "rpy": [0.0, 0.0, 0.0]},
    )


def fit_cylinder(mesh: trimesh.Trimesh) -> PrimitiveSpec:
    """Fit a cylinder to the mesh using PCA to determine the principal axis.

    Algorithm:
    1. Compute vertex covariance matrix.
    2. Eigendecompose (eigh — symmetric, ascending order); principal axis is
       the eigenvector corresponding to the largest eigenvalue.
    3. Canonicalize axis sign so the component with the largest absolute value
       is positive (makes results deterministic across runs).
    4. Project vertices onto the axis to get length and axial centre offset.
    5. Compute perpendicular distance for radius.
    6. Convert axis to RPY via trimesh.geometry.align_vectors([0,0,1], axis).

    Args:
        mesh: Input trimesh object.

    Returns:
        PrimitiveSpec of type "cylinder" with radius, length, and orientation.

    Raises:
        ValueError: If the mesh has no vertices.
    """
    if len(mesh.vertices) == 0:
        raise ValueError("empty mesh")

    verts = np.asarray(mesh.vertices, dtype=float)
    centroid = verts.mean(axis=0)
    centered = verts - centroid

    cov = np.cov(centered.T)
    _eigvals, eigvecs = np.linalg.eigh(cov)  # ascending order
    axis = eigvecs[:, -1].copy()  # largest eigenvalue last

    # Canonicalize sign: component with largest |value| must be positive.
    dominant = int(np.argmax(np.abs(axis)))
    if axis[dominant] < 0:
        axis = -axis

    # Axial projections → length and centre.
    proj = centered @ axis  # shape (N,)
    proj_max = float(proj.max())
    proj_min = float(proj.min())
    length = proj_max - proj_min
    axial_offset = (proj_max + proj_min) / 2.0
    center = centroid + axial_offset * axis

    # Perpendicular radius.
    perp = centered - np.outer(proj, axis)
    radius = float(np.linalg.norm(perp, axis=1).max())

    # Convert axis to RPY.
    z_axis = np.array([0.0, 0.0, 1.0])
    dot = float(np.dot(axis, z_axis))

    if abs(dot) > 0.9999:
        # Already (anti-)parallel to Z — no rotation needed.
        rpy = [0.0, 0.0, 0.0]
    else:
        T = trimesh.geometry.align_vectors(z_axis, axis)  # 4x4 matrix
        R = T[:3, :3]
        rpy = Rotation.from_matrix(R).as_euler("xyz").tolist()

    return PrimitiveSpec(
        type="cylinder",
        dimensions={"radius": radius, "length": length},
        origin={"xyz": center.tolist(), "rpy": rpy},
    )


def scale_primitive(spec: PrimitiveSpec, margin: float) -> PrimitiveSpec:
    """Scale all geometric dimensions by (1 + margin).

    The origin (xyz and rpy) is preserved unchanged.

    Args:
        spec: The PrimitiveSpec to scale.
        margin: Fractional margin, e.g. 0.10 for +10%.

    Returns:
        A new PrimitiveSpec with scaled dimensions and identical origin.

    Raises:
        ValueError: If spec.type is not recognised.
    """
    factor = 1.0 + margin

    if spec.type == "box":
        new_dims: dict[str, float] = {
            "size_x": spec.dimensions["size_x"] * factor,
            "size_y": spec.dimensions["size_y"] * factor,
            "size_z": spec.dimensions["size_z"] * factor,
        }
    elif spec.type == "sphere":
        new_dims = {"radius": spec.dimensions["radius"] * factor}
    elif spec.type == "cylinder":
        new_dims = {
            "radius": spec.dimensions["radius"] * factor,
            "length": spec.dimensions["length"] * factor,
        }
    else:
        raise ValueError(f"Unknown primitive type: {spec.type!r}")

    return PrimitiveSpec(
        type=spec.type,
        dimensions=new_dims,
        origin=dict(spec.origin),
    )
