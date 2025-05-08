"""Factory for creating ObjectData instances from DXF entities.

This module provides a factory pattern for creating ObjectData objects
from various DXF entity types with intelligent shape detection and
dimension calculation.
"""

import logging

from ezdxf.entities.arc import Arc
from ezdxf.entities.circle import Circle
from ezdxf.entities.dxfentity import DXFEntity
from ezdxf.entities.insert import Insert
from ezdxf.entities.line import Line
from ezdxf.entities.polyline import Polyline
from shapely.geometry import GeometryCollection, LineString
from shapely.geometry.point import Point as ShPoint
from shapely.lib import Geometry

from ..readers.dxf import DxfReader
from . import handler

log = logging.getLogger(__name__)


class ShapelyFactory:
    """Factory for creating ObjectData from DXF entities."""

    def __init__(self, dxf_reader: DxfReader):
        """Initialize factory with DXF document.

        Parameters
        ----------
        dxf_document : Drawing
            DXF document for block resolution
        """
        self.dxf_reader = dxf_reader

    def create_from_entity(self, entity: DXFEntity) -> Geometry | None:
        entity_type = entity.dxftype()

        if entity_type == "HATCH":
            return None  # HATCH entities are not processed here
        if entity_type == "INSERT":
            return self._create_from_insert(entity)
        if entity_type == "CIRCLE":
            return self._create_from_circle(entity)
        if entity_type in ("POLYLINE", "LWPOLYLINE"):
            return self._create_from_polyline(entity)
        if entity_type == "LINE":
            return self._create_from_line(entity)
        if entity_type == "ARC":
            return self._create_from_arc(entity)
        log.warning(f"Unsupported entity type: {entity_type}")
        return None

    def _create_from_insert(self, entity: DXFEntity) -> Geometry | None:
        if not isinstance(entity, Insert):
            log.error("Expected INSERT entity for block reference")
            return None

        insert_point = entity.dxf.insert
        position = ShPoint(*insert_point.get_xy())

        block_entities = self.dxf_reader.block_by_name(entity)
        geometries = [self.create_from_entity(block) for block in block_entities]
        return GeometryCollection(position, *geometries)

    def _create_from_circle(self, entity: DXFEntity) -> Geometry | None:
        if not isinstance(entity, Circle):
            log.error("Expected CIRCLE entity")
            return None

        center = entity.dxf.center
        position = ShPoint(center.get_xy())
        return position.buffer(entity.dxf.radius, resolution=16)

    def _create_from_polyline(self, entity: DXFEntity) -> Geometry | None:
        if not isinstance(entity, Polyline):
            log.error("Expected POLYLINE entity")
            return None

        shapely_points = handler.get_shapely_points_from(entity)
        return LineString(shapely_points)

    def _create_from_line(self, entity: DXFEntity) -> Geometry | None:
        if not isinstance(entity, Line):
            log.error("Expected LINE entity")
            return None

        shapely_points = handler.get_shapely_points_from(entity)
        return LineString(shapely_points)

    def _create_from_arc(self, entity: DXFEntity) -> Geometry | None:
        if not isinstance(entity, Arc):
            log.debug("Expected ARC entity")
            return None

        shapely_points = handler.get_shapely_points_from(entity)
        return LineString(shapely_points)

    def _create_bulge_point_based_object(self, entity: DXFEntity) -> Geometry | None:
        pass
