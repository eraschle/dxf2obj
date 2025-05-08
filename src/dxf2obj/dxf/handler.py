"""Entity handler functions for DXF shape detection and classification.

This module provides functions to analyze DXF entities and determine their
shape characteristics (round, rectangular, multi-sided) and processing type.
"""

import logging
import math
from collections.abc import Iterable

import numpy as np
from ezdxf import math as ezmath
from ezdxf.entities.arc import Arc
from ezdxf.entities.dxfentity import DXFEntity
from ezdxf.entities.line import Line
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline
from ezdxf.math import Vec3
from shapely.geometry import Point

log = logging.getLogger(__name__)


def extract_dxf_points_from(entity: DXFEntity) -> Iterable[Vec3]:
    """Extract coordinate points from any DXF entity.

    Parameters
    ----------
    entity : DXFEntity
        DXF entity to extract points from

    Returns
    -------
    List[Point3D]
        List of extracted points
    """
    if isinstance(entity, Line):
        return [Vec3(entity.dxf.start), Vec3(entity.dxf.end)]
    if isinstance(entity, Polyline):
        return entity.points()
    if isinstance(entity, LWPolyline):
        coords = entity.get_points("xy")
        return [Vec3(x, y, 0.0) for x, y in coords]
    if isinstance(entity, Arc):
        src_length = get_arc_length(entity)
        return split_arc_to_points(entity, num_points=int(src_length / 0.2))
    return []


def get_shapely_points_from(entity: DXFEntity) -> list[Point]:
    dxf_points = extract_dxf_points_from(entity)
    return [Point(point.xyz) for point in dxf_points]


def get_arc_length(arc: Arc) -> float:
    radius = arc.dxf.radius
    start_angle = math.radians(arc.dxf.start_angle)
    end_angle = math.radians(arc.dxf.end_angle)
    if end_angle < start_angle:
        end_angle += 2 * math.pi
    return radius * (end_angle - start_angle)


def split_arc_to_points(arc: Arc, num_points: int = 0, spacing: float = 0) -> list[Vec3]:
    """Split an ARC into points"""
    center = Vec3(arc.dxf.center)
    radius = arc.dxf.radius
    start_angle = math.radians(arc.dxf.start_angle)
    end_angle = math.radians(arc.dxf.end_angle)

    # Handle angle wraparound
    if end_angle < start_angle:
        end_angle += 2 * math.pi

    if num_points > 0:
        angles = np.linspace(start_angle, end_angle, num_points)
    elif spacing > 0:
        arc_length = get_arc_length(arc)
        num_points = int(arc_length / spacing) + 1
        angles = np.linspace(start_angle, end_angle, num_points)
    else:
        angles = []

    points = []
    for angle in angles:
        x = center.x + radius * math.cos(angle)
        y = center.y + radius * math.sin(angle)
        z = center.z
        points.append(Vec3(x, y, z))
    return points


def has_bulge_value(entity: DXFEntity) -> bool:
    """Check if a polyline entity has bulge values.

    Parameters
    ----------
    entity : DXFEntity
        Entity to check

    Returns
    -------
    bool
        True if entity has bulge values
    """
    if not isinstance(entity, LWPolyline):
        return False
    return any(point[-1] != 0.0 for point in entity.get_points())


def _get_bulge_start_index(entity: LWPolyline) -> int:
    for idx, point_values in enumerate(entity.get_points()):
        if point_values[-1] == 0.0:
            continue
        return idx
    raise ValueError("No bulge found in polyline entity.")


def get_bulge_center_and_diameter(entity: DXFEntity) -> tuple[Vec3, float]:
    """Get the center point and diameter of a bulge in a polyline."""
    if not isinstance(entity, LWPolyline):
        raise TypeError("Entity must be a LWPolyline with bulge values.")
    if not has_bulge_value(entity):
        raise ValueError("Entity does not have bulge values. Did you check with has_bulge_value?")
    points_vec2 = entity.get_points("xy")
    start_index = _get_bulge_start_index(entity)
    start = points_vec2[start_index]
    end = points_vec2[(start_index + 1) % len(points_vec2)]
    bulge_value = entity.get_points()[start_index][-1]
    center = ezmath.bulge_center(start_point=start, end_point=end, bulge=bulge_value)
    radius = ezmath.bulge_radius(start_point=start, end_point=end, bulge=bulge_value)
    return (Vec3(center.x, center.y, 0.0), radius * 2.0)
