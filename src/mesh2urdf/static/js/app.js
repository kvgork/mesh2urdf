import {
  initViewer,
  addMeshToScene,
  focusCameraOn,
  animate,
  initTransformControls,
  setTransformTarget,
  onTransformChange,
  removeFromScene,
  scene,
} from './viewer.js';
import {
  showToast,
  addLinkToSidebar,
  setUploadLoading,
  init as initUI,
  showPrimitiveEditor,
  updatePrimitiveEditorSpec,
} from './ui.js';
import {
  createPrimitiveOverlay,
  updateCollisionOverlay,
  updatePrimitiveFromObject,
  disposePrimitiveOverlay,
  applySpecPose,
} from './primitives.js';

const state = {
  meshes: {},        // mesh_id -> { name, threeObj, bbox_min, bbox_max }
  links: [],         // [{name, mesh_id, mesh_filename, primitive, collision_margin, visualOverlay, collisionOverlay}]
  joints: [],
  selectedLink: null,
  linkOverlays: {},  // linkName -> { visual, collision }
};

let linkCounter = 0;

// ---------------------------------------------------------------------------
// Primitive fitting
// ---------------------------------------------------------------------------

async function fitPrimitive(linkName, primitiveType) {
  const link = state.links.find(l => l.name === linkName);
  if (!link) return;

  try {
    const response = await fetch('/api/primitive/fit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mesh_id: link.mesh_id, primitive_type: primitiveType }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Fit failed' }));
      showToast(err.detail || 'Fit failed', 'error');
      return;
    }

    const spec = await response.json();
    link.primitive = spec;

    // Dispose existing overlays if any
    const existing = state.linkOverlays[linkName];
    if (existing) {
      disposePrimitiveOverlay(existing);
      delete state.linkOverlays[linkName];
    }

    const margin = link.collision_margin ?? 0.05;
    const { visual, collision } = createPrimitiveOverlay(spec, margin);
    scene.add(visual);
    scene.add(collision);

    link.visualOverlay = visual;
    link.collisionOverlay = collision;
    state.linkOverlays[linkName] = { visual, collision };

    setTransformTarget(visual);
    updatePrimitiveEditorSpec(spec);
    showToast(`Fitted ${primitiveType} to ${linkName}`, 'success');
  } catch (e) {
    showToast('Fit error: ' + e.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Link selection
// ---------------------------------------------------------------------------

function selectLink(linkName) {
  const link = state.links.find(l => l.name === linkName);
  if (!link) return;

  state.selectedLink = linkName;

  // Highlight selected link item
  document.querySelectorAll('.link-item').forEach(el => el.classList.remove('selected'));
  const item = document.querySelector(`.link-item[data-name="${linkName}"]`);
  if (item) item.classList.add('selected');

  // Attach gizmo to this link's visual overlay if it exists
  if (state.linkOverlays[linkName]) {
    setTransformTarget(state.linkOverlays[linkName].visual);
  } else {
    setTransformTarget(null);
  }

  const margin = link.collision_margin ?? 0.05;
  const spec = link.primitive || {
    type: 'box',
    dimensions: { size_x: 0.1, size_y: 0.1, size_z: 0.1 },
    origin: { xyz: [0, 0, 0], rpy: [0, 0, 0] },
  };

  showPrimitiveEditor(linkName, spec, margin, {
    onFit: (type) => fitPrimitive(linkName, type),
    onTypeChange: (type) => fitPrimitive(linkName, type),
    onMarginChange: (m) => {
      link.collision_margin = m;
      const overlay = state.linkOverlays[linkName];
      if (overlay && link.primitive) {
        updateCollisionOverlay(overlay.collision, link.primitive, m);
      }
    },
    onDimensionChange: (_dims) => {
      // Rebuild overlays from updated spec (spec.dimensions already mutated by ui.js)
      const overlay = state.linkOverlays[linkName];
      if (!overlay || !link.primitive) return;
      const m = link.collision_margin ?? 0.05;

      // Dispose old overlays
      disposePrimitiveOverlay(overlay);
      delete state.linkOverlays[linkName];
      link.visualOverlay = null;
      link.collisionOverlay = null;

      const { visual, collision } = createPrimitiveOverlay(link.primitive, m);
      scene.add(visual);
      scene.add(collision);
      link.visualOverlay = visual;
      link.collisionOverlay = collision;
      state.linkOverlays[linkName] = { visual, collision };
      setTransformTarget(visual);
    },
    onOriginChange: (_origin) => {
      // spec.origin already mutated by ui.js input handler; sync Three.js objects
      const overlay = state.linkOverlays[linkName];
      if (!overlay || !link.primitive) return;
      applySpecPose(overlay.visual, link.primitive);
      applySpecPose(overlay.collision, link.primitive);
    },
  });
}

// ---------------------------------------------------------------------------
// Mesh upload
// ---------------------------------------------------------------------------

async function uploadMesh(file) {
  setUploadLoading(true);
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/mesh/load', { method: 'POST', body: formData });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
      showToast(err.detail || 'Upload failed', 'error');
      return;
    }

    const data = await response.json();
    linkCounter++;
    const linkName = `link_${linkCounter}`;

    const threeObj = addMeshToScene(data.vertices, data.indices, linkName);
    focusCameraOn(threeObj);

    state.meshes[data.mesh_id] = { name: linkName, threeObj, bbox_min: data.bbox_min, bbox_max: data.bbox_max };
    state.links.push({
      name: linkName,
      mesh_id: data.mesh_id,
      mesh_filename: file.name,
      collision_margin: 0.05,
      primitive: null,
      visualOverlay: null,
      collisionOverlay: null,
    });

    addLinkToSidebar(linkName, selectLink);
    showToast(`Loaded ${file.name} as ${linkName}`, 'success');

    // Clear input so same file can be re-uploaded
    document.getElementById('mesh-file-input').value = '';

    // Auto-fit a box primitive immediately after upload, then open the editor
    await fitPrimitive(linkName, 'box');
    selectLink(linkName);
  } catch (e) {
    showToast('Network error: ' + e.message, 'error');
  } finally {
    setUploadLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('viewport-container');
  initViewer(container);
  animate();
  initUI();
  initTransformControls();

  // Register transform-change handler once: syncs spec + collision when gizmo dragged
  onTransformChange(() => {
    const selName = state.selectedLink;
    if (!selName) return;
    const link = state.links.find(l => l.name === selName);
    const overlay = state.linkOverlays[selName];
    if (!link || !overlay || !link.primitive) return;

    updatePrimitiveFromObject(link.primitive, overlay.visual);

    // Sync collision overlay position/rotation to match visual
    overlay.collision.position.copy(overlay.visual.position);
    overlay.collision.rotation.copy(overlay.visual.rotation);

    updatePrimitiveEditorSpec(link.primitive);
  });

  document.getElementById('upload-btn').addEventListener('click', () => {
    const input = document.getElementById('mesh-file-input');
    if (input.files.length > 0) uploadMesh(input.files[0]);
    else showToast('Select a file first', 'info');
  });

  document.getElementById('mesh-file-input').addEventListener('change', (e) => {
    if (e.target.files.length > 0) uploadMesh(e.target.files[0]);
  });
});

// Dev convenience
if (typeof window !== 'undefined') {
  window.__mesh2urdf = { state };
}

export { state };
