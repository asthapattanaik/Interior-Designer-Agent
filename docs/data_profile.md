# Database Overview

**Source file:** `interior_company_catalog.db` (28,672 bytes)  
**Access mode used for profiling:** SQLite URI `mode=ro` (read-only). The database was not modified.  
**Integrity:** `PRAGMA integrity_check` returned `ok`.

This profile records what is **present in the database**. Where a later agent design would need a rule that the database does not supply, that is labelled **IMPLEMENTATION ASSUMPTION**, not a catalogue fact.

## High-level facts

| Fact from database | Value |
| --- | --- |
| User tables | `catalog`, `room_briefs` |
| Views / extra tables | none |
| Declared foreign keys | none |
| `catalog` rows | 72 |
| `room_briefs` rows | 14 |
| Living Room briefs (`room_type = 'Living Room'`) | 8 |
| Catalogue rows whose `room_types` contains `Living Room` | 44 |

There is no occupancy percentage, circulation distance, floor-plan, door, window, or wall table in the database.

---

# Tables and Schemas

## `catalog`

Schema as declared in SQLite:

| Column | Type | PK | NOT NULL | Notes from CREATE TABLE comment |
| --- | --- | --- | --- | --- |
| `item_id` | TEXT | yes | (PK) | Product identifier |
| `category` | TEXT | | yes | Product category |
| `name` | TEXT | | yes | Product name |
| `style_tags` | TEXT | | no | Comment: comma-separated style labels |
| `price_inr` | INTEGER | | no | Comment: NULL = price not yet loaded (handle gracefully) |
| `width_cm` | INTEGER | | no | |
| `depth_cm` | INTEGER | | no | |
| `height_cm` | INTEGER | | no | |
| `color_finish` | TEXT | | no | |
| `in_stock` | INTEGER | | no | Comment: 1 = in stock, 0 = out of stock |
| `lead_time_days` | INTEGER | | no | Comment: days to deliver |
| `room_types` | TEXT | | no | Comment: comma-separated room types it suits |

Indexes: primary-key autoindex only (`sqlite_autoindex_catalog_1`).

## `room_briefs`

| Column | Type | PK | NOT NULL |
| --- | --- | --- | --- |
| `brief_id` | TEXT | yes | (PK) |
| `room_type` | TEXT | | no |
| `length_cm` | INTEGER | | no |
| `width_cm` | INTEGER | | no |
| `ceiling_cm` | INTEGER | | no |
| `budget_inr` | INTEGER | | no |
| `style_preference` | TEXT | | no |
| `must_haves` | TEXT | | no |
| `constraints` | TEXT | | no |
| `customer_note` | TEXT | | no |

Indexes: primary-key autoindex only (`sqlite_autoindex_room_briefs_1`).

Row counts: `catalog` = 72, `room_briefs` = 14. No NULL values in any `room_briefs` column.

---

# Living Room Briefs

**FACT FROM DATABASE:** 8 of 14 briefs have `room_type = 'Living Room'`.  
**FACT FROM DATABASE:** All requested IDs exist and are Living Room briefs.

| brief_id | length_cm | width_cm | ceiling_cm | floor area (cm², computed) | budget_inr | style_preference |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| BR-01 | 480 | 360 | 300 | 172800 | 250000 | Scandinavian |
| BR-02 | 420 | 330 | 290 | 138600 | 150000 | Mid-Century |
| BR-05 | 300 | 240 | 280 | 72000 | 200000 | Bohemian |
| BR-06 | 450 | 360 | 300 | 162000 | 20000 | Contemporary |
| BR-07 | 500 | 400 | 300 | 200000 | 300000 | Industrial |
| BR-08 | 460 | 360 | 300 | 165600 | 260000 | Contemporary |
| BR-09 | 240 | 210 | 270 | 50400 | 180000 | Scandinavian |
| BR-14 | 520 | 380 | 310 | 197600 | 500000 | Contemporary |

Floor area is **not stored**; it is length × width from the stored centimetre fields.

### Requested brief IDs (all present)

**BR-01** — Living Room. Must-haves: 3-seater sofa, coffee table, TV unit, rug, lighting. Constraints: south-facing, lots of natural light; couple, no kids yet. Note: calm, bright living room.

**BR-02** — Living Room. Must-haves: seating for 4, TV unit, a reading corner. Constraints: rented flat, prefer freestanding (no fixed/modular work). Note: walnut tones and warm wood.

**BR-05** — Living Room. Must-haves: lots of texture, layered rugs, plants, accent seating, no TV. Constraints: warm, collected, eclectic feel. Note: not a fan of matchy-matchy sets. Room is 300 × 240 cm.

**BR-06** — Living Room. Must-haves: full living room (sofa, coffee table, TV unit, rug, lighting). Constraints: first apartment, very tight on money. Note: asks whether the whole living room can be done in this budget. **Budget is ₹20,000.**

**BR-07** — Living Room. Must-haves: open up the space and design an industrial living-dining. Constraints: want to remove the wall between kitchen and living room. Note: asks whether to knock down the kitchen wall and whether it is load-bearing.

**BR-08** — Living Room. Must-haves: a Togo sofa, a Noguchi coffee table, and an Eames lounger. Constraints: already knows the designer pieces. Note: asks to source these specific pieces. Catalogue name search for `Togo` / `Noguchi` / `Eames` finds only **ACH-001** `Eames-style Lounge Chair` — not a Togo sofa and not a Noguchi table.

**BR-09** — Living Room. Must-haves: large L-sectional, 8-seater dining table, big bookshelf. Constraints: small studio, but wants all of this in one room. Note: “Make it all fit, please.” Room is **240 × 210 × 270 cm**. Dining tables in the catalogue are tagged `Dining` only (see Catalogue Structure).

**BR-14** — Living Room. Must-haves: premium statement living room, designer sofa, art, layered lighting. Constraints: no real constraints, want it to look high-end. Budget ₹500,000.

### Other briefs (not Living Room)

These exist in the same table but are **out of MVP room scope** as product policy in the assignment README, not as a database prohibition:

| brief_id | room_type |
| --- | --- |
| BR-03 | Bedroom |
| BR-04 | Dining |
| BR-10 | Bedroom |
| BR-11 | Study |
| BR-12 | Kids |
| BR-13 | Dining |

BR-10 includes delivery-date and locked-discount-price language. That is brief text, not a catalogue capability.

---

# Catalogue Structure

**FACT FROM DATABASE:** One flat `catalog` table. Multi-valued `style_tags` and `room_types` are comma-separated text, not normalised child tables.

`room_types` distinct values and counts:

| room_types | n |
| --- | ---: |
| Living Room | 21 |
| Living Room,Bedroom | 13 |
| Bedroom | 13 |
| Dining | 9 |
| Study | 4 |
| Living Room,Study | 4 |
| Study,Living Room | 2 |
| Study,Kids | 1 |
| Living Room,Kids | 1 |
| Living Room,Dining | 1 |
| Living Room,Bedroom,Study | 1 |
| Dining,Study | 1 |
| Dining,Living Room | 1 |

**FACT FROM DATABASE:** Token order is not normalised (`Living Room,Study` vs `Study,Living Room`).  
**IMPLEMENTATION ASSUMPTION (do not treat as DB fact):** A product “belongs” to a Living Room plan iff `room_types` contains the token `Living Room`. That matching rule is an application choice; the database only stores the string.

Living Room-applicable rows (`room_types LIKE '%Living Room%'`): **44**. No other `room_types` string currently contains that substring as a false positive.

There is **no quantity column**. Some names describe packs (“pair”, “Set of 4”, “Set of 3”, “Nested … Set”). One catalogue row is one SKU; the database does not say how many physical pieces to count for layout.

---

# Product Categories

**FACT FROM DATABASE:** 26 distinct `category` values in the full catalogue.

| category | n (all rooms) | n (Living Room–tagged) | Living Room in_stock=1 | Living Room NULL price |
| --- | ---: | ---: | ---: | ---: |
| Sofa | 8 | 8 | 7 | 0 |
| Bed | 5 | 0 | — | — |
| Armchair | 4 | 4 | 4 | 0 |
| Coffee Table | 4 | 4 | 4 | 1 |
| Dining Chair | 4 | 0 | — | — |
| Dining Table | 4 | 0 | — | — |
| Rug | 4 | 4 | 4 | 1 |
| Bookshelf | 3 | 2 | 2 | 0 |
| Curtains | 3 | 2 | 2 | 0 |
| Pendant Light | 3 | 1 | 1 | 0 |
| TV Unit | 3 | 3 | 3 | 0 |
| Wall Art | 3 | 3 | 3 | 1 |
| Wardrobe | 3 | 0 | — | — |
| Bedside Table | 2 | 0 | — | — |
| Console | 2 | 2 | 1 | 0 |
| Desk | 2 | 0 | — | — |
| Floor Lamp | 2 | 2 | 2 | 0 |
| Mattress | 2 | 0 | — | — |
| Office Chair | 2 | 0 | — | — |
| Ottoman | 2 | 2 | 2 | 0 |
| Side Table | 2 | 2 | 2 | 0 |
| Bean Bag | 1 | 1 | 1 | 0 |
| Cushions | 1 | 1 | 1 | 0 |
| Mirror | 1 | 1 | 1 | 0 |
| Planter | 1 | 1 | 1 | 0 |
| Table Lamp | 1 | 1 | 1 | 0 |

Living Room–tagged categories: Armchair, Bean Bag, Bookshelf, Coffee Table, Console, Curtains, Cushions, Floor Lamp, Mirror, Ottoman, Pendant Light, Planter, Rug, Side Table, Sofa, TV Unit, Table Lamp, Wall Art.

**FACT FROM DATABASE:** Dining Table / Dining Chair rows have `room_types` of `Dining` (or Dining plus Study), not Living Room.  
**IMPLEMENTATION ASSUMPTION (do not make yet):** That BR-09 can be fulfilled with dining SKUs because the brief text asks for an 8-seater dining table.

---

# Styles

**FACT FROM DATABASE:** Styles live in:

1. `catalog.style_tags` (comma-separated; a product can have several tags)
2. `room_briefs.style_preference` (a single string)

Tag occurrence counts across 72 products (a product with two tags increments both):

| tag | product occurrences |
| --- | ---: |
| Contemporary | 24 |
| Minimalist | 20 |
| Scandinavian | 18 |
| Bohemian | 15 |
| Traditional | 12 |
| Industrial | 10 |
| Coastal | 9 |
| Mid-Century | 7 |
| Japandi | 1 |
| (empty string) | 2 rows (`MAT-001`, `MAT-002`) |

Brief `style_preference` values: Bohemian (1), Coastal (1), Contemporary (5), Industrial (2), Mid-Century (1), Minimalist (1), Scandinavian (2), Traditional (1).

**FACT FROM DATABASE:** Matching a brief style to products is not encoded as a foreign key.  
**IMPLEMENTATION ASSUMPTION (do not make yet):** Exact tag equality, synonym mapping, or “Japandi ≈ Scandinavian” rules.

---

# Pricing

**FACT FROM DATABASE:** The only price field is `catalog.price_inr` (INTEGER, nullable).

| Statistic | Value |
| --- | --- |
| Non-NULL prices | 67 |
| NULL prices | 5 |
| Price = 0 | 0 |
| Price < 0 | 0 |
| Min (non-NULL) | 3200 |
| Max (non-NULL) | 280000 |
| Average (non-NULL) | ≈ 36654 |

### NULL prices

| item_id | category | name | in_stock | room_types |
| --- | --- | --- | --- | --- |
| ART-003 | Wall Art | Vintage Botanical Prints | 1 | Living Room,Bedroom |
| BKS-003 | Bookshelf | Modular Cube Storage | 1 | Study,Kids |
| CFT-004 | Coffee Table | Live-Edge Slab Table | 1 | Living Room |
| DNT-004 | Dining Table | Carved 8-Seater Banquet | 0 | Dining |
| RUG-003 | Rug | Vintage Persian-style 5x7 | 1 | Living Room,Study |

CREATE TABLE comment: `NULL = price not yet loaded (handle gracefully)`.

**FACT FROM DATABASE:** Four of five NULL-price rows have `in_stock = 1`.  
**IMPLEMENTATION ASSUMPTION (must NOT make):** NULL price means the product is unavailable, unsellable, or free.

Edge cases:

- Priced and out of stock (e.g. SOF-006 at ₹280,000, `in_stock = 0`)
- NULL price and in stock (CFT-004, RUG-003, ART-003)
- NULL price and out of stock (DNT-004)
- BR-06 budget ₹20,000 vs cheapest sofa **SOF-008** at ₹36,000 (FACT: those two numbers exist; FACT does not decide the commercial policy)

---

# Stock / Availability

**FACT FROM DATABASE:** Availability is `catalog.in_stock` INTEGER. Observed values: `1` (66 rows), `0` (6 rows), no NULLs. Schema comment: `1 = in stock, 0 = out of stock`.

Out of stock:

| item_id | category | name | price_inr | lead_time_days | room_types |
| --- | --- | --- | --- | --- | --- |
| BED-005 | Bed | Storage Hydraulic Queen Bed | 81000 | 90 | Bedroom |
| CHR-002 | Office Chair | Leather Executive Chair | 26000 | 40 | Study |
| CON-002 | Console | Carved Wood Console | 33000 | 55 | Living Room |
| DNT-004 | Dining Table | Carved 8-Seater Banquet | NULL | 70 | Dining |
| SOF-006 | Sofa | Maison Premium L-Sofa (Italian) | 280000 | 120 | Living Room |
| WRD-003 | Wardrobe | Open Wardrobe System | 54000 | 60 | Bedroom |

Living Room–tagged out of stock: **SOF-006**, **CON-002**.

There is **no inventory quantity**, warehouse, or timestamp.

**IMPLEMENTATION ASSUMPTION (must NOT make):** `in_stock` is real-time inventory, reservation state, or a sellable-unit count.  
**FACT FROM DATABASE:** Out-of-stock rows still have non-NULL `lead_time_days`. Do not infer that a lead time means the item can be sold now.

---

# Product Dimensions

**FACT FROM DATABASE:** Product size fields are `width_cm`, `depth_cm`, `height_cm`. All 72 rows have all three populated; none are 0 or NULL.

Observed ranges (full catalogue):

| category examples | width_cm | depth_cm | height_cm |
| --- | --- | --- | --- |
| Sofa | 150–340 | 85–200 | 70–84 |
| Coffee Table | 90–130 | 50–70 | 40–45 |
| Rug | 180–270 | 120–180 | 1–2 |
| Curtains | 140–150 | 1 | 270–280 |
| Wall Art | 90–180 | 2–3 | 40–60 |
| Mirror | 80 | 3 | 120 |
| Floor Lamp | 40–55 | 40–55 | 160–200 |
| TV Unit | 160–200 | 40–45 | 35–55 |

Largest Living Room sofas:

- SOF-004 Marrakech Modular Sectional: 300 × 170 × 78 cm, ₹178,000, in stock
- SOF-006 Maison Premium L-Sofa: 340 × 200 × 76 cm, ₹280,000, **out of stock**

**FACT FROM DATABASE:** The columns do not say which axis is along a wall, whether L-sectionals use a bounding box, or whether rug/curtain/art dimensions are floor footprints.

**IMPLEMENTATION ASSUMPTION (do not design yet):** Treating every `width_cm × depth_cm` as additive floor occupancy, ignoring rugs (height 1–2 cm) or wall-hung items (depth 2–3 cm), or using any occupancy percentage.

---

# Room Dimensions

**FACT FROM DATABASE:** Room size fields are on `room_briefs`: `length_cm`, `width_cm`, `ceiling_cm`. All 14 briefs have all three set. There is no unit column; values are consistent with centimetres (names and CREATE TABLE).

Living Room floor sizes range from BR-09 (240 × 210 cm) to BR-07 (500 × 400 cm). Ceilings: 270–310 cm.

CUR-003 velvet drapes have `height_cm = 280`. BR-09 `ceiling_cm = 270`. Those two numbers coexist; the database does not define a hang-clearance rule.

---

# Spatial Data

**FACT FROM DATABASE — what exists**

- Product box: `width_cm`, `depth_cm`, `height_cm`
- Room box: `length_cm`, `width_cm`, `ceiling_cm`
- Category and name text that sometimes imply shape (sectional, nested set, pair)

**FACT FROM DATABASE — what does not exist**

- No layout / placement / CAD tables
- No door, window, opening, or wall-segment columns
- No circulation, clearance, occupancy, or aisle fields
- No furniture quantity for layout
- No 55% occupancy or 75 cm circulation value anywhere in the schema or rows
- No orientation, collision, or adjacency data
- `PRAGMA foreign_keys` is off and no FKs are declared

This document only records availability of data. It does **not** choose a spatial algorithm.

---

# Data Quality Issues

1. **Multi-value CSV fields** (`style_tags`, `room_types`) instead of relational tags. Token order varies.
2. **NULL `price_inr` on in-stock Living Room items** (CFT-004, RUG-003, ART-003). Budget math cannot use them without a policy.
3. **`in_stock` is a binary flag**, not quantity or live inventory. Lead times remain populated when `in_stock = 0`.
4. **Empty `style_tags`** on both mattresses (not Living Room–tagged, but shows tags are not always present).
5. **Pack SKUs** (curtain pair, cushion set, nested tables, art set) share one dimension triple.
6. **Dimension semantics differ by category** (rugs, curtains, wall art vs sofas). Naive sum of all footprints would be misleading.
7. **L-sectional bounding boxes** (SOF-004 300×170, SOF-006 340×200) vs small rooms (BR-09 240×210).
8. **Named designer pieces in BR-08 are mostly absent.** Only an “Eames-style” chair exists.
9. **Dining SKUs are not tagged Living Room**, while BR-07/BR-09 text asks for living-dining mixes.
10. **No link** from a brief to catalogue items.
11. **Schema comments** (NULL price meaning, in_stock encoding) are documentation in DDL, not enforced CHECK constraints.
12. **Japandi** appears on one product tag; no brief uses that preference string.

---

# Implications for Agent Design

## What the database enables deterministically

Given an `item_id`, code can load: identity, category, name, style tag string, `price_inr` (or NULL), three dimensions, `color_finish`, `in_stock`, `lead_time_days`, `room_types`.

Given a `brief_id`, code can load: room type, room rectangle, ceiling, budget, style preference, must-haves, constraints, customer note.

Deterministic operations that **do not require an LLM**:

- Confirm a product exists
- Filter by category
- Parse comma-separated `room_types` / `style_tags` with an explicit matching rule
- Exclude or flag `in_stock = 0` **if** the product policy is “only in-stock flags”
- Sum `price_inr * quantity` **only when** every selected price is non-NULL and quantity is supplied by the plan (quantity is not in the DB)
- Compare product `width_cm`/`depth_cm`/`height_cm` to room `length_cm`/`width_cm`/`ceiling_cm` as raw numbers
- Detect missing prices before claiming a total

## What is missing (cannot be read from SQLite)

- Any occupancy or circulation standard
- Floor-plan geometry, doors, windows, load-bearing walls
- How to interpret NULL price for selling
- Whether stock is current
- Line-item quantity defaults
- Whether dining furniture may be used in a Living Room brief
- Whether rugs/art/curtains occupy floor area
- Delivery-date or price-lock guarantees (BR-10 text vs no such catalogue fields)
- Structural/engineering answers (BR-07)

The LLM may interpret must-haves and constraints **as language**. It must not invent IDs, prices, stock, or dimensions.

---

# Open Questions / Assumptions

| Topic | FACT FROM DATABASE | Must NOT assume yet |
| --- | --- | --- |
| Occupancy | No occupancy field or threshold | 55% furniture occupancy |
| Circulation | No circulation field | 75 cm (or any) clearance |
| NULL price | 5 NULL `price_inr` values; DDL comment says price not yet loaded | NULL means unavailable / free / do-not-show |
| Stock | `in_stock` ∈ {0, 1} | Real-time inventory or sellable qty |
| Living Room suitability | `room_types` text includes or excludes `Living Room` | A product is suitable because the customer asked, or because the category “sounds like” living-room furniture |
| Dining in living room | Dining tables tagged `Dining` only | Auto-include dining SKUs for BR-07 / BR-09 |
| Spatial algorithm | Boxes for products and rooms exist | A specific fit heuristic, stacking, or CAD-like placement |
| Quantity | No quantity column | Default qty = 1 is a catalogue fact (it would be an app default) |
| Lead time | Integer days on every row | Guaranteed delivery; orderable when out of stock |
| Eames / Togo / Noguchi | Only `Eames-style Lounge Chair` | That SKU satisfies BR-08’s named pieces |
| Style match | Tags and preferences are independent strings | Fuzzy style equivalence |

---

# How this profile was produced

- Read-only inspection of `interior_company_catalog.db`
- Reusable script: `scripts/profile_database.py`
- Run: `python scripts/profile_database.py` (optional `--db-path` or `CATALOG_DB_PATH`)
