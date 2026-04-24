from __future__ import annotations

import os
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_\-\.]*$')


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
    primitive_type: Literal["box", "cylinder", "sphere"]
    vertex_indices: list[int] | None = None


class PrimitiveSpec(BaseModel):
    type: Literal["box", "cylinder", "sphere"]
    dimensions: dict[str, float]
    origin: dict = Field(
        default_factory=lambda: {"xyz": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0]}
    )


class LinkSpec(BaseModel):
    name: str
    mesh_filename: str = "mesh.stl"
    primitive: PrimitiveSpec
    collision_margin: float = 0.05
    mass: float = 1.0
    origin_xyz: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    origin_rpy: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    parent: str | None = None

    @field_validator('name')
    @classmethod
    def validate_link_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(
                f"Invalid link name '{v}': must start with letter/underscore, "
                "alphanumeric/underscore/hyphen/dot only"
            )
        return v

    @field_validator('mesh_filename')
    @classmethod
    def validate_mesh_filename(cls, v: str) -> str:
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError(
                f"mesh_filename must be a plain filename, not a path: '{v}'"
            )
        basename = os.path.basename(v)
        if not basename:
            raise ValueError(f"mesh_filename must not be empty: '{v}'")
        return v


class JointSpec(BaseModel):
    name: str
    type: Literal["fixed", "revolute", "prismatic", "continuous"]
    parent: str
    child: str
    origin_xyz: list[float]
    origin_rpy: list[float]
    axis: list[float] | None = None
    limit: dict[str, float] | None = None

    @field_validator('name')
    @classmethod
    def validate_joint_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(f"Invalid joint name '{v}'")
        return v


class URDFExportRequest(BaseModel):
    robot_name: str
    links: list[LinkSpec]
    joints: list[JointSpec] = Field(default_factory=list)

    @field_validator('robot_name')
    @classmethod
    def validate_robot_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError(f"Invalid robot name '{v}'")
        return v
