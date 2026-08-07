from datetime import datetime
from decimal import Decimal

import pytest
from openpyxl.utils.datetime import CALENDAR_WINDOWS_1900, to_excel

from app.services.excel.parsers import (
    mask_sensitive_value,
    parse_cpf,
    parse_date,
    parse_money,
    round_money,
)


def test_valid_and_invalid_cpf() -> None:
    assert parse_cpf("529.982.247-25").value == "52998224725"
    invalid = parse_cpf("111.111.111-11")
    assert invalid.value is None
    assert invalid.issue is not None
    assert invalid.issue.kind == "invalid_cpf"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", Decimal("1234.56")),
        ("1234,56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        (1234, Decimal("1234.00")),
        (1234.56, Decimal("1234.56")),
    ],
)
def test_money_parser_returns_decimal_for_safe_formats(raw, expected: Decimal) -> None:
    parsed = parse_money(raw)
    assert parsed.value == expected
    assert isinstance(parsed.value, Decimal)
    assert not isinstance(parsed.value, float)


@pytest.mark.parametrize("raw", ["1.234", "1,234", "12.34.56"])
def test_money_parser_rejects_ambiguous_values(raw: str) -> None:
    parsed = parse_money(raw)
    assert parsed.value is None
    assert parsed.issue is not None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (Decimal("123.454"), Decimal("123.45")),
        (Decimal("123.455"), Decimal("123.46")),
        (Decimal("123.4567"), Decimal("123.46")),
    ],
)
def test_business_rounding_is_half_up(raw: Decimal, expected: Decimal) -> None:
    assert round_money(raw) == expected
    parsed = parse_money(raw)
    assert parsed.value == expected
    assert isinstance(parsed.value, Decimal)


def test_text_native_and_serial_dates() -> None:
    text_date = parse_date("31/01/2026", epoch=CALENDAR_WINDOWS_1900)
    serial = to_excel(datetime(2026, 1, 31), epoch=CALENDAR_WINDOWS_1900)
    serial_date = parse_date(serial, epoch=CALENDAR_WINDOWS_1900)
    native_date = parse_date(datetime(2026, 1, 31), epoch=CALENDAR_WINDOWS_1900)
    assert text_date.value == datetime(2026, 1, 31).date()
    assert serial_date.value == datetime(2026, 1, 31).date()
    assert native_date.value == datetime(2026, 1, 31).date()


def test_iso_datetime_text_is_accepted_without_timezone_loss() -> None:
    parsed = parse_date("2026-01-31T00:00:00", epoch=CALENDAR_WINDOWS_1900)
    assert parsed.value == datetime(2026, 1, 31).date()


def test_invalid_date_is_not_guessed() -> None:
    parsed = parse_date("31/02/2026", epoch=CALENDAR_WINDOWS_1900)
    assert parsed.value is None
    assert parsed.issue is not None


def test_sensitive_mask_never_contains_full_cpf() -> None:
    cpf = "52998224725"
    masked = mask_sensitive_value("NUM_CPF", cpf)
    assert masked is not None
    assert cpf not in masked
    assert masked.endswith("25)")
