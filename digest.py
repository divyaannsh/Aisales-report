"""
Daily Exception Digest Generator for Indus Towers Operations.
Deterministic CLI script (zero LLM dependency) that extracts daily/monthly
infrastructure exceptions from the database and generates an executive digest.

Usage:
    python digest.py
"""

import os
import datetime
import pandas as pd
from db import execute_query

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def generate_daily_digest(uptime_threshold: float = 95.0, energy_overrun_pct: float = 10.0):
    """
    Extract latest month exceptions deterministically via SQL and write Markdown + CSV reports.
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 1. Determine latest month in dataset
    month_df = execute_query("SELECT MAX(month) AS latest_month FROM tower_sites;", read_only=True)
    latest_month = month_df.iloc[0]["latest_month"]
    if not latest_month:
        print("❌ Error: No records found in tower_sites.")
        return

    print(f"📊 Running Daily Exception Digest for reporting month: {latest_month} (Generated: {today_str})")

    # 2. Query total evaluated records
    total_df = execute_query(f"SELECT COUNT(*) AS total_records, COUNT(DISTINCT site_id) AS total_sites FROM tower_sites WHERE month = '{latest_month}';", read_only=True)
    total_records = int(total_df.iloc[0]["total_records"])
    total_sites = int(total_df.iloc[0]["total_sites"])

    # 3. Query SLA Breaches
    sla_sql = f"""
    SELECT circle, site_id, tenant, uptime_pct, sla_target_pct, month
    FROM tower_sites
    WHERE month = '{latest_month}' AND uptime_pct < {uptime_threshold}
    ORDER BY uptime_pct ASC;
    """
    sla_df = execute_query(sla_sql, read_only=True)

    # 4. Query Colocation Shortfalls
    coloc_sql = f"""
    SELECT circle, site_id, tenant, colocation_count, target_colocations,
           (target_colocations - colocation_count) AS colocation_gap, month
    FROM tower_sites
    WHERE month = '{latest_month}' AND colocation_count < target_colocations
    ORDER BY colocation_gap DESC;
    """
    coloc_df = execute_query(coloc_sql, read_only=True)

    # 5. Query Energy Overruns
    energy_factor = 1.0 + (energy_overrun_pct / 100.0)
    energy_sql = f"""
    SELECT circle, site_id, tenant, energy_consumption_kwh, energy_budget_kwh,
           ROUND(energy_consumption_kwh - energy_budget_kwh, 1) AS overrun_kwh,
           ROUND(((energy_consumption_kwh - energy_budget_kwh) / energy_budget_kwh) * 100, 1) AS overrun_pct,
           month
    FROM tower_sites
    WHERE month = '{latest_month}' AND energy_consumption_kwh > (energy_budget_kwh * {energy_factor})
    ORDER BY overrun_kwh DESC;
    """
    energy_df = execute_query(energy_sql, read_only=True)

    # Combine all flagged exceptions into a master CSV
    combined_sql = f"""
    SELECT circle, site_id, tenant, colocation_count, target_colocations,
           uptime_pct, sla_target_pct, energy_consumption_kwh, energy_budget_kwh, month
    FROM tower_sites
    WHERE month = '{latest_month}' AND (
        uptime_pct < {uptime_threshold}
        OR colocation_count < target_colocations
        OR energy_consumption_kwh > (energy_budget_kwh * {energy_factor})
    )
    ORDER BY circle, site_id;
    """
    master_exceptions_df = execute_query(combined_sql, read_only=True)

    # 6. Write CSV export
    csv_filename = f"digest_exceptions_{today_str}.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_filename)
    master_exceptions_df.to_csv(csv_path, index=False)

    # 7. Write Markdown digest report
    md_filename = f"digest_{today_str}.md"
    md_path = os.path.join(OUTPUT_DIR, md_filename)

    total_exceptions = len(master_exceptions_df)
    total_energy_overrun_kwh = energy_df["overrun_kwh"].sum() if not energy_df.empty else 0.0

    md_content = f"""# 🗼 Indus Towers — Daily Operations Exception Digest
**Report Date:** {today_str} | **Reporting Period:** {latest_month} | **Source:** Local SQL Database

---

## Executive Summary
- **Total Monitored Sites:** {total_sites} unique sites ({total_records} tenant allocations)
- **Total Flagged Exception Events:** {total_exceptions} ({(total_exceptions/total_records*100):.1f}% exception rate)
- **Critical SLA Uptime Breaches (< {uptime_threshold}%):** {len(sla_df)} events
- **Colocation Sharing Shortfalls:** {len(coloc_df)} sites
- **Energy Overrun Sites (> {energy_overrun_pct}% over budget):** {len(energy_df)} sites ({total_energy_overrun_kwh:,.1f} kWh total variance)

---

## 1. SLA Uptime Breaches (< {uptime_threshold}%)
"""
    if sla_df.empty:
        md_content += "\n*No SLA uptime breaches detected for the reporting period.*\n"
    else:
        md_content += "\n| Circle | Site ID | Tenant | Uptime % | Contract SLA | Deficit |\n|---|---|---|---|---|---|\n"
        for _, r in sla_df.iterrows():
            deficit = round(99.5 - r["uptime_pct"], 2)
            md_content += f"| {r['circle']} | `{r['site_id']}` | {r['tenant']} | {r['uptime_pct']:.2f}% | {r['sla_target_pct']}% | -{deficit}% |\n"

    md_content += f"\n---\n\n## 2. Colocation Shortfalls (Actual < Target)\n"
    if coloc_df.empty:
        md_content += "\n*No colocation shortfalls detected.*\n"
    else:
        md_content += "\n| Circle | Site ID | Primary Tenant | Actual Colocs | Target Colocs | Gap |\n|---|---|---|---|---|---|\n"
        for _, r in coloc_df.iterrows():
            md_content += f"| {r['circle']} | `{r['site_id']}` | {r['tenant']} | {r['colocation_count']} | {r['target_colocations']} | -{r['colocation_gap']} |\n"

    md_content += f"\n---\n\n## 3. Energy Overruns (> {energy_overrun_pct}% Over Budget)\n"
    if energy_df.empty:
        md_content += "\n*No energy overruns detected.*\n"
    else:
        md_content += "\n| Circle | Site ID | Tenant | Actual kWh | Budget kWh | Overrun (kWh) | Overrun % |\n|---|---|---|---|---|---|---|\n"
        for _, r in energy_df.iterrows():
            md_content += f"| {r['circle']} | `{r['site_id']}` | {r['tenant']} | {r['energy_consumption_kwh']:,.1f} | {r['energy_budget_kwh']:,.1f} | +{r['overrun_kwh']:,.1f} | +{r['overrun_pct']}% |\n"

    md_content += f"""
---

## Remedial Actions & Next Steps
1. **P1 SLA Breaches:** Dispatch mobile DG bowsers and OTDR fiber repair teams to affected clusters.
2. **Energy Anomalies:** Verify digital sub-meter calibration and inspect PAC cabinet cooling units.
3. **Colocation Follow-up:** Coordinate with Circle Sales Acquisition Leads on delayed secondary tenant onboarding.

*Full granular exceptions export saved to: `{csv_filename}`*
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Digest report written: {md_path}")
    print(f"✅ Exceptions CSV written: {csv_path}")
    print(f"Summary: {total_exceptions} exceptions flagged ({len(sla_df)} SLA, {len(coloc_df)} Coloc, {len(energy_df)} Energy Overrun)")


if __name__ == "__main__":
    generate_daily_digest()
