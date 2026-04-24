# mesh2urdf

A web-based tool to convert 3D mesh files (STL/OBJ) into URDF robot descriptions with an interactive 3D viewer.

Load a mesh, auto-fit a collision primitive, connect links with joints, and export a valid URDF — all in the browser.

## Features

- **Mesh loading** — STL (binary + ASCII) and OBJ format support
- **Primitive fitting** — Auto-fit box, cylinder, or sphere using AABB / PCA / min-bounding-sphere
- **Interactive editing** — Translate, rotate, and scale primitives with 3D gizmos (W / E / R)
- **Multi-link robots** — Define multiple links and connect them with fixed, revolute, or prismatic joints
- **Collision shapes** — Collision primitives scaled by a configurable margin (default 5%, slider 0–30%)
- **URDF export** — Download a valid URDF with mesh visuals and primitive collision geometry

## Quick Start

Requires [pixi](https://pixi.sh).

```bash
pixi install
pixi run dev
```

Open <http://localhost:8000> in your browser.

## Usage

1. Click **Upload** or select a `.stl` / `.obj` file — the mesh appears in the 3D viewer and is auto-fitted with a box primitive (green wireframe)
2. Click the link name in the sidebar to open its editor:
   - Change the primitive type (box / sphere / cylinder) or click **Auto-fit**
   - Adjust dimensions with the number inputs
   - Drag the origin with the 3D gizmo — **W** translate, **E** rotate, **R** scale
   - Set the collision margin with the slider — the red wireframe shows the collision shape in real time
3. Upload additional meshes to create more links
4. Expand **+ Add Joint**, pick parent/child links and joint type, and click **Add Joint**
5. Click **Export URDF** to download `robot.urdf`

## Project Structure

```
mesh2urdf/
├── pyproject.toml              # pixi project + dependencies
├── pytest.ini                  # suppress ROS2 pytest plugins
├── src/mesh2urdf/
│   ├── main.py                 # FastAPI app, static mount, routers
│   ├── api/
│   │   ├── mesh.py             # POST /api/mesh/load, GET /api/mesh/{id}
│   │   ├── primitive.py        # POST /api/primitive/fit
│   │   └── urdf.py             # POST /api/urdf/export
│   ├── core/
│   │   ├── mesh_loader.py      # trimesh STL/OBJ loading + validation
│   │   ├── mesh_cache.py       # TTL in-memory cache (1 h, 32 slots)
│   │   ├── primitive_fitter.py # box / sphere / cylinder fitting
│   │   └── urdf_generator.py   # lxml URDF XML generation
│   ├── models/
│   │   └── schema.py           # Pydantic v2 request/response models
│   └── static/
│       ├── index.html
│       ├── css/style.css
│       └── js/
│           ├── app.js          # upload flow, state, event wiring
│           ├── viewer.js       # Three.js scene, camera, OrbitControls
│           ├── primitives.js   # primitive overlays + TransformControls
│           ├── urdf_model.js   # client-side Link/Joint model + validation
│           └── ui.js           # sidebar panels, toasts, dropdowns
└── tests/
    ├── fixtures/               # cube.stl, cube.obj
    ├── test_mesh_loader.py
    ├── test_primitive_fitter.py
    ├── test_primitive_api.py
    ├── test_urdf_generator.py
    ├── test_urdf_api.py
    └── test_api.py
```

## API Reference

All endpoints are served at `http://localhost:8000`.

### `GET /healthz`
Returns `{"status": "ok"}`.

### `POST /api/mesh/load`
Upload a mesh file.

- **Body:** `multipart/form-data`, field `file` (`.stl` or `.obj`)
- **Response:** `MeshLoadResponse`

```json
{
  "mesh_id": "uuid4",
  "vertex_count": 8,
  "face_count": 12,
  "bbox_min": [0.0, 0.0, 0.0],
  "bbox_max": [1.0, 1.0, 1.0],
  "vertices": [...],
  "indices": [...]
}
```

### `GET /api/mesh/{mesh_id}`
Returns mesh metadata (no vertex data). `404` if not in cache.

### `POST /api/primitive/fit`
Fit a primitive to a cached mesh.

- **Body:**
```json
{ "mesh_id": "uuid4", "primitive_type": "box" }
```
- **Response:** `PrimitiveSpec`
```json
{
  "type": "box",
  "dimensions": { "size_x": 1.0, "size_y": 1.0, "size_z": 1.0 },
  "origin": { "xyz": [0.5, 0.5, 0.5], "rpy": [0.0, 0.0, 0.0] }
}
```

Supported types: `box`, `cylinder`, `sphere`.

### `POST /api/urdf/export`
Generate and download a URDF file.

- **Body:** `URDFExportRequest` (JSON)
```json
{
  "robot_name": "my_robot",
  "links": [
    {
      "name": "base_link",
      "mesh_filename": "base.stl",
      "primitive": { "type": "box", "dimensions": {...}, "origin": {...} },
      "collision_margin": 0.05,
      "origin": { "xyz": [0,0,0], "rpy": [0,0,0] }
    }
  ],
  "joints": [
    {
      "name": "joint_1",
      "type": "revolute",
      "parent": "base_link",
      "child": "arm_link",
      "origin": { "xyz": [0,0,0.3], "rpy": [0,0,0] },
      "axis": [0, 0, 1],
      "limits": { "lower": -1.57, "upper": 1.57, "effort": 10.0, "velocity": 1.0 }
    }
  ]
}
```
- **Response:** `text/xml` attachment (`robot.urdf`)

## Development

```bash
pixi run test    # run pytest
pixi run lint    # ruff check
pixi run dev     # uvicorn with --reload on :8000
```

Tests use `FastAPI.TestClient` (via `httpx`). Fixtures live in `tests/fixtures/`.

## Architecture

```
Browser (Three.js)              FastAPI backend
──────────────────              ──────────────
viewer.js   (Three.js scene)
primitives.js (overlays + gizmos)  ←── POST /api/primitive/fit
urdf_model.js (Link/Joint model)
app.js      (orchestration)    ←──→  POST /api/mesh/load
ui.js       (sidebar panels)         POST /api/urdf/export
```

The backend is **stateless** except for a short-lived in-memory mesh cache (TTL 1 h, 32 slots). All robot state lives in the browser. **Single uvicorn worker required** — the cache is not shared across processes.

## Extending

### Inertial properties
`LinkSpec` has a reserved `inertial` field. To compute inertia from the mesh:

1. Add `urdf-mesh-inertia` and `pymeshlab` to `[tool.pixi.pypi-dependencies]`
2. In `urdf_generator.py`, call `compute_inertial_parameters(mesh_path, mass)` and render the returned `<inertial>` block per link

### Mesh-based collision (VHACD)
`object2urdf` is already a dependency. Replace the primitive collision element with a VHACD-decomposed mesh:

```python
from object2urdf import ObjectUrdfBuilder
builder = ObjectUrdfBuilder(tmp_dir)
builder.do_vhacd(mesh_path, vhacd_out_path)
```

### ROS package mesh paths
In `urdf_generator.py`, change:
```python
f"meshes/{link.mesh_filename}"
# to
f"package://{robot_name}/meshes/{link.mesh_filename}"
```

## License

MIT
