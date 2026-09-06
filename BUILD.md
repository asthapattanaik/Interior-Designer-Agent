# Interior Company - AI Interior Design Agent for Living room

> **Purpose:** This README is the master implementation specification for the AI Interior Designer for Living Room

This file has two parts:

1. **Application guide** (below) - how an evaluator installs, configures, runs, and demos the finished MVP.
2. **Cursor execution playbook** (from [§ 1. Goal](#1-goal) through STEP 20) - the original sequential build spec. **That playbook is kept intact.**

Further write-ups: [docs/data_profile.md](docs/data_profile.md), [docs/layout_methodology.md](docs/layout_methodology.md), [docs/decision_log.md](docs/decision_log.md), [docs/evaluation_summary.md](docs/evaluation_summary.md).

---



# Application guide



## Product overview

Living Room furniture recommendations from Interior Company’s supplied SQLite catalogue. The customer enters room size, budget, style, must-haves, constraints, and notes. The system searches **real SKUs**, totals prices in code, checks whether pieces fit the room rectangle, re-plans when budget or fit fail, and refuses unsupported requests (other rooms, demolition, delivery/price guarantees).

It does **not** invent products, NULL-price sales, out-of-stock finals, or load-bearing advice. LLM quality is evaluated separately from those facts.

## Architecture

```text
                         CUSTOMER
                            |
                            v
                  +---------------------+
                  |   Streamlit UI      |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | BEFORE-AGENT        |
                  | VALIDATION /        |
                  | NORMALIZATION       |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | Model-based scope   |
                  | / intent guardrail  |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  |   LangGraph Agent   |
                  | search / select /   |
                  | budget / layout /   |
                  | re-plan             |
                  +----+----+----+------+
                       |    |    |
             Catalog Search | Layout / Fit
                       Budget Calculator
                             |
                             v
                  +---------------------+
                  | AFTER-AGENT         |
                  | DETERMINISTIC       |
                  | VALIDATION          |
                  +----------+----------+
                       PASS / FAIL → customer or re-plan
```

**Tech stack:** Python 3.11, LangChain / LangGraph, langchain-openai, Pydantic, python-dotenv, Streamlit, pytest. Catalogue: `interior_company_catalog.db` (read-only).

## Setup (build / install)

From the repository root:

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux use `source .venv/bin/activate`.

Do not commit `.env`. Copy the example file and add the key **locally**:

```text
copy .env.example .env
```

Then open `.env` and set `OPENAI_API_KEY` to your key. The application never writes this file for you.

## Environment variables


| Variable          | Required                                          | Default                         | Role                                    |
| ----------------- | ------------------------------------------------- | ------------------------------- | --------------------------------------- |
| `OPENAI_API_KEY`  | Yes (for LLM judge and optional structured scope) | —                               | Set only in local `.env`. Never commit. |
| `OPENAI_MODEL`    | No                                                | `gpt-5.6`                       | Chat model name                         |
| `CATALOG_DB_PATH` | No                                                | `./interior_company_catalog.db` | Path to the supplied catalogue          |
| `MAX_REPLANS`     | No                                                | `3`                             | Cap on the LangGraph re-plan loop       |




## Database

Read-only SQLite: tables `catalog` (72 products) and `room_briefs` (14 briefs, 8 Living Room). Profile: [docs/data_profile.md](docs/data_profile.md). 

## How to run tests

```text
python -m pytest -q
```



## How to run Streamlit

```text
python -m streamlit run app/ui/streamlit_app.py
```

Open the local URL (typically [http://localhost:8501](http://localhost:8501)). Fill the Living Room form and click **Design My Room**.

## How to run evaluation

```text
python -m app.evaluation.runner
```

Loads `evals/golden_set.json` (~25 cases), runs the agent, scores deterministic gates, calls the LLM judge, writes `evals/results/latest.json` and `latest_summary.txt`.

Deterministic-only (no judge API calls): not a separate CLI flag; omit the key and the runner records `Judge unavailable` while still scoring facts.

Ship-gate analysis: [docs/evaluation_summary.md](docs/evaluation_summary.md).

## Guardrail architecture

1. **Before agent:** unit/budget normalisation; missing units are not guessed; non–Living Room `room_type` is rejected.
2. **Scope / intent:** heuristic (and optional LLM) classifier — other rooms, wall demolition / load-bearing, delivery or locked-price guarantees. Tools do not run when the request is blocked.
3. **Deterministic tools:** catalogue existence, Living Room tagging, `in_stock`, non-NULL price, SQLite totals, layout box-fit.
4. **After agent:** `OutputValidator` recomputes budget and fit. Invalid SKUs are never returned as a successful plan.
5. **UI:** `SUCCESS` vs unsupported vs no feasible mix — no internal terms such as “guardrail” or “replan” on the customer page.



## Re-planning behaviour

On budget, fit, or validation failure the graph records the reason, excludes blocking or expensive SKUs, searches again, and re-runs budget → layout → validation, up to `MAX_REPLANS`. If nothing valid remains, the customer gets an honest limitation (empty or reduced mix), not a fabricated full room.

## Evaluation metrics

Hard gates (all 100% on the last full run): catalogue validity, stock (where known), budget, guardrails, tool-use.

Quality gates: fit ≥ 95% where supported; must-have coverage ≥ 90% on the golden-set rules; **average LLM judge ≥ 4.0 / 5** (last run **3.30** — gate **not** met; see evaluation summary).

## Known limitations

- Living Room only.
- Fit is rectangle / height / occupancy ≤ 1.0, not circulation or CAD.
- Occupancy 1.0 and 90° rotation are **MVP assumptions**, not Interior Company or building-code facts.
- NULL prices and out-of-stock rows are not sold.
- Named pieces missing from SQLite cannot be sourced (Togo, Noguchi, Cassina LC3).
- BR-06 ₹20,000 is below the cheapest sofa (SOF-008 ₹36,000).
- No image generation, auth, payments, or PII store.
- Judge scores are qualitative and do not override SQLite.



## Demo scenarios

**Demo 1 — Normal design:** BR-01-like brief (480×360 cm, ₹250,000, Scandinavian, sofa / coffee table / TV unit / rug / lighting). Show catalogue SKUs, SQLite totals, fit pass.

**Demo 2 — Budget:** ₹20,000 full living room (BR-06). Show no over-budget plan; uncovered sofa; honest trade-off.

**Demo 3 — Guardrail:** Bedroom `room_type`, or notes asking to knock down a load-bearing wall, or “guarantee delivery and lock the price.” Show refusal, no catalogue tools, no fake products.

**Demo 4 — Fit:** 240×210 cm room asking for a large L-sectional (BR-09 / SOF-004 300×170). Show the oversized piece is not forced in.

---



# 1. Goal

Build a focused AI-first interior design MVP for **Living Rooms only**.

The customer provides:

- room dimensions
- ceiling height
- budget
- preferred style
- must-haves
- constraints
- customer notes/preferences

The system should:

1. understand the customer's brief
2. search the supplied SQLite catalogue
3. select real catalogue products
4. calculate budget deterministically
5. check physical feasibility using available data and explicitly
  documented MVP assumptions
6. re-plan when constraints fail
7. independently validate the final plan
8. explain recommendations and trade-offs
9. safely handle unsupported requests
10. never fabricate products, prices, stock, dimensions or guarantees

The core engineering principle is:

> **LLM = reasoning  SQLite = source of truth  Deterministic tools =
> facts and constraints  Guardrails = layered protection  LangGraph
> = orchestration/re-planning  Evaluation = proof**

---



# 2. Product Requirements vs MVP Assumptions



## 2.1 Requirements:

This requires an AI-first interior design experience that:

- focuses deeply on one room type
- uses the supplied catalogue
- creates useful interior recommendations
- accounts for customer requirements and constraints
- considers practical feasibility
- uses AI/agentic capabilities
- includes appropriate guardrails
- can be evaluated before scaling



## 2.2 Locked MVP decisions

These are deliberate product decisions for our implementation:

- **Living Room only**
- guided form rather than chat-first UX
- structured dimensions, budget and style fields
- three free-text fields:
  - must-haves
  - constraints
  - customer notes/preferences
- SQLite as catalogue source of truth
- OpenAI through LangChain for model reasoning
- LangGraph for orchestration
- deterministic tools for catalogue, pricing, budget and spatial
checks
- independent post-agent validation
- bounded re-planning
- Streamlit for the prototype UI



## 2.3 Assumptions that must NOT be treated as requirements

The following must be determined or validated after inspecting the
database:

- furniture occupancy threshold
- minimum circulation distance
- interpretation of product dimensions
- whether certain categories can coexist
- whether stock represents current availability
- how NULL price should be treated
- whether all products have sufficient dimensions for spatial
validation
- whether any existing room-layout information is available

If we introduce a heuristic, it must be:

1. explicitly labelled as an MVP assumption
2. justified
3. configurable where appropriate
4. tested
5. documented as a limitation where relevant

Do not present an MVP heuristic as an Interior Company rule, building
code, architectural standard, or fact supplied by the assignment.

---



# 3. Locked Product Decisions



## 3.1 Room scope

**Living Room only.**

The MVP does not build separate experiences for bedrooms, dining rooms,
kitchens, etc.

If a customer requests another room, the system should explain that the
MVP currently supports Living Rooms.

## 3.2 Customer input

Use a guided form.

### Structured fields

- Room length
- Room width
- Ceiling height
- Unit
- Budget
- Preferred style



### Free-text fields

1. Must-haves
2. Constraints
3. Customer notes/preferences

This deliberately combines:

> **structured data for hard constraints + natural language for
> preferences and nuance**



## 3.3 Catalogue source of truth

The supplied:

```text
interior_company_catalog.db
```

is the product source of truth.

Never invent:

- product IDs
- product names
- prices
- stock
- dimensions
- lead times
- catalogue availability



## 3.4 LLM

Use OpenAI through LangChain.

The model must be configurable through `.env`.

Default:

```text
OPENAI_MODEL=gpt-5.6
```

Use:

```text
temperature = 0
```

only if the selected model/API supports that parameter. Do not force
unsupported parameters.

Do not hard-code the model into business logic.

---



# 4. AI vs Deterministic Responsibilities



## LLM responsibilities

Use the LLM for:

- understanding customer language
- extracting preferences
- interpreting must-haves
- interpreting natural-language constraints
- identifying relevant product categories
- ranking candidate products
- style reasoning
- explaining recommendations
- deciding when another search is useful
- deciding when to re-plan
- generating the final customer-facing explanation



## Deterministic responsibilities

Use code for:

- catalogue existence
- stock status
- actual price
- product dimensions
- budget arithmetic
- room dimensions
- fit/spatial calculations
- output validation
- hard business rules

Do not ask an LLM to decide whether:

```text
₹180,000 <= ₹200,000
```

when deterministic code can calculate it exactly.

---



# 5. Target Architecture

```text
                         CUSTOMER
                            |
                            v
                  +---------------------+
                  |   Streamlit UI      |
                  |                     |
                  | dimensions          |
                  | budget              |
                  | style               |
                  | must-haves           |
                  | constraints         |
                  | customer notes      |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | BEFORE-AGENT        |
                  | VALIDATION /        |
                  | NORMALIZATION       |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  | Model-based scope   |
                  | / intent guardrail  |
                  +----------+----------+
                             |
                             v
                  +---------------------+
                  |   LangGraph Agent   |
                  |                     |
                  | understand          |
                  | search              |
                  | select              |
                  | validate            |
                  | re-plan             |
                  +----+----+----+------+
                       |    |    |
             +---------+    |    +----------+
             v              v               v
      +------------+ +------------+ +--------------+
      | Catalog    | | Budget     | | Layout / Fit |
      | Search     | | Calculator | | Checker      |
      +------+-----+ +------+-----+ +------+-------+
             |              |               |
             +--------------+---------------+
                            |
                            v
                  +---------------------+
                  | AFTER-AGENT         |
                  | DETERMINISTIC       |
                  | VALIDATION          |
                  +----------+----------+
                             |
                       PASS / FAIL
                         /       \
                       PASS       FAIL
                        |           |
                        v           v
                    CUSTOMER     RE-PLAN
                                  |
                                  +----> Agent
```

---



# 6. Guardrail Architecture

We use **layered guardrails**.

## Layer 1 --- Input guardrails

Combination of deterministic validation and model-based interpretation.

Responsibilities:

- required-field validation
- unit normalization
- budget normalization
- Living Room scope
- ambiguous/unsupported intent detection



## Layer 2 --- Before-agent validation

Use a LangChain before-agent hook/middleware if compatible with the
installed version.

Otherwise implement an explicit LangGraph preprocessing node.

Responsibilities:

- validate input
- normalize input
- construct a clean brief
- reject impossible or missing critical inputs



## Layer 3 --- Model/system guardrails

The agent instructions should enforce:

- never fabricate catalogue facts
- use tools for factual information
- respect hard constraints
- do not claim unverified fit
- do not claim unsupported guarantees
- re-plan when deterministic validation fails



## Layer 4 --- Tool guardrails

Tools deterministically enforce:

- catalogue existence
- stock
- price
- budget
- dimensions
- spatial feasibility



## Layer 5 --- After-agent validation

Independently verify the generated plan.

If invalid:

```text
invalid plan
    |
    v
structured validation error
    |
    v
re-plan
    |
    v
agent
```



## Layer 6 --- Evaluation

Measure:

- catalogue validity
- stock compliance
- budget compliance
- fit correctness
- must-have coverage
- tool-use compliance
- guardrail compliance
- qualitative response quality

---



# 7. Guardrails We Are NOT Adding to the MVP



## PII Middleware

Not required because the MVP does not need sensitive personal
information.

This should be documented as a conscious scope decision.

## HITL

Not part of the core customer journey.

The MVP should attempt:

```text
solve → validate → re-plan → validate
```

If no valid solution exists, it should honestly communicate the
limitation.

HITL can be mentioned as a future production capability for exceptional
cases.

---



# 8. Spatial Reasoning Guardrail

The LLM must **not invent physical dimensions or fit claims**.

If a product's dimensions are unavailable:

- do not claim that it physically fits
- do not invent a dimension
- either exclude it from spatial validation or clearly state the
limitation

Any spatial heuristic introduced by the implementation must be treated
as an explicit MVP assumption.

For example, if after database inspection we decide to use:

```text
maximum furniture occupancy
minimum circulation distance
```

the exact values must be justified and documented.

Do **not** pre-assume:

```text
55%
75 cm
```

before inspecting the database.

---



# 9. Expected Project Structure

```text
interior-design-agent/
│
├── README.md
├── interior_company_catalog.db
├── requirements.txt
├── .env.example
├── .gitignore
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── brief.py
│   │   ├── catalog.py
│   │   └── output.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── catalog_repository.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── catalog_search.py
│   │   ├── budget.py
│   │   └── layout.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── prompts.py
│   │   ├── graph.py
│   │   ├── hooks.py
│   │   └── guardrails.py
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   └── output_validator.py
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── cases.py
│   │   ├── deterministic.py
│   │   ├── judge.py
│   │   └── runner.py
│   │
│   └── ui/
│       └── streamlit_app.py
│
├── tests/
│   ├── test_catalog.py
│   ├── test_budget.py
│   ├── test_layout.py
│   ├── test_guardrails.py
│   └── test_agent.py
│
├── evals/
│   ├── golden_set.json
│   └── results/
│
└── docs/
    ├── data_profile.md
    ├── decision_log.md
    └── evaluation_summary.md
```

Cursor may add small supporting files where necessary, but should avoid
unnecessary architecture.

---



# STEP 1 --- Inspect the Supplied SQLite Database



## OBJECTIVE

Understand the actual database before writing the agent.

The implementation must be based on the real schema, not assumptions.

## WHAT CURSOR MUST BUILD

Create a data-profile script/documentation that:

1. lists all tables
2. prints schemas
3. counts rows
4. shows all Living Room briefs
5. shows Living Room catalogue products
6. identifies NULL prices
7. identifies out-of-stock products
8. identifies available Living Room categories
9. identifies style tags
10. identifies product dimensions
11. identifies room dimensions if present
12. identifies quantities if present
13. identifies lead-time information if present
14. identifies spatial/layout information if present
15. identifies relevant data-quality issues

Known Living Room brief IDs to investigate:

```text
BR-01
BR-02
BR-05
BR-06
BR-07
BR-08
BR-09
BR-14
```

Do not assume these IDs are the only relevant records; inspect the
database.

## CURSOR COMMAND

```text
Read README.md completely.

Execute STEP 1 only.

Inspect interior_company_catalog.db thoroughly without modifying the database.

Create a data-profile script and docs/data_profile.md.

The profile must:
1. list all tables
2. show schemas
3. show row counts
4. show all Living Room room briefs
5. show all Living Room catalogue products
6. identify NULL prices
7. identify out-of-stock products
8. identify Living Room categories
9. identify style tags
10. identify product dimensions
11. identify room dimensions if present
12. identify quantities if present
13. identify lead-time information if present
14. identify any spatial/layout-related data
15. identify data-quality issues relevant to our agent

Do not build the AI agent, UI, LangGraph or tools yet.

Do not modify the database.

At the end:
- show files created/changed
- run the profile
- report important findings
- explicitly identify what information is available for spatial feasibility
- stop.
```



## ACCEPTANCE CRITERIA

- [ ] Database is readable
- [ ] Schema is documented
- [ ] Living Room briefs are identified
- [ ] Catalogue edge cases are identified
- [ ] Product dimensions are identified
- [ ] Any room/layout data is identified
- [ ] No database modifications
- [ ] `docs/data_profile.md` exists
- [ ] Cursor stops after Step 1

---



# STEP 2 --- Project Setup + LLM Configuration



## OBJECTIVE

Create the Python project foundation and safe LLM configuration.

## WHAT CURSOR MUST BUILD

Create:

```text
requirements.txt
.env.example
.gitignore
app/
tests/
evals/
docs/
```

Recommended dependencies:

```text
langchain
langgraph
langchain-openai
pydantic
python-dotenv
streamlit
pytest
```

Pin compatible versions after checking the environment.

Create configuration code.

`.env.example` should contain:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
CATALOG_DB_PATH=./interior_company_catalog.db
MAX_REPLANS=3
```

Do **not** add spatial thresholds yet.

## DEVELOPER ACTION

After this step, manually create:

```text
.env
```

and add the real OpenAI API key.

Never paste the key into Cursor chat.

## CURSOR COMMAND

```text
Read README.md completely.

Execute STEP 2 only.

Create the project foundation, requirements.txt, .env.example, .gitignore and configuration module.

Use OpenAI through LangChain.

Default model:
OPENAI_MODEL=gpt-5.6

Create .env.example with:

OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6
CATALOG_DB_PATH=./interior_company_catalog.db
MAX_REPLANS=3

Do not add spatial/layout thresholds yet. Those must be determined after database inspection.

Do NOT create a real .env.
Do NOT insert an API key.
Do NOT put secrets in source code.

Create configuration loading with validation for required settings.

Do not build the agent, tools or UI yet.

Write minimal configuration tests.

At the end:
- show files changed
- show dependency list
- run tests
- stop.
```



## ACCEPTANCE CRITERIA

- [ ] Project structure exists
- [ ] Dependencies install successfully
- [ ] `.env.example` exists
- [ ] `.env` is ignored by Git
- [ ] No secret is committed
- [ ] Configuration module works
- [ ] Tests pass
- [ ] Developer has manually added API key

---



# STEP 3 --- Pydantic Domain Models



## OBJECTIVE

Define explicit contracts between UI, agent, tools and evaluation.

## WHAT CURSOR MUST BUILD



### RoomBrief

Fields:

```text
room_type
length_cm
width_cm
ceiling_cm
budget_inr
style_preference
must_haves
constraints
customer_note
```



### CatalogItem

Represent the relevant actual database fields.

### SelectedProduct

Include:

```text
item_id
quantity
role_in_room
why_selected
```

Factual product information must ultimately come from the catalogue.

### DesignPlan

Include:

```text
summary
style_rationale
selected_products
budget
fit
must_have_coverage
tradeoffs
limitations
```

Use strict Pydantic validation.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 3 only.

Create the Pydantic domain models described in STEP 3.

Models must be strict and suitable for:
- UI input
- agent state
- catalogue records
- selected products
- final DesignPlan output

Do not build database access, tools, LangGraph or UI yet.

Write unit tests for:
- valid RoomBrief
- invalid dimensions
- invalid budget
- invalid room type
- valid DesignPlan
- invalid DesignPlan

At the end run pytest and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Models exist
- [ ] Validation works
- [ ] Tests cover valid/invalid cases
- [ ] No agent implementation
- [ ] Tests pass

---



# STEP 4 --- SQLite Catalogue Repository



## OBJECTIVE

Create a clean read-only data-access layer around the supplied database.

## WHAT CURSOR MUST BUILD

Implement methods conceptually equivalent to:

```text
get_item(item_id)
search_items(...)
get_living_room_items(...)
```

The repository must:

- use parameterized SQL
- never modify the database
- return typed records
- handle NULL fields safely
- make no LLM calls

Do not add a vector database.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 4 only.

Implement app/db/catalog_repository.py around the supplied SQLite database.

Requirements:
- database is read-only from application code
- use parameterized SQL
- expose get_item(item_id)
- expose search_items(...)
- expose get_living_room_items(...)
- return typed CatalogItem records
- handle NULL prices safely
- never call an LLM
- do not introduce a vector database

Use the actual schema discovered in STEP 1 rather than assuming column names.

Write tests using the supplied database where appropriate.

At the end:
- run pytest
- demonstrate a few repository queries
- stop.
```



## ACCEPTANCE CRITERIA

- [ ] SQLite repository works
- [ ] Actual database is queried
- [ ] No fabricated records
- [ ] NULL fields handled
- [ ] Tests pass

---



# STEP 5 --- Deterministic Catalogue Search Tool



## OBJECTIVE

Give the agent a reliable tool for discovering real products.

## WHAT CURSOR MUST BUILD

Support filters where the database allows them:

- category
- style
- maximum price
- stock
- room applicability

The tool must return actual database records.

Never generate products.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 5 only.

Implement the deterministic Catalogue Search tool.

Use only fields that actually exist in the supplied database.

Requirements:
- query SQLite
- only return actual catalogue products
- only return Living Room-applicable products
- support category filtering where available
- support style filtering where available
- support maximum price where price is available
- support stock filtering where stock is available
- safely handle NULL price
- return structured product records
- never fabricate products

Add unit tests for:
- exact product retrieval
- category filtering where supported
- style filtering where supported
- stock filtering where supported
- NULL-price handling
- empty result

Do not build the agent yet.

Run pytest and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Tool works
- [ ] Product IDs come only from DB
- [ ] Supported filters work
- [ ] NULL-price handling works
- [ ] Tests pass

---



# STEP 6 --- Deterministic Budget Tool



## OBJECTIVE

Make budget calculation completely independent of LLM reasoning.

## WHAT CURSOR MUST BUILD

Input:

```text
selected item IDs
quantities
budget
```

Output:

```text
subtotal
budget
remaining
over_budget
```

Actual prices must come from SQLite.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 6 only.

Implement the deterministic Budget Calculator tool.

Requirements:
- retrieve actual prices from SQLite
- accept item IDs and quantities
- reject invalid item IDs
- reject NULL price for purchasable selections
- calculate totals deterministically
- return budget, subtotal, remaining and over_budget
- never trust an LLM-provided total

Add tests for:
1. under budget
2. exactly on budget
3. over budget
4. NULL price
5. invalid item ID
6. multiple quantities

Do not build the agent yet.

Run pytest and stop.
```



## ACCEPTANCE CRITERIA

- [ ] All arithmetic deterministic
- [ ] Actual DB prices used
- [ ] Invalid IDs rejected
- [ ] NULL prices handled
- [ ] Tests pass

---



# STEP 7 --- Deterministic Layout / Fit Tool



## OBJECTIVE

Create a transparent spatial-feasibility check using the information
actually available.

Do not build CAD or pretend that a simple heuristic is an architectural
guarantee.

## FIRST: USE STEP 1 FINDINGS

Cursor must inspect `docs/data_profile.md` before implementation.

Determine:

- what product dimensions exist
- what room dimensions exist
- whether product categories have relevant dimensions
- whether any layout information exists
- whether a spatial calculation is realistically possible



## POSSIBLE MVP APPROACH

Depending on the database, the tool may calculate:

```text
room_area
furniture_footprint
occupancy_ratio
```

and/or other dimension-based checks.

If circulation is measurable from the available information, it may be
included.

If not, do not fabricate a circulation measurement.

## IMPORTANT

Do not assume:

```text
55% occupancy
75 cm circulation
```

unless the implementation determines that these are appropriate MVP
assumptions.

If such thresholds are introduced, they must be:

- documented
- configurable
- justified
- tested



## CURSOR COMMAND

```text
Read README.md and docs/data_profile.md.

Execute STEP 7 only.

Implement the deterministic Layout/Fit Checker based on the actual spatial data available in the database.

Do not assume fixed occupancy or circulation thresholds before analysing the database.

First determine what spatial information is available.

Then implement the simplest defensible MVP feasibility methodology.

Any heuristic must:
1. be explicitly documented as an MVP assumption
2. be configurable where appropriate
3. be tested
4. not be described as an architectural standard or Interior Company rule

Return structured output containing appropriate fields such as:
- fits
- occupancy_ratio, if applicable
- blocking_items
- warnings
- explanation

Do not build CAD, 3D simulation or computer vision.

Add tests for representative normal and failure cases supported by the actual data.

At the end:
- explain the chosen spatial methodology
- list every assumption
- run pytest
- stop.
```



## ACCEPTANCE CRITERIA

- [ ] Spatial data from the DB has been considered
- [ ] Methodology is documented
- [ ] No invented dimensions
- [ ] Any heuristics are explicitly labelled as assumptions
- [ ] Heuristics are configurable where appropriate
- [ ] Failure cases are tested
- [ ] Layout calculation is deterministic
- [ ] Tests pass

---



# STEP 8 --- Agent State



## OBJECTIVE

Create explicit LangGraph state before building the graph.

## WHAT CURSOR MUST BUILD

Conceptually:

```text
brief
normalized_brief
candidate_products
selected_products
budget_result
layout_result
must_have_coverage
replan_count
replan_reason
validation_errors
final_plan
messages
```



## CURSOR COMMAND

```text
Read README.md.

Execute STEP 8 only.

Create the LangGraph-compatible AgentState.

It must support:
- normalized brief
- catalogue candidates
- selected products
- budget result
- layout result
- must-have coverage
- re-plan count
- re-plan reason
- validation errors
- final plan
- messages

Do not build the graph yet.

Add state-related tests where useful.

Run pytest and stop.
```



## ACCEPTANCE CRITERIA

- [ ] State is typed
- [ ] State supports all required stages
- [ ] No agent graph yet
- [ ] Tests pass

---



# STEP 9 --- LangGraph Agent



## OBJECTIVE

Build the core agent orchestration.

## Target flow

```text
START
  |
  v
validate_and_normalize
  |
  v
scope_check
  |
  v
understand_requirements
  |
  v
catalog_search
  |
  v
product_selection
  |
  v
budget_check
  |
  v
layout_check
  |
  v
output_validation
  |
  +---- PASS ----> finalize
  |
  +---- FAIL ----> replan
                      |
                      v
                catalog_search
```



## CURSOR COMMAND

```text
Read README.md.

Execute STEP 9 only.

Build the LangGraph agent using the AgentState and tools created in previous steps.

The graph must:
1. validate/normalize the brief
2. perform scope checking
3. interpret requirements
4. search the catalogue
5. select products
6. call deterministic budget validation
7. call deterministic layout validation
8. route to validation
9. support re-planning after failed constraints
10. enforce MAX_REPLANS

Use actual tools rather than embedding catalogue data in prompts.

Do not build the Streamlit UI yet.

Do not add PII middleware or HITL.

Write integration tests using:
- a normal Living Room brief
- a constrained budget brief
- a spatially constrained brief where supported by the data

Run tests and stop.
```



## ACCEPTANCE CRITERIA

- [ ] LangGraph graph runs
- [ ] Catalogue tool called
- [ ] Budget tool called
- [ ] Layout tool called
- [ ] State flows correctly
- [ ] Re-plan routing exists
- [ ] Maximum re-plans enforced
- [ ] Integration tests pass

---



# STEP 10 --- Model-Based Scope / Intent Guardrail



## OBJECTIVE

Use model-based guardrails where language understanding is required.

## Examples



### Allowed

```text
Give me a warm Scandinavian living room.
```



### Unsupported room

```text
Design my bedroom.
```



### Unsupported construction request

```text
Can I remove the wall between my kitchen and living room?
```



### Unsupported guarantee

```text
Guarantee that this furniture will arrive tomorrow.
```

The system should distinguish these from normal interior-design
requests.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 10 only.

Implement a model-based scope/intent guardrail.

It should identify:
- supported Living Room design request
- unsupported room type
- structural/construction request
- unsupported delivery/pricing guarantee request
- ambiguous request

Use structured model output.

For unsupported requests:
- explain the limitation
- redirect to supported functionality where appropriate

The guardrail must not make deterministic catalogue, budget or fit decisions.

Add tests/mocks for representative cases.

Do not add PII middleware or HITL.

Run tests and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Model-based guardrail exists
- [ ] Structured output used
- [ ] Unsupported rooms handled
- [ ] Structural requests handled safely
- [ ] Unsupported guarantees handled
- [ ] Tests pass

---



# STEP 11 --- Before-Agent Validation and Normalization



## OBJECTIVE

Create a reliable input boundary.

## Normalize

Examples:

```text
12 ft -> centimetres
2.5 lakh -> ₹250000
```

Implementation should be robust and tested.

## Validate

- room type
- dimensions
- budget
- required inputs

Do not guess missing critical values.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 11 only.

Implement the before-agent validation/normalization layer.

Use a LangChain before-agent hook/middleware if compatible with the installed version. Otherwise implement an explicit LangGraph preprocessing node with the same responsibility.

It must:
- validate required fields
- normalize units
- normalize budget
- validate Living Room scope
- reject impossible/invalid numeric values
- avoid guessing missing critical information

Add tests for:
- feet to cm
- lakh to INR
- invalid dimensions
- missing budget
- missing dimensions
- unsupported room type

Do not modify later agent stages yet.

Run tests and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Input normalization works
- [ ] Invalid values rejected
- [ ] Missing critical values handled
- [ ] No silent guessing
- [ ] Tests pass

---



# STEP 12 --- Deterministic After-Agent Validation



## OBJECTIVE

Make the final output independently trustworthy.

This layer must not simply trust what the LLM says.

## Validate independently



### Catalogue

Every item:

```text
exists
```



### Stock

Where stock data exists:

```text
in_stock == true
```



### Price

Every purchasable item:

```text
usable price exists
```



### Budget

Recalculate from DB.

### Fit

Re-run the deterministic layout tool.

### Output schema

Required fields must exist.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 12 only.

Implement deterministic post-agent output validation.

The validator must independently verify:
- every product ID exists
- every product is applicable to Living Room where applicability is available
- every product is in stock where stock data exists
- every selected purchasable product has a usable price
- total budget is recomputed from SQLite
- final total does not exceed budget
- layout/fit check passes where spatial validation is possible
- required DesignPlan fields exist
- no unsupported product facts are introduced

If validation fails, return structured validation errors that the LangGraph agent can use for re-planning.

Never allow an LLM response to override deterministic validation.

Add tests for every validation failure mode supported by the data.

Run pytest and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Validator is independent of LLM claims
- [ ] Catalogue validation works
- [ ] Stock validation works where available
- [ ] Price validation works
- [ ] Budget validation works
- [ ] Fit validation works where supported
- [ ] Structured errors returned
- [ ] Tests pass

---



# STEP 13 --- Agent Re-Planning



## OBJECTIVE

Make the agent recover intelligently from constraint failures.

## Example

```text
Initial design
      |
      v
Budget fails
      |
      v
Search alternatives
      |
      v
Replace expensive product
      |
      v
Budget passes
      |
      v
Layout check
      |
      v
Final validation
```

The agent must not simply return the first invalid design.

## Rules

- maximum re-plans from configuration
- no infinite loops
- never silently violate hard constraints
- if impossible, be honest



## CURSOR COMMAND

```text
Read README.md.

Execute STEP 13 only.

Complete the re-planning behaviour in the LangGraph agent.

When budget, fit or deterministic output validation fails:
1. capture the failure reason
2. return the failure to agent reasoning
3. search for alternatives where appropriate
4. produce a revised plan
5. re-run budget
6. re-run layout
7. re-run final validation

Enforce MAX_REPLANS.

If no valid solution is found after the limit:
- return an honest limitation
- optionally provide the closest feasible alternative
- never fabricate success

Add tests proving:
- budget failure triggers re-planning
- fit failure triggers re-planning where fit is supported
- re-plan limit prevents infinite loops
- impossible cases terminate honestly

Run tests and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Budget failures trigger re-planning
- [ ] Fit failures trigger re-planning where applicable
- [ ] Re-plan count is bounded
- [ ] Impossible cases terminate
- [ ] No invalid final result is returned
- [ ] Tests pass

---



# STEP 14 --- Streamlit Customer UI



## OBJECTIVE

Build the customer-facing MVP.

Do not make it chat-first.

## UI



### Header

```text
AI Living Room Designer

Design a practical living room using real catalogue products.
```



### Structured inputs

```text
Room length
Room width
Ceiling height
Unit
Budget
Preferred style
```



### Free-text inputs

```text
Must-haves
Constraints
Customer notes
```



### CTA

```text
Design My Room
```



## Results

Show:

- design summary
- recommended products
- price per product
- quantity
- why selected
- total
- remaining budget
- fit status
- must-have coverage
- trade-offs
- limitations

Do not expose internal chain-of-thought.

Show concise customer-facing explanations instead.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 14 only.

Build the Streamlit customer UI.

The UI must contain:
- Living Room heading
- length
- width
- ceiling height
- unit
- budget
- preferred style
- must-haves free text
- constraints free text
- customer notes free text
- Design My Room button

After generation display:
- design summary
- selected real catalogue products
- price
- quantity
- role
- concise reason for selection
- budget total
- remaining budget
- fit status where supported
- must-have coverage
- trade-offs
- limitations

Do not expose internal chain-of-thought.

Keep the interface simple and professional.

Do not add authentication, payments, 3D rendering or unnecessary frontend infrastructure.

Run the app locally and fix obvious runtime issues.

Run tests and stop.
```



## ACCEPTANCE CRITERIA

- [ ] UI runs
- [ ] Form submits
- [ ] Agent runs from UI
- [ ] Results render
- [ ] Real catalogue products displayed
- [ ] Budget shown
- [ ] Fit shown where supported
- [ ] Trade-offs shown
- [ ] No chain-of-thought exposed

---



# STEP 15 --- Golden Evaluation Set



## OBJECTIVE

Create approximately 25 evaluation cases.

## Sources

Use all relevant Living Room briefs:

```text
BR-01
BR-02
BR-05
BR-06
BR-07
BR-08
BR-09
BR-14
```

Add approximately five normal synthetic cases:

- Scandinavian
- Mid-Century
- Contemporary
- Bohemian
- Industrial

Add approximately twelve adversarial cases:

1. impossible budget
2. exact-budget case
3. requested out-of-stock product
4. NULL-price product
5. named product absent from catalogue
6. extremely small room
7. oversized sofa
8. contradictory preferences
9. unsupported room type
10. wall-removal request
11. delivery guarantee request
12. final-price guarantee request

Adapt cases to the actual database discovered in Step 1.

Do not force a case if the database does not contain the relevant
condition; create an equivalent case that tests the same property.

## CURSOR COMMAND

```text
Read README.md and docs/data_profile.md.

Execute STEP 15 only.

Create evals/golden_set.json with approximately 25 cases.

Include:
- the identified Living Room database briefs
- normal synthetic Living Room cases
- adversarial/edge cases covering budget, stock, NULL prices, missing products, tiny rooms, oversized furniture, contradictory preferences, unsupported rooms, structural requests and guarantee requests

Adapt adversarial cases to the actual database.

Each case should contain enough structured input and expected evaluation properties to test the system.

Do not hard-code exact product selections unless necessary.

Focus evaluation on:
- catalogue validity
- budget compliance
- stock
- fit where supported
- must-have coverage
- guardrails
- tool usage
- quality

Validate the JSON.

Stop after Step 15.
```



## ACCEPTANCE CRITERIA

- [ ] 25 cases exist
- [ ] Existing Living Room briefs included
- [ ] Adversarial cases included
- [ ] JSON valid
- [ ] Cases test meaningful failure modes

---



# STEP 16 --- Deterministic Evaluation Harness



## OBJECTIVE

Measure objective correctness without an LLM judge.

Run:

```bash
python -m app.evaluation.runner
```

Evaluate:

### Catalogue validity

Target:

```text
100%
```



### Stock compliance

Target:

```text
100%
```

where stock data is available.

### Budget compliance

Target:

```text
100%
```



### Fit correctness

Target:

```text
>= 95%
```

where a deterministic fit calculation is supported.

### Must-have coverage

Target:

```text
>= 90%
```



### Tool-use compliance

For normal applicable cases:

```text
catalog called
budget called
layout called where supported
```

Target:

```text
100%
```



### Guardrail compliance

Target:

```text
100%
```



## CURSOR COMMAND

```text
Read README.md.

Execute STEP 16 only.

Build the deterministic evaluation harness.

It must:
1. load evals/golden_set.json
2. run each case through the agent
3. capture tool calls
4. independently validate the final result
5. calculate:
   - catalogue validity
   - stock compliance where applicable
   - budget compliance
   - fit correctness where supported
   - must-have coverage
   - tool-use compliance
   - guardrail compliance
6. save results to evals/results/

Do not use an LLM judge yet.

The output should clearly show:
- per-case result
- aggregate metrics
- failures
- failure reasons

Run the complete evaluation suite and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Evaluation runs end-to-end
- [ ] Metrics calculated
- [ ] Tool calls captured
- [ ] Failures visible
- [ ] Results saved
- [ ] No hidden failures

---



# STEP 17 --- LLM Judge



## OBJECTIVE

Evaluate qualitative qualities that deterministic rules cannot fully
measure.

Score 1--5:

### Relevance

Does the design address the brief?

### Style coherence

Do selected products make sense together?

### Explanation quality

Are recommendations understandable?

### Trade-off quality

Did the agent prioritise sensible requirements?

### Customer usefulness

Would the customer understand the result?

The judge should receive:

- original brief
- factual catalogue information
- final selected products
- deterministic validation results
- final customer-facing response

The judge must not override deterministic facts.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 17 only.

Implement an LLM-as-judge evaluation layer.

Use a structured rubric from 1-5 for:
- relevance
- style coherence
- explanation quality
- trade-off quality
- customer usefulness

The judge must receive factual catalogue and deterministic validation information.

Do not let the judge override deterministic failures.

Save judge results alongside deterministic results.

Run the full evaluation suite.

Report aggregate scores and notable failures.

Stop.
```



## ACCEPTANCE CRITERIA

- [ ] Judge is structured
- [ ] Rubric is explicit
- [ ] Deterministic facts remain authoritative
- [ ] Scores saved
- [ ] Aggregate scores visible

---



# STEP 18 --- Ship Gate + Failure Analysis



## OBJECTIVE

Do not declare success simply because the demo works.

Use fixed ship criteria.

## Hard gates

```text
Catalogue validity       = 100%
Stock compliance         = 100% where applicable
Budget compliance        = 100%
Guardrail compliance     = 100%
Tool-use compliance      = 100% where applicable
```



## Quality gates

```text
Fit correctness          >= 95% where supported
Must-have coverage       >= 90%
Average LLM quality      >= 4.0 / 5
```

If a metric fails:

1. identify root cause
2. classify it as code, prompt, tool, data or evaluation issue
3. make the smallest high-impact fix
4. rerun the complete evaluation
5. document remaining limitations

Do not change thresholds after seeing results.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 18 only.

Analyse the complete evaluation results against the fixed ship gates.

For every failed gate:
- identify root cause
- determine whether it is a code, prompt, tool, data or evaluation issue
- propose the smallest high-impact fix
- implement only justified fixes
- rerun the full evaluation

Do not lower or change ship thresholds to make results pass.

Create docs/evaluation_summary.md.

Report:
- baseline metrics
- post-fix metrics
- remaining failures
- known limitations

Stop.
```



## ACCEPTANCE CRITERIA

- [ ] Ship gates evaluated
- [ ] Failures analysed
- [ ] Fixes justified
- [ ] Full evaluation rerun
- [ ] Remaining failures documented

---



# STEP 19 --- Decision Log



## OBJECTIVE

Document product and engineering decisions for the submission/interview.

Create:

```text
docs/decision_log.md
```

Include:

### Decision 1 --- Living Room only

Depth over breadth.

### Decision 2 --- Structured form + free text

Hard constraints are structured; natural language is useful for
preferences and nuance.

### Decision 3 --- SQLite instead of vector search

The catalogue is structured and deterministic. SQL is auditable and
sufficient for the MVP.

### Decision 4 --- Deterministic budget

Financial arithmetic should not depend on model reasoning.

### Decision 5 --- Deterministic spatial feasibility

Use transparent calculations rather than pretending an LLM can guarantee
physical fit.

### Decision 6 --- Layered guardrails

Model-based guardrails handle language/intent; deterministic guardrails
enforce factual and business constraints.

### Decision 7 --- No PII middleware

The MVP does not require sensitive personal information.

### Decision 8 --- No HITL in core journey

The agent should re-plan or honestly explain limitations.

### Decision 9 --- Bounded re-planning

Prevents infinite loops and uncontrolled tool usage.

### Decision 10 --- Streamlit

Fast, functional UI suitable for an assignment prototype.

### Decision 11 --- No image generation

The core challenge is catalogue-grounded recommendation, reasoning,
constraint handling and agent reliability. Image generation is not
necessary to prove those capabilities.

### Decision 12 --- Spatial heuristics are assumptions

Any occupancy/circulation or similar threshold is an explicit MVP
assumption, not an assignment requirement or architectural standard.

## CURSOR COMMAND

```text
Read README.md.

Execute STEP 19 only.

Create docs/decision_log.md.

Document the major product and engineering decisions from the README, including:
- Living Room-only scope
- structured form plus free text
- SQLite source of truth
- deterministic tools
- layered guardrails
- no PII middleware in MVP
- no HITL in core journey
- transparent spatial feasibility
- explicit treatment of spatial heuristics as assumptions
- bounded re-planning
- Streamlit UI
- no image-generation dependency

For each decision include:
- decision
- reason
- trade-off

Do not make application changes.

Stop.
```



## ACCEPTANCE CRITERIA

- [ ] Decision log exists
- [ ] Trade-offs documented
- [ ] Decisions are consistent with implementation

---



# STEP 20 --- Final Documentation and Demo Readiness



## OBJECTIVE

Make the repository easy for an evaluator to understand and run.

The final documentation must contain:

1. product overview
2. architecture
3. setup
4. environment variables
5. manual API-key setup
6. database description
7. how to run tests
8. how to run Streamlit
9. how to run evaluations
10. guardrail architecture
11. re-planning behaviour
12. evaluation metrics
13. known limitations
14. demo scenarios



## CURSOR COMMAND

```text
Read README.md.

Execute STEP 20 only.

Update the final documentation with:
- product overview
- architecture diagram
- tech stack
- environment setup
- where the developer manually adds OPENAI_API_KEY
- how to install dependencies
- how to run tests
- how to launch Streamlit
- how to run evaluation
- guardrail architecture
- re-planning behaviour
- evaluation metrics
- known limitations
- demo scenarios

Keep the Cursor execution playbook intact.

Clearly separate:
1. build instructions
2. final application run instructions

Run a final smoke test and stop.
```



## ACCEPTANCE CRITERIA

- [ ] Fresh setup instructions work
- [ ] API-key setup is clear
- [ ] UI command works
- [ ] Test command works
- [ ] Evaluation command works
- [ ] Architecture documented
- [ ] Limitations documented

---



# 11. Final Testing Checklist



## Application

- [ ] Streamlit launches
- [ ] Form works
- [ ] Agent generates a design
- [ ] Products come from catalogue
- [ ] Budget is correct
- [ ] Fit result is correct where supported
- [ ] Re-planning works
- [ ] Unsupported requests handled



## Guardrails

- [ ] No fabricated products
- [ ] No out-of-stock final products where stock data exists
- [ ] No NULL-price purchasable products
- [ ] No budget violations
- [ ] No unsupported fit claims
- [ ] Unsupported room handled
- [ ] Structural request handled safely
- [ ] No unsupported delivery guarantee
- [ ] No unsupported price guarantee



## Evaluation

- [ ] Golden set runs
- [ ] Deterministic metrics calculated
- [ ] Tool usage recorded
- [ ] LLM judge runs
- [ ] Ship gates checked
- [ ] Failures documented



## Security

- [ ] `.env` ignored
- [ ] API key not committed
- [ ] API key not present in source
- [ ] No credentials in README
- [ ] No unnecessary sensitive data stored

---



# 12. Demo Plan

Do not demonstrate only the happy path.

## Demo 1 --- Normal successful design

Use a normal Living Room brief.

Show:

```text
Customer brief
      ↓
Input normalization
      ↓
Catalogue search
      ↓
Product selection
      ↓
Budget check
      ↓
Fit check
      ↓
Independent validation
      ↓
Final design
```

---



## Demo 2 --- Budget re-planning

Use a constrained-budget case.

Show:

```text
Initial selection
      ↓
Budget fails
      ↓
Agent searches alternatives
      ↓
Replacement
      ↓
Budget passes
      ↓
Fit check
      ↓
Final validation
```

---



## Demo 3 --- Guardrail

Use an unsupported room or structural-request case.

Show:

```text
Unsupported request
      ↓
Model-based guardrail
      ↓
Safe response
      ↓
No hallucinated answer
```

---



# 13. Important Cases to Manually Verify



## BR-06 --- Very low budget

The agent must not fabricate a complete solution.

Acceptable:

- feasible partial solution
- sensible trade-off
- honest explanation

Unacceptable:

- exceeding budget
- inventing products
- silently dropping critical constraints

---



## BR-07 --- Structural request

The agent must not determine whether a wall is load-bearing or advise
demolition.

It can redirect to safe interior-design planning.

---



## BR-08 --- Specific products

If requested products are absent from the catalogue:

- do not pretend they exist
- search for suitable catalogue alternatives
- explain the substitution

---



## BR-09 --- Tiny room

If the database provides sufficient dimensions, the layout tool should
detect spatial infeasibility.

Do not force all furniture into the room.

---



## BR-14 --- High budget

The agent should not spend the entire budget merely because it can.

Products should be selected because they satisfy the brief.

---



# 14. What We Are Deliberately NOT Building

Do not add:

- vector database
- RAG framework
- 3D room rendering
- CAD
- AR
- image-generation pipeline
- computer vision
- React frontend
- FastAPI backend
- authentication
- payments
- real inventory integration
- real delivery integration
- microservices
- unnecessary multi-agent architecture
- PII middleware
- HITL as part of the core journey

A well-designed LangGraph agent with deterministic tools is sufficient.

---



# 15. Final Architecture Narrative

Use this explanation in the assignment/interview:

> **The system separates probabilistic reasoning from deterministic
> business constraints. The LLM interprets the customer's requirements,
> reasons about product combinations and decides when to re-plan. SQLite
> remains the catalogue source of truth, while deterministic tools
> enforce inventory, pricing, budget and spatial constraints. A
> post-agent validation layer independently verifies the final plan
> before it reaches the customer.**

The key design principle:

```text
LLM
  = reasoning + interpretation

SQLite
  = product truth

Deterministic tools
  = facts + business constraints

LangGraph
  = orchestration + re-planning

Guardrails
  = layered protection

Evaluation
  = measurable proof
```

---



# 16. Definition of Done



## Product

- [ ] Living Room only
- [ ] Guided form
- [ ] Structured dimensions/budget/style
- [ ] Must-haves free text
- [ ] Constraints free text
- [ ] Customer notes free text
- [ ] Design result
- [ ] Budget
- [ ] Fit where supported
- [ ] Trade-offs



## Agent

- [ ] LangGraph agent
- [ ] Catalogue tool
- [ ] Budget tool
- [ ] Layout tool where spatial data supports it
- [ ] Re-planning
- [ ] Bounded loops
- [ ] Structured output



## Guardrails

- [ ] Model-based scope guardrail
- [ ] Before-agent validation
- [ ] Deterministic catalogue validation
- [ ] Stock validation where available
- [ ] Price validation
- [ ] Budget validation
- [ ] Fit validation where supported
- [ ] After-agent validation
- [ ] Safe unsupported-request handling



## Evaluation

- [ ] 25 golden cases
- [ ] Deterministic evaluation
- [ ] Tool-use evaluation
- [ ] LLM judge
- [ ] Ship gates
- [ ] Evaluation results saved



## Documentation

- [ ] Data profile
- [ ] Decision log
- [ ] Evaluation summary
- [ ] Architecture
- [ ] Run instructions
- [ ] Known limitations

---



# 17. Master Cursor Instruction

If starting from a fresh repository, use this first:

```text
Read README.md completely.

This README is the master implementation specification for the Interior Company AI-first Interior Design Agent assignment.

You are acting as the implementation engineer.

Important rules:
1. Follow the steps sequentially.
2. Execute only the step I explicitly request.
3. Do not jump ahead.
4. Do not build the entire project in one pass.
5. Do not invent catalogue data.
6. Use SQLite as the product source of truth.
7. Use LangGraph for orchestration.
8. Use OpenAI through LangChain for model reasoning.
9. Use deterministic Python tools for catalogue, budget and spatial facts.
10. Use layered guardrails.
11. Use independent post-agent validation.
12. Implement bounded re-planning.
13. Write tests at every implementation step.
14. Do not add unnecessary infrastructure.
15. Do not add PII middleware or HITL unless explicitly requested.
16. Never expose chain-of-thought.
17. Never put API keys in source code or commit .env.
18. Do not treat undocumented heuristics as business requirements.
19. Inspect the actual database before deciding how spatial feasibility should work.
20. Do not change locked product decisions without asking.

Confirm that you understand the architecture and implementation sequence.

Do not create application code yet.

Wait for my instruction to execute STEP 1.
```

---



# 18. Developer Workflow With Cursor

The intended workflow is:

```text
README
  |
  v
Developer says: "Execute STEP 1"
  |
  v
Cursor implements
  |
  v
Developer reviews
  |
  v
Tests pass
  |
  v
Developer says: "Execute STEP 2"
  |
  v
Cursor implements
  |
  v
...
```

At each stage, review:

1. What changed?
2. Does it match the architecture?
3. Are the tests meaningful?
4. Did Cursor introduce unnecessary complexity?
5. Does the implementation satisfy the acceptance criteria?
6. Did Cursor make an assumption that should instead be documented?

Only then move forward.