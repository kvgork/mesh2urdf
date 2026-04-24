export function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

export function addLinkToSidebar(name, onSelect) {
  const list = document.getElementById('links-list');
  const hint = list.querySelector('.empty-hint');
  if (hint) hint.remove();

  const item = document.createElement('div');
  item.className = 'link-item';
  item.dataset.name = name;
  item.textContent = name;

  if (onSelect) {
    item.addEventListener('click', () => onSelect(name));
  }

  list.appendChild(item);
  updateExportButton();
}

export function updateExportButton() {
  const list = document.getElementById('links-list');
  const hasLinks = list.querySelectorAll('.link-item').length > 0;
  document.getElementById('export-btn').disabled = !hasLinks;
}

export function setUploadLoading(loading) {
  const btn = document.getElementById('upload-btn');
  btn.disabled = loading;
  btn.textContent = loading ? 'Uploading...' : 'Upload';
}

export function init() {
  // Export button handler is wired in app.js after URDFModel is available
}

// ---------------------------------------------------------------------------
// Primitive editor sidebar panel
// ---------------------------------------------------------------------------

/**
 * Render or replace the primitive editor panel in the sidebar.
 *
 * @param {string} linkName  - Display name for the panel header
 * @param {object} spec      - PrimitiveSpec {type, dimensions, origin:{xyz,rpy}}
 * @param {number} margin    - Collision margin fraction (e.g. 0.05 = 5%)
 * @param {object} callbacks - {onFit, onTypeChange, onMarginChange, onDimensionChange, onOriginChange}
 */
export function showPrimitiveEditor(linkName, spec, margin, callbacks) {
  // Remove existing editor if any
  const existing = document.getElementById('primitive-editor');
  if (existing) existing.remove();

  const panel = document.createElement('div');
  panel.id = 'primitive-editor';

  const pct = Math.round(margin * 100);
  panel.innerHTML = `
    <h3>Edit: ${linkName}</h3>
    <label>Primitive type
      <select id="prim-type">
        <option value="box"      ${spec.type === 'box'      ? 'selected' : ''}>Box</option>
        <option value="sphere"   ${spec.type === 'sphere'   ? 'selected' : ''}>Sphere</option>
        <option value="cylinder" ${spec.type === 'cylinder' ? 'selected' : ''}>Cylinder</option>
      </select>
    </label>
    <button id="autofit-btn" class="btn-primary">Auto-fit</button>
    <div id="dim-controls"></div>
    <div id="origin-controls">
      <label>Origin XYZ (m)</label>
      <div class="input-row">
        ${numInput('origin-x', 'X', spec.origin.xyz[0])}
        ${numInput('origin-y', 'Y', spec.origin.xyz[1])}
        ${numInput('origin-z', 'Z', spec.origin.xyz[2])}
      </div>
      <label>Origin RPY (rad)</label>
      <div class="input-row">
        ${numInput('origin-r', 'R', spec.origin.rpy[0])}
        ${numInput('origin-p', 'P', spec.origin.rpy[1])}
        ${numInput('origin-y', 'Y', spec.origin.rpy[2])}
      </div>
    </div>
    <label>Collision margin: <span id="margin-val">${pct}%</span></label>
    <input type="range" id="margin-slider" min="0" max="30" step="1" value="${pct}">
  `;

  const exportSection = document.getElementById('export-section');
  exportSection.parentNode.insertBefore(panel, exportSection);

  // Render dimension inputs for current type
  _renderDimControls(spec, callbacks);

  // Type dropdown
  document.getElementById('prim-type').addEventListener('change', (e) => {
    if (callbacks.onTypeChange) callbacks.onTypeChange(e.target.value);
  });

  // Auto-fit button
  document.getElementById('autofit-btn').addEventListener('click', () => {
    const type = document.getElementById('prim-type').value;
    if (callbacks.onFit) callbacks.onFit(type);
  });

  // Margin slider
  document.getElementById('margin-slider').addEventListener('input', (e) => {
    const m = parseInt(e.target.value, 10) / 100;
    document.getElementById('margin-val').textContent = e.target.value + '%';
    if (callbacks.onMarginChange) callbacks.onMarginChange(m);
  });

  // Origin inputs
  _wireOriginInputs(spec, callbacks);
}

function _wireOriginInputs(spec, callbacks) {
  const ids = [
    { id: 'dim-origin-x', idx: 0, axis: 'xyz' },
    { id: 'dim-origin-y', idx: 1, axis: 'xyz' },
    { id: 'dim-origin-z', idx: 2, axis: 'xyz' },
    { id: 'dim-origin-r', idx: 0, axis: 'rpy' },
    { id: 'dim-origin-p', idx: 1, axis: 'rpy' },
    { id: 'dim-origin-y', idx: 2, axis: 'rpy' },
  ];
  for (const { id, idx, axis } of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.addEventListener('change', () => {
      const val = parseFloat(el.value);
      if (!isNaN(val)) {
        spec.origin[axis][idx] = val;
        if (callbacks.onOriginChange) callbacks.onOriginChange(spec.origin);
      }
    });
  }
}

function _renderDimControls(spec, callbacks) {
  const container = document.getElementById('dim-controls');
  if (!container) return;
  const d = spec.dimensions;
  let html = '';
  if (spec.type === 'box') {
    html = numInput('dim-size_x', 'Width (X)', d.size_x)
         + numInput('dim-size_y', 'Height (Y)', d.size_y)
         + numInput('dim-size_z', 'Depth (Z)', d.size_z);
  } else if (spec.type === 'sphere') {
    html = numInput('dim-radius', 'Radius', d.radius);
  } else if (spec.type === 'cylinder') {
    html = numInput('dim-radius', 'Radius', d.radius)
         + numInput('dim-length', 'Length', d.length);
  }
  container.innerHTML = html;

  // Wire change listeners for dimension inputs
  for (const el of container.querySelectorAll('input[type=number]')) {
    el.addEventListener('change', () => {
      const key = el.id.replace('dim-', '');
      const val = parseFloat(el.value);
      if (!isNaN(val) && val > 0) {
        spec.dimensions[key] = val;
        if (callbacks.onDimensionChange) callbacks.onDimensionChange(spec.dimensions);
      }
    });
  }
}

function numInput(id, label, value) {
  const v = (typeof value === 'number' ? value : 0).toFixed(4);
  return `<label class="dim-label">${label}<input type="number" id="dim-${id}" value="${v}" step="0.001" min="0.0001"></label>`;
}

/**
 * Refresh all input values in the primitive editor from the latest spec.
 * Called after a gizmo drag or auto-fit to keep inputs in sync.
 */
export function updatePrimitiveEditorSpec(spec) {
  const typeEl = document.getElementById('prim-type');
  if (!typeEl) return; // panel not open

  if (typeEl.value !== spec.type) {
    typeEl.value = spec.type;
  }

  // Dimension inputs (re-render to handle type changes)
  const container = document.getElementById('dim-controls');
  if (container) {
    // Update values without losing focus; fall back to re-render
    const d = spec.dimensions;
    const setVal = (id, v) => {
      const el = document.getElementById(`dim-${id}`);
      if (el && document.activeElement !== el) el.value = (+v).toFixed(4);
    };
    if (spec.type === 'box') {
      setVal('dim-size_x', d.size_x);
      setVal('dim-size_y', d.size_y);
      setVal('dim-size_z', d.size_z);
    } else if (spec.type === 'sphere') {
      setVal('dim-radius', d.radius);
    } else if (spec.type === 'cylinder') {
      setVal('dim-radius', d.radius);
      setVal('dim-length', d.length);
    }
  }

  // Origin inputs
  const setOrigin = (id, v) => {
    const el = document.getElementById(`dim-${id}`);
    if (el && document.activeElement !== el) el.value = (+v).toFixed(4);
  };
  setOrigin('origin-x', spec.origin.xyz[0]);
  setOrigin('origin-y', spec.origin.xyz[1]);
  setOrigin('origin-z', spec.origin.xyz[2]);
  setOrigin('origin-r', spec.origin.rpy[0]);
  setOrigin('origin-p', spec.origin.rpy[1]);
  setOrigin('origin-y', spec.origin.rpy[2]);
}

// ---------------------------------------------------------------------------
// Joint UI helpers
// ---------------------------------------------------------------------------

/**
 * Populate the parent/child link dropdowns in the joint creation form.
 * Preserves current selection if still valid.
 * @param {string[]} linkNames - Array of available link names from URDFModel
 */
export function updateLinkDropdowns(linkNames) {
  const parentSel = document.getElementById('joint-parent');
  const childSel = document.getElementById('joint-child');
  if (!parentSel || !childSel) return;

  const prevParent = parentSel.value;
  const prevChild = childSel.value;

  parentSel.innerHTML = '<option value="">-- select --</option>';
  childSel.innerHTML = '<option value="">-- select --</option>';

  for (const name of linkNames) {
    const opt1 = document.createElement('option');
    opt1.value = name;
    opt1.textContent = name;
    parentSel.appendChild(opt1);

    const opt2 = document.createElement('option');
    opt2.value = name;
    opt2.textContent = name;
    childSel.appendChild(opt2);
  }

  // Restore previous selections if still valid
  if (linkNames.includes(prevParent)) parentSel.value = prevParent;
  if (linkNames.includes(prevChild)) childSel.value = prevChild;
}

/**
 * Append a joint row to the joints list in the sidebar.
 * @param {string} name
 * @param {string} type
 * @param {string} parent
 * @param {string} child
 * @param {function} onRemove - Called with (name) when remove button clicked
 */
export function addJointToList(name, type, parent, child, onRemove) {
  const list = document.getElementById('joints-list');
  const hint = list.querySelector('.empty-hint');
  if (hint) hint.remove();

  const item = document.createElement('div');
  item.className = 'joint-item';
  item.dataset.name = name;
  item.innerHTML = `
    <span class="joint-info">
      <strong>${name}</strong>
      <span class="joint-type">${type}</span>
      <span class="joint-parents">${parent} &rarr; ${child}</span>
    </span>
    <button class="joint-remove-btn" title="Remove joint">&times;</button>
  `;

  item.querySelector('.joint-remove-btn').addEventListener('click', () => {
    item.remove();
    if (onRemove) onRemove(name);
    // Restore hint if no joints remain
    if (!list.querySelector('.joint-item')) {
      const hint2 = document.createElement('p');
      hint2.className = 'empty-hint';
      hint2.textContent = 'Add links first';
      list.insertBefore(hint2, list.firstChild);
    }
  });

  list.appendChild(item);
}
