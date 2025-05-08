"""LandXML file reader for extracting Z coordinates from DGM data.

This module handles reading LandXML files using the lxml library to
extract elevation data that will be used to set Z coordinates for
DXF points based on spatial interpolation.
"""

import xml.etree.ElementTree as ET
import numpy as np
from collections.abc import Sequence
from pathlib import Path

from shapely.geometry.point import Point
from shapely.strtree import STRtree

from ..protocols import IReadable


class LandXMLReader(IReadable):
    """Reader for LandXML files to extract elevation data (DGM).

    This class processes LandXML files and extracts elevation points
    that are used to determine Z coordinates for DXF elements through
    spatial interpolation.
    """

    LAND_XML_NS = {"xmlns": "http://www.landxml.org/schema/LandXML-1.2"}

    def __init__(self, landxml_path: Path) -> None:
        self.landxml_path = landxml_path
        self.elevation_points: Sequence[Point] = []
        self._tree: STRtree | None = None

    def load_file(self) -> None:
        if not self.landxml_path.exists():
            raise FileNotFoundError(f"LandXML file not found: {self.landxml_path}")

        try:
            tree = ET.parse(str(self.landxml_path))
            root = tree.getroot()

            self.elevation_points = self._extract_elevation_points(root)

            if self.elevation_points:
                self._tree = STRtree(self.elevation_points)

        except Exception as e:
            raise Exception(f"Cannot parse LandXML file {self.landxml_path}: {e}") from e

    def get_elevation(self, point: Point, max_distance: float) -> float:
        """Get elevation (Z coordinate) for a given point using spatial interpolation.

        Uses the nearest elevation points within max_distance to interpolate
        the Z coordinate. If only one point is found, returns its Z value directly.
        If multiple points are found, uses inverse distance weighting interpolation.

        Parameters
        ----------
        point : Point
            Point (X, Y) to get elevation for
        max_distance : float
            Maximum search distance for finding nearest elevation points

        Returns
        -------
        float
            Interpolated Z coordinate (elevation)

        Raises
        ------
        RuntimeError
            If elevation points are not loaded or STRtree is not initialized
        """
        if not self.elevation_points or self._tree is None:
            raise RuntimeError("Elevation points not loaded or KDTree not initialized")

        # Find nearest elevation points
        distances, indices = self._tree.query_nearest(point, max_distance=max_distance)
        if np.isscalar(distances):
            return self.elevation_points[int(indices)].z

        # Multiple points - inverse distance weighting interpolation
        weights = 1.0 / (distances + 1e-10)  # Add small epsilon to avoid division by zero
        summed_weights = 0
        for i, idx in enumerate(indices):
            sum_weights = weights[i] * self.elevation_points[int(idx)].z
            summed_weights += sum_weights
        interpolated_z = summed_weights / np.sum(weights)
        return float(interpolated_z)

    def _extract_elevation_points(self, root: ET.Element) -> Sequence[Point]:
        elevation_points = self._extract_surface_points(root)
        if not elevation_points:
            elevation_points = self._extract_tin_faces(root)
        return elevation_points

    def _create_point(self, coords_text: str) -> Point | None:
        coords_text = coords_text.strip()
        if "," in coords_text:
            coords = coords_text.split(",")
        else:
            coords = coords_text.split()

        if len(coords) < 3:
            return None
        return Point(*[float(coord) for coord in coords])

    def _extract_surface_points(self, root: ET.Element) -> Sequence[Point]:
        """Extract surface points from LandXML root element.

        Searches for surface points in the LandXML structure under
        Pnts/P elements and converts them to Shapely Point objects.

        Parameters
        ----------
        root : ET.Element
            Root element of the LandXML document

        Returns
        -------
        Sequence[Point]
            List of surface points extracted from LandXML
        """
        surface_points = root.findall(".//xmlns:Pnts/xmlns:P", namespaces=self.LAND_XML_NS)

        elevation_points = []
        for point_elem in surface_points:
            if not point_elem.text:
                continue
            try:
                point = self._create_point(point_elem.text)
                if point is None:
                    continue
                elevation_points.append(point)
            except (ValueError, IndexError):
                continue
        return elevation_points

    def _extract_surface_point_lookup(self, root: ET.Element) -> dict[int, Point]:
        """Extract surface points and create a lookup dictionary.

        Creates a mapping from point indices (1-based) to Point objects
        for use in TIN face processing.

        Parameters
        ----------
        root : ET.Element
            Root element of the LandXML document

        Returns
        -------
        dict[int, Point]
            Dictionary mapping point indices to Point objects
        """
        point_lookup = {}
        point_refs = root.findall(".//xmlns:Pnts/xmlns:P", namespaces=self.LAND_XML_NS)
        for idx, point_tag in enumerate(point_refs):
            if not point_tag.text:
                continue
            try:
                point = self._create_point(point_tag.text.strip())
                if point is None:
                    continue
                point_lookup[idx + 1] = point
            except (ValueError, IndexError):
                continue
        return point_lookup

    def _extract_tin_faces(self, root: ET.Element) -> Sequence[Point]:
        """Extract unique points from TIN faces in LandXML root element.

        Processes TIN face definitions to extract all unique points
        referenced by the triangular faces.

        Parameters
        ----------
        root : ET.Element
            Root element of the LandXML document

        Returns
        -------
        Sequence[Point]
            List of unique points extracted from TIN faces
        """
        unique_points = set()

        point_lookup = self._extract_surface_point_lookup(root)
        tin_faces = root.findall(".//xmlns:Faces/xmlns:F", namespaces=self.LAND_XML_NS)
        for face_elem in tin_faces:
            if not face_elem.text:
                continue
            try:
                # Face format is usually "p1 p2 p3" referencing point indices
                face_text = face_elem.text.strip()
                point_indices = [int(idx) for idx in face_text.split()]

                for idx in point_indices:
                    if idx not in point_lookup:
                        continue
                    point = point_lookup[idx]
                    unique_points.add(point)

            except (ValueError, IndexError):
                continue

        return list(unique_points)
