from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from shapely.geometry import GeometryCollection, Point
from shapely.geometry.base import BaseGeometry


class ObjectType(StrEnum):
    POINT = "POINT"
    LINE = "LINE"


class GeometryType(StrEnum):
    """Types of geometries in a structure."""

    OUTLINE = "outline"
    CENTERLINE = "centerline"
    INLET = "inlet"
    OUTLET = "outlet"
    REFERENCE_POINT = "reference_point"


Color = str | int | tuple[int, int, int] | None


@dataclass(slots=True)
class Layer:
    name: str | None = None
    color: Color = None
    block: str | None = None


@dataclass(frozen=True)
class LayerPair:
    element: Layer = field(default_factory=Layer)
    text: Layer = field(default_factory=Layer)


@dataclass
class Config:
    name: str
    layers: list[LayerPair]
    units: str
    family: str
    family_type: str
    object_id: str


@dataclass
class Medium:
    name: str
    point: Config
    line: Config


@dataclass
class ProcessorConfig:
    pass


@dataclass
class GeometryObject:
    """Represents a processed geometry object."""

    geometry: BaseGeometry
    object_type: str
    properties: dict[str, Any]


@dataclass
class ComponentGeometry:
    """A single geometry component of a structure."""

    geometry: BaseGeometry
    geometry_type: str  # Will be replaced with proper enum
    layer_name: str | None = None


@dataclass
class InfraElement:
    """Universal base class for all infrastructure objects (pipes, shafts, cables, etc.)."""

    object_id: str
    object_type: str  # "pipe", "shaft", "cable", "pole", etc.
    medium: str  # "wastewater", "water", "electric", "telecom", etc.
    components: list[ComponentGeometry]
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def geometry_collection(self) -> GeometryCollection:
        """All geometries as Collection for Tree operations."""
        geometries = [comp.geometry for comp in self.components]
        return GeometryCollection(geometries)

    def get_geometries_by_type(self, geometry_type: str) -> list[BaseGeometry]:
        """Get geometries of a specific type."""
        return [comp.geometry for comp in self.components if comp.geometry_type == geometry_type]


@dataclass
class Connection:
    """Connection between two infrastructure objects."""

    from_object: InfraElement
    to_object: InfraElement
    connection_type: str  # "start_connection", "end_connection", "intersection"
    connection_point: Point
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiGeometryStructure:
    """A structure consisting of multiple geometries."""

    structure_id: str
    structure_type: str
    components: list[ComponentGeometry]
    properties: dict[str, Any]

    @property
    def geometry_collection(self) -> GeometryCollection:
        """Get all geometries as a Shapely GeometryCollection."""
        geometries = [comp.geometry for comp in self.components]
        return GeometryCollection(geometries)

    def get_geometry_by_type(self, geometry_type: GeometryType) -> list[BaseGeometry]:
        """Get geometries of a specific type."""
        return [comp.geometry for comp in self.components if comp.geometry_type == geometry_type]

    def get_reference_point(self) -> Point | None:
        """Get the reference point of the structure."""
        ref_points = self.get_geometry_by_type(GeometryType.REFERENCE_POINT)
        return ref_points[0] if ref_points else None

    def get_outline(self) -> BaseGeometry | None:
        """Get the outline geometry of the structure."""
        outlines = self.get_geometry_by_type(GeometryType.OUTLINE)
        return outlines[0] if outlines else None

    def bounds(self) -> tuple[float, float, float, float]:
        """Get bounds of all geometries."""
        return self.geometry_collection.bounds

    def contains_point(self, point: Point) -> bool:
        """Check if any geometry contains the point."""
        return self.geometry_collection.contains(point)

    def distance_to(self, other_geometry: BaseGeometry) -> float:
        """Get minimum distance to another geometry."""
        return self.geometry_collection.distance(other_geometry)
