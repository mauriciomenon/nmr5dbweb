from collections import namedtuple

from interface.access_parser_utils import normalize_access_parser_rows


def test_normalize_access_parser_rows_accepts_tuple_rows():
    parsed = [(1, "a"), (2, "b")]
    rows = normalize_access_parser_rows(parsed)
    assert rows == [
        {"col_0": 1, "col_1": "a"},
        {"col_0": 2, "col_1": "b"},
    ]


def test_normalize_access_parser_rows_accepts_namedtuple_rows():
    Row = namedtuple("Row", ["id", "name"])
    parsed = [Row(1, "alpha"), Row(2, "beta")]
    rows = normalize_access_parser_rows(parsed)
    assert rows == [
        {"id": 1, "name": "alpha"},
        {"id": 2, "name": "beta"},
    ]
