from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mesh2urdf.api.mesh import router as mesh_router
from mesh2urdf.api.primitive import router as primitive_router

app = FastAPI(title="mesh2urdf", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/healthz", tags=["health"])
async def healthz():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/", tags=["frontend"])
async def root():
    """Serve the frontend index.html."""
    return FileResponse(STATIC_DIR / "index.html")


app.include_router(mesh_router, prefix="/api")
app.include_router(primitive_router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
