# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-10

### Added

- Zero-dependency parser for `.kicad_pcb` S-expression files (KiCad 5–10),
  including the KiCad 10 format change where segments store the net *name*
  instead of a numeric id.
- Corner detection: right angles (89°–91°, error), acute corners (<89°,
  error, including 0° overlapping copper) and shallow corners (91°–134°,
  warning), with configurable `--tolerance`.
- Endpoint-junction handling: points where 3+ segment endpoints meet are
  skipped by default, checked with `--include-junctions`.
- CLI with text and JSON output, `--strict`, repeatable `--ignore-net`
  fnmatch patterns, multi-file aggregation and CI-friendly exit codes
  (0 clean / 1 violations / 2 usage error).
- Python API: `load_board()`, `find_corners()`, `classify()`.
- Demo board in `examples/`, 56-test pytest suite, ruff + gitleaks CI.
