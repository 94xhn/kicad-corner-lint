"""kicad-corner-lint: flag right-angle and acute track corners in KiCad PCBs."""

from .core import Board, Corner, Segment, classify, find_corners, load_board

__version__ = "0.1.0"

__all__ = [
    "Board",
    "Corner",
    "Segment",
    "classify",
    "find_corners",
    "load_board",
    "__version__",
]
