"""Load evals/golden_set.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

DEFAULT_GOLDEN_PATH = PROJECT_ROOT / "evals" / "golden_set.json"


def load_golden_set(path: Path | None = None) -> dict[str, Any]:
    golden_path = path or DEFAULT_GOLDEN_PATH
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if not isinstance(cases, list) or len(cases) < 20:
        raise ValueError(f"Golden set at {golden_path} must contain ~25 cases")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Golden set case ids must be unique")
    return payload
