from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from openpyxl.utils.datetime import from_excel

_CPF_DIGITS = re.compile(r"\D")
_INTEGER = re.compile(r"^[+-]?\d+$")
_BR_DECIMAL = re.compile(r"^[+-]?\d+,\d{1,2}$")
_BR_GROUPED = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+,\d{1,2}$")
_DOT_DECIMAL = re.compile(r"^[+-]?\d+\.\d{1,2}$")
_RATE_DECIMAL = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
_MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ParseIssue:
    kind: str
    message: str


@dataclass(frozen=True, slots=True)
class Parsed[T]:
    value: T | None
    issue: ParseIssue | None = None


def normalize_code(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).upper()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        decimal_value = Decimal(str(value))
        if decimal_value == decimal_value.to_integral_value():
            return format(decimal_value.quantize(Decimal(1)), "f")
        return format(decimal_value.normalize(), "f")
    text = " ".join(str(value).strip().split())
    return text or None


def normalize_name(value: Any) -> str | None:
    normalized = normalize_code(value)
    return normalized.upper() if normalized else None


def parse_cpf(value: Any) -> Parsed[str]:
    if value is None or not str(value).strip():
        return Parsed(None)
    digits = _CPF_DIGITS.sub("", str(value))
    if len(digits) != 11 or len(set(digits)) == 1 or not _has_valid_cpf_digits(digits):
        return Parsed(None, ParseIssue("invalid_cpf", "CPF inválido."))
    return Parsed(digits)


def _has_valid_cpf_digits(digits: str) -> bool:
    for position in (9, 10):
        weight = position + 1
        total = sum(int(digit) * (weight - index) for index, digit in enumerate(digits[:position]))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != int(digits[position]):
            return False
    return True


def parse_date(value: Any, *, epoch: datetime) -> Parsed[date]:
    if value is None or value == "":
        return Parsed(None)
    if isinstance(value, datetime):
        return Parsed(value.date())
    if isinstance(value, date):
        return Parsed(value)
    if isinstance(value, int | float) and not isinstance(value, bool):
        try:
            converted = from_excel(value, epoch=epoch)
            parsed = converted.date() if isinstance(converted, datetime) else converted
            if isinstance(parsed, date) and date(1900, 1, 1) <= parsed <= date(2200, 12, 31):
                return Parsed(parsed)
        except (TypeError, ValueError, OverflowError):
            pass
        return Parsed(None, ParseIssue("invalid_date", "Data serial inválida."))

    text = str(value).strip()
    try:
        return Parsed(datetime.fromisoformat(text).date())
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M:%S"):
        try:
            return Parsed(datetime.strptime(text, pattern).date())
        except ValueError:
            continue
    return Parsed(None, ParseIssue("invalid_date", "Data inválida."))


def parse_money(value: Any) -> Parsed[Decimal]:
    if value is None or value == "":
        return Parsed(None)
    try:
        if isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, int) and not isinstance(value, bool):
            decimal_value = Decimal(value)
        elif isinstance(value, float):
            # Excel numbers arrive as float; conversion is textual and no float arithmetic occurs.
            decimal_value = Decimal(str(value))
        else:
            text = _clean_numeric_text(value)
            if _INTEGER.fullmatch(text):
                decimal_value = Decimal(text)
            elif _BR_GROUPED.fullmatch(text):
                decimal_value = Decimal(text.replace(".", "").replace(",", "."))
            elif _BR_DECIMAL.fullmatch(text):
                decimal_value = Decimal(text.replace(",", "."))
            elif _DOT_DECIMAL.fullmatch(text):
                decimal_value = Decimal(text)
            else:
                return Parsed(
                    None,
                    ParseIssue("ambiguous_money", "Valor monetário inválido ou ambíguo."),
                )
    except (InvalidOperation, ValueError):
        return Parsed(None, ParseIssue("invalid_money", "Valor monetário inválido."))

    quantized = round_money(decimal_value)
    if len(quantized.copy_abs().to_integral_value().as_tuple().digits) > 12:
        return Parsed(None, ParseIssue("money_overflow", "Valor monetário fora do limite."))
    return Parsed(quantized)


def round_money(value: Decimal) -> Decimal:
    """Round monetary values to cents using the business-approved half-up rule."""
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def parse_rate(value: Any) -> Parsed[Decimal]:
    if value is None or value == "":
        return Parsed(None)
    try:
        if isinstance(value, Decimal):
            parsed = value
        elif isinstance(value, int | float) and not isinstance(value, bool):
            parsed = Decimal(str(value))
        else:
            text = _clean_numeric_text(value)
            if not _RATE_DECIMAL.fullmatch(text):
                raise InvalidOperation
            parsed = Decimal(text.replace(",", "."))
        return Parsed(parsed)
    except (InvalidOperation, ValueError):
        return Parsed(None, ParseIssue("invalid_rate", "Taxa inválida."))


def parse_integer(value: Any) -> Parsed[int]:
    if value is None or value == "":
        return Parsed(None)
    if isinstance(value, int) and not isinstance(value, bool):
        return Parsed(value)
    if isinstance(value, float) and value.is_integer():
        return Parsed(int(value))
    text = str(value).strip()
    if _INTEGER.fullmatch(text):
        return Parsed(int(text))
    return Parsed(None, ParseIssue("invalid_integer", "Número inteiro inválido."))


def mask_sensitive_value(field_name: str | None, value: Any) -> str | None:
    if value is None or value == "":
        return None
    field = (field_name or "").upper()
    if "CPF" in field:
        digits = _CPF_DIGITS.sub("", str(value))
        suffix = digits[-2:] if len(digits) >= 2 else "**"
        return f"***.***.***-** (final {suffix})"
    text = str(value)
    if len(text) <= 2:
        return "**"
    return f"{text[0]}***{text[-1]}"


def serialize_raw(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        return format(Decimal(str(value)), "f")
    return value


def _clean_numeric_text(value: Any) -> str:
    return (
        str(value)
        .strip()
        .replace("R$", "")
        .replace("r$", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )
