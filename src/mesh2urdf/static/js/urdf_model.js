/**
 * Client-side URDF data model — pure data, no Three.js dependencies.
 *
 * Maintains the set of links and joints that will be serialised to URDF.
 * Performs structural validation (duplicate names, unknown references,
 * multi-parent tree constraint, cycle detection) at mutation time so the
 * UI always shows a consistent state.
 *
 * @typedef {Object} LinkSpec
 * @property {string}   name             - Unique link identifier
 * @property {string}   mesh_filename    - Mesh file name (e.g. "arm.stl")
 * @property {Object}   primitive        - PrimitiveSpec {type, dimensions, origin_xyz, origin_rpy}
 * @property {number}   collision_margin - Fractional margin for collision geometry (e.g. 0.05)
 * @property {number[]} origin_xyz       - Visual origin xyz in link frame [x, y, z]
 * @property {number[]} origin_rpy       - Visual origin rpy in link frame [r, p, y]
 * @property {Object}   [threeRefs]      - Three.js scene objects (stripped on export)
 *
 * @typedef {Object} JointSpec
 * @property {string}        name       - Unique joint identifier
 * @property {string}        type       - "fixed" | "revolute" | "prismatic" | "continuous"
 * @property {string}        parent     - Parent link name
 * @property {string}        child      - Child link name
 * @property {number[]}      origin_xyz - Joint origin xyz in parent frame
 * @property {number[]}      origin_rpy - Joint origin rpy in parent frame
 * @property {number[]|null} axis       - Rotation/translation axis (required for revolute/prismatic)
 * @property {Object|null}   limit      - {lower, upper, effort, velocity}
 */

export class URDFModel {
  constructor() {
    /** @type {string} */
    this.robotName = 'robot';
    /** @type {Map<string, LinkSpec>} */
    this.links = new Map();
    /** @type {Map<string, JointSpec>} */
    this.joints = new Map();
  }

  // ---------------------------------------------------------------------------
  // Link management
  // ---------------------------------------------------------------------------

  /**
   * Add a link to the model.
   * @param {LinkSpec} spec
   * @throws {Error} If name is missing or already exists.
   */
  addLink(spec) {
    if (!spec.name) throw new Error('Link spec must have a name');
    if (this.links.has(spec.name)) throw new Error(`Duplicate link name: ${spec.name}`);
    this.links.set(spec.name, { ...spec });
  }

  /**
   * Remove a link from the model.
   * @param {string} name
   * @throws {Error} If any joint references this link.
   */
  removeLink(name) {
    for (const [, j] of this.joints) {
      if (j.parent === name || j.child === name) {
        throw new Error(`Cannot remove link '${name}': referenced by joint '${j.name}'`);
      }
    }
    this.links.delete(name);
  }

  /**
   * Update fields on an existing link spec.
   * @param {string} name
   * @param {Partial<LinkSpec>} updates
   */
  updateLink(name, updates) {
    if (!this.links.has(name)) throw new Error(`Unknown link: ${name}`);
    Object.assign(this.links.get(name), updates);
  }

  /**
   * Return an array of all link names (for dropdown population).
   * @returns {string[]}
   */
  getLinkNames() {
    return Array.from(this.links.keys());
  }

  // ---------------------------------------------------------------------------
  // Joint management
  // ---------------------------------------------------------------------------

  /**
   * Add a joint to the model, running full structural validation.
   * @param {JointSpec} spec
   * @throws {Error} On any validation failure.
   */
  addJoint(spec) {
    if (!spec.name) throw new Error('Joint spec must have a name');
    if (this.joints.has(spec.name)) throw new Error(`Duplicate joint name: ${spec.name}`);
    if (!this.links.has(spec.parent)) throw new Error(`Unknown parent link: ${spec.parent}`);
    if (!this.links.has(spec.child)) throw new Error(`Unknown child link: ${spec.child}`);
    if (spec.parent === spec.child) throw new Error('Joint cannot connect a link to itself');

    // Tree constraint: child must have at most one parent
    for (const [, j] of this.joints) {
      if (j.child === spec.child) {
        throw new Error(
          `Link '${spec.child}' is already a child of joint '${j.name}'. ` +
          `URDF requires a tree structure (each link can have only one parent).`
        );
      }
    }

    // Cycle detection
    if (_detectCycle(this.joints, spec.parent, spec.child)) {
      throw new Error(
        `Adding joint '${spec.name}' (${spec.parent} → ${spec.child}) would create a cycle`
      );
    }

    // Axis required for non-fixed joints
    if ((spec.type === 'revolute' || spec.type === 'prismatic') && !spec.axis) {
      throw new Error(`Joint '${spec.name}' of type '${spec.type}' requires an axis`);
    }

    this.joints.set(spec.name, { ...spec });
  }

  /**
   * Remove a joint.
   * @param {string} name
   */
  removeJoint(name) {
    this.joints.delete(name);
  }

  // ---------------------------------------------------------------------------
  // Serialisation
  // ---------------------------------------------------------------------------

  /**
   * Build the JSON payload for POST /api/urdf/export.
   * Strips Three.js scene references (threeRefs) from link specs.
   * @returns {{ robot_name: string, links: Object[], joints: Object[] }}
   */
  toExportPayload() {
    const links = Array.from(this.links.values()).map((spec) => {
      // Destructure to exclude threeRefs from the serialised payload
      const { threeRefs, ...linkJson } = spec; // eslint-disable-line no-unused-vars
      return linkJson;
    });
    const joints = Array.from(this.joints.values()).map((spec) => {
      const { threeRefs, ...jointJson } = spec; // eslint-disable-line no-unused-vars
      return jointJson;
    });
    return {
      robot_name: this.robotName,
      links,
      joints,
    };
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Detect whether adding an edge parent→child to the existing joint graph
 * would create a directed cycle.
 *
 * Algorithm: build parent-to-children adjacency from existing joints,
 * then DFS from the proposed child. If we can reach the proposed parent,
 * a cycle would form.
 *
 * @param {Map<string, JointSpec>} joints - Current joint map
 * @param {string} parent - Proposed parent link
 * @param {string} child  - Proposed child link
 * @returns {boolean} true if adding this edge creates a cycle
 */
function _detectCycle(joints, parent, child) {
  if (parent === child) return true;

  // Build parent → children map from existing joints
  /** @type {Map<string, string[]>} */
  const parentToChildren = new Map();
  for (const [, j] of joints) {
    if (!parentToChildren.has(j.parent)) parentToChildren.set(j.parent, []);
    parentToChildren.get(j.parent).push(j.child);
  }

  // DFS from the proposed child: can we reach the proposed parent?
  const visited = new Set();
  const stack = [child];
  const maxIter = joints.size + 2; // safety cap
  let iter = 0;

  while (stack.length && iter < maxIter) {
    iter++;
    const node = stack.pop();
    if (node === parent) return true; // cycle detected
    if (visited.has(node)) continue;
    visited.add(node);
    for (const c of (parentToChildren.get(node) || [])) {
      stack.push(c);
    }
  }

  return false;
}
