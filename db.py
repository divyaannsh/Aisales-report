"""
Database module for AI Sales Exception Reporter.

Handles SQLite database creation, sample data seeding, schema extraction,
and query execution for Tech Electronics Store dataset.
"""

import os
import sqlite3
import random
import pandas as pd
from typing import Tuple, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales.db")

REGIONS = ["Delhi", "Mumbai", "Bengaluru", "Hyderabad"]
PRODUCTS = ["iPhone 15", "MacBook Air", "AirPods Pro", "Samsung S24", "Sony Headphones"]
MONTHS = ["2024-03", "2024-04", "2024-05", "2024-06", "2024-07", "2024-08"]


def init_db(db_path: str = DB_PATH) -> None:
    """
    Initialize SQLite database and seed 'sales' table with realistic Tech Electronics Store data.
    4 cities x 5 products x 6 months = 120 rows.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            product TEXT NOT NULL,
            month TEXT NOT NULL,
            target_units INTEGER NOT NULL,
            actual_units INTEGER NOT NULL
        )
    """)

    # Check row count
    cursor.execute("SELECT COUNT(*) FROM sales")
    count = cursor.fetchone()[0]

    # Re-seed if empty or outdated schema
    if count == 0:
        _seed_data(cursor)
        conn.commit()

    conn.close()


def _seed_data(cursor: sqlite3.Cursor) -> None:
    """Insert 120 realistic sales performance records."""
    random.seed(42)  # Fixed seed for reproducible metrics
    seed_rows = []

    for month in MONTHS:
        for region in REGIONS:
            for product in PRODUCTS:
                # Realistic target units based on product type
                if "iPhone" in product or "MacBook" in product:
                    target = random.randint(300, 800)
                else:
                    target = random.randint(800, 2000)

                # Performance factor ranging from 0.60 to 1.25 (some target misses, some target beats)
                performance_factor = random.uniform(0.60, 1.25)
                actual = int(target * performance_factor)
                seed_rows.append((region, product, month, target, actual))

    cursor.executemany("""
        INSERT INTO sales (region, product, month, target_units, actual_units)
        VALUES (?, ?, ?, ?, ?)
    """, seed_rows)


def reset_and_reseed_db(db_path: str = DB_PATH) -> None:
    """Force recreate table and reseed fresh dataset."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS sales")
    cursor.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            product TEXT NOT NULL,
            month TEXT NOT NULL,
            target_units INTEGER NOT NULL,
            actual_units INTEGER NOT NULL
        )
    """)
    _seed_data(cursor)
    conn.commit()
    conn.close()


def get_schema(db_path: str = DB_PATH) -> str:
    """Return schema description for LLM prompt context."""
    return (
        "Table: sales\n"
        "Columns:\n"
        "  - region (TEXT): Store City location ('Delhi', 'Mumbai', 'Bengaluru', 'Hyderabad')\n"
        "  - product (TEXT): Tech product name ('iPhone 15', 'MacBook Air', 'AirPods Pro', 'Samsung S24', 'Sony Headphones')\n"
        "  - month (TEXT): Sales month in YYYY-MM format ('2024-03' to '2024-08')\n"
        "  - target_units (INTEGER): Target units planned for the month\n"
        "  - actual_units (INTEGER): Actual units sold during the month\n"
    )


def get_allowed_tables_and_columns(db_path: str = DB_PATH) -> Tuple[List[str], List[str]]:
    """Retrieve allowed table names and column names for validation layer."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    allowed_columns = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        allowed_columns.extend(columns)

    conn.close()
    return tables, list(set(allowed_columns))


def execute_query(sql: str, db_path: str = DB_PATH) -> pd.DataFrame:
    """Execute validated SELECT query and return Pandas DataFrame."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(sql, conn)
        return df
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with Tech Electronics dataset.")
    print(get_schema())
