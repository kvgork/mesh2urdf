import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

let renderer, camera, scene, controls;
let transformControls = null;
let _keyDownHandler = null;

export function initViewer(container) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);

  camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.001, 500);
  camera.position.set(0.5, 0.5, 1.5);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.shadowMap.enabled = true;
  container.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;

  // Lights
  const hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 1.0);
  dir.position.set(2, 3, 2);
  dir.castShadow = true;
  scene.add(dir);

  // Helpers
  scene.add(new THREE.AxesHelper(0.5));
  const grid = new THREE.GridHelper(10, 20, 0x444444, 0x222222);
  scene.add(grid);

  // Responsive resize via ResizeObserver
  const ro = new ResizeObserver(() => resizeToContainer(container));
  ro.observe(container);

  // Fallback window resize listener
  window.addEventListener('resize', () => resizeToContainer(container));

  return { scene, camera, renderer, controls };
}

/**
 * Initialise TransformControls and wire up:
 *   - dragging-changed: disables OrbitControls while gizmo is active to prevent
 *     camera rotation interfering with primitive manipulation
 *   - keyboard shortcuts W/E/R (outside input elements): translate/rotate/scale
 *   - Escape: detach (deselect)
 *
 * Uses `getHelper?.()` for Three.js r169+ compatibility while falling back to
 * direct scene.add(transformControls) for r160-168.
 *
 * Returns the TransformControls instance.
 */
export function initTransformControls() {
  transformControls = new TransformControls(camera, renderer.domElement);
  transformControls.setSize(1.2);

  transformControls.addEventListener('dragging-changed', (e) => {
    controls.enabled = !e.value;
  });

  // Use getHelper() if available (r169+), otherwise add directly (r160-168)
  const helper = typeof transformControls.getHelper === 'function'
    ? transformControls.getHelper()
    : transformControls;
  scene.add(helper);

  _keyDownHandler = (e) => {
    // Do not hijack shortcuts while user is typing in an input field
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
    if (e.key === 'w') setTransformMode('translate');
    if (e.key === 'e') setTransformMode('rotate');
    if (e.key === 'r') setTransformMode('scale');
    if (e.key === 'Escape') setTransformTarget(null);
  };
  window.addEventListener('keydown', _keyDownHandler);

  return transformControls;
}

/**
 * Attach TransformControls to obj, or detach if obj is null.
 */
export function setTransformTarget(obj) {
  if (!transformControls) return;
  if (obj == null) {
    transformControls.detach();
  } else {
    transformControls.attach(obj);
  }
}

/**
 * Switch the active gizmo mode.
 * @param {'translate'|'rotate'|'scale'} mode
 */
export function setTransformMode(mode) {
  if (transformControls) transformControls.setMode(mode);
}

/**
 * Register a callback to be called on every objectChange event (i.e. while
 * the user is dragging the gizmo). The callback receives the TransformControls
 * event object; use transformControls.object to access the attached mesh.
 */
export function onTransformChange(callback) {
  if (transformControls) transformControls.addEventListener('objectChange', callback);
}

export function addMeshToScene(vertices, indices, name) {
  const verts = vertices instanceof Float32Array ? vertices : new Float32Array(vertices);
  const idx = indices instanceof Uint32Array ? indices : new Uint32Array(indices);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(verts, 3));
  geometry.setIndex(new THREE.BufferAttribute(idx, 1));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();

  const material = new THREE.MeshPhongMaterial({ color: 0x8888aa, shininess: 30 });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  return mesh;
}

export function focusCameraOn(mesh) {
  const box = new THREE.Box3().setFromObject(mesh);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const dist = maxDim * 2.5;
  camera.position.set(center.x + dist * 0.5, center.y + dist * 0.5, center.z + dist);
  camera.near = maxDim * 0.001;
  camera.far = maxDim * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

export function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

export function resizeToContainer(container) {
  if (!renderer) return;
  const w = container.clientWidth;
  const h = container.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

export function removeFromScene(obj) {
  if (obj) scene.remove(obj);
}

export { scene, camera, renderer, controls };
