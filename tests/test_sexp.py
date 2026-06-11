import pytest

from kicad_corner_lint.sexp import QuotedStr, parse


def test_basic_nesting():
    assert parse('(a (b "c d") e)') == [["a", ["b", "c d"], "e"]]


def test_multiple_top_level_forms():
    assert parse("(a)(b)") == [["a"], ["b"]]


def test_empty_input():
    assert parse("") == []
    assert parse("   \n\t ") == []


def test_quoted_atom_keeps_spaces_and_parens():
    assert parse('(x "(not a list)")') == [["x", "(not a list)"]]


def test_escaped_quote_inside_string():
    assert parse('(n "a\\"b")') == [["n", 'a"b']]


def test_escaped_backslash_and_newline():
    assert parse('(n "a\\\\b\\nc")') == [["n", "a\\b\nc"]]


def test_unquoted_and_quoted_atoms_equivalent():
    # KiCad 5 writes (layer F.Cu); KiCad 6+ writes (layer "F.Cu")
    assert parse("(layer F.Cu)") == parse('(layer "F.Cu")')


def test_stray_close_paren_tolerated():
    # KiCad's own parser skips stray ')' (official demo boards contain
    # hundreds); match that so boards KiCad opens also parse here.
    assert parse("(a))") == [["a"]]


def test_unbalanced_open_raises():
    with pytest.raises(ValueError, match="unbalanced"):
        parse("((a)")


def test_numbers_stay_strings():
    assert parse("(start 1.5 -2)") == [["start", "1.5", "-2"]]


def test_quoted_atoms_are_marked():
    quoted, plain = parse('("a" b)')[0]
    assert isinstance(quoted, QuotedStr)
    assert not isinstance(plain, QuotedStr)
    assert quoted == "a"  # still compares as a plain str
