from interface.access_parser_utils import list_access_tables_from_parser


def test_list_access_tables_from_catalog_dedup_and_filter():
    class FakeCatalog:
        @staticmethod
        def keys():
            return ["MSysObjects", "users", "users", "orders", " msysTemp "]

    class FakeParser:
        catalog = FakeCatalog()

    tables = list_access_tables_from_parser(FakeParser())
    assert tables == ["users", "orders"]


def test_list_access_tables_from_table_names_callable():
    class FakeParser:
        def table_names(self):
            return ["MSysA", "table_a", "table_b", "table_a"]

    tables = list_access_tables_from_parser(FakeParser())
    assert tables == ["table_a", "table_b"]


def test_list_access_tables_from_get_table_names():
    class FakeParser:
        def get_table_names(self):
            return ["alpha", "beta", "MSysInternal"]

    tables = list_access_tables_from_parser(FakeParser())
    assert tables == ["alpha", "beta"]


def test_list_access_tables_falls_back_when_tables_attr_is_empty():
    class FakeParser:
        tables = []

        def table_names(self):
            return ["table_a", "MSysSkip", "table_b"]

    tables = list_access_tables_from_parser(FakeParser())
    assert tables == ["table_a", "table_b"]
