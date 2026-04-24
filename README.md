# mesh2urdf

A web-based tool to convert 3D mesh files (STL/OBJ) into URDF robot descriptions with an interactive 3D viewer.

## Features

- **Mesh loading** — STL (binary + ASCII) and OBJ format support
- **Primitive fitting** — Auto-fit box, cylinder, or sphere to loaded meshes using AABB / PCA / min-sphere algorithms
- **Interactive editing** — Adjust primitive size, position, and rotation with 3D transform gizmos (W/E/R keys)
- **Multi-link robots** — Create multiple links and define fixed, revolute, or prismatic joints between them
- **Collision shapes** — Collision primitives scaled by a configurable margin (default 5%, slider 0–30%)
- **URDF export** — Download valid URDF with mesh visuals and primitive collision geometry

## Quick Start

```bash
pixi install
pixi run dev
```

Open http://localhost:8000 in your browser.

## Usage

1. Click **Upload** or drag a `.stl` / `.obj` file into the file input
2. The mesh appears in the 3D viewer and is auto-fitted with a box primitive (green wireframe)
3. Select the link in the sidebar to adjust the primitive type, dimensions, and collision margin
4. Use **W** (translate) / **E** (rotate) / **R** (scale) to move the primitive with the 3D gizmo
5. Add more links by uploading additional meshes
6. Use **+ Add Joint** to connect links with fixed, revolute, or prismatic joints
7. Click **Export URDF** to download `robot.urdf`

## Architecture

```
Browser (Three.js)          FastAPI backend
──────────────────          ──────────────
viewer.js  (scene)    ←──→  /api/mesh/load
primitives.js (overlays)    /api/primitive/fit
urdf_model.js (data)        /api/urdf/export
app.js (orchestration)
```

Backend is stateless (except a 1-hour mesh cache). All robot state lives in the browser.

## Development

```bash
pixi run test    # pytest -v
pixi run lint    # ruff check
pixi run dev     # uvicorn --reload
```

Tests live in `tests/`. Fixtures (cube.stl, cube.obj) are in `tests/fixtures/`.

## Extending

- **Inertial properties (Phase 7)**: Add `urdf-mesh-inertia` + `pymeshlab` deps and call
  `compute_inertial_parameters()` from `urdf_generator.py` to fill the `<inertial>` block.
  `LinkSpec` already has the reserved `inertial` field.
- **Mesh collision (VHACD)**: `object2urdf` is already a dependency — use
  `ObjectUrdfBuilder.do_vhacd()` to replace the primitive collision with a convex-decomposed mesh.
- **Mesh paths**: Change `meshes/{filename}` to `package://robot_name/meshes/{filename}` in
  `urdf_generator.py` for ROS package compatibility.
