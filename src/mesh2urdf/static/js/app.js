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
  updateLinkDropdowns,
  addJointToList,
} from './ui.js';
import {
  createPrimitiveOverlay,
  updateCollisionOverlay,
  updatePrimitiveFromObject,
  disposePrimitiveOverlay,
  applySpecPose,
} from './primitives.js';
import { URDFModel } from './urdf_model.js';

const state = {
  meshes: {},        // mesh_id -> { name, threeObj, bbox_min, bbox_max }
  links: [],         // [{name, mesh_id, mesh_filename, primitive, collision_margin, visualOverlay, collisionOverlay}]
  joints: [],
  selectedLink: null,
  linkOverlays: {},  // linkName -> { visual, collision }
};

let linkCounter = 0;
const urdfModel = new URDFModel();

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

    // Sync primitive into URDFModel
    if (urdfModel.links.has(linkName)) {
      urdfModel.updateLink(linkName, { primitive: spec });
    }

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
      if (urdfModel.links.has(linkName)) {
        urdfModel.updateLink(linkName, { collision_margin: m });
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
    const linkState = {
      name: linkName,
      mesh_id: data.mesh_id,
      mesh_filename: file.name,
      collision_margin: 0.05,
      primitive: null,
      visualOverlay: null,
      collisionOverlay: null,
    };
    state.links.push(linkState);

    // Register link in URDF model
    urdfModel.addLink({
      name: linkName,
      mesh_filename: file.name,
      primitive: null,
      collision_margin: 0.05,
      origin_xyz: [0.0, 0.0, 0.0],
      origin_rpy: [0.0, 0.0, 0.0],
    });

    addLinkToSidebar(linkName, selectLink);
    updateLinkDropdowns(urdfModel.getLinkNames());
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
// Joint creation
// ---------------------------------------------------------------------------

function _wireJointForm() {
  const typeSelect = document.getElementById('joint-type');
  const axisRow = document.getElementById('joint-axis-row');

  typeSelect.addEventListener('change', (e) => {
    const needsAxis = e.target.value !== 'fixed';
    axisRow.style.display = needsAxis ? 'block' : 'none';
  });

  document.getElementById('add-joint-btn').addEventListener('click', () => {
    const name = document.getElementById('joint-name').value.trim();
    const type = document.getElementById('joint-type').value;
    const parent = document.getElementById('joint-parent').value;
    const child = document.getElementById('joint-child').value;

    if (!name || !parent || !child) {
      showToast('Fill in all joint fields', 'error');
      return;
    }

    const axis = type !== 'fixed' ? [
      parseFloat(document.getElementById('axis-x').value) || 0,
      parseFloat(document.getElementById('axis-y').value) || 0,
      parseFloat(document.getElementById('axis-z').value) || 1,
    ] : null;

    const spec = {
      name,
      type,
      parent,
      child,
      origin_xyz: [0.0, 0.0, 0.0],
      origin_rpy: [0.0, 0.0, 0.0],
      axis,
      limit: null,
    };

    try {
      urdfModel.addJoint(spec);
    } catch (e) {
      showToast(e.message, 'error');
      return;
    }

    addJointToList(name, type, parent, child, (removedName) => {
      urdfModel.removeJoint(removedName);
    });

    showToast(`Added ${type} joint: ${name}`, 'success');

    // Reset form
    document.getElementById('joint-name').value = '';
    document.getElementById('joint-parent').value = '';
    document.getElementById('joint-child').value = '';
    axisRow.style.display = 'none';
    typeSelect.value = 'fixed';
  });
}

// ---------------------------------------------------------------------------
// URDF export
// ---------------------------------------------------------------------------

function _wireExportButton() {
  document.getElementById('export-btn').addEventListener('click', async () => {
    // Ensure all links have a fitted primitive before export
    for (const link of state.links) {
      if (!link.primitive) {
        showToast(`Link '${link.name}' has no fitted primitive. Auto-fitting box...`, 'info');
        await fitPrimitive(link.name, 'box');
      }
    }

    const payload = urdfModel.toExportPayload();

    try {
      const response = await fetch('/api/urdf/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Export failed' }));
        showToast(err.detail || 'Export failed', 'error');
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${urdfModel.robotName}.urdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('URDF exported!', 'success');
    } catch (e) {
      showToast('Export error: ' + e.message, 'error');
    }
  });
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

  _wireJointForm();
  _wireExportButton();

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
  window.__mesh2urdf = { state, urdfModel };
}

export { state, urdfModel };
