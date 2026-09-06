"""Read-only SQLite catalogue profiler for STEP 1.

Does not modify the database. Prints schema, counts, Living Room
briefs/products, pricing, stock, dimensions, and data-quality notes.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

KNOWN_BRIEF_IDS = (
    "BR-01",
    "BR-02",
    "BR-05",
    "BR-06",
    "BR-07",
    "BR-08",
    "BR-09",
    "BR-14",
)

DEFAULT_DB = Path(__file__).resolve().parents[1] / "interior_company_catalog.db"


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def quote_ident(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_row(row: sqlite3.Row) -> None:
    print(dict(row))


def list_user_tables(cur: sqlite3.Cursor) -> list[str]:
    rows = cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [r["name"] for r in rows]


def split_csv(value: str | None) -> list[str]:
    if value is None or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def profile(db_path: Path) -> int:
    conn = connect_readonly(db_path)
    cur = conn.cursor()

    print_header("Database")
    print(f"path: {db_path.resolve()}")
    print(f"size_bytes: {db_path.stat().st_size}")
    print(f"integrity_check: {cur.execute('PRAGMA integrity_check').fetchone()[0]}")
    print(f"foreign_keys pragma: {cur.execute('PRAGMA foreign_keys').fetchone()[0]}")
    print("note: opened with mode=ro; this script does not write to the DB")

    print_header("sqlite_master")
    for row in cur.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
    ):
        print_row(row)

    tables = list_user_tables(cur)
    print_header("Tables")
    print(f"user_tables: {tables}")

    print_header("Schemas, indexes, foreign keys, row counts")
    for table in tables:
        qtable = quote_ident(table)
        print(f"\n--- {table} ---")
        cols = list(cur.execute(f"PRAGMA table_info({qtable})"))
        for col in cols:
            print(
                "  column:"
                f" cid={col['cid']} name={col['name']} type={col['type']}"
                f" notnull={col['notnull']} default={col['dflt_value']} pk={col['pk']}"
            )
        fks = list(cur.execute(f"PRAGMA foreign_key_list({qtable})"))
        print(f"  foreign_keys: {len(fks)}")
        for fk in fks:
            print_row(fk)
        indexes = list(cur.execute(f"PRAGMA index_list({qtable})"))
        for idx in indexes:
            print_row(idx)
        n = cur.execute(f"SELECT COUNT(*) AS n FROM {qtable}").fetchone()["n"]
        print(f"  row_count: {n}")

    if "room_briefs" in tables:
        print_header("Room types in room_briefs")
        for row in cur.execute(
            """
            SELECT room_type, COUNT(*) AS n
            FROM room_briefs
            GROUP BY room_type
            ORDER BY n DESC, room_type
            """
        ):
            print_row(row)

        print_header("Living Room briefs")
        lr_briefs = list(
            cur.execute(
                """
                SELECT *
                FROM room_briefs
                WHERE room_type = 'Living Room'
                ORDER BY brief_id
                """
            )
        )
        print(f"living_room_brief_count: {len(lr_briefs)}")
        for row in lr_briefs:
            print_row(row)

        print_header("Requested brief IDs")
        for brief_id in KNOWN_BRIEF_IDS:
            row = cur.execute(
                "SELECT * FROM room_briefs WHERE brief_id = ?", (brief_id,)
            ).fetchone()
            if row is None:
                print(f"{brief_id}: NOT FOUND")
            else:
                print(f"{brief_id}: present; room_type={row['room_type']}")
                print_row(row)

        print_header("room_briefs null counts")
        cols = [r["name"] for r in cur.execute("PRAGMA table_info(room_briefs)")]
        for col in cols:
            n = cur.execute(
                f"SELECT COUNT(*) AS n FROM room_briefs WHERE {quote_ident(col)} IS NULL"
            ).fetchone()["n"]
            print(f"  {col}: {n} NULL")

    if "catalog" in tables:
        print_header("Catalogue categories")
        for row in cur.execute(
            """
            SELECT category, COUNT(*) AS n
            FROM catalog
            GROUP BY category
            ORDER BY category
            """
        ):
            print_row(row)

        print_header("Catalogue room_types values")
        for row in cur.execute(
            """
            SELECT room_types, COUNT(*) AS n
            FROM catalog
            GROUP BY room_types
            ORDER BY n DESC, room_types
            """
        ):
            print_row(row)

        print_header("Living Room catalogue products")
        lr_like = list(
            cur.execute(
                """
                SELECT *
                FROM catalog
                WHERE room_types LIKE '%Living Room%'
                ORDER BY category, item_id
                """
            )
        )
        print(f"living_room_like_count: {len(lr_like)}")
        for row in lr_like:
            print_row(row)

        print_header("Living Room categories")
        for row in cur.execute(
            """
            SELECT
                category,
                COUNT(*) AS n,
                SUM(CASE WHEN in_stock = 1 THEN 1 ELSE 0 END) AS in_stock_n,
                SUM(CASE WHEN price_inr IS NULL THEN 1 ELSE 0 END) AS null_price_n
            FROM catalog
            WHERE room_types LIKE '%Living Room%'
            GROUP BY category
            ORDER BY category
            """
        ):
            print_row(row)

        print_header("Style tags (split on comma)")
        tag_counts: Counter[str] = Counter()
        empty_style = 0
        for row in cur.execute("SELECT item_id, style_tags FROM catalog"):
            tags = split_csv(row["style_tags"])
            if not tags:
                empty_style += 1
                continue
            for tag in tags:
                tag_counts[tag] += 1
        print(f"rows_with_empty_style_tags: {empty_style}")
        for tag, n in tag_counts.most_common():
            print(f"  {tag}: {n}")

        print_header("Pricing")
        stats = cur.execute(
            """
            SELECT
                COUNT(*) AS n,
                SUM(CASE WHEN price_inr IS NULL THEN 1 ELSE 0 END) AS null_n,
                SUM(CASE WHEN price_inr = 0 THEN 1 ELSE 0 END) AS zero_n,
                SUM(CASE WHEN price_inr < 0 THEN 1 ELSE 0 END) AS negative_n,
                MIN(price_inr) AS min_price,
                MAX(price_inr) AS max_price,
                AVG(price_inr) AS avg_price
            FROM catalog
            """
        ).fetchone()
        print_row(stats)
        print("NULL price rows:")
        for row in cur.execute(
            """
            SELECT item_id, category, name, price_inr, in_stock, room_types
            FROM catalog
            WHERE price_inr IS NULL
            ORDER BY item_id
            """
        ):
            print_row(row)

        print_header("Stock / availability")
        for row in cur.execute(
            """
            SELECT in_stock, COUNT(*) AS n
            FROM catalog
            GROUP BY in_stock
            ORDER BY in_stock
            """
        ):
            print_row(row)
        print("in_stock = 0 or NULL rows:")
        for row in cur.execute(
            """
            SELECT item_id, category, name, price_inr, in_stock, lead_time_days, room_types
            FROM catalog
            WHERE in_stock IS NULL OR in_stock = 0
            ORDER BY item_id
            """
        ):
            print_row(row)

        print_header("Product dimensions")
        for col in ("width_cm", "depth_cm", "height_cm"):
            row = cur.execute(
                f"""
                SELECT
                    SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS null_n,
                    SUM(CASE WHEN {col} = 0 THEN 1 ELSE 0 END) AS zero_n,
                    MIN({col}) AS min_v,
                    MAX({col}) AS max_v
                FROM catalog
                """
            ).fetchone()
            print(f"{col}: {dict(row)}")
        print("per-category dimension ranges:")
        for row in cur.execute(
            """
            SELECT
                category,
                COUNT(*) AS n,
                MIN(width_cm) AS min_w, MAX(width_cm) AS max_w,
                MIN(depth_cm) AS min_d, MAX(depth_cm) AS max_d,
                MIN(height_cm) AS min_h, MAX(height_cm) AS max_h
            FROM catalog
            GROUP BY category
            ORDER BY category
            """
        ):
            print_row(row)

        print_header("Lead time")
        for row in cur.execute(
            """
            SELECT lead_time_days, COUNT(*) AS n
            FROM catalog
            GROUP BY lead_time_days
            ORDER BY lead_time_days
            """
        ):
            print_row(row)
        lt = cur.execute(
            """
            SELECT
                MIN(lead_time_days) AS min_d,
                MAX(lead_time_days) AS max_d,
                SUM(CASE WHEN lead_time_days IS NULL THEN 1 ELSE 0 END) AS null_n
            FROM catalog
            """
        ).fetchone()
        print(f"lead_time_days summary: {dict(lt)}")

        print_header("Quantity fields")
        catalog_cols = {r["name"] for r in cur.execute("PRAGMA table_info(catalog)")}
        brief_cols = (
            {r["name"] for r in cur.execute("PRAGMA table_info(room_briefs)")}
            if "room_briefs" in tables
            else set()
        )
        qty_like = {
            c
            for c in catalog_cols | brief_cols
            if "qty" in c.lower() or "quantity" in c.lower()
        }
        print(f"quantity-like columns: {sorted(qty_like) or 'NONE'}")

        print_header("Spatial / layout columns")
        spatial_hints = (
            "layout",
            "placement",
            "door",
            "window",
            "wall",
            "circulation",
            "occupancy",
            "clearance",
            "position",
            "footprint",
            "area",
        )
        all_cols = catalog_cols | brief_cols
        hinted = [c for c in sorted(all_cols) if any(h in c.lower() for h in spatial_hints)]
        print(f"columns with spatial-ish names: {hinted or 'NONE'}")
        print(
            "present dimension-like columns:"
            f" {[c for c in sorted(all_cols) if c.endswith('_cm') or 'length' in c or 'width' in c or 'height' in c or 'depth' in c or 'ceiling' in c]}"
        )

    print_header("Relationships")
    print("Declared foreign keys: none (PRAGMA foreign_key_list empty on both tables).")
    print("No join table between room_briefs and catalog.")

    conn.close()
    print_header("Done")
    print("FACT: profiling completed in read-only mode.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile interior_company_catalog.db")
    parser.add_argument(
        "--db-path",
        default=os.environ.get("CATALOG_DB_PATH", str(DEFAULT_DB)),
        help="Path to SQLite database (or set CATALOG_DB_PATH)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return profile(Path(args.db_path))
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
