import json
from pathlib import Path

import pytest

from kicad_corner_lint.cli import main

DEMO = Path(__file__).resolve().parent.parent / "examples" / "demo.kicad_pcb"

CLEAN_BOARD = (
    '(kicad_pcb (version 20240108) (generator "test")\n'
    '  (net 0 "")\n'
    '  (net 1 "SIG")\n'
    '  (segment (start 0 0) (end 10 0) (width 0.25) (layer "F.Cu") (net 1))\n'
    '  (segment (start 10 0) (end 20 10) (width 0.25) (layer "F.Cu") (net 1))\n'
    ")"
)

SHALLOW_ONLY_BOARD = (
    '(kicad_pcb (version 20240108) (generator "test")\n'
    '  (net 0 "")\n'
    '  (net 1 "SIG")\n'
    '  (segment (start 0 0) (end 10 0) (width 0.25) (layer "F.Cu") (net 1))\n'
    '  (segment (start 10 0) (end 20 17.3205) (width 0.25) (layer "F.Cu") (net 1))\n'
    ")"
)


def test_demo_board_fails_with_expected_counts(capsys):
    assert main([str(DEMO)]) == 1
    out = capsys.readouterr().out
    assert "right-angle" in out
    assert "acute" in out
    assert "shallow" in out
    assert "FAIL: 2 error(s), 1 warning(s)" in out


def test_demo_board_junctions_add_one_error(capsys):
    assert main([str(DEMO), "--include-junctions"]) == 1
    assert "FAIL: 3 error(s), 1 warning(s)" in capsys.readouterr().out


def test_clean_board_passes(tmp_path, capsys):
    board = tmp_path / "clean.kicad_pcb"
    board.write_text(CLEAN_BOARD, encoding="utf-8")
    assert main([str(board)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_warning_does_not_fail_without_strict(tmp_path):
    board = tmp_path / "shallow.kicad_pcb"
    board.write_text(SHALLOW_ONLY_BOARD, encoding="utf-8")
    assert main([str(board)]) == 0
    assert main([str(board), "--strict"]) == 1


def test_ignore_net_silences_violations(capsys):
    code = main([str(DEMO), "--ignore-net", "SIG", "--ignore-net", "GND"])
    assert code == 0
    assert "PASS" in capsys.readouterr().out


def test_json_output_is_machine_readable(capsys):
    main([str(DEMO), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_errors"] == 2
    assert payload["total_warnings"] == 1
    (file_result,) = payload["files"]
    kinds = {c["kind"] for c in file_result["corners"]}
    assert {"right-angle", "acute", "shallow"} == kinds
    assert all("x_mm" in c and "angle_deg" in c for c in file_result["corners"])


def test_missing_file_exits_2(capsys):
    assert main(["no_such_board.kicad_pcb"]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_bad_file_does_not_block_other_files(tmp_path, capsys):
    board = tmp_path / "clean.kicad_pcb"
    board.write_text(CLEAN_BOARD, encoding="utf-8")
    assert main(["no_such_board.kicad_pcb", str(board)]) == 2
    captured = capsys.readouterr()
    assert "cannot read" in captured.err
    assert "clean.kicad_pcb" in captured.out  # the good file was still checked


def test_non_board_file_exits_2(tmp_path, capsys):
    bogus = tmp_path / "x.kicad_pcb"
    bogus.write_text("(kicad_sch)", encoding="utf-8")
    assert main([str(bogus)]) == 2
    assert "kicad_pcb" in capsys.readouterr().err


def test_multiple_files_aggregate(tmp_path, capsys):
    board = tmp_path / "clean.kicad_pcb"
    board.write_text(CLEAN_BOARD, encoding="utf-8")
    assert main([str(board), str(DEMO)]) == 1
    assert "across 2 file(s)" in capsys.readouterr().out


def test_version_flag():
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
