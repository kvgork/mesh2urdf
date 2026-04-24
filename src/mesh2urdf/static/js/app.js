import { initViewer, addMeshToScene, focusCameraOn, animate } from './viewer.js';
import { showToast, addLinkToSidebar, setUploadLoading, init as initUI } from './ui.js';

const state = {
  meshes: {},   // mesh_id -> { name, threeObj, bbox_min, bbox_max }
  links: [],
  joints: []
};

let linkCounter = 0;

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
    state.links.push({ name: linkName, mesh_id: data.mesh_id, mesh_filename: file.name });

    addLinkToSidebar(linkName);
    showToast(`Loaded ${file.name} as ${linkName}`, 'success');

    // Clear input so same file can be re-uploaded
    document.getElementById('mesh-file-input').value = '';
  } catch (e) {
    showToast('Network error: ' + e.message, 'error');
  } finally {
    setUploadLoading(false);
  }
}

// Wire up events after DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('viewport-container');
  initViewer(container);
  animate();
  initUI();

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
