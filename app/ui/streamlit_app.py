"""Streamlit customer UI for the Living Room designer. Not a chat interface."""

from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for _mod in list(sys.modules):
    if _mod == "app.ui.service" or _mod.startswith("app.ui.service."):
        sys.modules.pop(_mod, None)

import streamlit as st

from app.ui.results import UiResultKind
from app.ui.service import (
    DIMENSION_UNITS,
    PREFERRED_STYLES,
    customer_limitations,
    customer_tradeoffs,
    design_from_form,
    format_inr,
    product_name,
    product_price,
)

COVER = ROOT / "assets" / "cover.png"
NAVY = "#1A3A7A"
AMBER = "#C47B17"
GREEN = "#2F6B4F"

_INTERNAL_TERMS = (
    "guardrail",
    "validation",
    "replan",
    "scope check",
    "scope_check",
    "max_replans",
    "sqlite",
    "langgraph",
    "llm",
    "chain-of-thought",
    "output_validation",
)

_CATEGORY_ICON = {
    "Sofa": "🛋️",
    "Coffee Table": "🪵",
    "TV Unit": "📺",
    "Rug": "🧶",
    "Floor Lamp": "💡",
    "Pendant Light": "💡",
    "Table Lamp": "💡",
    "Armchair": "🪑",
    "Side Table": "🪵",
    "Bookshelf": "📚",
    "Curtains": "🪟",
    "Wall Art": "🖼️",
    "Cushions": "⬜",
    "Console": "🪵",
    "Ottoman": "🪑",
    "Planter": "🌿",
    "Mirror": "🪞",
}


def _public(text: str) -> str | None:
    cleaned = (
        text.replace(" from SQLite", "")
        .replace("SQLite", "the catalogue")
        .replace("MVP", "this designer")
        .strip()
    )
    if not cleaned:
        return None
    lower = cleaned.lower()
    if any(term in lower for term in _INTERNAL_TERMS):
        return None
    if "revision limit" in lower or "re-plan" in lower:
        return None
    if "looks like a supported" in lower or "continue with catalogue-backed" in lower:
        return None
    return cleaned


def _public_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        cleaned = _public(line)
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


st.set_page_config(
    page_title="Interior Company · Living Room",
    page_icon=str(COVER) if COVER.is_file() else None,
    layout="wide",
)

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{
  font-family: Inter, "Segoe UI", sans-serif;
}}
.stApp {{
  background:
    linear-gradient(rgba(255,255,255,0.92), rgba(255,255,255,0.92)),
    repeating-linear-gradient(60deg, {NAVY}08 0 1px, transparent 1px 28px),
    repeating-linear-gradient(-60deg, {NAVY}08 0 1px, transparent 1px 28px);
  background-color: #f4f6fb;
}}
#MainMenu, footer, header {{ display: none; }}
.stApp > header {{ display: none !important; }}
.block-container {{
  padding-top: 0.35rem !important;
  max-width: 100% !important;
}}
div[data-testid="stImage"] {{
  margin-top: 0 !important;
  margin-bottom: 0.35rem !important;
}}
.hero-title {{
  color: {NAVY};
  text-align: center;
  letter-spacing: 0.04em;
  font-size: 1.55rem;
  font-weight: 700;
  margin: 0.35rem 0 0.35rem 0;
}}
.hero-tagline {{
  text-align: center;
  color: {NAVY};
  font-size: 1.02rem;
  font-weight: 500;
  margin: 0 0 1.1rem 0;
  line-height: 1.45;
}}
h1, h2, h3 {{
  color: {NAVY} !important;
  letter-spacing: 0.06em;
}}
div[data-testid="stForm"] {{
  background: #fff;
  border: 1px solid {NAVY}33;
  padding: 1rem 1.2rem 0.4rem 1.2rem;
  border-radius: 10px;
}}
.stFormSubmitButton button, .stButton button {{
  background: {NAVY} !important;
  color: #fff !important;
  border: 0 !important;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 600 !important;
}}
.stFormSubmitButton button:hover, .stButton button:hover {{
  background: #152e62 !important;
  color: #fff !important;
}}
div[data-testid="stMetric"] {{
  background: #fff;
  border: 1px solid {NAVY}33;
  border-top: 3px solid {NAVY};
  padding: 0.75rem 0.9rem;
  border-radius: 8px;
}}
.product-card {{
  background: #fff;
  border: 1px solid {NAVY}33;
  border-radius: 10px;
  padding: 1rem 1rem 0.85rem 1rem;
  min-height: 168px;
  margin-bottom: 0.75rem;
}}
.product-card .icon {{
  font-size: 1.6rem;
  line-height: 1;
}}
.product-card .sku {{
  color: {NAVY};
  letter-spacing: 0.08em;
  font-size: 0.72rem;
}}
.product-card .price {{
  color: {NAVY};
  font-weight: 700;
  font-size: 1.05rem;
}}
.product-card .role {{
  font-size: 0.8rem;
  color: #445;
  letter-spacing: 0.04em;
}}
.status-card {{
  border-radius: 10px;
  padding: 1.1rem 1.2rem;
  margin: 0.6rem 0 1rem 0;
}}
.status-ok {{ background: #e8f4ee; border: 1px solid {GREEN}55; }}
.status-warn {{ background: #fff6e8; border: 1px solid {AMBER}66; }}
.status-info {{ background: #eef2fa; border: 1px solid {NAVY}33; }}
.badge {{
  display: inline-block;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  margin-bottom: 0.45rem;
}}
.badge-ok {{ background: {GREEN}; color: #fff; }}
.badge-warn {{ background: {AMBER}; color: #fff; }}
.badge-info {{ background: {NAVY}; color: #fff; }}
</style>
""",
    unsafe_allow_html=True,
)

if COVER.is_file():
    st.image(str(COVER), use_container_width=True)
else:
    st.markdown(
        f'<div style="background:{NAVY};color:#fff;text-align:center;padding:1.6rem 1rem;'
        'letter-spacing:0.28em;">iNTERIOR COMPANY</div>',
        unsafe_allow_html=True,
    )
st.markdown(
    '<h1 class="hero-title">AI Interior Design Agent for Living Room</h1>'
    '<p class="hero-tagline">Design a living room that feels like you - '
    "Personalised to your space, style, and budget.</p>",
    unsafe_allow_html=True,
)

with st.form("living_room_brief"):
    dims = st.columns(4)
    length = dims[0].number_input("Room length", min_value=0.0, value=480.0, step=1.0)
    width = dims[1].number_input("Room width", min_value=0.0, value=360.0, step=1.0)
    ceiling = dims[2].number_input("Ceiling height", min_value=0.0, value=300.0, step=1.0)
    unit = dims[3].selectbox("Unit", DIMENSION_UNITS, index=0)

    budget_col, style_col = st.columns(2)
    budget = budget_col.number_input("Budget (INR)", min_value=0, value=250000, step=1000)
    style = style_col.selectbox("Preferred style", PREFERRED_STYLES, index=0)

    must_haves = st.text_area(
        "Must-haves",
        value="3-seater sofa, coffee table, TV unit, rug, lighting",
        height=90,
    )
    constraints = st.text_area("Constraints", value="", height=70)
    customer_notes = st.text_area("Customer notes", value="", height=70)

    submitted = st.form_submit_button("Design My Room")

if submitted:
    with st.spinner("Looking through the catalogue…"):
        st.session_state["ui_result"] = design_from_form(
            {
                "room_type": "Living Room",
                "length": length,
                "width": width,
                "ceiling": ceiling,
                "unit": unit,
                "budget": budget,
                "style_preference": style,
                "must_haves": must_haves,
                "constraints": constraints,
                "customer_note": customer_notes,
            }
        )

result = st.session_state.get("ui_result")
if result is None:
    st.stop()


def _status_card(kind: str, badge: str, title: str, lines: list[str]) -> None:
    css = {"ok": "status-ok", "warn": "status-warn", "info": "status-info"}[kind]
    badge_css = {"ok": "badge-ok", "warn": "badge-warn", "info": "badge-info"}[kind]
    body = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    st.markdown(
        f'<div class="status-card {css}">'
        f'<span class="badge {badge_css}">{html.escape(badge)}</span>'
        f"<h3 style='margin:0.2rem 0 0.5rem 0;color:{NAVY}'>{html.escape(title)}</h3>"
        f"{body}</div>",
        unsafe_allow_html=True,
    )


if result.kind is UiResultKind.NOT_SUPPORTED:
    extra = _public_lines(result.details)
    _status_card(
        "info",
        "Living rooms",
        "We design living rooms",
        [
            "We furnish living rooms from our catalogue — seating, tables, lighting, rugs, and storage.",
            "Share the room size, budget, and style (without construction work or delivery promises) and we can put a scheme together.",
            *extra[:3],
        ],
    )
    st.stop()

if result.kind is UiResultKind.INPUT_INVALID:
    extra = _public_lines(result.details) or [
        "Please add room size, budget, style, and what the room must include."
    ]
    _status_card("warn", "Brief", "A few details are still needed", extra)
    st.stop()

if result.kind is UiResultKind.NO_VALID_SOLUTION:
    extra = _public_lines(result.details)
    _status_card(
        "warn",
        "Room & budget",
        "We couldn't furnish this room within the current limits",
        [
            "Nothing in the catalogue currently fits this budget and room size together.",
            "Try a larger budget or double-check the length, width, and ceiling, then design again.",
            *extra[:3],
        ],
    )
    st.stop()

plan = result.plan
if not result.show_full_plan or plan is None:
    _status_card(
        "warn",
        "Room & budget",
        "We couldn't furnish this room within the current limits",
        ["Try a larger budget or double-check the room measurements."],
    )
    st.stop()

st.subheader("Design summary")
summary = _public(plan.summary) or "A living room scheme using catalogue pieces."
st.write(summary)
rationale = _public(plan.style_rationale)
if rationale:
    st.caption(rationale)

st.subheader("Recommended products")
products = list(plan.selected_products)
for row_start in range(0, len(products), 2):
    cols = st.columns(2)
    for col, product in zip(cols, products[row_start : row_start + 2]):
        category = product.catalog_item.category if product.catalog_item else ""
        icon = _CATEGORY_ICON.get(category, "🏠")
        reason = _public(product.why_selected) or "Chosen from the catalogue for this brief."
        with col:
            st.markdown(
                f'<div class="product-card">'
                f'<div class="icon">{icon}</div>'
                f'<div class="sku">{html.escape(product.item_id)}</div>'
                f"<strong>{html.escape(product_name(product))}</strong>"
                f'<div class="price">{html.escape(product_price(product))}'
                f" · qty {product.quantity}</div>"
                f'<div class="role">{html.escape(product.role_in_room)}</div>'
                f"<p>{html.escape(reason)}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

st.subheader("Budget")
b1, b2, b3 = st.columns(3)
b1.metric("Total", format_inr(plan.budget.subtotal))
b2.metric("Your budget", format_inr(plan.budget.budget))
b3.metric("Remaining", format_inr(plan.budget.remaining))

st.subheader("Fit")
fit_customer = _public(plan.fit_status_customer) or (
    "Selected pieces fit within the room length, width, and ceiling."
    if plan.fit.fits
    else "One or more pieces are larger than the room."
)
if plan.fit.fits:
    _status_card(
        "ok",
        "Fits",
        "These pieces fit the room",
        [fit_customer],
    )
else:
    _status_card(
        "warn",
        "Tight fit",
        "The current mix does not fit the room",
        [fit_customer],
    )

st.subheader("Must-haves")
covered = ", ".join(plan.must_have_coverage.covered) or "None yet"
missing = ", ".join(plan.must_have_coverage.missing)
if plan.must_have_coverage.missing:
    _status_card(
        "warn",
        "Partial",
        "Some requested pieces are still open",
        [f"Included: {covered}", f"Still to add: {missing}"],
    )
else:
    _status_card(
        "ok",
        "Covered",
        "Requested pieces are included",
        [f"Included: {covered}"],
    )

tradeoffs = _public_lines(customer_tradeoffs(plan))
st.subheader("Trade-offs")
if tradeoffs:
    _status_card("warn", "Choices", "What we traded off", tradeoffs)
else:
    _status_card("ok", "Choices", "No extra trade-offs", ["The scheme stays within budget and the room size."])

limitations = _public_lines(customer_limitations(plan))
st.subheader("Limitations")
if limitations:
    _status_card("info", "Please note", "What this scheme does not cover", limitations)
else:
    _status_card(
        "info",
        "Please note",
        "What this scheme does not cover",
        [
            "This checks that your furniture fits the room's overall size and height — "
            "it isn't a full floor plan or a guarantee of exact placement."
        ],
    )
