"""Catalogue record contract aligned to interior_company_catalog.db."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CatalogItem(BaseModel):
    """One row from the `catalog` table. Nullable DB columns stay optional."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    item_id: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    style_tags: str | None = None
    price_inr: int | None = Field(default=None, ge=0)
    width_cm: int | None = Field(default=None, gt=0)
    depth_cm: int | None = Field(default=None, gt=0)
    height_cm: int | None = Field(default=None, gt=0)
    color_finish: str | None = None
    in_stock: int | None = Field(default=None, ge=0, le=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    room_types: str | None = None

    @field_validator("item_id", "category", "name")
    @classmethod
    def required_text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    def style_tag_list(self) -> list[str]:
        return _split_csv(self.style_tags)

    def room_type_list(self) -> list[str]:
        return _split_csv(self.room_types)

    def is_living_room_applicable(self) -> bool:
        return LIVING_ROOM_TOKEN in self.room_type_list()

    def has_usable_price(self) -> bool:
        return self.price_inr is not None


LIVING_ROOM_TOKEN = "Living Room"


def _split_csv(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]
