"""Before-agent validation and unit/budget normalization.

Does not guess missing length, width, ceiling, budget, room type, style, or must-haves.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.brief import RoomBrief
from app.models.input import CustomerInput

CM_PER_FOOT = 30.48
CM_PER_METRE = 100.0
INR_PER_LAKH = 100_000
INR_PER_CRORE = 10_000_000

_NUMBER = r"([0-9]+(?:[.,][0-9]+)?)"


class NormalizationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _as_float(number_text: str) -> float:
    return float(number_text.replace(",", ""))


def parse_dimension_cm(value: Any, *, field: str, default_unit: str | None) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise NormalizationError([f"missing:{field}"])
    if isinstance(value, bool):
        raise NormalizationError([f"invalid:{field}"])
    if isinstance(value, (int, float)):
        if not default_unit:
            raise NormalizationError(
                [f"missing_unit:{field} (will not assume centimetres or feet)"]
            )
        amount = float(value)
        unit = default_unit.lower()
    else:
        text = (
            str(value)
            .strip()
            .lower()
            .replace("centimetres", "cm")
            .replace("centimeters", "cm")
        )
        match = re.search(_NUMBER, text.replace(",", ""))
        if not match:
            raise NormalizationError([f"invalid:{field}"])
        amount = _as_float(match.group(1))
        unit = default_unit or "cm"
        if re.search(r"\bft\b|\bfoot\b|\bfeet\b|'", text):
            unit = "ft"
        elif re.search(r"\bm\b|\bmetre|\bmeter", text) and "cm" not in text:
            unit = "m"
        elif "cm" in text:
            unit = "cm"
        elif default_unit:
            unit = default_unit.lower()
        elif re.fullmatch(r"[\d.,\s]+", text):
            raise NormalizationError(
                [f"missing_unit:{field} (will not assume centimetres or feet)"]
            )
    if amount <= 0:
        raise NormalizationError([f"invalid:{field}"])
    unit = unit.lower()
    if unit in {"ft", "foot", "feet"}:
        cm = amount * CM_PER_FOOT
    elif unit in {"m", "metre", "meter", "metres", "meters"}:
        cm = amount * CM_PER_METRE
    elif unit in {"cm", "centimetre", "centimeter"}:
        cm = amount
    else:
        raise NormalizationError([f"unsupported_unit:{field}:{unit}"])
    rounded = int(round(cm))
    if rounded <= 0:
        raise NormalizationError([f"invalid:{field}"])
    return rounded


def parse_budget_inr(value: Any) -> int:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise NormalizationError(["missing:budget"])
    if isinstance(value, bool):
        raise NormalizationError(["invalid:budget"])
    if isinstance(value, (int, float)):
        amount = float(value)
        if amount <= 0:
            raise NormalizationError(["invalid:budget"])
        return int(round(amount))
    text = str(value).strip().lower().replace("₹", "").replace("rs", "").replace(",", "")
    match = re.search(_NUMBER, text)
    if not match:
        raise NormalizationError(["invalid:budget"])
    amount = _as_float(match.group(1))
    if "crore" in text:
        amount *= INR_PER_CRORE
    elif "lakh" in text or "lac" in text:
        amount *= INR_PER_LAKH
    if amount <= 0:
        raise NormalizationError(["invalid:budget"])
    return int(round(amount))


def normalize_room_type(value: str | None) -> str:
    if value is None or not str(value).strip():
        raise NormalizationError(["missing:room_type"])
    cleaned = re.sub(r"\s+", " ", str(value).strip())
    if cleaned.casefold() == "living room":
        return "Living Room"
    raise NormalizationError([f"unsupported_room_type:{cleaned}"])


def normalize_customer_input(raw: CustomerInput | dict[str, Any]) -> RoomBrief:
    payload = raw if isinstance(raw, CustomerInput) else CustomerInput.model_validate(raw)
    errors: list[str] = []

    room_type = "Living Room"
    try:
        room_type = normalize_room_type(payload.room_type)
    except NormalizationError as exc:
        errors.extend(exc.errors)

    unit = payload.unit
    length_source = payload.length_cm if payload.length_cm not in (None, "") else payload.length
    width_source = payload.width_cm if payload.width_cm not in (None, "") else payload.width
    ceiling_source = payload.ceiling_cm if payload.ceiling_cm not in (None, "") else payload.ceiling
    length_unit = "cm" if payload.length_cm not in (None, "") else unit
    width_unit = "cm" if payload.width_cm not in (None, "") else unit
    ceiling_unit = "cm" if payload.ceiling_cm not in (None, "") else unit

    length_cm = width_cm = ceiling_cm = None
    try:
        length_cm = parse_dimension_cm(length_source, field="length", default_unit=length_unit)
    except NormalizationError as exc:
        errors.extend(exc.errors)
    try:
        width_cm = parse_dimension_cm(width_source, field="width", default_unit=width_unit)
    except NormalizationError as exc:
        errors.extend(exc.errors)
    try:
        ceiling_cm = parse_dimension_cm(ceiling_source, field="ceiling", default_unit=ceiling_unit)
    except NormalizationError as exc:
        errors.extend(exc.errors)

    budget_source = payload.budget_inr if payload.budget_inr not in (None, "") else payload.budget
    budget_inr = None
    try:
        budget_inr = parse_budget_inr(budget_source)
    except NormalizationError as exc:
        errors.extend(exc.errors)

    if not payload.style_preference:
        errors.append("missing:style_preference")
    if not payload.must_haves:
        errors.append("missing:must_haves")

    if errors:
        raise NormalizationError(errors)

    return RoomBrief(
        room_type=room_type,  # type: ignore[arg-type]
        length_cm=length_cm,
        width_cm=width_cm,
        ceiling_cm=ceiling_cm,
        budget_inr=budget_inr,
        style_preference=payload.style_preference or "",
        must_haves=payload.must_haves or "",
        constraints=payload.constraints or "",
        customer_note=payload.customer_note or "",
    )
