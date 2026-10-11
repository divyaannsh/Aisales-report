"""
test_validator.py — Direct unit tests for validate.py.
No LLM involved. Calls validate_sql() with hand-crafted inputs.
Run with: python test_validator.py
"""

import sys
import os

# Ensure the module is importable from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from validate import validate_sql

# ------------------------------------------------------------------
# Test schema fixture (mirrors production schema)
# ------------------------------------------------------------------
ALLOWED_TABLES = ["tower_sites"]
ALLOWED_COLUMNS = [
    "circle", "site_id", "tenant", "colocation_count", "target_colocations",
    "uptime_pct", "sla_target_pct", "energy_consumption_kwh",
    "energy_budget_kwh", "month"
]

_pass_count = 0
_fail_count = 0
_cases = []


def _check(label: str, sql: str, expect_valid: bool, note: str = ""):
    """Run one test case and record result."""
    global _pass_count, _fail_count
    ok, msg = validate_sql(sql, ALLOWED_COLUMNS, ALLOWED_TABLES)
    passed = (ok == expect_valid)
    if passed:
        _pass_count += 1
    else:
        _fail_count += 1
    status = "PASS" if passed else "FAIL"
    expected_label = "VALID" if expect_valid else "BLOCKED"
    direction = "got BLOCKED" if not ok else "got VALID"
    detail = f"[{status}] {label!r}" + (f" | note: {note}" if note else "")
    if not passed:
        detail += f"\n      Validator said: {msg!r}"
    _cases.append((passed, detail))


# ==================== MUST-BLOCK CASES ====================

_check(
    "DELETE statement",
    "DELETE FROM tower_sites WHERE circle = 'Delhi'",
    expect_valid=False
)

_check(
    "DROP TABLE statement",
    "DROP TABLE tower_sites",
    expect_valid=False
)

_check(
    "UPDATE statement",
    "UPDATE tower_sites SET uptime_pct = 100 WHERE circle = 'Delhi'",
    expect_valid=False
)

_check(
    "INSERT statement",
    "INSERT INTO tower_sites (circle) VALUES ('Delhi')",
    expect_valid=False
)

_check(
    "Multi-statement with semicolon",
    "SELECT * FROM tower_sites; DROP TABLE tower_sites",
    expect_valid=False
)

_check(
    "SQL comment -- injection",
    "SELECT * FROM tower_sites -- drop table tower_sites",
    expect_valid=False
)

_check(
    "SQL block comment /* */",
    "SELECT * FROM tower_sites /* malicious */",
    expect_valid=False
)

_check(
    "Unknown column (revenue)",
    "SELECT circle, revenue FROM tower_sites WHERE circle = 'Delhi'",
    expect_valid=False
)

_check(
    "Unknown table (sales_data)",
    "SELECT * FROM sales_data WHERE circle = 'Delhi'",
    expect_valid=False
)

_check(
    "Truncated: SELECT COUNT(*) AS c (no FROM)",
    "SELECT COUNT(*) AS c",
    expect_valid=False,
    note="No FROM clause at all"
)

_check(
    "Truncated: ends with AND",
    "SELECT * FROM tower_sites WHERE circle = 'Delhi' AND",
    expect_valid=False,
    note="Dangling AND at end"
)

_check(
    "Truncated: ends with WHERE",
    "SELECT * FROM tower_sites WHERE",
    expect_valid=False,
    note="Dangling WHERE at end"
)

_check(
    "Truncated: ends with comma",
    "SELECT circle, site_id, FROM tower_sites WHERE circle = 'Delhi'",
    expect_valid=False,
    note="Trailing comma before FROM — SQLite parse will catch this"
)

_check(
    "Unknown column (profit_margin)",
    "SELECT circle, site_id, profit_margin FROM tower_sites",
    expect_valid=False
)

_check(
    "Unknown column (revenue) in GROUP BY query",
    "SELECT circle, SUM(revenue) FROM tower_sites GROUP BY circle",
    expect_valid=False
)

# ==================== MUST-PASS CASES ====================

_check(
    "COUNT(*) aggregate — no alias",
    "SELECT COUNT(*) FROM tower_sites WHERE circle = 'Delhi'",
    expect_valid=True
)

_check(
    "COUNT(*) aggregate — with alias",
    "SELECT COUNT(*) AS total_count FROM tower_sites WHERE circle = 'Delhi'",
    expect_valid=True
)

_check(
    "AVG aggregate with alias",
    "SELECT AVG(uptime_pct) AS avg_uptime FROM tower_sites WHERE circle = 'Mumbai' AND month = '2026-08'",
    expect_valid=True
)

_check(
    "SUM aggregate GROUP BY",
    "SELECT circle, SUM(energy_consumption_kwh) AS total_energy FROM tower_sites WHERE month = '2026-08' GROUP BY circle",
    expect_valid=True
)

_check(
    "ORDER BY ASC with LIMIT",
    "SELECT site_id, circle, tenant, uptime_pct FROM tower_sites WHERE month = '2026-08' ORDER BY uptime_pct ASC LIMIT 5",
    expect_valid=True
)

_check(
    "OR condition inside parentheses",
    "SELECT circle, site_id, tenant FROM tower_sites WHERE circle = 'Karnataka' AND (tenant = 'Airtel' OR tenant = 'Reliance Jio')",
    expect_valid=True
)

_check(
    "Multi-column filter with IN()",
    "SELECT site_id, tenant, uptime_pct FROM tower_sites WHERE tenant IN ('Airtel', 'Reliance Jio') AND month = '2026-08'",
    expect_valid=True
)

_check(
    "Energy budget comparison",
    "SELECT circle, site_id, energy_consumption_kwh, energy_budget_kwh FROM tower_sites WHERE energy_consumption_kwh > energy_budget_kwh AND month = '2026-07'",
    expect_valid=True
)

_check(
    "Colocation shortfall filter",
    "SELECT circle, site_id, colocation_count, target_colocations FROM tower_sites WHERE colocation_count < target_colocations",
    expect_valid=True
)

_check(
    "COUNT(DISTINCT site_id) with alias",
    "SELECT COUNT(DISTINCT site_id) AS unique_sites FROM tower_sites WHERE circle = 'UP-East'",
    expect_valid=True
)

# ------------------------------------------------------------------
# Final report
# ------------------------------------------------------------------
print("=" * 60)
print(f"  TowerPulse Validator Unit Tests — {_pass_count + _fail_count} cases")
print("=" * 60)

for passed, detail in _cases:
    print(detail)

print("-" * 60)
print(f"  PASSED: {_pass_count}  |  FAILED: {_fail_count}  |  TOTAL: {_pass_count + _fail_count}")
print("=" * 60)

if _fail_count > 0:
    sys.exit(1)
