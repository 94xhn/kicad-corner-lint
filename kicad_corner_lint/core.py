"""Track corner detection for KiCad PCB files.

Zero-dependency: parses the ``.kicad_pcb`` s-expression text directly, so it
runs anywhere Python runs — no pcbnew bindings or KiCad installation needed.

Angle convention: the angle between two track segments meeting at a point.
180 deg is a straight line, 135 deg is a standard 45-degree corner, 90 deg is
a right angle, and anything below 90 deg is an acute corner (acid trap).
"""

from __future__ import annotations

import fnmatch
import math
from dataclasses import dataclass, field

from .sexp import QuotedStr, parse

NM_PER_MM = 1_000_000

RIGHT_DEG = 90.0
STANDARD_DEG = 135.0


@dataclass(frozen=True)
class Segment:
    """A straight track segment; coordinates are integer nanometres.

    ``net`` is the net *name*, normalized across formats: KiCad <= 9 stores a
    numeric id in each segment (resolved through the board's net table) while
    KiCad 10 stores the name directly.
    """

    start: tuple[int, int]
    end: tuple[int, int]
    layer: str
    net: str


@dataclass
class Board:
    segments: list[Segment] = field(default_factory=list)
    net_names: dict[int, str] = field(default_factory=dict)
    arc_count: int = 0


@dataclass(frozen=True)
class Corner:
    x_mm: float
    y_mm: float
    layer: str
    net_name: str
    angle_deg: float
    arms: int
    kind: str  # "acute" | "right-angle" | "shallow"
    severity: str  # "error" | "warning"

    def to_dict(self) -> dict:
        return {
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "layer": self.layer,
            "net_name": self.net_name,
            "angle_deg": round(self.angle_deg, 2),
            "arms": self.arms,
            "kind": self.kind,
            "severity": self.severity,
        }


def _coord_nm(tokens: list) -> tuple[int, int]:
    return (
        round(float(tokens[0]) * NM_PER_MM),
        round(float(tokens[1]) * NM_PER_MM),
    )


def _parse_segment(node: list, net_names: dict[int, str]) -> Segment | None:
    start = end = layer = net_token = None
    for item in node[1:]:
        if not isinstance(item, list) or not item:
            continue
        key = item[0]
        if key == "start":
            start = _coord_nm(item[1:3])
        elif key == "end":
            end = _coord_nm(item[1:3])
        elif key == "layer":
            layer = item[1]
        elif key == "net":
            net_token = item[1]
    if start is None or end is None or layer is None or net_token is None:
        return None
    if start == end:
        return None  # zero-length segments carry no direction

    if isinstance(net_token, QuotedStr):
        net = str(net_token)  # KiCad 10: segment stores the net name
    else:
        try:
            net_id = int(net_token)
        except ValueError:
            net = str(net_token)  # unquoted non-numeric token: treat as a name
        else:
            net = net_names.get(net_id, f"#{net_id}")
    return Segment(start=start, end=end, layer=layer, net=net)


def load_board(text: str) -> Board:
    """Extract track segments and net names from ``.kicad_pcb`` source text."""
    forms = parse(text)
    root = next(
        (f for f in forms if isinstance(f, list) and f and f[0] == "kicad_pcb"),
        None,
    )
    if root is None:
        raise ValueError("not a KiCad board file: no (kicad_pcb ...) form found")

    board = Board()
    children = [n for n in root if isinstance(n, list) and n]
    # A stray ')' can close (kicad_pcb ...) early, leaving the rest of the
    # board as orphaned top-level forms. KiCad still loads such files (an
    # official demo board ships this way), so adopt those forms too.
    root_idx = forms.index(root)
    children += [n for n in forms[root_idx + 1 :] if isinstance(n, list) and n]

    # First pass: the net table — present in KiCad <= 9, absent in KiCad 10,
    # where segments reference nets by name instead of id.
    for node in children:
        if node[0] == "net" and len(node) >= 2:
            try:
                net_id = int(node[1])
            except (TypeError, ValueError):
                continue
            name = node[2] if len(node) >= 3 and isinstance(node[2], str) else ""
            board.net_names[net_id] = name

    for node in children:
        if node[0] == "segment":
            seg = _parse_segment(node, board.net_names)
            if seg is not None:
                board.segments.append(seg)
        elif node[0] == "arc":
            board.arc_count += 1
    return board


def _angle_deg(u: tuple[int, int], v: tuple[int, int]) -> float:
    dot = u[0] * v[0] + u[1] * v[1]
    norm = math.hypot(*u) * math.hypot(*v)
    cos_a = max(-1.0, min(1.0, dot / norm))
    return math.degrees(math.acos(cos_a))


def classify(angle_deg: float, tolerance: float = 1.0) -> tuple[str, str] | None:
    """Map a corner angle to ``(kind, severity)``, or None when compliant.

    A corner of 0 deg means two collinear segments overlap — reported as
    acute because overlapping copper is worth a look anyway.
    """
    if angle_deg < RIGHT_DEG - tolerance:
        return ("acute", "error")
    if angle_deg <= RIGHT_DEG + tolerance:
        return ("right-angle", "error")
    if angle_deg < STANDARD_DEG - tolerance:
        return ("shallow", "warning")
    return None


def find_corners(
    board: Board,
    *,
    tolerance: float = 1.0,
    include_junctions: bool = False,
    ignore_nets: tuple[str, ...] = (),
) -> list[Corner]:
    """Return all non-compliant track corners on the board.

    Only points where segment *endpoints* meet (same net, same layer) are
    corners. Points where 3+ endpoints meet are junctions and are skipped
    unless ``include_junctions`` is set — a stub teeing into the middle of
    another segment is a branch, not a corner, and is never reported.
    """
    def is_ignored(net_name: str) -> bool:
        return any(fnmatch.fnmatchcase(net_name, pat) for pat in ignore_nets)

    joints: dict[tuple[str, str, tuple[int, int]], set[tuple[int, int]]] = {}
    for seg in board.segments:
        if ignore_nets and is_ignored(seg.net):
            continue
        joints.setdefault((seg.net, seg.layer, seg.start), set()).add(seg.end)
        joints.setdefault((seg.net, seg.layer, seg.end), set()).add(seg.start)

    corners: list[Corner] = []
    for (net, layer, point), far_ends in joints.items():
        arms = len(far_ends)
        if arms < 2:
            continue
        if arms > 2 and not include_junctions:
            continue
        vectors = [(fx - point[0], fy - point[1]) for fx, fy in far_ends]
        worst = min(
            _angle_deg(u, v)
            for i, u in enumerate(vectors)
            for v in vectors[i + 1 :]
        )
        verdict = classify(worst, tolerance)
        if verdict is None:
            continue
        kind, severity = verdict
        corners.append(
            Corner(
                x_mm=point[0] / NM_PER_MM,
                y_mm=point[1] / NM_PER_MM,
                layer=layer,
                net_name=net,
                angle_deg=worst,
                arms=arms,
                kind=kind,
                severity=severity,
            )
        )
    corners.sort(
        key=lambda c: (c.severity != "error", c.angle_deg, c.layer, c.x_mm, c.y_mm)
    )
    return corners
