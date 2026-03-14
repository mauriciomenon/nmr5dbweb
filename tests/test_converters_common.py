from converters.common import extract_date_from_filename


def test_extract_date_from_filename_supported_formats():
    assert extract_date_from_filename("01-02-2026_DB.accdb") == "2026-02-01"
    assert extract_date_from_filename("2026_02_01_DB.accdb") == "2026-02-01"
    assert extract_date_from_filename("01022026_DB.accdb") == "2026-02-01"
    assert extract_date_from_filename("20260201_DB.accdb") == "2026-02-01"


def test_extract_date_from_filename_rejects_invalid_date():
    assert extract_date_from_filename("2026-13-40_DB.accdb") is None
    assert extract_date_from_filename("31112026_DB.accdb") is None
