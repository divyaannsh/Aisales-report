"""
Database module for Indus Towers AI Exception Reporter.

Handles SQLite database creation from tower_sites.csv, schema extraction,
read-only query execution, and query audit logging.
"""

import os
import time
import json
import sqlite3
import datetime
import pandas as pd
from typing import Tuple, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales.db")
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tower_sites.csv")
AUDIT_LOG_JSONL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_log.jsonl")


def init_db(db_path: str = DB_PATH, csv_path: str = CSV_PATH) -> None:
    """
    Initialize SQLite database, load 'tower_sites' from CSV, and create audit log table.
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

    # Audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_question TEXT NOT NULL,
            generated_sql TEXT NOT NULL,
            is_valid INTEGER NOT NULL,
            validation_msg TEXT,
            rows_returned INTEGER,
            execution_time_ms REAL,
            finish_reason TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE query_audit_log ADD COLUMN finish_reason TEXT DEFAULT 'stop'")
        conn.commit()
    except Exception:
        pass

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
    cursor.execute("DROP TABLE IF EXISTS sales")  # Drop old legacy table

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
        "  - uptime_pct (REAL): Actual site uptime percentage (e.g. 99.8, 93.5)\n"
        "  - sla_target_pct (REAL): Contracted SLA target uptime (constant 99.5)\n"
        "  - energy_consumption_kwh (REAL): Monthly energy consumption in kWh (800-2500)\n"
        "  - energy_budget_kwh (REAL): Monthly budgeted energy in kWh\n"
        "  - month (TEXT): Month in YYYY-MM format ('2026-03' through '2026-08')\n"
    )


def get_allowed_tables_and_columns(db_path: str = DB_PATH) -> Tuple[List[str], List[str]]:
    """Retrieve allowed table names and column names for validation layer (excluding internal audit tables)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    all_tables = [row[0] for row in cursor.fetchall()]
    # Exclude internal audit log from user queryable tables
    tables = [t for t in all_tables if t not in ("query_audit_log", "sales")]

    allowed_columns = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        allowed_columns.extend(columns)

    conn.close()
    return tables, list(set(allowed_columns))


def execute_query(sql: str, db_path: str = DB_PATH, read_only: bool = True) -> pd.DataFrame:
    """
    Execute SELECT query and return Pandas DataFrame.
    By default connects via SQLite URI 'file:sales.db?mode=ro' to enforce
    operating system-level read-only security against write mutations.
    """
    if read_only:
        # Enforce read-only at the database engine level
        conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_path)

    try:
        df = pd.read_sql_query(sql, conn)
        return df
    finally:
        conn.close()


def log_query_audit(
    user_question: str,
    generated_sql: str,
    is_valid: bool,
    validation_msg: str,
    rows_returned: int = 0,
    execution_time_ms: float = 0.0,
    finish_reason: str = "stop",
    db_path: str = DB_PATH,
    jsonl_path: str = AUDIT_LOG_JSONL
) -> None:
    """Record query execution audit entry in both SQLite table and JSONL file."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 1. Append to JSONL log
    audit_record = {
        "timestamp": now_iso,
        "user_question": user_question,
        "generated_sql": generated_sql,
        "is_valid": is_valid,
        "validation_msg": validation_msg,
        "rows_returned": rows_returned,
        "execution_time_ms": round(execution_time_ms, 2),
        "finish_reason": finish_reason
    }
    try:
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_record) + "\n")
    except Exception:
        pass

    # 2. Append to SQLite audit table
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO query_audit_log (
                timestamp, user_question, generated_sql, is_valid,
                validation_msg, rows_returned, execution_time_ms, finish_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_iso, user_question, generated_sql, 1 if is_valid else 0,
            validation_msg, rows_returned, execution_time_ms, finish_reason
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_recent_audit_logs(limit: int = 15, db_path: str = DB_PATH) -> pd.DataFrame:
    """Retrieve recent query audit log entries for display in security dashboard."""
    conn = sqlite3.connect(db_path)
    try:
        query = f"""
            SELECT timestamp, user_question, generated_sql, is_valid, validation_msg, rows_returned, execution_time_ms, finish_reason
            FROM query_audit_log
            ORDER BY id DESC
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Indus Towers SQLite Database initialized successfully.")
    print("Read-only test:")
    df_test = execute_query("SELECT COUNT(*) AS total_rows FROM tower_sites;", read_only=True)
    print("Result:", df_test.to_dict(orient="records"))
