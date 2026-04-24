# mesh2urdf — Project Notes for Claude

## Stack
- Python backend: FastAPI + uvicorn, served via `pixi run dev`
- Frontend: vanilla JS + Three.js r160 via CDN import-map (no bundler)
- Mesh processing: trimesh
- URDF generation: lxml
- Package manager: pixi (`pyproject.toml` unified config)

## Key Schema Conventions
- `PrimitiveSpec.origin` is a nested dict: `{"xyz": [x,y,z], "rpy": [r,p,y]}` — NOT flat fields
- `PrimitiveSpec.dimensions` keys by type: box→`{size_x,size_y,size_z}`, cylinder→`{radius,length}`, sphere→`{radius}`
- `LinkSpec.mesh_filename` is basename only — path traversal blocked by validator
- All URDF names validated against `^[A-Za-z_][A-Za-z0-9_\-\.]*$`

## Architecture
- Backend is **stateless** — only a TTL mesh cache (1h, 32 entries) keyed by uuid4
- Frontend holds all robot state (links, joints, Three.js objects) in memory
- `URDFModel` JS class strips `threeRefs` before POST to `/api/urdf/export`
- Single uvicorn worker required (in-memory cache not shared across workers)

## Future Extensions
- **Phase 7 — Inertial**: add `urdf-mesh-inertia` + `pymeshlab`, call `compute_inertial_parameters()` in `urdf_generator.py`. `LinkSpec` has reserved `inertial` field.
- **VHACD mesh collision**: `object2urdf` is already a dep — use `ObjectUrdfBuilder.do_vhacd()` as alternative collision mode
- **ROS mesh paths**: change `meshes/{filename}` to `package://robot_name/meshes/{filename}` in `urdf_generator.py`

## Running Tests
```bash
pixi run test    # pytest -v (61 passing, 1 skipped)
pixi run lint    # ruff check
pixi run dev     # uvicorn --reload on :8000
```

## Known Issue
`pytest.ini` suppresses ROS2 ament/launch pytest11 entry points that leak into the pixi Python 3.14 env.
