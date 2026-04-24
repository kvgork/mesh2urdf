import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let renderer, camera, scene, controls;

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

export { scene, camera, renderer, controls };
