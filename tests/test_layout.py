"""Tests for the deterministic layout/fit checker using real catalogue dimensions."""

import pytest

from app.db.catalog_repository import CatalogRepository
from app.models.catalog import CatalogItem
from app.tools.layout import (
    DEFAULT_MAX_OCCUPANCY_RATIO,
    LayoutChecker,
    LayoutConfig,
    UnknownCatalogItemError,
)


@pytest.fixture(scope="module")
def checker() -> LayoutChecker:
    return LayoutChecker(repository=CatalogRepository())


def test_normal_living_room_sofa_fits(checker: LayoutChecker):
    # BR-01 480×360; SOF-001 210×90×82
    result = checker.check(
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        selections=[("SOF-001", 1), ("CFT-001", 1), ("TVU-001", 1)],
    )
    assert result.fits is True
    assert result.occupancy_ratio is not None
    assert result.occupancy_ratio < 1
    assert result.blocking_items == []
    assert result.room_area_cm2 == 480 * 360
    assert "Circulation was not measured" in result.explanation


def test_sectional_does_not_fit_tiny_room(checker: LayoutChecker):
    # BR-09 240×210; SOF-004 300×170 — FACT: 300 exceeds both room axes
    result = checker.check(
        length_cm=240,
        width_cm=210,
        ceiling_cm=270,
        selections=[("SOF-004", 1)],
    )
    assert result.fits is False
    assert "SOF-004" in result.blocking_items
    assert result.occupancy_ratio is not None
    assert result.occupancy_ratio > 1


def test_curtain_taller_than_ceiling_fails(checker: LayoutChecker):
    # CUR-003 height_cm = 280; BR-09 ceiling_cm = 270
    result = checker.check(
        length_cm=240,
        width_cm=210,
        ceiling_cm=270,
        selections=[("CUR-003", 1)],
    )
    assert result.fits is False
    assert "CUR-003" in result.blocking_items


def test_rug_excluded_from_occupancy_but_checked_for_size(checker: LayoutChecker):
    sofa = checker.check(
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        selections=[("SOF-001", 1)],
    )
    with_rug = checker.check(
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        selections=[("SOF-001", 1), ("RUG-001", 1)],
    )
    assert sofa.fits and with_rug.fits
    assert sofa.furniture_footprint_cm2 == with_rug.furniture_footprint_cm2
    assert any("floor covering" in w for w in with_rug.warnings)


def test_unknown_item_id_rejected(checker: LayoutChecker):
    with pytest.raises(UnknownCatalogItemError):
        checker.check(
            length_cm=480,
            width_cm=360,
            ceiling_cm=300,
            selections=[("NOT-A-REAL-SKU", 1)],
        )


def test_occupancy_cap_is_configurable():
    repo = CatalogRepository()
    strict = LayoutChecker(
        repository=repo,
        config=LayoutConfig(max_occupancy_ratio=0.05),
    )
    result = strict.check(
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        selections=[("SOF-001", 1)],
    )
    assert DEFAULT_MAX_OCCUPANCY_RATIO == 1.0
    assert result.fits is False
    assert result.occupancy_ratio is not None
    assert result.occupancy_ratio > 0.05
    assert "SOF-001" in result.blocking_items


def test_missing_dimensions_are_not_invented():
    class StubRepo:
        def get_item(self, item_id: str) -> CatalogItem | None:
            return CatalogItem(
                item_id=item_id,
                category="Sofa",
                name="Incomplete sofa",
                width_cm=None,
                depth_cm=None,
                height_cm=None,
            )

    checker = LayoutChecker(repository=StubRepo())  # type: ignore[arg-type]
    result = checker.check(
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        selections=[("SOF-X", 1)],
    )
    assert result.fits is False
    assert "SOF-X" in result.blocking_items
    assert any("missing" in w for w in result.warnings)
    assert result.furniture_footprint_cm2 == 0


def test_no_circulation_field_on_result(checker: LayoutChecker):
    result = checker.check(
        length_cm=480,
        width_cm=360,
        ceiling_cm=300,
        selections=[("SOF-001", 1)],
    )
    assert not hasattr(result, "circulation_cm")
    dumped = result.model_dump()
    assert "circulation" not in dumped
