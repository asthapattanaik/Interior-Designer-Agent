# Evaluation summary (STEP 18)

This note compares the Living Room designer against the **fixed** ship gates. Thresholds were not changed after seeing scores.

LLM-as-judge **is implemented** (STEP 17). Quality scores come from `python -m app.evaluation.runner` (structured 1–5 rubric). Deterministic SQLite/layout/budget checks remain authoritative; the judge cannot mark a factual failure as a pass.

## Ship gates

### Hard gates

| Gate | Target | Baseline | Post-fix | Status |
| --- | --- | --- | --- | --- |
| Catalogue validity | 100% | 100% (25/25) | 100% (25/25) | Pass |
| Stock compliance | 100% where applicable | 100% (19/19) | 100% (19/19) | Pass |
| Budget compliance | 100% | 100% (25/25) | 100% (25/25) | Pass |
| Guardrail compliance | 100% | 100% (25/25) | 100% (25/25) | Pass |
| Tool-use compliance | 100% where applicable | 100% (25/25) | 100% (25/25) | Pass |

### Quality gates

| Gate | Target | Baseline | Post-fix | Status |
| --- | --- | --- | --- | --- |
| Fit correctness | ≥ 95% where supported | 100% (19/19) | 100% (19/19) | Pass |
| Must-have coverage | ≥ 90% | 100% (20/20)* | 100% (20/20)* | Pass |
| Average LLM quality | ≥ 4.0 / 5 | **2.88** (n=25) | **3.30** (n=25) | **Fail** |

\*Coverage pass-rate uses each golden case’s `min_coverage` (partial/empty plans are allowed on tight-budget and missing-SKU briefs). It is not “every must-have phrase was physically sourced.”

Baseline judge run: `evals/results/eval_20260905T155224Z.json`  
Post-fix judge run: `evals/results/eval_20260905T160424Z.json` (also `latest.json`)

## Failed gate: average LLM quality

### Root cause

The judge’s low scores were **not** inventing SKUs or breaking budget/stock. They were mostly:

1. **Cheapest-SKU selection** ignored `style_tags`. Almost every sofa was SOF-008 (Minimalist futon), including Scandinavian, Mid-Century, Contemporary, and premium briefs.
2. **Customer text leaked internals** (`SQLite`, occupancy, re-plan tokens, MAX_REPLANS).
3. **“Lighting” expanded to three fixture categories**, so schemes looked cluttered and under-explained.
4. **Catalogue/data limits** the judge still penalises: no Togo/Noguchi/Cassina rows; CFT-004 has NULL price so it cannot be sold; BR-06’s ₹20,000 is below SOF-008 ₹36,000; dining tables are Dining-only; SOF-004 does not fit 240×210 cm.

### Classification

| Issue | Type | Action |
| --- | --- | --- |
| Always pick cheapest SKU / ignore style tags | **Code** | Prefer `style_tags` match, then 3-seater width when asked, then price; spend up only on explicit premium/high-end briefs |
| “from SQLite” / re-plan dumps in the plan | **Code** | Customer-facing `why_selected`, summary, trade-offs; skip success-path scope boilerplate |
| Three lights for one “lighting” phrase | **Code** | Map plain “lighting” to floor lamp; keep three fixtures only for “layered lighting” |
| Absent named designer pieces, NULL prices, ₹20k vs ₹36k sofa, dining-in-living-room | **Data** | No invented products; documented as remaining limitations |
| Judge wanting CFT-004 sold despite NULL price | **Evaluation** | Deterministic policy wins; quality score still counts |

### Fix applied (smallest high-impact)

In `app/agent/graph.py` and `app/agent/requirements.py` only:

- Style-tag-aware ranking of in-stock, priced Living Room rows
- 3-seater vs loveseat preference when the brief says so
- Premium briefs prefer higher-priced **style-matched** SKUs (still never over budget after replan)
- One lighting category unless the brief asks for layered lighting
- Copy without SQLite / MAX_REPLANS / raw replan tokens

No thresholds were lowered. No fake catalogue rows.

### Post-fix LLM dimension means (n=25)

| Dimension | Baseline | Post-fix |
| --- | --- | --- |
| Overall | 2.88 | 3.30 |
| Relevance | 3.44 | 3.80 |
| Style coherence | 2.64 | 3.52 |
| Explanation quality | 2.56 | 3.04 |
| Trade-off quality | 3.24 | 3.36 |
| Customer usefulness | 2.52 | 2.76 |

Normal style synthetics and guardrail refusals now often sit at ~4.0. BR-01 uses SOF-001 (Scandinavian 3-seater) instead of SOF-008.

## Remaining failures (quality, not facts)

These cases still score &lt; 3.0 after the fix. Deterministic checks still pass.

| Case | Mean | Why the judge is unhappy (and why we do not “fix” it with invented SKUs) |
| --- | --- | --- |
| ADV-absent-named-product | 1.40 | Cassina LC3 / Noguchi are not in the catalogue |
| ADV-oversized-sofa | 1.80 | SOF-004 (300×170) cannot fit 240×210; substitute seating is not the named sectional |
| BR-09 | 2.00 | Same size conflict plus dining table is Dining-tagged only |
| BR-06 | 2.00 | ₹20,000 &lt; cheapest sofa ₹36,000 |
| ADV-null-price | 2.20 | CFT-004 has NULL `price_inr`; it is not sold |
| BR-08 | 2.40 | Togo sofa and Noguchi table are absent; only an Eames-style chair exists |
| BR-14 | 2.40 | Premium brief still cannot fully match “designer statement” from 72 SKUs |

**Ship recommendation:** hard factual gates pass; **do not ship as quality-complete** until average LLM quality is ≥ 4.0 or the product explicitly accepts catalogue-bound substitutions.

## Known limitations

- Layout is a rectangle/height/occupancy-≤1.0 check, not circulation or a floor plan (`docs/layout_methodology.md`).
- Style match is CSV `style_tags` equality, not embeddings.
- Must-have coverage in the harness is category-level (and case `min_coverage`), not named-SKU retrieval.
- Judge scores vary run-to-run; they never override SQLite prices, stock, or fit.
- Living Room MVP only; structural, guarantee, and other-room requests are refused by design.

## How to reproduce

```text
python -m app.evaluation.runner
```

Outputs: `evals/results/latest.json`, `evals/results/latest_summary.txt`.
