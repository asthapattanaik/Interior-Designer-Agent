# Decision log

These are the locked product and engineering choices for the Living Room MVP. Each entry records the decision, why it was taken, and what was given up. They match the running code in `app/`.

------------------------------------------------------------------------

## Decision 1 — Living Room only

**Decision:** The MVP designs Living Rooms only. Other room types are refused with a redirect.

**Reason:** Depth over breadth. One room type lets catalogue matching, budget, fit, and evaluation be proven end-to-end without a shallow multi-room product.

**Trade-off:** Bedroom, dining, study, kitchen, and kids briefs in the same SQLite file are out of scope. Customers who want those rooms get an honest limitation, not a half-built second designer.

------------------------------------------------------------------------

## Decision 2 — Structured form plus free text

**Decision:** Hard constraints (length, width, ceiling, unit, budget, style) are structured fields. Must-haves, constraints, and customer notes are free text. The UI is a form, not a chat-first product.

**Reason:** Dimensions and money must be normalisable without guessing. Natural language is still useful for preferences, named pieces, and nuance.

**Trade-off:** The experience is less conversational. Ambiguous free text cannot invent missing length, unit, or budget.

------------------------------------------------------------------------

## Decision 3 — SQLite instead of vector search

**Decision:** `interior_company_catalog.db` is the source of truth. Catalogue access is parameterized SQL (`app/db/catalog_repository.py`), not embeddings.

**Reason:** The catalogue is a small, structured table. SQL is auditable, deterministic, and enough for Living Room MVP search (category, style tags, stock, price).

**Trade-off:** Named designer pieces that are not in the table (Togo, Noguchi, Cassina LC3) cannot be “semantically retrieved.” The agent can only substitute from real rows or say they are missing.

------------------------------------------------------------------------

## Decision 4 — Deterministic budget

**Decision:** Totals are `SQLite price_inr × quantity` in `BudgetCalculator`. The model never supplies the subtotal. NULL prices cannot be sold.

**Reason:** Financial arithmetic should not depend on model reasoning. `₹180,000 ≤ ₹200,000` is code, not a prompt.

**Trade-off:** Items with `price_inr IS NULL` (e.g. CFT-004) are excluded even if the customer names them. There is no “call for price” checkout path in the MVP.

------------------------------------------------------------------------

## Decision 5 — Deterministic spatial feasibility

**Decision:** Fit is a rectangle / height / occupancy check in `LayoutChecker`, using catalogue centimetres and room centimetres. Circulation is not computed.

**Reason:** An LLM cannot guarantee physical fit. Transparent calculations can be tested and independently re-run after the agent.

**Trade-off:** The tool does not produce a furnished floor plan. Doors, windows, and aisles are not in the database, so they are not invented.

------------------------------------------------------------------------

## Decision 6 — Layered guardrails

**Decision:** Language/intent is classified before tools (heuristic, with an optional structured-LLM classifier). Facts are enforced by SQL, budget, layout, and `OutputValidator`. The UI maps failures to customer outcomes without internal jargon.

**Reason:** Models are good at spotting demolition or guarantee language. Models are bad at being the source of prices, stock, and geometry.

**Trade-off:** Heuristic scope can over-block (e.g. a Living Room brief that also asks about a load-bearing wall is refused entirely). That is preferred to unsafe structural advice.

------------------------------------------------------------------------

## Decision 7 — No PII middleware

**Decision:** The MVP does not collect identity, payment cards, or household PII. There is no auth, logging of personal data, or PII redaction pipeline.

**Reason:** The assignment is catalogue-grounded design, not a production tenancy. Extra PII machinery would not prove the core loop.

**Trade-off:** The app is not ready for real customer accounts. Free-text notes could still contain personal details; we do not store a customer database.

------------------------------------------------------------------------

## Decision 8 — No HITL in the core journey

**Decision:** After a budget/fit/validation failure the graph re-plans or returns an honest limitation. There is no designer-in-the-loop approval step.

**Reason:** The agent should recover or explain. A human queue would hide orchestration bugs and is not required to prove the MVP.

**Trade-off:** Substitutions (e.g. CFT-002 instead of NULL-priced CFT-004) are automatic. A human merchandiser might choose differently.

------------------------------------------------------------------------

## Decision 9 — Bounded re-planning

**Decision:** `MAX_REPLANS` (default 3, from `.env`) caps the loop. After the limit, invalid SKUs are dropped rather than returned as success.

**Reason:** Prevents infinite tool loops and unbounded spend. Forces an honest empty or partial plan when the catalogue cannot satisfy the brief.

**Trade-off:** A better mix might exist beyond three revisions. The MVP will not search forever.

------------------------------------------------------------------------

## Decision 10 — Streamlit

**Decision:** The customer UI is Streamlit (`app/ui/streamlit_app.py`).

**Reason:** Fast, form-based prototype suitable for an assignment. No extra frontend stack.

**Trade-off:** Layout and theming are constrained by Streamlit. This is not a production design-studio website.

------------------------------------------------------------------------

## Decision 11 — No image generation

**Decision:** No diffusion/render step. Recommendations are catalogue SKUs, prices, roles, and fit text.

**Reason:** The challenge is grounded recommendation, constraints, and reliability. Pretty pictures would not prove those capabilities and would invite hallucinated rooms.

**Trade-off:** The customer does not see a photoreal living room. Product cards use category icons, not generated photography.

------------------------------------------------------------------------

## Decision 12 — Spatial heuristics are assumptions

**Decision:** Occupancy cap defaults to **1.0** (summed floor footprints cannot exceed the room rectangle). 90° rotation in plan is allowed. Rugs are size-checked but excluded from occupancy. This is documented in `docs/layout_methodology.md` and is **not** a 55% interior-design rule or a 75 cm circulation standard.

**Reason:** The database has product and room boxes only. Any tighter “styling” occupancy would be invented. Assumptions must be labelled, configurable (`LayoutConfig`), and tested.

**Trade-off:** A plan can pass fit while still feeling cramped in real life. We state that limitation in the UI and in evaluation docs rather than pretending CAD-quality layout.
