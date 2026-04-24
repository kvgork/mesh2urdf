from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MeshLoadResponse(BaseModel):
    mesh_id: str
    vertex_count: int
    face_count: int
    bounds: list[list[float]]
    centroid: list[float]
    vertices: list[float]
    indices: list[int]


class MeshMetadataResponse(BaseModel):
    mesh_id: str
    vertex_count: int
    face_count: int
    bounds: list[list[float]]
    centroid: list[float]


class PrimitiveFitRequest(BaseModel):
    mesh_id: str
    primitive_type: Literal["box", "cylinder", "sphere", "capsule"]
    vertex_indices: list[int] | None = None


class PrimitiveSpec(BaseModel):
    type: Literal["box", "cylinder", "sphere", "capsule"]
    dimensions: dict[str, float]
    origin_xyz: list[float]
    origin_rpy: list[float]


class LinkSpec(BaseModel):
    name: str
    primitive: PrimitiveSpec
    mass: float = 1.0
    parent: str | None = None


class JointSpec(BaseModel):
    name: str
    type: Literal["fixed", "revolute", "prismatic", "continuous"]
    parent: str
    child: str
    origin_xyz: list[float]
    origin_rpy: list[float]
    axis: list[float] | None = None
    limit: dict[str, float] | None = None


class URDFExportRequest(BaseModel):
    robot_name: str
    links: list[LinkSpec]
    joints: list[JointSpec] = Field(default_factory=list)
