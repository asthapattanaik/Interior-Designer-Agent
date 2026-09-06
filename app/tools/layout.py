"""Deterministic layout/fit checker using catalogue and room centimetre boxes.

Spatial facts available (see docs/data_profile.md):
- product width_cm, depth_cm, height_cm
- room length_cm, width_cm, ceiling_cm

Not available: doors, windows, placement, circulation, occupancy standards.

This is a box-fit and floor-area check, not CAD or an architectural guarantee.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.db.catalog_repository import CatalogRepository
from app.models.catalog import CatalogItem
from app.models.output import FitResult

# MVP ASSUMPTION: category groups for how dimensions are used.
# The database does not classify footprint vs wall vs ceiling.
FLOOR_STANDING_CATEGORIES = frozenset(
    {
        "Armchair",
        "Bean Bag",
        "Bed",
        "Bedside Table",
        "Bookshelf",
        "Coffee Table",
        "Console",
        "Desk",
        "Dining Chair",
        "Dining Table",
        "Floor Lamp",
        "Mattress",
        "Office Chair",
        "Ottoman",
        "Planter",
        "Side Table",
        "Sofa",
        "TV Unit",
        "Wardrobe",
    }
)
WALL_CATEGORIES = frozenset({"Curtains", "Mirror", "Wall Art"})
CEILING_CATEGORIES = frozenset({"Pendant Light"})
FLOOR_COVERING_CATEGORIES = frozenset({"Rug"})
ACCESSORY_CATEGORIES = frozenset({"Cushions", "Table Lamp"})

# MVP ASSUMPTION: fail occupancy only when summed floor footprints exceed the
# room rectangle. This is not a 55% interior-design standard. Circulation is
# not computed because placement data does not exist.
DEFAULT_MAX_OCCUPANCY_RATIO = 1.0


class LayoutError(ValueError):
    """Raised when a layout check cannot be computed from catalogue data."""


class UnknownCatalogItemError(LayoutError):
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(f"Unknown catalogue item_id: {item_id}")


class InvalidQuantityError(LayoutError):
    def __init__(self, item_id: str, quantity: int) -> None:
        self.item_id = item_id
        self.quantity = quantity
        super().__init__(f"Quantity for {item_id} must be a positive integer, got {quantity}")


class InvalidRoomError(LayoutError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class LayoutConfig:
    """Configurable MVP layout assumptions. Not Interior Company building rules."""

    max_occupancy_ratio: float = DEFAULT_MAX_OCCUPANCY_RATIO
    allow_plan_rotation: bool = True
    floor_standing_categories: frozenset[str] = field(
        default_factory=lambda: FLOOR_STANDING_CATEGORIES
    )
    wall_categories: frozenset[str] = field(default_factory=lambda: WALL_CATEGORIES)
    ceiling_categories: frozenset[str] = field(default_factory=lambda: CEILING_CATEGORIES)
    floor_covering_categories: frozenset[str] = field(
        default_factory=lambda: FLOOR_COVERING_CATEGORIES
    )
    accessory_categories: frozenset[str] = field(default_factory=lambda: ACCESSORY_CATEGORIES)


def _fits_in_rectangle(
    item_a: int,
    item_b: int,
    room_a: int,
    room_b: int,
    *,
    allow_rotation: bool,
) -> bool:
    axis_aligned = item_a <= room_a and item_b <= room_b
    if axis_aligned:
        return True
    if not allow_rotation:
        return False
    return item_b <= room_a and item_a <= room_b


class LayoutChecker:
    def __init__(
        self,
        repository: CatalogRepository | None = None,
        config: LayoutConfig | None = None,
    ) -> None:
        self._repository = repository or CatalogRepository()
        self._config = config or LayoutConfig()

    def check(
        self,
        *,
        length_cm: int,
        width_cm: int,
        ceiling_cm: int,
        selections: Sequence[tuple[str, int]],
    ) -> FitResult:
        if length_cm <= 0 or width_cm <= 0 or ceiling_cm <= 0:
            raise InvalidRoomError("Room length, width and ceiling must be positive centimetres")

        room_area = length_cm * width_cm
        warnings: list[str] = []
        blocking: list[str] = []
        footprint = 0
        occupancy_limited_ids: list[str] = []

        warnings.append(
            "MVP assumption: this is a rectangle/height and summed-footprint check, "
            "not a floor-plan, circulation measurement, or architectural standard."
        )
        if self._config.allow_plan_rotation:
            warnings.append(
                "MVP assumption: floor items may be rotated 90 degrees in plan "
                "(width and depth swapped); height stays vertical."
            )

        for item_id, quantity in selections:
            if quantity <= 0:
                raise InvalidQuantityError(item_id, quantity)
            item = self._repository.get_item(item_id)
            if item is None:
                raise UnknownCatalogItemError(item_id)
            self._assess_item(
                item=item,
                quantity=quantity,
                length_cm=length_cm,
                width_cm=width_cm,
                ceiling_cm=ceiling_cm,
                warnings=warnings,
                blocking=blocking,
                occupancy_limited_ids=occupancy_limited_ids,
            )
            role = self._role(item.category)
            if role == "floor_standing" and self._has_plan_dims(item):
                footprint += item.width_cm * item.depth_cm * quantity  # type: ignore[operator]

        occupancy = footprint / room_area if room_area else None
        if (
            occupancy is not None
            and occupancy > self._config.max_occupancy_ratio
        ):
            for item_id in occupancy_limited_ids:
                if item_id not in blocking:
                    blocking.append(item_id)
            warnings.append(
                f"MVP occupancy cap is {self._config.max_occupancy_ratio:.2f} "
                f"(default 1.00 = summed floor footprints cannot exceed room area; "
                "not a 55% interior-design rule)."
            )

        fits = not blocking and (
            occupancy is None or occupancy <= self._config.max_occupancy_ratio
        )
        explanation = self._explain(
            fits=fits,
            occupancy=occupancy,
            footprint=footprint,
            room_area=room_area,
            blocking=blocking,
        )
        return FitResult(
            fits=fits,
            explanation=explanation,
            warnings=warnings,
            blocking_items=blocking,
            occupancy_ratio=None if occupancy is None else round(occupancy, 4),
            room_area_cm2=room_area,
            furniture_footprint_cm2=footprint,
        )

    def _role(self, category: str) -> str:
        cfg = self._config
        if category in cfg.floor_standing_categories:
            return "floor_standing"
        if category in cfg.wall_categories:
            return "wall"
        if category in cfg.ceiling_categories:
            return "ceiling"
        if category in cfg.floor_covering_categories:
            return "floor_covering"
        if category in cfg.accessory_categories:
            return "accessory"
        return "unknown"

    def _has_plan_dims(self, item: CatalogItem) -> bool:
        return item.width_cm is not None and item.depth_cm is not None

    def _assess_item(
        self,
        *,
        item: CatalogItem,
        quantity: int,
        length_cm: int,
        width_cm: int,
        ceiling_cm: int,
        warnings: list[str],
        blocking: list[str],
        occupancy_limited_ids: list[str],
    ) -> None:
        role = self._role(item.category)
        if role == "unknown":
            warnings.append(
                f"{item.item_id} category {item.category!r} is not classified; "
                "treated as floor-standing (conservative MVP assumption)."
            )
            role = "floor_standing"

        missing = [
            name
            for name, value in (
                ("width_cm", item.width_cm),
                ("depth_cm", item.depth_cm),
                ("height_cm", item.height_cm),
            )
            if value is None
        ]
        if missing:
            warnings.append(
                f"{item.item_id} is missing {', '.join(missing)}; "
                "it was excluded from spatial claims (no invented dimensions)."
            )
            if role in {"floor_standing", "floor_covering", "wall", "ceiling"}:
                if item.item_id not in blocking:
                    blocking.append(item.item_id)
            return

        if item.height_cm is not None and item.height_cm > ceiling_cm:
            blocking.append(item.item_id)
            warnings.append(
                f"{item.item_id} height {item.height_cm} cm exceeds ceiling {ceiling_cm} cm."
            )

        if role in {"floor_standing", "floor_covering"}:
            if not _fits_in_rectangle(
                item.width_cm,  # type: ignore[arg-type]
                item.depth_cm,  # type: ignore[arg-type]
                length_cm,
                width_cm,
                allow_rotation=self._config.allow_plan_rotation,
            ):
                if item.item_id not in blocking:
                    blocking.append(item.item_id)
                warnings.append(
                    f"{item.item_id} plan size {item.width_cm}×{item.depth_cm} cm "
                    f"does not fit in the {length_cm}×{width_cm} cm room rectangle "
                    f"(rotation allowed={self._config.allow_plan_rotation})."
                )
            if role == "floor_standing":
                occupancy_limited_ids.append(item.item_id)
            else:
                warnings.append(
                    f"{item.item_id} is a floor covering; its area is not added to "
                    "furniture occupancy (MVP assumption: rugs can sit under furniture)."
                )

        if role == "wall":
            warnings.append(
                f"{item.item_id} is treated as wall-mounted; it is not added to floor occupancy."
            )
            if not _fits_in_rectangle(
                item.width_cm,  # type: ignore[arg-type]
                1,
                max(length_cm, width_cm),
                min(length_cm, width_cm),
                allow_rotation=True,
            ):
                if item.item_id not in blocking:
                    blocking.append(item.item_id)
                warnings.append(
                    f"{item.item_id} width {item.width_cm} cm does not fit on a room wall."
                )

        if role == "ceiling":
            warnings.append(
                f"{item.item_id} is treated as a ceiling fixture; it is not added to floor occupancy."
            )

        if role == "accessory":
            warnings.append(
                f"{item.item_id} is treated as an accessory (not an independent floor footprint)."
            )

        if quantity > 1 and role == "floor_standing":
            warnings.append(
                f"{item.item_id} quantity {quantity} multiplies floor footprint; "
                "items are not placed, so overlap is not modelled."
            )

    def _explain(
        self,
        *,
        fits: bool,
        occupancy: float | None,
        footprint: int,
        room_area: int,
        blocking: list[str],
    ) -> str:
        occ_txt = "n/a" if occupancy is None else f"{occupancy:.4f}"
        if fits:
            return (
                f"Selected floor-standing items fit the room rectangle and ceiling. "
                f"Furniture footprint {footprint} cm² / room {room_area} cm² "
                f"(occupancy_ratio={occ_txt}). Circulation was not measured."
            )
        return (
            f"Layout check failed. Blocking items: {', '.join(blocking) or 'none'}. "
            f"Furniture footprint {footprint} cm² / room {room_area} cm² "
            f"(occupancy_ratio={occ_txt}, cap={self._config.max_occupancy_ratio:.2f}). "
            "Circulation was not measured."
        )
