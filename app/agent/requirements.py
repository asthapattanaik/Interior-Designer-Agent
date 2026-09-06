"""Requirement understanding schemas and offline phrase→category baseline helpers.

Runtime `understand_requirements` uses the LLM schema below. The keyword helpers
remain for unit-test baselines only and are not used by the LangGraph agent.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

CATALOG_CATEGORIES = (
    "Armchair",
    "Bean Bag",
    "Bookshelf",
    "Coffee Table",
    "Console",
    "Curtains",
    "Cushions",
    "Floor Lamp",
    "Mirror",
    "Ottoman",
    "Pendant Light",
    "Planter",
    "Rug",
    "Side Table",
    "Sofa",
    "TV Unit",
    "Table Lamp",
    "Wall Art",
)

REQUIREMENTS_SYSTEM_PROMPT = """You extract Living Room furniture requirements from a customer brief.

Return structured fields only:
- needed_categories: catalogue categories to search (must be chosen from the allowed list)
- must_haves: one entry per distinct requested item; each has:
  - phrase: a short, clean customer-facing label (2-4 words) using generic furniture terms
  - covering_categories: catalogue categories that would cover that item
- preferences: short preference notes from style/notes (may be empty)
- constraints: short constraint notes (may be empty)
- prefer_large_sofa: true if they want a large/sectional/L-sofa
- prefer_higher_spend: true if they want premium/high-end/statement pieces

Allowed categories:
""" + ", ".join(CATALOG_CATEGORIES) + """

Rules:
- Use only allowed category names exactly as listed.
- Map lighting requests to Floor Lamp, Table Lamp, and/or Pendant Light as appropriate.
- Do not invent product SKUs, prices, or stock claims.
- If must-haves are empty, infer a minimal sensible living-room set from the note/style.

Must-have label rules (critical for UI display):
- Read the full free-text must-haves, constraints, and notes to understand intent.
- Do NOT copy verbatim spans, brand names, TV/character references, or long descriptive clauses into phrase.
- Normalize each item into a short generic label such as "3-seater sofa", "coffee table", "table lamp", "floor lamp", "decorative lighting", "tv unit", "area rug".
- Examples: "lamp like Monica Geller lighting" → "table lamp" or "decorative lighting"; "comfy big couch for movie nights" → "sofa"; "that round marble coffee table vibe" → "coffee table".
"""


class MustHaveNeed(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phrase: str = Field(
        ...,
        min_length=1,
        max_length=40,
        description=(
            "Short clean customer-facing must-have label (2-4 words, generic furniture "
            "terms). Never a verbatim echo of the customer's free text."
        ),
    )
    covering_categories: list[str] = Field(default_factory=list)


class UnderstoodRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    needed_categories: list[str] = Field(default_factory=list)
    must_haves: list[MustHaveNeed] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    prefer_large_sofa: bool = False
    prefer_higher_spend: bool = False


# --- Offline baseline helpers (tests only; not used by the agent graph) ---

_PHRASE_CATEGORIES: list[tuple[str, list[str]]] = [
    ("sectional", ["Sofa"]),
    ("3-seater", ["Sofa"]),
    ("2-seater", ["Sofa"]),
    ("loveseat", ["Sofa"]),
    ("sofa", ["Sofa"]),
    ("seating for", ["Sofa"]),
    ("reading corner", ["Armchair", "Floor Lamp"]),
    ("coffee table", ["Coffee Table"]),
    ("tv unit", ["TV Unit"]),
    ("media unit", ["TV Unit"]),
    ("no tv", []),
    ("rug", ["Rug"]),
    ("layered lighting", ["Floor Lamp", "Table Lamp", "Pendant Light"]),
    ("lighting", ["Floor Lamp", "Table Lamp", "Pendant Light"]),
    ("lamp", ["Floor Lamp", "Table Lamp"]),
    ("pendant", ["Pendant Light"]),
    ("armchair", ["Armchair"]),
    ("accent seating", ["Armchair", "Ottoman"]),
    ("bookshelf", ["Bookshelf"]),
    ("bookcase", ["Bookshelf"]),
    ("console", ["Console"]),
    ("plant", ["Planter"]),
    ("art", ["Wall Art"]),
    ("curtain", ["Curtains"]),
    ("ottoman", ["Ottoman"]),
]


def parse_must_have_phrases(must_haves: str) -> list[str]:
    return [part.strip() for part in must_haves.split(",") if part.strip()]


def categories_for_phrase(phrase: str) -> list[str]:
    lowered = phrase.lower()
    for fragment, categories in _PHRASE_CATEGORIES:
        if fragment in lowered:
            return list(categories)
    return []


def needed_categories(must_haves: str) -> list[str]:
    found: list[str] = []
    for phrase in parse_must_have_phrases(must_haves):
        for category in categories_for_phrase(phrase):
            if category not in found:
                found.append(category)
    return found


def prefer_large_sofa(must_haves: str) -> bool:
    text = must_haves.lower()
    return any(
        token in text for token in ("sectional", "large l", "l-sectional", "l-sofa")
    )
