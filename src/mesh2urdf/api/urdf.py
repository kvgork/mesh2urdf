"""FastAPI router for URDF export."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from mesh2urdf.core.urdf_generator import _validate_request, generate_urdf
from mesh2urdf.models.schema import URDFExportRequest

router = APIRouter(prefix="/api/urdf", tags=["urdf"])


@router.post("/export")
def export_urdf(req: URDFExportRequest) -> Response:
    """Generate and return a URDF file for download.

    Validates the request (link/joint references, cycle detection) and
    returns the URDF XML as an attachment.

    Returns:
        XML response with Content-Disposition: attachment; filename="robot.urdf"

    Raises:
        HTTPException 422: If the request fails structural validation.
    """
    try:
        _validate_request(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # generate_urdf returns UTF-8 bytes with XML declaration
    xml_bytes = generate_urdf(req)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="robot.urdf"'},
    )
