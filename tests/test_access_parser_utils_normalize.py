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


def test_normalize_access_parser_rows_accepts_generator_rows():
    def row_gen():
        yield (10, "x")
        yield (20, "y")

    rows = normalize_access_parser_rows(row_gen())
    assert rows == [
        {"col_0": 10, "col_1": "x"},
        {"col_0": 20, "col_1": "y"},
    ]


def test_normalize_access_parser_rows_accepts_mixed_list():
    Row = namedtuple("Row", ["id", "name"])
    parsed = [{"id": 1, "name": "a"}, Row(2, "b"), [3, "c"], "raw"]
    rows = normalize_access_parser_rows(parsed)
    assert rows == [
        {"id": 1, "name": "a"},
        {"id": 2, "name": "b"},
        {"col_0": 3, "col_1": "c"},
        {"value": "raw"},
    ]


def test_normalize_access_parser_rows_prefers_to_dict_over_iterable():
    class FakeFrame:
        def __iter__(self):
            yield "id"
            yield "name"

        def to_dict(self, orient="records"):
            assert orient == "records"
            return [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]

    rows = normalize_access_parser_rows(FakeFrame())
    assert rows == [
        {"id": 1, "name": "alpha"},
        {"id": 2, "name": "beta"},
    ]
