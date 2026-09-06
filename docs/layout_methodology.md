# Layout / Fit Methodology (STEP 7)

This is an **MVP assumption document**, not an Interior Company rule, building
code, or architectural standard.

## Spatial data used (facts from the database)

- Products: `width_cm`, `depth_cm`, `height_cm` (all catalogue rows currently populated)
- Rooms: `length_cm`, `width_cm`, `ceiling_cm`

## Spatial data not used because it does not exist

- Doors, windows, walls as segments, placement, adjacency
- Circulation / clearance distances
- Occupancy percentage stored in the catalogue
- Furniture quantity on catalogue rows

**Circulation is not calculated.** There is no placement data that would make a
75 cm (or any) aisle width measurable.

## Checks performed

1. **Plan rectangle:** each floor-standing item and rug must fit in the room
   rectangle. **MVP assumption:** 90° rotation in plan is allowed.
2. **Height:** `height_cm` must be `<= ceiling_cm`.
3. **Occupancy ratio:** sum of floor-standing `width_cm * depth_cm * quantity`
   divided by `length_cm * width_cm`.
4. **Default occupancy cap = 1.00** (summed footprints cannot exceed the room).
   This is **not** a 55% furnishing standard. It is configurable via
   `LayoutConfig.max_occupancy_ratio`.
5. **Category roles (MVP assumption):** sofas/tables/etc. occupy floor;
   rugs are floor covering (checked for size, excluded from occupancy);
   curtains/art/mirrors are wall; pendants are ceiling; cushions and table
   lamps are accessories.

Missing dimensions are not invented: the item is listed as blocking and
explained in warnings.
