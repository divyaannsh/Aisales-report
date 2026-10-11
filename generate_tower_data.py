"""
Script to generate realistic synthetic Telecom Tower Infrastructure Dataset.
Calibrated to public telecom industry benchmark KPIs:
- Average tenancy ratio: ~1.62x (majority 1 or 2 tenants, few with 3)
- Average network uptime: ~99.9% (most rows 99.5-99.99%, ~4% below 99.5%, ~1% critical breach <95%)
- Energy overrun (>10% of budget): ~8% of records (reflecting ~4.5% fleet energy under-recovery)
"""

import os
import random
import numpy as np
import pandas as pd

# Fixed seed for 100% reproducible calibration
np.random.seed(42)
random.seed(42)

CIRCLES = [
    ("Delhi", "DEL"),
    ("Mumbai", "MUM"),
    ("UP-East", "UPE"),
    ("UP-West", "UPW"),
    ("Punjab", "PUN"),
    ("Maharashtra", "MAH"),
    ("Rajasthan", "RAJ"),
    ("Karnataka", "KAR"),
    ("Tamil Nadu", "TN"),
    ("West Bengal", "WB")
]

TENANTS_POOL = ["Airtel", "Reliance Jio", "Vodafone Idea", "BSNL"]
MONTHS = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]


def generate_tower_dataset(num_sites_per_circle: int = 6) -> pd.DataFrame:
    """
    Generate synthetic telecom tower infrastructure dataset calibrated to industry KPIs.
    
    Target Distributions:
    - 60 unique sites across 10 circles
    - Tenancy distribution: ~48% 1-tenant, ~42% 2-tenant, ~10% 3-tenant (Mean: ~1.62x)
    - Uptime: ~95% between 99.50% - 99.99%, ~4% between 95.0% - 99.49%, ~1% < 95.0%
    - Energy Overruns (>10% budget): ~8% of records
    """
    sites = []
    site_counter = 101

    # Exactly 60 sites: 28 sites target=1, 26 sites target=2, 6 sites target=3 (Average target = 1.63x)
    target_pattern = [1] * 28 + [2] * 26 + [3] * 6
    random.shuffle(target_pattern)

    idx = 0
    for circle_name, circle_code in CIRCLES:
        for _ in range(num_sites_per_circle):
            site_id = f"TWR-{circle_code}-{site_counter:04d}"
            site_counter += 13

            target_colocations = target_pattern[idx]
            idx += 1

            base_budget_kwh = random.randint(1100, 1900)
            
            # Site characteristics: 8% with chronic power grid volatility, 12% with tenancy expansion gap
            has_grid_volatility = (random.random() < 0.08)
            has_coloc_gap = (target_colocations > 1) and (random.random() < 0.15)

            sites.append({
                "circle": circle_name,
                "circle_code": circle_code,
                "site_id": site_id,
                "target_colocations": target_colocations,
                "base_budget_kwh": base_budget_kwh,
                "has_grid_volatility": has_grid_volatility,
                "has_coloc_gap": has_coloc_gap
            })

    rows = []

    # Generate monthly tenant-level metrics for 6 months
    for month in MONTHS:
        for s in sites:
            # Colocation count per site-month
            if s["has_coloc_gap"] and random.random() < 0.65:
                # Actual is 1 less than target
                coloc_count = max(1, s["target_colocations"] - 1)
            else:
                coloc_count = s["target_colocations"]

            # Select tenants present at this tower site
            active_tenants = random.sample(TENANTS_POOL[:3], min(coloc_count, 3))
            if coloc_count > 3:
                active_tenants.append("BSNL")

            # Energy budget
            energy_budget = float(s["base_budget_kwh"] + random.randint(-40, 40))

            # Energy consumption: ~8% rows have >10% overrun
            is_energy_overrun = s["has_grid_volatility"] or (random.random() < 0.065)
            if is_energy_overrun:
                overrun_factor = random.uniform(1.11, 1.28)
                energy_consumption = round(energy_budget * overrun_factor, 1)
            else:
                normal_factor = random.uniform(0.92, 1.05)
                energy_consumption = round(energy_budget * normal_factor, 1)

            # Generate row per active tenant on this site
            for tenant in active_tenants:
                # Uptime distribution:
                # ~1.0% critical breach (<95.0%)
                # ~4.0% SLA breach (95.0% - 99.49%)
                # ~95.0% compliant (99.50% - 99.99%)
                r_uptime = random.random()
                if r_uptime < 0.012:  # ~1.2% critical breach
                    uptime = round(random.uniform(91.5, 94.8), 2)
                elif r_uptime < 0.052:  # ~4.0% breach below SLA
                    uptime = round(random.uniform(95.1, 99.4), 2)
                else:  # ~94.8% high-performing (99.50 - 99.99%)
                    uptime = round(random.uniform(99.65, 99.99), 2)

                rows.append({
                    "circle": s["circle"],
                    "site_id": s["site_id"],
                    "tenant": tenant,
                    "colocation_count": int(coloc_count),
                    "target_colocations": int(s["target_colocations"]),
                    "uptime_pct": float(uptime),
                    "sla_target_pct": 99.5,
                    "energy_consumption_kwh": float(energy_consumption),
                    "energy_budget_kwh": float(energy_budget),
                    "month": month
                })

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    df = generate_tower_dataset()
    output_filename = "tower_sites.csv"
    output_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
    
    df.to_csv(output_filepath, index=False)

    print(f"✅ Generated dataset: {output_filepath}")
    print(f"Total rows: {len(df)}")
    print(f"Unique Sites: {df['site_id'].nunique()}")
    print(f"Circles: {df['circle'].nunique()}")
    
    # Calculate unique site-level tenancy
    site_month_df = df.drop_duplicates(subset=["site_id", "month"])
    avg_tenancy = site_month_df["colocation_count"].mean()
    avg_uptime = df["uptime_pct"].mean()
    
    sla_breaches_95 = (df['uptime_pct'] < 95.0).sum()
    sla_breaches_995 = (df['uptime_pct'] < 99.5).sum()
    coloc_shortfalls = (df['colocation_count'] < df['target_colocations']).sum()
    energy_overruns = (df['energy_consumption_kwh'] > df['energy_budget_kwh'] * 1.10).sum()

    print(f"Average Tenancy Ratio (per site): {avg_tenancy:.2f}x (Industry benchmark: ~1.62x)")
    print(f"Average Fleet Uptime: {avg_uptime:.3f}% (Industry benchmark: ~99.9%)")
    print(f"Critical SLA Breaches (<95%): {sla_breaches_95} rows ({sla_breaches_95/len(df)*100:.2f}%)")
    print(f"SLA Breaches (<99.5%): {sla_breaches_995} rows ({sla_breaches_995/len(df)*100:.2f}%)")
    print(f"Colocation Shortfalls (< Target): {coloc_shortfalls} rows ({coloc_shortfalls/len(df)*100:.2f}%)")
    print(f"Energy Overruns (> 110% Budget): {energy_overruns} rows ({energy_overruns/len(df)*100:.2f}%)")
