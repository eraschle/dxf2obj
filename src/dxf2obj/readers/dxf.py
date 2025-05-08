import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from ezdxf import filemanagement as man
from ezdxf.colors import RGB
from ezdxf.document import Drawing
from ezdxf.entities.dxfentity import DXFEntity
from ezdxf.entities.dxfgfx import DXFGraphic
from ezdxf.entities.insert import Insert
from ezdxf.enums import ACI

from ..models import Layer
from ..protocols import IReadable

log = logging.getLogger(__name__)

LAYER_TRANSLATION = {
    "VON BLOCK": "BY BLOCK",
    "VON LAYER": "BY LAYER",
    "BLAU": "BLUE",
    "ROT": "RED",
    "GRÜN": "GREEN",
    "GELB": "YELLOW",
    "CYAN": "CYAN",
    "MAGENTA": "MAGENTA",
    "WEISS": "WHITE",
    "SCHWARZ": "BLACK",
    "GRAU": "GRAY",
    "HELLGRAU": "LIGHTGRAY",
}


def get_color_filter(entity: DXFEntity, layer: Layer) -> bool:
    """Check if entity color matches the specified layer color.

    Supports RGB tuples, ACI color indices, and color name strings.
    Handles German color name translations to English equivalents.
    Returns True if no color is specified in the layer configuration.

    Parameters
    ----------
    entity : DXFEntity
        DXF entity to check
    layer : Layer
        Layer configuration with color specification

    Returns
    -------
    bool
        True if entity color matches layer color or no color specified, False otherwise
    """
    if layer.color is None:
        return True
    if isinstance(layer.color, (tuple | list)):
        entity_color = getattr(entity, "rgb", RGB(0, 0, 0))
        layer_color = RGB(*layer.color)
        return entity_color == layer_color
    elif isinstance(layer.color, int):
        return entity.dxf.color == layer.color
    elif isinstance(layer.color, str):
        layer_color = layer.color.upper()
        layer_color = layer_color.replace("FARBE", "").strip()
        layer_color = LAYER_TRANSLATION.get(layer_color, layer_color)
        for aci_color in ACI:
            if aci_color.name != layer_color:
                continue
            return True
    log.warning(
        f"No able to find color for {entity} in layer {layer.name} with color {layer.color}"
    )
    return False


class DxfNotLoadedError(Exception):
    """Exception raised when attempting to access DXF data before loading the file.

    This exception is thrown when methods that require a loaded DXF document
    are called before load_file() has been successfully executed.
    """

    def __init__(self, message: str = "DXF file not loaded. Call load_file() first."):
        super().__init__(message)


DxfFilter = Callable[[DXFEntity], bool]


class DxfReader(IReadable):
    """Reader for DXF files using ezdxf library.

    Provides functionality to load DXF files and query entities
    based on layer configurations with support for color filtering.
    """

    def __init__(self, file_path: Path):
        """Initialize DXF reader with file path.

        Parameters
        ----------
        file_path : Path
            Path to the DXF file to be read
        """
        self.file_path = file_path
        self._document = None
        self._block_cache: dict[str, list[DXFGraphic]] = {}

    def load_file(self):
        """Load the DXF file into memory.

        Raises
        ------
        FileNotFoundError
            If the DXF file does not exist
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"DXF file not found: {self.file_path}")

        try:
            drawing = man.readfile(filename=self.file_path, encoding="utf-8")
            self._document = drawing
        except Exception as e:
            log.error("Failed to load DXF file: %s", e)
            self._document = None

    @property
    def is_loaded(self) -> bool:
        """Check if the DXF file is successfully loaded.

        Returns
        -------
        bool
            True if DXF document is loaded and ready for querying, False otherwise
        """
        return self._document is not None

    def _check_is_loaded(self):
        """Check if the DXF file is loaded and raise exception if not.

        Raises
        ------
        DxfNotLoadedError
            If DXF file is not loaded
        """
        if not self.is_loaded:
            raise DxfNotLoadedError()

    @property
    def document(self) -> Drawing:
        """Get the loaded DXF document.

        Returns
        -------
        Drawing
            The loaded ezdxf Drawing object

        Raises
        ------
        DxfNotLoadedError
            If DXF file is not loaded
        """
        if self._document is None:
            raise DxfNotLoadedError()
        return self._document

    def get_layer_names(self) -> list[str]:
        """Get all layer names from the loaded DXF file.

        Returns
        -------
        list[str]
            List of all layer names present in the DXF file

        Raises
        ------
        DxfNotLoadedError
            If DXF file is not loaded
        """
        self._check_is_loaded()
        return [layer.dxf.name for layer in self.document.layers]

    def _build_query(self, layer: Layer) -> str:
        """Build a query string for the given layer configuration.

        Constructs ezdxf query strings based on layer name and block
        specifications in the Layer object.

        Parameters
        ----------
        layer : Layer
            Layer configuration containing name and/or block information

        Returns
        -------
        str
            Query string for ezdxf modelspace.query()
        """
        if layer.name is None and layer.block is None:
            # If no name or block is specified, return all entities
            return "*"

        if layer.name is not None and layer.block is None:
            # If only name is specified, use the layer name
            return f'*[layer=="{layer.name}"]'

        if layer.block is not None and layer.name is None:
            # If only block is specified, use the name field
            return f'INSERT[name=="{layer.block}"]'

        # If both name and block are specified, combine them
        return f'INSERT[layer=="{layer.name}" & name=="{layer.block}"]'

    def query(self, layer: Layer, *filters: DxfFilter) -> Sequence[DXFEntity]:
        """Query entities from the specified layer with optional filters.

        Applies layer-based querying and color filtering, plus any additional
        custom filters provided.

        Parameters
        ----------
        layer : Layer
            Layer configuration to query
        *filters : DxfFilter
            Additional filter functions to apply to the query results

        Returns
        -------
        Sequence[DXFEntity]
            Filtered entities from the specified layer

        Raises
        ------
        DxfNotLoadedError
            If DXF file is not loaded
        """
        self._check_is_loaded()

        modelspace = self.document.modelspace()
        query_str = self._build_query(layer)
        query = modelspace.query(query_str)

        def color_filter(entity: DXFEntity) -> bool:
            """Filter function to check entity color against layer color."""
            return get_color_filter(entity, layer)

        for func in (color_filter,) + filters:
            query = query.filter(func)
        return query

    def block_by_name(self, entity: Insert) -> list[DXFGraphic]:
        """Get block entities by name from an INSERT entity.

        Retrieves all entities contained within a block definition.
        Uses caching to improve performance for repeated access to the same block.

        Parameters
        ----------
        entity : Insert
            INSERT entity containing the block name reference

        Returns
        -------
        list[DXFGraphic]
            List of all entities contained in the specified block
        """
        block_name = entity.dxf.name

        if block_name not in self._block_cache:
            entities = list(self.document.blocks[block_name])
            self._block_cache[block_name] = entities
        return self._block_cache[block_name]
