# AI Interior Design Agent — Living Room MVP

A focused AI agent that turns a customer's living-room brief into a **catalogue-backed, budget-fit design plan** using real Interior Company catalogue data.

> **Submission for the Associate Product Manager — Product & Technology build challenge**

## What I built

The MVP accepts:
- Room dimensions and ceiling height
- Budget
- Preferred style
- Must-haves
- Constraints and customer notes

It then:

1. Interprets the customer's brief.
2. Searches the supplied SQLite catalogue for real products.
3. Selects products based on style, requirements, availability and price.
4. Calculates the budget deterministically.
5. Checks spatial feasibility with a transparent layout heuristic.
6. Re-plans when budget, fit or validation constraints fail.
7. Independently validates the final output before showing it to the customer.
8. Explains recommendations and trade-offs.
9. Refuses unsupported requests instead of fabricating an answer.

### Core principle

**LLM handles reasoning; SQLite is the source of truth; deterministic tools enforce facts and constraints; LangGraph orchestrates the workflow and re-planning.**

## Architecture

```text
Customer
   |
   v
Streamlit UI
   |
   v
Input validation / normalization
   |
   v
Scope & intent guardrail
   |
   v
LangGraph Agent
   |---- Catalog Search
   |---- Product Selection
   |---- Budget Calculator
   |---- Layout / Fit Check
   |---- Re-plan when required
   |
   v
Independent Output Validation
   |
   +---- Valid plan ------> Customer
   |
   +---- Invalid ----------> Re-plan / honest limitation
```

### Why this architecture?

I deliberately separated probabilistic reasoning from deterministic business constraints. The model can reason about combinations and explain choices, but it cannot invent catalogue facts, calculate the final bill, or override physical-fit checks.

## Evaluation

The evaluation harness contains **25 golden/adversarial cases** with deterministic checks, tool-use checks and an LLM-as-judge quality rubric.

| Metric | Result | Gate |
|---|---:|---:|
| Catalogue validity | **100%** | 100% |
| Stock compliance | **100%** | 100% |
| Budget compliance | **100%** | 100% |
| Guardrail compliance | **100%** | 100% |
| Tool-use compliance | **100%** | 100% |
| Fit correctness | **100%** | ≥95% |
| Must-have coverage | **100%** | ≥90% |
| Average LLM quality | **3.30 / 5** | ≥4.0 |

**Current status:** All factual/safety gates pass. The subjective quality gate is not yet met. The remaining low-scoring cases are primarily catalogue-bound or intentionally difficult briefs (missing named products, insufficient budget, unavailable pricing, or spatial infeasibility).

I have kept these failures visible rather than lowering the evaluation threshold or inventing catalogue products.

See [`docs/evaluation_summary.md`](docs/evaluation_summary.md) for the full results and failure analysis.

## Key product decisions

- **Living Room only:** depth over breadth for the MVP.
- **Structured inputs + free text:** dimensions and budget are explicit; preferences remain flexible.
- **SQLite over vector search:** the supplied catalogue is small and structured, making SQL auditable and deterministic.
- **Deterministic budget and fit checks:** financial and spatial facts are not delegated to the LLM.
- **Layered guardrails:** scope is checked before tools; outputs are independently validated afterward.
- **Bounded re-planning:** the agent can recover from budget/fit failures without entering an infinite loop.
- **No image generation:** the assignment's core value is grounded product recommendation and constraint handling, not visual generation.

More detail: [`docs/decision_log.md`](docs/decision_log.md)

## Run locally

### 1. Install

```bash
python -m venv .venv
```

Windows:

```text
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and add your `OPENAI_API_KEY`.

**Never commit `.env`.**

### 3. Run the app

```bash
python -m streamlit run app/ui/streamlit_app.py
```

### 4. Run tests

```bash
python -m pytest -q
```

### 5. Run the evaluation harness

```bash
python -m app.evaluation.runner
```

Evaluation outputs are written under `evals/results/`.

## Demo cases

**Happy path:** Scandinavian living room with a ₹2.5L budget and specified furniture requirements.

**Budget constraint:** ₹20K living-room brief where the catalogue cannot satisfy every must-have. The agent explains the limitation instead of exceeding budget.

**Guardrail:** Bedroom/structural/delivery-guarantee request. The agent refuses the unsupported part and does not invoke product tools.

**Fit constraint:** Small room requesting an oversized sofa. The agent does not force an infeasible product into the plan.

## Known limitations

- Living Room only.
- Layout is a transparent rectangle/height/occupancy heuristic, not CAD or a furnished floor plan.
- Catalogue style matching currently uses `style_tags` rather than embeddings.
- Products with NULL prices cannot be sold in this MVP.
- Named products absent from the supplied catalogue cannot be sourced.
- The quality score remains below the defined 4.0/5 ship gate.

## Repository guide

| Path | Purpose |
|---|---|
| `app/` | Application, agent, tools, validation and UI |
| `evals/` | Golden evaluation cases and results |
| `tests/` | Unit, integration and evaluation tests |
| `docs/decision_log.md` | Product and engineering decisions |
| `docs/evaluation_summary.md` | Evaluation results and failure analysis |
| `docs/data_profile.md` | Catalogue/database profile |
| `docs/layout_methodology.md` | Spatial-fit methodology and assumptions |
| `BUILD.md` | Detailed build specification and implementation notes |

---

**Built as a focused MVP: grounded in the supplied catalogue, deterministic where facts matter, and explicit about where the current product does not yet meet the ship bar.**
