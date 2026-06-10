# kicad-corner-lint

[![CI](https://github.com/94xhn/kicad-corner-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/94xhn/kicad-corner-lint/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)

A zero-dependency linter that flags **right-angle and acute track corners** in
KiCad PCB files (KiCad 5 through 10). It walks every pair of track segments
meeting at a point and classifies the corner angle: 135° corners — standard
45° routing — pass; right angles (90° ± tolerance) and acute "acid-trap"
corners (< 89°, including 0° overlapping copper) are errors; anything between
91° and 134° is a warning. T-junctions are recognised and skipped by default,
and nets can be excluded by pattern. Reports come as human-readable text or
JSON with exact board coordinates, and the exit code gates CI. No KiCad
installation, no pcbnew bindings, no setup — it parses the board file
directly, so it runs anywhere Python runs (GitHub Actions, pre-commit hooks,
your laptop).

[中文简介](#中文简介) below.

```text
$ kicad-corner-lint examples/demo.kicad_pcb
examples/demo.kicad_pcb: 12 segments, 2 error(s), 1 warning(s)
  ERROR   acute        45.00 deg  (130.000, 100.000) mm  F.Cu  net "GND"
  ERROR   right-angle  90.00 deg  (110.000, 100.000) mm  F.Cu  net "SIG"
  WARNING shallow     120.00 deg  (190.000, 100.000) mm  B.Cu  net "SIG"
FAIL: 2 error(s), 1 warning(s) across 1 file(s)
```

## Why

Hand-finished and script-generated boards accumulate 90° corners that
autorouted sections don't have: GND stitching jogs, QFN escape fixes,
last-minute GUI edits. Whether right angles actually hurt your board is a
long-running debate — for most low-speed digital boards they're cosmetic, for
RF and fast edges they matter — but if your team's convention is 45°/arc
routing, you want a **check**, not folklore. Nothing off-the-shelf does this
as a lint:

- **KiCad's built-in DRC** has a generic track-angle constraint framework, but
  it's opt-in: you must hand-write a custom rule in Board Setup per project,
  and it only runs inside KiCad.
- **[kicad-round-tracks](https://github.com/mitxela/kicad-round-tracks)**
  *modifies* tracks (melts corners into arcs); it doesn't report or gate.
- **KiBot** and friends drive KiCad's own DRC — same opt-in limitation.

`kicad-corner-lint` is the missing standalone check: zero config, zero
dependencies, machine-readable output, meaningful exit codes.

## Install

```bash
pip install git+https://github.com/94xhn/kicad-corner-lint
```

Or just copy the `kicad_corner_lint/` package into your tooling — it is three
small files with no dependencies.

## Usage

```bash
# lint one or more boards; exit 1 if any error-level corner is found
kicad-corner-lint MAIN.kicad_pcb

# machine-readable
kicad-corner-lint MAIN.kicad_pcb --format json

# treat shallow corners (91-134 deg) as errors too
kicad-corner-lint MAIN.kicad_pcb --strict

# skip nets you don't care about (fnmatch patterns, repeatable)
kicad-corner-lint MAIN.kicad_pcb --ignore-net "GND" --ignore-net "/sense*"

# also check points where 3+ segment endpoints meet
kicad-corner-lint MAIN.kicad_pcb --include-junctions
```

### What counts as a violation

The angle between two track segments meeting at a point — 180° is a straight
line, 135° is a standard 45° corner:

| Corner angle | Class | Severity | Note |
|---|---|---|---|
| < 89° | `acute` | **error** | acid-trap territory; 0° means overlapping copper |
| 89° – 91° | `right-angle` | **error** | the classic 90° corner |
| 91° – 134° | `shallow` | warning | sharper than 45°-rule routing allows |
| ≥ 134° | — | clean | compliant 45° / arc-style routing |

Band edges follow `--tolerance` (default `1.0°`). Warnings don't affect the
exit code unless `--strict`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | no error-level corners |
| 1 | at least one error (or warning with `--strict`) |
| 2 | file unreadable / not a KiCad board |

### CI integration

```yaml
# GitHub Actions
- name: Lint track corners
  run: |
    pip install git+https://github.com/94xhn/kicad-corner-lint
    kicad-corner-lint hardware/*.kicad_pcb
```

### Python API

```python
from kicad_corner_lint import load_board, find_corners

board = load_board(open("MAIN.kicad_pcb", encoding="utf-8").read())
for c in find_corners(board, ignore_nets=("GND",)):
    print(c.severity, c.kind, round(c.angle_deg, 1), c.net_name, (c.x_mm, c.y_mm))
```

## Compatibility

- **KiCad 5 through 10.** Both net conventions are handled: KiCad ≤ 9 stores a
  net *id* per segment plus a board-level net table; KiCad 10 stores the net
  *name* directly (and drops the table).
- Python ≥ 3.9, any OS, no dependencies.

## Known limitations (v0.1)

- **Corners inside pads are still reported.** A 90° bend fully covered by a
  pad is harmless, but pad geometry isn't parsed yet — use `--ignore-net` or
  review the report. Pad-aware filtering is on the roadmap.
- **Arc tracks are not checked.** Arcs are counted but segment↔arc tangency is
  not verified. (Boards rounded with kicad-round-tracks therefore pass — which
  is the correct outcome.)
- **Mid-span T-junctions are not corners.** A stub teeing into the middle of
  another segment is a branch; this tool checks corners (endpoint-to-endpoint
  bends) only. Endpoint junctions of 3+ segments are checked with
  `--include-junctions`.

## Roadmap

- `--fix`: rewrite right angles as 45° chamfers (opt-in, with backup)
- Pad-aware filtering of in-pad corners
- PyPI release
- pre-commit hook id

## Related tools

Part of a small family of zero-dependency KiCad lint tools:

- [kicad-board-lint](https://github.com/94xhn/kicad-board-lint) — board
  problems DRC silently accepts: pads with no net, duplicate-pad net
  mismatches, power tracks too thin for their current (IPC-2221).
- [kicad-file-doctor](https://github.com/94xhn/kicad-file-doctor) — explains
  why KiCad rejects or mis-loads a file, with line numbers.

## 中文简介

零依赖的 KiCad 走线直角检查工具：直接解析 `.kicad_pcb` 文本（不需要安装
KiCad、不依赖 pcbnew），检出 90° 直角与锐角（酸角）拐角，按严重度分级输出，
退出码可直接做 CI 门禁。

- KiCad 内置 DRC 的角度约束需要每个工程手写自定义规则且只能在 KiCad 里跑；
  [kicad-round-tracks](https://github.com/mitxela/kicad-round-tracks) 是"把拐角
  改圆"的修改工具，不做检测。本工具补上"独立检测"这个空位。
- 角度语义：180° 直行，135° 即标准 45° 拐角（合规）；89°–91° 报直角 error，
  <89° 报锐角 error，91°–134° 报 warning（`--strict` 下升级为 error）。
- 兼容 KiCad 5–10（KiCad 10 的 segment 改存网络名而非编号，已适配）。
- 已知局限：焊盘内部的拐角同样会被报出（v0.1 不解析焊盘几何）；圆弧走线不参与
  检查；横插到走线中段的 T 形分支不算拐角。

```bash
pip install git+https://github.com/94xhn/kicad-corner-lint
kicad-corner-lint 你的板子.kicad_pcb
```

## License

[MIT](LICENSE)
