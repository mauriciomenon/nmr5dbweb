import io
import logging

from interface.access_parser_utils import (
    ensure_access_parser_logging,
    is_access_parser_no_data_error,
    is_access_parser_no_data_message,
)


def _capture_access_parser_output(message_one, message_two, configure_filter=True):
    root = logging.getLogger()
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    old_level = root.level
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    try:
        if configure_filter:
            ensure_access_parser_logging()
        logger = logging.getLogger("access_parser.test")
        logger.warning(message_one)
        logger.warning(message_two)
        handler.flush()
        return buffer.getvalue()
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)


def test_access_parser_noise_hidden_by_default(monkeypatch):
    monkeypatch.delenv("NMR5DBWEB_ACCESS_PARSER_VERBOSE", raising=False)
    logging.getLogger("access_parser").setLevel(logging.NOTSET)
    output = _capture_access_parser_output(
        "table ABC has no data",
        "table DEF warning kept",
        configure_filter=True,
    )
    assert "has no data" not in output
    assert "warning kept" in output


def test_access_parser_noise_visible_in_verbose_mode(monkeypatch):
    monkeypatch.setenv("NMR5DBWEB_ACCESS_PARSER_VERBOSE", "1")
    logging.getLogger("access_parser").setLevel(logging.NOTSET)

    output = _capture_access_parser_output(
        "table ABC has no data",
        "table DEF warning kept",
        configure_filter=True,
    )
    assert "has no data" in output
    assert "warning kept" in output


def test_is_access_parser_no_data_message_variants():
    assert is_access_parser_no_data_message("Table X has no data")
    assert is_access_parser_no_data_message("TABLE X NO DATA")
    assert is_access_parser_no_data_message("tabela vazia")
    assert is_access_parser_no_data_message("sem dados")
    assert is_access_parser_no_data_message("No rows returned")
    assert is_access_parser_no_data_message("table contains no records")
    assert is_access_parser_no_data_message("query returned 0 rows")
    assert not is_access_parser_no_data_message("table loaded successfully")


def test_is_access_parser_no_data_error_accepts_exception():
    err = RuntimeError("table contains no records")
    assert is_access_parser_no_data_error(err)
    assert not is_access_parser_no_data_error(ValueError("hard parser crash"))
