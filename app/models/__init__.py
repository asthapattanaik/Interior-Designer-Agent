"""Domain models for briefs, catalogue records, and design output."""

from app.models.brief import RoomBrief
from app.models.catalog import CatalogItem
from app.models.output import (
    BudgetResult,
    DesignPlan,
    FitResult,
    MustHaveCoverage,
    SelectedProduct,
)

__all__ = [
    "BudgetResult",
    "CatalogItem",
    "DesignPlan",
    "FitResult",
    "MustHaveCoverage",
    "RoomBrief",
    "SelectedProduct",
]
