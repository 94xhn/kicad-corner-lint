# Contributing

Issues and PRs are welcome — including reports of boards that parse wrong or
corners that are misclassified. If you can, attach a minimal `.kicad_pcb`
snippet (a few `(segment ...)` forms are enough).

## Development setup

```bash
git clone https://github.com/94xhn/kicad-corner-lint
cd kicad-corner-lint
python -m venv .venv
.venv/bin/pip install -e .[dev]      # Windows: .venv\Scripts\pip install -e .[dev]
```

## Running checks

```bash
ruff check .
pytest
```

Both must pass; CI runs them on Python 3.9 / 3.11 / 3.13 plus a gitleaks
secret scan.

## Architecture conventions

- `kicad_corner_lint/sexp.py` — S-expression tokenizer/parser. Knows nothing
  about PCBs.
- `kicad_corner_lint/core.py` — board model + corner detection. Pure logic,
  no I/O, no printing; everything here must be unit-testable.
- `kicad_corner_lint/cli.py` — argument parsing, file I/O, rendering. No
  geometry.

Keep it that way: new detection logic goes in `core.py` with tests in
`tests/test_core.py`; new output formats go in `cli.py`.

The package stays **zero-dependency** — that is its main selling point for CI
use. PRs adding runtime dependencies will be asked to find another way.
