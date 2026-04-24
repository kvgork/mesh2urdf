from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from mesh2urdf.core.mesh_cache import get_mesh, put_mesh
from mesh2urdf.core.mesh_loader import load_mesh, mesh_to_response
from mesh2urdf.models.schema import MeshMetadataResponse

router = APIRouter(prefix="/mesh", tags=["mesh"])

_ALLOWED_EXTENSIONS = {".stl", ".obj"}


@router.post("/load")
async def load_mesh_endpoint(file: UploadFile = File(...)):
    """Upload a mesh file (STL or OBJ) and return its geometry data.

    The mesh is stored in the in-memory cache and a mesh_id is returned
    for subsequent API calls.
    """
    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    data = await file.read()

    try:
        mesh = load_mesh(data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mesh_id = put_mesh(mesh)
    return mesh_to_response(mesh, mesh_id)


@router.get("/{mesh_id}", response_model=MeshMetadataResponse)
async def get_mesh_metadata(mesh_id: str):
    """Return metadata for a previously uploaded mesh."""
    mesh = get_mesh(mesh_id)
    if mesh is None:
        raise HTTPException(status_code=404, detail="Mesh not found")

    return MeshMetadataResponse(
        mesh_id=mesh_id,
        vertex_count=int(len(mesh.vertices)),
        face_count=int(len(mesh.faces)),
        bounds=mesh.bounds.tolist(),
        centroid=mesh.centroid.tolist(),
    )
