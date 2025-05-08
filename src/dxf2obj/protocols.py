from pathlib import Path
from typing import Protocol

from ezdxf.entities.dxfentity import DXFEntity
from shapely.geometry.base import BaseGeometry

from .models import ComponentGeometry, Connection, InfraElement


class IReadable(Protocol):
    file_path: Path

    def load_file(self) -> None:
        """Load the file into the object.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        Exception
            If the file cannot be parsed or loaded.
        """
        ...


class IDxfEntityConverter(Protocol):
    """Protocol for converting DXF entities to Shapely geometries."""

    def convert_to_shapely(self, entity: DXFEntity) -> BaseGeometry | None:
        """Convert a DXF entity to a Shapely geometry.

        Parameters
        ----------
        entity : DXFEntity
            The DXF entity to convert

        Returns
        -------
        BaseGeometry | None
            The converted Shapely geometry, or None if conversion failed
        """
        ...


class IMediaConverter(Protocol):
    """Interface for media-specific DXF-to-Shapely conversion."""

    def get_supported_layers(self) -> dict[str, str]:
        """Define which layers correspond to which geometry types."""
        ...

    def convert_entity_to_components(self, entity: DXFEntity, layer_name: str) -> list[ComponentGeometry]:
        """Convert DXF entity to ComponentGeometry(s)."""
        ...

    def group_entities_to_objects(self, entities: list[DXFEntity]) -> dict[str, list[DXFEntity]]:
        """Group related entities into objects (e.g., by spatial proximity or attributes)."""
        ...

    def create_infrastructure_object(self, object_id: str, components: list[ComponentGeometry]) -> InfraElement:
        """Create media-specific infrastructure object."""
        ...


class IGeometryProcessor(Protocol):
    """Interface for media-specific geometry processing."""

    def find_connections(self, obj: InfraElement, candidates: list[InfraElement]) -> list[Connection]:
        """Find connections to other objects."""
        ...

    def process_connections(self, obj: InfraElement, connections: list[Connection]) -> list[InfraElement]:
        """Process connections (e.g., subdivide pipes)."""
        ...

    def merge_objects(self, objects: list[InfraElement]) -> InfraElement:
        """Merge multiple objects into one (e.g., pipe segments)."""
        ...
