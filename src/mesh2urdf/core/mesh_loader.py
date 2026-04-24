from __future__ import annotations

import io

import numpy as np
import trimesh

_SUPPORTED = {"stl", "obj"}


def load_mesh(data: bytes, filename: str) -> trimesh.Trimesh:
    """Load a mesh from raw bytes.

    Args:
        data: Raw bytes of the mesh file.
        filename: Original filename (used to determine format by extension).

    Returns:
        A validated trimesh.Trimesh object.

    Raises:
        ValueError: If the format is unsupported, or the mesh is empty/invalid.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _SUPPORTED:
        raise ValueError(f"Unsupported format: '{ext}'. Supported: {sorted(_SUPPORTED)}")

    try:
        result = trimesh.load(io.BytesIO(data), file_type=ext, force="mesh")
    except Exception as exc:
        raise ValueError(f"Failed to parse mesh: {exc}") from exc

    # Handle Scene fallback (force="mesh" usually handles this, but be defensive)
    if isinstance(result, trimesh.Scene):
        meshes = list(result.geometry.values())
        if not meshes:
            raise ValueError("Empty or invalid mesh: Scene contains no geometries")
        result = trimesh.util.concatenate(meshes)

    if not isinstance(result, trimesh.Trimesh):
        raise ValueError("Empty or invalid mesh: could not produce a Trimesh object")

    if len(result.vertices) == 0 or len(result.faces) == 0:
        raise ValueError("Empty or invalid mesh: no vertices or faces")

    if not np.isfinite(result.vertices).all():
        raise ValueError("Non-finite vertices detected in mesh")

    return result


def mesh_to_response(mesh: trimesh.Trimesh, mesh_id: str) -> dict:
    """Convert a trimesh.Trimesh to a serialisable response dict.

    Args:
        mesh: The loaded mesh.
        mesh_id: Cache identifier for this mesh.

    Returns:
        Dict compatible with MeshLoadResponse schema.
    """
    vertices = mesh.vertices.astype(np.float32).flatten().tolist()
    indices = mesh.faces.astype(np.uint32).flatten().tolist()
    bounds = mesh.bounds.tolist()  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
    centroid = mesh.centroid.tolist()

    return {
        "mesh_id": mesh_id,
        "vertex_count": int(len(mesh.vertices)),
        "face_count": int(len(mesh.faces)),
        "bounds": bounds,
        "centroid": centroid,
        "vertices": vertices,
        "indices": indices,
    }
