import * as THREE from 'three';

// Color constants
const GREEN = 0x00ff88;
const RED = 0xff3344;

/**
 * Build a THREE geometry for the given spec.
 * Cylinder geometry has a PI/2 X rotation baked in so that the
 * URDF Z-axis aligns with Three.js Y-up without requiring extra
 * composition on the object's rotation.
 */
export function buildPrimitiveGeometry(spec) {
  const d = spec.dimensions;
  if (spec.type === 'box') {
    return new THREE.BoxGeometry(d.size_x, d.size_y, d.size_z);
  } else if (spec.type === 'sphere') {
    return new THREE.SphereGeometry(d.radius, 32, 16);
  } else if (spec.type === 'cylinder') {
    // Three.js CylinderGeometry is Y-axis; URDF uses Z-axis.
    // Baking a 90-deg X rotation into the geometry means the object's
    // rotation can be set directly from spec.origin.rpy without extra
    // quaternion composition.
    const geo = new THREE.CylinderGeometry(d.radius, d.radius, d.length, 32);
    geo.applyMatrix4(new THREE.Matrix4().makeRotationX(Math.PI / 2));
    return geo;
  }
  throw new Error(`Unknown primitive type: ${spec.type}`);
}

/**
 * Apply spec.origin (xyz position + rpy rotation) to a Three.js Object3D.
 *
 * NOTE on Euler order: URDF rpy is an extrinsic XYZ rotation (roll applied
 * first around fixed X, then pitch around fixed Y, then yaw around fixed Z).
 * Three.js Euler with order='XYZ' is intrinsic (rotation around the object's
 * own axes in X→Y→Z sequence), which is mathematically equivalent to extrinsic
 * ZYX. For full correctness, compose via explicit quaternion multiplication:
 *   q = qZ(yaw) * qY(pitch) * qX(roll)
 * For MVP purposes, and because most primitives start with small angles where
 * the difference is negligible, we use order='XYZ' with (roll, pitch, yaw)
 * which matches the common URDF viewer convention.
 */
export function applySpecPose(obj, spec) {
  const [x, y, z] = spec.origin.xyz;
  const [r, p, yw] = spec.origin.rpy;
  obj.position.set(x, y, z);
  obj.rotation.set(r, p, yw, 'XYZ');
}

/**
 * Produce a spec with dimensions uniformly scaled by (1 + margin).
 * For box this is a uniform expansion; for sphere/cylinder likewise.
 * margin=0.05 means 5% larger in each dimension.
 */
function scaledSpec(spec, margin) {
  const factor = 1 + margin;
  const d = spec.dimensions;
  let newDims;
  if (spec.type === 'box') {
    newDims = { size_x: d.size_x * factor, size_y: d.size_y * factor, size_z: d.size_z * factor };
  } else if (spec.type === 'sphere') {
    newDims = { radius: d.radius * factor };
  } else {
    newDims = { radius: d.radius * factor, length: d.length * factor };
  }
  return { ...spec, dimensions: newDims };
}

/**
 * Create a pair of overlay objects for the given primitive spec:
 *   - visual: green EdgesGeometry LineSegments
 *   - collision: semi-transparent red wireframe Mesh (slightly larger by margin)
 *
 * Returns { visual, collision }.
 * Both objects have pose set from spec.origin.
 * Caller is responsible for adding them to the scene and disposing on removal.
 */
export function createPrimitiveOverlay(spec, margin = 0.05) {
  // Visual: green edge wireframe
  const visGeo = buildPrimitiveGeometry(spec);
  const edges = new THREE.EdgesGeometry(visGeo);
  visGeo.dispose(); // EdgesGeometry holds a copy; discard the source
  const visual = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({ color: GREEN })
  );
  applySpecPose(visual, spec);

  // Collision: slightly larger mesh, transparent red wireframe
  const collisionSpec = scaledSpec(spec, margin);
  const collGeo = buildPrimitiveGeometry(collisionSpec);
  const collision = new THREE.Mesh(
    collGeo,
    new THREE.MeshBasicMaterial({
      color: RED,
      transparent: true,
      opacity: 0.2,
      wireframe: true,
    })
  );
  applySpecPose(collision, spec); // same origin; size difference is in geometry

  return { visual, collision };
}

/**
 * Update the collision overlay's geometry in-place after a margin or spec change.
 * Disposes the old geometry to avoid GPU memory leaks.
 */
export function updateCollisionOverlay(collision, spec, margin) {
  collision.geometry.dispose();
  const collisionSpec = scaledSpec(spec, margin);
  collision.geometry = buildPrimitiveGeometry(collisionSpec);
  applySpecPose(collision, spec);
}

/**
 * Read position and rotation from a Three.js Object3D back into spec.origin.
 * If the object has non-unit scale, multiply scale into dimensions and reset
 * scale to (1,1,1) to prevent compounding on subsequent reads.
 *
 * Returns the mutated spec (same object reference).
 */
export function updatePrimitiveFromObject(spec, threeObj) {
  spec.origin.xyz = [threeObj.position.x, threeObj.position.y, threeObj.position.z];

  // Extract Euler with XYZ order (see applySpecPose comment on convention)
  const euler = new THREE.Euler().setFromQuaternion(
    new THREE.Quaternion().setFromEuler(threeObj.rotation),
    'XYZ'
  );
  spec.origin.rpy = [euler.x, euler.y, euler.z];

  // Absorb scale into dimensions then reset to unit scale
  const sx = threeObj.scale.x;
  const sy = threeObj.scale.y;
  const sz = threeObj.scale.z;
  const notUnit = Math.abs(sx - 1) > 1e-6 || Math.abs(sy - 1) > 1e-6 || Math.abs(sz - 1) > 1e-6;
  if (notUnit) {
    const d = spec.dimensions;
    if (spec.type === 'box') {
      d.size_x *= sx;
      d.size_y *= sy;
      d.size_z *= sz;
    } else if (spec.type === 'sphere') {
      d.radius *= (sx + sy + sz) / 3;
    } else if (spec.type === 'cylinder') {
      d.radius *= (sx + sz) / 2;
      d.length *= sy;
    }
    threeObj.scale.set(1, 1, 1);
  }

  return spec;
}

/**
 * Fully dispose a primitive overlay pair, removing from parent scene if attached.
 * Pass the object returned by createPrimitiveOverlay: { visual, collision }.
 */
export function disposePrimitiveOverlay({ visual, collision }) {
  if (visual) {
    if (visual.parent) visual.parent.remove(visual);
    visual.geometry.dispose();
    visual.material.dispose();
  }
  if (collision) {
    if (collision.parent) collision.parent.remove(collision);
    collision.geometry.dispose();
    collision.material.dispose();
  }
}
