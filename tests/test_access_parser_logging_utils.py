import io
import logging

from interface.access_parser_utils import ensure_access_parser_logging


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
