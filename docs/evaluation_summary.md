# Evaluation summary

This note compares the Living Room designer against the **fixed** ship gates using the current golden set (**25 cases**). Thresholds were not changed after seeing scores.

LLM-as-judge is implemented. Quality scores come from `python -m app.evaluation.runner` (structured 1–5 rubric). Deterministic SQLite / layout / budget checks remain authoritative; the judge cannot mark a factual failure as a pass.

**Current run:** `evals/results/latest.json` / `evals/results/latest_summary.txt`  
**Generated at:** `2026-09-06T15:03:17Z`  
**Cases:** 25/25 deterministic pass

## Ship gates

### Hard gates

| Gate | Target | Current | Status |
| --- | --- | --- | --- |
| Catalogue validity | 100% | 100% (25/25) | Pass |
| Stock compliance | 100% where applicable | 100% (14/14) | Pass |
| Budget compliance | 100% | 100% (25/25) | Pass |
| Guardrail compliance | 100% | 100% (25/25) | Pass |
| Tool-use compliance | 100% where applicable | 100% (25/25) | Pass |

### Quality gates

| Gate | Target | Current | Status |
| --- | --- | --- | --- |
| Fit correctness | ≥ 95% where supported | 100% (14/14) | Pass |
| Must-have coverage | ≥ 90% | 100% (20/20)* | Pass |
| Average LLM quality | ≥ 4.0 / 5 | **3.81** (n=25) | **Fail** |

\*Coverage pass-rate uses each golden case’s `min_coverage` (partial/empty plans are allowed on tight-budget and missing-SKU briefs). It is not “every must-have phrase was physically sourced.”

**Deterministic failures:** none.

## LLM judge (current)

| Dimension | Score |
| --- | --- |
| Overall mean | **3.81** |
| Relevance | 4.60 |
| Style coherence | 3.64 |
| Explanation quality | 3.48 |
| Trade-off quality | 3.96 |
| Customer usefulness | 3.36 |

Normal style synthetics and clear guardrail refusals often score ~4.0+. Exact-budget seating (`ADV-exact-budget` → SOF-008) scored **4.60**.

### Fact contradictions (judge flag)

The judge set `honours_deterministic_facts=false` on:

| Case | Notes |
| --- | --- |
| BR-09 | Presenting a 3-seater as covering an L-sectional / incomplete disclosure of dining omission |
| ADV-oversized-sofa | Vague “no valid combination” framing vs the decisive spatial conflict (300 cm sectional vs 240×210 room) |

These flags do **not** flip deterministic pass/fail.

## Failed gate: average LLM quality (≥ 4.0)

Hard factual gates pass. The remaining quality gap is mainly **customer usefulness and explanation clarity** on honest empty / blocked plans—not invented SKUs or broken budget/stock.

### Notable low scores (mean &lt; 3.0)

| Case | Mean | Why the judge is unhappy (and why we do not “fix” it with invented SKUs) |
| --- | --- | --- |
| ADV-out-of-stock | 2.80 | SOF-006 is out of stock and correctly excluded; explanation does not give a clear next step (waitlist / substitute / revise brief) |
| ADV-null-price | 2.60 | CFT-004 has NULL `price_inr` and cannot be sold; response is honest but vague about the specific blocker |
| ADV-oversized-sofa | 2.60 | Required sectional cannot fit 240×210; empty plan is correct, but the decisive fit reason is under-explained |

Other mid scores (still deterministic pass): BR-06 **3.00**, BR-08 **3.00**, BR-09 **3.20**, BR-14 **3.20**, ADV-absent-named-product **3.60**.

### Context vs earlier STEP 18 snapshot

| | Earlier post-fix (STEP 18 docs) | Current (`latest.json`) |
| --- | --- | --- |
| Overall mean | 3.30 | **3.81** |
| Relevance | 3.80 | 4.60 |
| Style coherence | 3.52 | 3.64 |
| Explanation quality | 3.04 | 3.48 |
| Trade-off quality | 3.36 | 3.96 |
| Customer usefulness | 2.76 | 3.36 |

Quality improved versus the Sept 5 post-fix write-up, but the **≥ 4.0** ship gate still fails.

**Ship recommendation:** hard factual gates pass; **do not ship as quality-complete** until average LLM quality is ≥ 4.0 or the product explicitly accepts catalogue-bound / empty-plan explanation quality as sufficient.

## Known limitations

- Layout is a rectangle/height/occupancy check, not circulation or a floor plan (`docs/layout_methodology.md`).
- Style match uses catalogue `style_tags`, not embeddings.
- Must-have coverage in the harness is category-level (and case `min_coverage`), not named-SKU retrieval.
- Judge scores vary run-to-run; they never override SQLite prices, stock, or fit.
- Living Room MVP only; structural, guarantee, and other-room requests are refused by design.
- Catalogue data limits remain: no Togo/Noguchi/Cassina LC3 rows; CFT-004 NULL price; SOF-006 out of stock; BR-06 ₹20,000 below cheapest sofa ₹36,000; SOF-004 does not fit 240×210 cm.

## How to reproduce

```text
python -m app.evaluation.runner
```

Uses the configured golden set (~25 cases). Outputs: `evals/results/latest.json`, `evals/results/latest_summary.txt` (same run).
