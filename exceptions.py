"""
Exception detection module for Indus Towers AI Exception Reporter.

Flags telecom tower infrastructure exceptions across 3 business vectors:
1. SLA Uptime Breaches (e.g., Uptime < 95.0% or < 99.5% contract SLA)
2. Colocation Shortfalls (Actual Tenants < Target Tenants)
3. Energy Overruns (Consumption > Budget * Overrun Threshold)
"""

import pandas as pd
from typing import Tuple


def flag_exceptions(
    df: pd.DataFrame,
    exception_type: str = "All Exceptions",
    uptime_sla_threshold: float = 95.0,
    energy_overrun_pct: float = 10.0
) -> pd.DataFrame:
    """
    Filter DataFrame to return only rows matching telecom tower exception rules.

    Parameters:
        df: Input pandas DataFrame from SQL query execution.
        exception_type: Filter category ('All Exceptions', 'SLA Uptime Breach', 'Colocation Shortfall', 'Energy Overrun').
        uptime_sla_threshold: Uptime breach threshold percentage (default 95.0%).
        energy_overrun_pct: Energy overrun budget buffer percentage (default 10.0% overrun).

    Returns:
        Filtered DataFrame with added exception diagnostic metric columns.
    """
    if df.empty:
        return df

    df_copy = df.copy()

    # Identify columns
    has_uptime = "uptime_pct" in df_copy.columns and ("sla_target_pct" in df_copy.columns or uptime_sla_threshold)
    has_coloc = "colocation_count" in df_copy.columns and "target_colocations" in df_copy.columns
    has_energy = "energy_consumption_kwh" in df_copy.columns and "energy_budget_kwh" in df_copy.columns

    # Exception Conditions
    sla_breach_cond = (df_copy["uptime_pct"] < float(uptime_sla_threshold)) if "uptime_pct" in df_copy.columns else pd.Series(False, index=df_copy.index)
    coloc_shortfall_cond = (df_copy["colocation_count"] < df_copy["target_colocations"]) if has_coloc else pd.Series(False, index=df_copy.index)
    
    if has_energy:
        overrun_factor = 1.0 + (float(energy_overrun_pct) / 100.0)
        energy_overrun_cond = (df_copy["energy_consumption_kwh"] > (df_copy["energy_budget_kwh"] * overrun_factor))
    else:
        energy_overrun_cond = pd.Series(False, index=df_copy.index)

    # Filter based on requested exception category
    if exception_type == "SLA Uptime Breach":
        flagged_df = df_copy[sla_breach_cond].copy()
    elif exception_type == "Colocation Shortfall":
        flagged_df = df_copy[coloc_shortfall_cond].copy()
    elif exception_type == "Energy Overrun":
        flagged_df = df_copy[energy_overrun_cond].copy()
    else:
        # 'All Exceptions' (Union of any exception condition)
        combined_cond = sla_breach_cond | coloc_shortfall_cond | energy_overrun_cond
        flagged_df = df_copy[combined_cond].copy()

    # Add calculated metrics if available
    if not flagged_df.empty:
        if "uptime_pct" in flagged_df.columns:
            flagged_df["uptime_deficit_pct"] = (99.5 - flagged_df["uptime_pct"]).round(2)
        if has_coloc:
            flagged_df["colocation_gap"] = flagged_df["target_colocations"] - flagged_df["colocation_count"]
        if has_energy:
            flagged_df["energy_variance_kwh"] = (flagged_df["energy_consumption_kwh"] - flagged_df["energy_budget_kwh"]).round(1)

    return flagged_df


def diagnose_root_cause_and_sop(flagged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform prescriptive diagnostic attribution on flagged exceptions.
    Maps exception parameters to realistic telecom root-causes, severity, and field SOP actions.
    """
    if flagged_df.empty:
        return flagged_df

    df_out = flagged_df.copy()
    root_causes = []
    prescriptive_sops = []
    severities = []

    for _, row in df_out.iterrows():
        uptime = row.get("uptime_pct", 99.5)
        energy_var = row.get("energy_variance_kwh", 0.0)
        coloc_gap = row.get("colocation_gap", 0)

        if uptime < 95.0:
            if energy_var > 100:
                severities.append("🔴 CRITICAL (P1)")
                root_causes.append("SEB grid failure (>12 hrs/day); DG backup exhausted battery bank buffer")
                prescriptive_sops.append("Dispatch mobile DG fuel bowser & replace dead battery strings. Raise SEB feeder restoration ticket.")
            else:
                severities.append("🔴 CRITICAL (P1)")
                root_causes.append("Optical fiber backhaul cut during road widening; microwave protection link faded")
                prescriptive_sops.append("Deploy OTDR fiber splicing crew. Realign secondary microwave antenna dish.")
        elif coloc_gap > 0:
            severities.append("🟡 MEDIUM (P3)")
            root_causes.append("Secondary tenant onboarding delayed due to tower wind-load structural audit & antenna clearance")
            prescriptive_sops.append("Issue Structural Clearance Certificate to telco. Schedule Joint Site Survey (JSS) with Circle Sales Lead.")
        elif energy_var > 0:
            severities.append("🟠 HIGH (P2)")
            root_causes.append("Precision Air Conditioner condenser clogged; BTS cabinet thermal throttling & high fan draw")
            prescriptive_sops.append("Service PAC condenser coils, clean dust filters, and calibrate digital check-meter against utility meter.")
        else:
            severities.append("🟢 MINOR (P4)")
            root_causes.append("Minor telemetry drift in IoT RMS controller gateway")
            prescriptive_sops.append("Initiate remote diagnostic reset on IoT RMS gateway via TOC.")

    df_out["severity"] = severities
    df_out["root_cause"] = root_causes
    df_out["prescriptive_sop"] = prescriptive_sops

    return df_out


if __name__ == "__main__":
    sample_df = pd.DataFrame({
        "circle": ["Delhi", "Mumbai", "UP-East"],
        "site_id": ["TWR-DEL-0101", "TWR-MUM-0102", "TWR-UPE-0103"],
        "tenant": ["Airtel", "Reliance Jio", "Vodafone Idea"],
        "colocation_count": [3, 2, 1],
        "target_colocations": [3, 3, 3],
        "uptime_pct": [99.8, 93.5, 98.0],
        "sla_target_pct": [99.5, 99.5, 99.5],
        "energy_consumption_kwh": [1200.0, 1500.0, 1800.0],
        "energy_budget_kwh": [1200.0, 1400.0, 1200.0]
    })
    ex = flag_exceptions(sample_df)
    diag = diagnose_root_cause_and_sop(ex)
    print("Sample Diagnostics:\n", diag[["site_id", "severity", "root_cause", "prescriptive_sop"]])

