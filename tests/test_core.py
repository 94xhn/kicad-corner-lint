import pytest

from kicad_corner_lint.core import classify, find_corners, load_board


def seg(x1, y1, x2, y2, layer="F.Cu", net=2, width=0.25):
    return (
        f"  (segment (start {x1} {y1}) (end {x2} {y2}) "
        f'(width {width}) (layer "{layer}") (net {net}))'
    )


def make_pcb(*tracks, nets=((1, "GND"), (2, "SIG"))):
    net_lines = "\n".join(f'  (net {nid} "{name}")' for nid, name in nets)
    body = "\n".join(tracks)
    return (
        '(kicad_pcb (version 20240108) (generator "test")\n'
        '  (net 0 "")\n'
        f"{net_lines}\n{body}\n)"
    )


def corners_of(*tracks, **kwargs):
    board = load_board(make_pcb(*tracks))
    return find_corners(board, **kwargs)


# ---------------------------------------------------------------- classify()


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (30.0, ("acute", "error")),
        (88.9, ("acute", "error")),
        (89.5, ("right-angle", "error")),
        (90.0, ("right-angle", "error")),
        (91.0, ("right-angle", "error")),
        (91.5, ("shallow", "warning")),
        (120.0, ("shallow", "warning")),
        (133.9, ("shallow", "warning")),
        (134.0, None),
        (135.0, None),
        (180.0, None),
        (0.0, ("acute", "error")),
    ],
)
def test_classify_default_tolerance(angle, expected):
    assert classify(angle, 1.0) == expected


def test_classify_tolerance_narrows_right_angle_band():
    assert classify(89.5, 0.1) == ("acute", "error")
    assert classify(89.95, 0.1) == ("right-angle", "error")


# ------------------------------------------------------------ find_corners()


def test_right_angle_detected():
    corners = corners_of(seg(0, 0, 10, 0), seg(10, 0, 10, 10))
    assert len(corners) == 1
    c = corners[0]
    assert c.kind == "right-angle"
    assert c.severity == "error"
    assert c.angle_deg == pytest.approx(90.0)
    assert (c.x_mm, c.y_mm) == (10.0, 0.0)
    assert c.net_name == "SIG"
    assert c.arms == 2


def test_45_degree_corner_is_clean():
    assert corners_of(seg(0, 0, 10, 0), seg(10, 0, 20, 10)) == []


def test_collinear_segments_are_clean():
    assert corners_of(seg(0, 0, 10, 0), seg(10, 0, 20, 0)) == []


def test_acute_corner_detected():
    corners = corners_of(seg(0, 0, 10, 0), seg(10, 0, 0, 5))
    assert len(corners) == 1
    assert corners[0].kind == "acute"
    assert corners[0].angle_deg == pytest.approx(26.565, abs=0.01)


def test_shallow_corner_is_warning():
    corners = corners_of(seg(0, 0, 10, 0), seg(10, 0, 20, 17.3205))
    assert len(corners) == 1
    assert corners[0].kind == "shallow"
    assert corners[0].severity == "warning"
    assert corners[0].angle_deg == pytest.approx(120.0, abs=0.01)


def test_different_layers_do_not_form_corner():
    assert corners_of(seg(0, 0, 10, 0, layer="F.Cu"), seg(10, 0, 10, 10, layer="B.Cu")) == []


def test_different_nets_do_not_form_corner():
    assert corners_of(seg(0, 0, 10, 0, net=1), seg(10, 0, 10, 10, net=2)) == []


def test_junction_skipped_by_default():
    tracks = (seg(0, 0, 10, 0), seg(10, 0, 10, 10), seg(10, 0, 20, 0))
    assert corners_of(*tracks) == []


def test_junction_checked_when_included():
    tracks = (seg(0, 0, 10, 0), seg(10, 0, 10, 10), seg(10, 0, 20, 0))
    corners = corners_of(*tracks, include_junctions=True)
    assert len(corners) == 1
    assert corners[0].arms == 3
    assert corners[0].angle_deg == pytest.approx(90.0)


def test_zero_length_segment_ignored():
    corners = corners_of(seg(5, 5, 5, 5), seg(0, 0, 10, 0), seg(10, 0, 10, 10))
    assert len(corners) == 1  # only the real right angle


def test_exact_duplicate_segments_deduplicated():
    # The same segment written twice must not create a fake 0-degree corner.
    assert corners_of(seg(0, 0, 10, 0), seg(0, 0, 10, 0), seg(10, 0, 20, 10)) == []


def test_partial_overlap_reported_as_acute():
    corners = corners_of(seg(0, 0, 10, 0), seg(0, 0, 5, 0))
    assert len(corners) == 1
    assert corners[0].kind == "acute"
    assert corners[0].angle_deg == pytest.approx(0.0)


def test_ignore_nets_pattern():
    tracks = (seg(0, 0, 10, 0, net=1), seg(10, 0, 10, 10, net=1))
    assert corners_of(*tracks, ignore_nets=("G*",)) == []
    assert len(corners_of(*tracks, ignore_nets=("XYZ",))) == 1


def test_net_zero_is_checked():
    corners = corners_of(seg(0, 0, 10, 0, net=0), seg(10, 0, 10, 10, net=0))
    assert len(corners) == 1
    assert corners[0].net_name == ""


def test_kicad5_unquoted_tokens():
    text = (
        "(kicad_pcb (version 20171130) (host pcbnew 5.1.6)\n"
        "  (net 0 \"\")\n"
        "  (net 1 GND)\n"
        "  (segment (start 0 0) (end 10 0) (width 0.25) (layer F.Cu) (net 1))\n"
        "  (segment (start 10 0) (end 10 10) (width 0.25) (layer F.Cu) (net 1))\n"
        ")"
    )
    board = load_board(text)
    corners = find_corners(board)
    assert len(corners) == 1
    assert corners[0].layer == "F.Cu"
    assert corners[0].net_name == "GND"


def test_arcs_counted_but_not_checked():
    text = make_pcb(
        "  (arc (start 0 0) (mid 5 2) (end 10 0) (width 0.25) (layer \"F.Cu\") (net 2))"
    )
    board = load_board(text)
    assert board.arc_count == 1
    assert board.segments == []
    assert find_corners(board) == []


def test_non_board_file_raises():
    with pytest.raises(ValueError, match="kicad_pcb"):
        load_board("(kicad_sch (version 1))")


# ------------------------------------------- KiCad 10 format (net by name)

KICAD10_HEADER = '(kicad_pcb (version 20250114) (generator "pcbnew")\n'


def _kicad10_right_angle(net_token: str) -> str:
    return (
        KICAD10_HEADER
        + f'  (segment (start 0 0) (end 10 0) (width 0.25) (layer "F.Cu") (net {net_token}))\n'
        + f'  (segment (start 10 0) (end 10 10) (width 0.25) (layer "F.Cu") (net {net_token}))\n'
        + ")"
    )


def test_kicad10_segment_stores_net_name():
    # KiCad 10 has no top-level net table; segments carry the net name.
    corners = find_corners(load_board(_kicad10_right_angle('"AIN3_P"')))
    assert len(corners) == 1
    assert corners[0].net_name == "AIN3_P"


def test_kicad10_numeric_looking_net_name_stays_a_name():
    text = (
        KICAD10_HEADER
        + '  (net 5 "GND")\n'
        + '  (segment (start 0 0) (end 10 0) (width 0.25) (layer "F.Cu") (net "5"))\n'
        + ")"
    )
    board = load_board(text)
    # the quoted "5" is a net *name*, not a reference to net id 5 ("GND")
    assert board.segments[0].net == "5"


def test_unknown_net_id_falls_back_to_hash_id():
    corners = find_corners(load_board(_kicad10_right_angle("7")))
    assert len(corners) == 1
    assert corners[0].net_name == "#7"


def test_kicad10_ignore_net_by_name():
    board = load_board(_kicad10_right_angle('"AIN3_P"'))
    assert find_corners(board, ignore_nets=("AIN*",)) == []


def test_errors_sort_before_warnings():
    corners = corners_of(
        seg(0, 0, 10, 0), seg(10, 0, 20, 17.3205),  # shallow warning
        seg(50, 0, 60, 0), seg(60, 0, 60, 10),      # right-angle error
    )
    assert [c.severity for c in corners] == ["error", "warning"]
