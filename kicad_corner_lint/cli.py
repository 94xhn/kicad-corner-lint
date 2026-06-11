"""Command-line interface for kicad-corner-lint."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from . import __version__
from .core import Corner, find_corners, load_board

EXIT_CLEAN = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kicad-corner-lint",
        description=(
            "Detect right-angle and acute track corners in KiCad PCB files. "
            "Compliant 45-degree routing (corner angles >= 135 deg) passes."
        ),
    )
    parser.add_argument(
        "boards",
        nargs="+",
        metavar="BOARD.kicad_pcb",
        help="board file(s) to check",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        metavar="DEG",
        help="angle tolerance in degrees around the 90/135 thresholds (default: 1.0)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat shallow-corner warnings (91-134 deg) as errors",
    )
    parser.add_argument(
        "--include-junctions",
        action="store_true",
        help="also check points where 3+ segment endpoints meet (off by default)",
    )
    parser.add_argument(
        "--ignore-net",
        action="append",
        default=[],
        metavar="PATTERN",
        help="net name pattern to skip (fnmatch syntax, repeatable), e.g. --ignore-net GND",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="fmt",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _check_file(path: Path, args: argparse.Namespace) -> dict:
    board = load_board(path.read_text(encoding="utf-8"))
    corners = find_corners(
        board,
        tolerance=args.tolerance,
        include_junctions=args.include_junctions,
        ignore_nets=tuple(args.ignore_net),
    )
    if args.strict:
        corners = [
            dataclasses.replace(c, severity="error") if c.severity == "warning" else c
            for c in corners
        ]
    return {
        "path": str(path),
        "segments": len(board.segments),
        "arcs": board.arc_count,
        "errors": sum(1 for c in corners if c.severity == "error"),
        "warnings": sum(1 for c in corners if c.severity == "warning"),
        "corners": corners,
    }


def _render_text(result: dict) -> str:
    lines = [
        f"{result['path']}: {result['segments']} segments, "
        f"{result['errors']} error(s), {result['warnings']} warning(s)"
    ]
    for corner in result["corners"]:
        assert isinstance(corner, Corner)
        net = f'"{corner.net_name}"' if corner.net_name else "<none>"
        lines.append(
            f"  {corner.severity.upper():7s} {corner.kind:11s} "
            f"{corner.angle_deg:6.2f} deg  ({corner.x_mm:.3f}, {corner.y_mm:.3f}) mm  "
            f"{corner.layer}  net {net}"
            + (f"  [{corner.arms} arms]" if corner.arms > 2 else "")
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    results = []
    file_errors = 0
    for raw in args.boards:
        path = Path(raw)
        try:
            results.append(_check_file(path, args))
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            file_errors += 1
        except ValueError as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            file_errors += 1

    total_errors = sum(r["errors"] for r in results)
    total_warnings = sum(r["warnings"] for r in results)

    if args.fmt == "json":
        payload = {
            "version": __version__,
            "files": [
                {**r, "corners": [c.to_dict() for c in r["corners"]]} for r in results
            ],
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        }
        print(json.dumps(payload, indent=2))
    else:
        for result in results:
            print(_render_text(result))
        verdict = "FAIL" if total_errors else "PASS"
        print(
            f"{verdict}: {total_errors} error(s), {total_warnings} warning(s) "
            f"across {len(results)} file(s)"
        )

    if file_errors:
        return EXIT_USAGE  # an unreadable/unparseable file outranks lint results
    return EXIT_VIOLATIONS if total_errors else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
