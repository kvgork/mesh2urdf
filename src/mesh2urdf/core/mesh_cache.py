from __future__ import annotations

import uuid

import trimesh
from cachetools import TTLCache

_cache: TTLCache = TTLCache(maxsize=32, ttl=3600)


def put_mesh(mesh: trimesh.Trimesh) -> str:
    """Store a mesh in the cache and return its unique ID.

    Args:
        mesh: The trimesh.Trimesh object to store.

    Returns:
        A UUID4 string that can be used to retrieve the mesh.
    """
    mesh_id = str(uuid.uuid4())
    _cache[mesh_id] = mesh
    return mesh_id


def get_mesh(mesh_id: str) -> trimesh.Trimesh | None:
    """Retrieve a mesh from the cache by ID.

    Args:
        mesh_id: The UUID4 string returned by put_mesh.

    Returns:
        The trimesh.Trimesh object, or None if not found or expired.
    """
    return _cache.get(mesh_id)


def clear_cache() -> None:
    """Clear all cached meshes (intended for testing)."""
    _cache.clear()
