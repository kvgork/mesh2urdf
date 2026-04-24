"""FastAPI router for primitive fitting operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from mesh2urdf.core.mesh_cache import get_mesh
from mesh2urdf.core.primitive_fitter import fit_box, fit_cylinder, fit_sphere
from mesh2urdf.models.schema import PrimitiveFitRequest, PrimitiveSpec

router = APIRouter(prefix="/primitive", tags=["primitive"])

_FITTERS = {
    "box": fit_box,
    "sphere": fit_sphere,
    "cylinder": fit_cylinder,
}


@router.post("/fit", response_model=PrimitiveSpec)
def fit(req: PrimitiveFitRequest) -> PrimitiveSpec:
    """Fit a geometric primitive to a cached mesh.

    Args:
        req: Request containing mesh_id and desired primitive_type.

    Returns:
        PrimitiveSpec describing the fitted primitive.

    Raises:
        HTTPException 404: If mesh_id is not found in the cache.
        HTTPException 400: If primitive_type is not supported.
    """
    mesh = get_mesh(req.mesh_id)
    if mesh is None:
        raise HTTPException(status_code=404, detail=f"mesh_id {req.mesh_id!r} not found")

    fitter = _FITTERS.get(req.primitive_type)
    if fitter is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported primitive_type {req.primitive_type!r}. "
            f"Supported: {sorted(_FITTERS)}",
        )

    return fitter(mesh)
