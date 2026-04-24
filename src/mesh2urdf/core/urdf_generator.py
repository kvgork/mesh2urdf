"""URDF XML generation using lxml.

Generates URDF v1 compliant XML from a URDFExportRequest.

Conventions:
- Mesh paths use ``meshes/<filename>`` relative to the URDF file.
  To deploy in a ROS package, replace with ``package://<robot_pkg>/meshes/<filename>``.
- Visual origin uses LinkSpec.origin_xyz / origin_rpy (link-frame pose of the visual geometry).
- Collision geometry is the fitted primitive scaled by (1 + collision_margin) via scale_primitive.
- object2urdf uses ``mesh.center_mass`` (trimesh) for visual origins — the same pattern applies
  here when mesh_id is available (Phase 7: pass mesh to _get_link_origin for CoM-based origin).
"""

from __future__ import annotations

from lxml import etree as ET

from mesh2urdf.core.primitive_fitter import scale_primitive
from mesh2urdf.models.schema import JointSpec, LinkSpec, PrimitiveSpec, URDFExportRequest


def _fmt(vals: list[float]) -> str:
    """Format a list of floats as a space-separated string with 6 decimal places."""
    if len(vals) != 3:
        raise ValueError(f"Expected 3 values, got {len(vals)}: {vals}")
    return " ".join(f"{v:.6f}" for v in vals)


def _fmt_xyz(vals: list[float]) -> str:
    """Semantic alias for _fmt — used for xyz positions."""
    return _fmt(vals)


def _fmt_rpy(vals: list[float]) -> str:
    """Semantic alias for _fmt — used for rpy rotations."""
    return _fmt(vals)


def _build_geometry(prim: PrimitiveSpec) -> ET.Element:
    """Build a URDF <geometry> element from a PrimitiveSpec."""
    geo = ET.Element("geometry")
    d = prim.dimensions
    if prim.type == "box":
        box = ET.SubElement(geo, "box")
        box.set("size", _fmt([d.get("size_x", 0.1), d.get("size_y", 0.1), d.get("size_z", 0.1)]))
    elif prim.type == "cylinder":
        cyl = ET.SubElement(geo, "cylinder")
        cyl.set("radius", f"{d.get('radius', 0.05):.6f}")
        cyl.set("length", f"{d.get('length', 0.1):.6f}")
    elif prim.type == "sphere":
        sph = ET.SubElement(geo, "sphere")
        sph.set("radius", f"{d.get('radius', 0.05):.6f}")
    else:
        raise ValueError(f"Unsupported primitive type for URDF geometry: {prim.type!r}")
    return geo


def _build_link(link: LinkSpec) -> ET.Element:
    """Build a URDF <link> element from a LinkSpec."""
    el = ET.Element("link")
    el.set("name", link.name)

    # Visual — references original mesh file
    # TODO (Phase 7): use mesh.center_mass (trimesh CoM, same as object2urdf) for visual origin
    vis = ET.SubElement(el, "visual")
    vis_origin = ET.SubElement(vis, "origin")
    vis_origin.set("xyz", _fmt_xyz(link.origin_xyz))
    vis_origin.set("rpy", _fmt_rpy(link.origin_rpy))
    vis_geo = ET.SubElement(vis, "geometry")
    mesh_el = ET.SubElement(vis_geo, "mesh")
    mesh_el.set("filename", f"meshes/{link.mesh_filename}")

    # Collision — scaled primitive
    coll = ET.SubElement(el, "collision")
    coll_origin = ET.SubElement(coll, "origin")
    coll_origin.set("xyz", _fmt_xyz(link.primitive.origin_xyz))
    coll_origin.set("rpy", _fmt_rpy(link.primitive.origin_rpy))
    scaled = scale_primitive(link.primitive, link.collision_margin)
    coll.append(_build_geometry(scaled))

    # Inertial placeholder — computed inertia to be added in Phase 7
    el.append(ET.Comment(" inertial: add computed inertia here (Phase 7) "))

    return el


def _build_joint(joint: JointSpec) -> ET.Element:
    """Build a URDF <joint> element from a JointSpec."""
    el = ET.Element("joint")
    el.set("name", joint.name)
    el.set("type", joint.type)

    parent_el = ET.SubElement(el, "parent")
    parent_el.set("link", joint.parent)
    child_el = ET.SubElement(el, "child")
    child_el.set("link", joint.child)

    origin = ET.SubElement(el, "origin")
    origin.set("xyz", _fmt_xyz(joint.origin_xyz))
    origin.set("rpy", _fmt_rpy(joint.origin_rpy))

    if joint.type != "fixed":
        axis_vals = joint.axis if joint.axis else [1.0, 0.0, 0.0]
        axis_el = ET.SubElement(el, "axis")
        axis_el.set("xyz", _fmt(axis_vals))

    if joint.limit and joint.type != "fixed":
        lim = ET.SubElement(el, "limit")
        lim.set("lower", f"{joint.limit.get('lower', -3.14159):.6f}")
        lim.set("upper", f"{joint.limit.get('upper', 3.14159):.6f}")
        lim.set("effort", f"{joint.limit.get('effort', 10.0):.6f}")
        lim.set("velocity", f"{joint.limit.get('velocity', 1.0):.6f}")

    return el


def _validate_request(req: URDFExportRequest) -> None:
    """Validate a URDFExportRequest before generating XML.

    Raises:
        ValueError: With a descriptive message if the request is invalid.
    """
    if not req.links:
        raise ValueError("URDF must have at least one link")

    link_names = {link.name for link in req.links}

    for joint in req.joints:
        if joint.parent not in link_names:
            raise ValueError(
                f"Joint '{joint.name}' references unknown parent link '{joint.parent}'"
            )
        if joint.child not in link_names:
            raise ValueError(
                f"Joint '{joint.name}' references unknown child link '{joint.child}'"
            )
        if joint.type in ("revolute", "prismatic") and not joint.axis:
            raise ValueError(
                f"Joint '{joint.name}' of type '{joint.type}' requires an axis"
            )

    # Cycle detection via DFS
    children: dict[str, list[str]] = {link.name: [] for link in req.links}
    for j in req.joints:
        children[j.parent].append(j.child)

    visited: set[str] = set()

    def dfs(node: str, path: set[str]) -> None:
        if node in path:
            raise ValueError(f"Cycle detected in joint graph at link '{node}'")
        if node in visited:
            return
        path.add(node)
        for child in children.get(node, []):
            dfs(child, path)
        path.discard(node)
        visited.add(node)

    for link_name in link_names:
        if link_name not in visited:
            dfs(link_name, set())


def generate_urdf(req: URDFExportRequest) -> bytes:
    """Generate URDF XML bytes from a URDFExportRequest.

    Validates the request, then serialises links and joints to lxml elements.
    Returns UTF-8 encoded bytes with an XML declaration header.

    Note: lxml does not support xml_declaration=True with encoding='unicode'.
    We use encoding='UTF-8' (bytes) so the XML declaration is emitted correctly.

    Args:
        req: Validated export request with links and joints.

    Returns:
        URDF XML as UTF-8 bytes.

    Raises:
        ValueError: If the request fails validation.
    """
    _validate_request(req)

    robot = ET.Element("robot")
    robot.set("name", req.robot_name)

    for link in req.links:
        robot.append(_build_link(link))

    for joint in req.joints:
        robot.append(_build_joint(joint))

    # encoding='UTF-8' produces bytes with a proper XML declaration.
    # encoding='unicode' would produce a str but does NOT support xml_declaration=True.
    return ET.tostring(robot, pretty_print=True, xml_declaration=True, encoding="UTF-8")
