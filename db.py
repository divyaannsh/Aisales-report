"""
Database module for Indus Towers AI Exception Reporter.

Handles SQLite database creation from tower_sites.csv, schema extraction,
and query execution.
"""

import os
import sqlite3
import pandas as pd
from typing import Tuple, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales.db")
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tower_sites.csv")


def init_db(db_path: str = DB_PATH, csv_path: str = CSV_PATH) -> None:
    """
    Initialize SQLite database and load 'tower_sites' table from tower_sites.csv.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tower_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle TEXT NOT NULL,
            site_id TEXT NOT NULL,
            tenant TEXT NOT NULL,
            colocation_count INTEGER NOT NULL,
            target_colocations INTEGER NOT NULL,
            uptime_pct REAL NOT NULL,
            sla_target_pct REAL NOT NULL,
            energy_consumption_kwh REAL NOT NULL,
            energy_budget_kwh REAL NOT NULL,
            month TEXT NOT NULL
        )
    """)

    # Check row count
    cursor.execute("SELECT COUNT(*) FROM tower_sites")
    count = cursor.fetchone()[0]

    # Populate from CSV if empty
    if count == 0 and os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df.to_sql("tower_sites", conn, if_exists="append", index=False)
        conn.commit()

    conn.close()


def reset_and_reseed_db(db_path: str = DB_PATH, csv_path: str = CSV_PATH) -> None:
    """Recreate tower_sites table and load fresh records from tower_sites.csv."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS tower_sites")
    cursor.execute("DROP TABLE IF EXISTS sales")  # Drop old table if present

    cursor.execute("""
        CREATE TABLE tower_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circle TEXT NOT NULL,
            site_id TEXT NOT NULL,
            tenant TEXT NOT NULL,
            colocation_count INTEGER NOT NULL,
            target_colocations INTEGER NOT NULL,
            uptime_pct REAL NOT NULL,
            sla_target_pct REAL NOT NULL,
            energy_consumption_kwh REAL NOT NULL,
            energy_budget_kwh REAL NOT NULL,
            month TEXT NOT NULL
        )
    """)

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df.to_sql("tower_sites", conn, if_exists="append", index=False)
    else:
        # Fallback run generator if CSV missing
        from generate_tower_data import generate_tower_dataset
        df = generate_tower_dataset()
        df.to_sql("tower_sites", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()


def get_schema(db_path: str = DB_PATH) -> str:
    """Return text representation of database schema for LLM prompt context."""
    return (
        "Table: tower_sites\n"
        "Columns:\n"
        "  - circle (TEXT): Telecom circle ('Delhi', 'Mumbai', 'UP-East', 'UP-West', 'Punjab', 'Maharashtra', 'Rajasthan', 'Karnataka', 'Tamil Nadu', 'West Bengal')\n"
        "  - site_id (TEXT): Unique tower ID, format 'TWR-DEL-0101'\n"
        "  - tenant (TEXT): Telecom operator ('Airtel', 'Reliance Jio', 'Vodafone Idea', 'BSNL')\n"
        "  - colocation_count (INTEGER): Actual operator colocations at site (1 to 4)\n"
        "  - target_colocations (INTEGER): Target/planned colocations for site (1 to 4)\n"
        "  - uptime_pct (REAL): Actual site uptime percentage (e.g. 98.5, 94.2)\n"
        "  - sla_target_pct (REAL): Contracted SLA target uptime (constant 99.5)\n"
        "  - energy_consumption_kwh (REAL): Monthly energy consumption in kWh (800-2500)\n"
        "  - energy_budget_kwh (REAL): Monthly budgeted energy in kWh\n"
        "  - month (TEXT): Month in YYYY-MM format ('2026-03' through '2026-08')\n"
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
    print("Indus Towers SQLite Database initialized successfully.")
    print(get_schema())
