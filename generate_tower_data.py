"""
Script to generate realistic synthetic Telecom Tower Infrastructure Dataset (Indus Towers style).

Outputs 'tower_sites.csv' with 360+ rows across 10 circles, 60 unique tower sites,
6 months of metrics (2026-03 to 2026-08), and realistic exception distributions.
"""

import os
import random
import numpy as np
import pandas as pd

# Set fixed random seed for 100% reproducible demo data
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

TENANTS_POOL = ["Airtel", "Reliance Jio", "Vodafone Idea"]
MONTHS = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]


def generate_tower_dataset(num_sites_per_circle: int = 6) -> pd.DataFrame:
    """
    Generate synthetic telecom tower infrastructure dataset.

    Parameters:
        num_sites_per_circle: Number of unique tower sites per circle (default 6 * 10 = 60 sites).

    Returns:
        pd.DataFrame containing generated tower_sites metrics.
    """
    sites = []

    # 1. Generate 60 unique sites
    site_counter = 101
    for circle_name, circle_code in CIRCLES:
        for _ in range(num_sites_per_circle):
            site_id = f"TWR-{circle_code}-{site_counter:04d}"
            site_counter += 13  # Incremental realistic site ID numbering

            # Base properties for the site
            target_colocations = random.choice([2, 3, 3, 4])
            base_budget_kwh = random.randint(1000, 2200)
            
            # Site characteristics (e.g. 15% faulty power grid, 15% capacity bottleneck)
            is_power_faulty = (random.random() < 0.15)
            is_underperforming_coloc = (random.random() < 0.18)

            sites.append({
                "circle": circle_name,
                "circle_code": circle_code,
                "site_id": site_id,
                "target_colocations": target_colocations,
                "base_budget_kwh": base_budget_kwh,
                "is_power_faulty": is_power_faulty,
                "is_underperforming_coloc": is_underperforming_coloc
            })

    rows = []

    # 2. Generate monthly tenant-level metrics for 6 months
    for month in MONTHS:
        for s in sites:
            # Actual colocation count calculation
            if s["is_underperforming_coloc"] and random.random() < 0.70:
                coloc_count = max(1, s["target_colocations"] - random.choice([1, 2]))
            else:
                coloc_count = s["target_colocations"]

            # Select tenants present at this tower site
            active_tenants = random.sample(TENANTS_POOL, min(coloc_count, len(TENANTS_POOL)))

            # If colocation count > len(TENANTS_POOL), append extra operator instance or regional player
            if coloc_count > len(TENANTS_POOL):
                active_tenants.append("BSNL")

            # Energy budget for the site
            energy_budget = float(s["base_budget_kwh"] + random.randint(-50, 50))

            # Energy consumption for the site
            if s["is_power_faulty"] and random.random() < 0.75:
                # Energy overrun by 12% to 35%
                overrun_factor = random.uniform(1.12, 1.35)
                energy_consumption = round(energy_budget * overrun_factor, 1)
            else:
                # Normal variation 88% to 104% of budget
                normal_factor = random.uniform(0.88, 1.04)
                energy_consumption = round(energy_budget * normal_factor, 1)

            # Generate row per tenant for this site and month
            for tenant in active_tenants:
                # Uptime percentage logic (approx 8-10% SLA breaches below 95.0%)
                is_sla_breach = (random.random() < 0.09) or (s["is_power_faulty"] and random.random() < 0.40)
                
                if is_sla_breach:
                    uptime = round(random.uniform(91.2, 94.8), 2)
                else:
                    uptime = round(random.uniform(97.2, 99.9), 2)

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

    print(f"Successfully generated dataset: {output_filepath}")
    print(f"Total rows generated: {len(df)}")
    print(f"Unique Sites: {df['site_id'].nunique()}")
    print(f"Circles covered: {df['circle'].nunique()}")
    print(f"Months covered: {df['month'].unique()}")
    print("\nDataset Sample (First 5 rows):")
    print(df.head())

    # Verify exception stats
    print("\n--- Exception Statistics Verification ---")
    sla_breaches = (df['uptime_pct'] < 95.0).sum()
    coloc_shortfalls = (df['colocation_count'] < df['target_colocations']).sum()
    energy_overruns = (df['energy_consumption_kwh'] > df['energy_budget_kwh'] * 1.10).sum()

    print(f"SLA Breaches (< 95.0% Uptime): {sla_breaches} rows ({sla_breaches/len(df)*100:.1f}%)")
    print(f"Colocation Shortfalls (< Target): {coloc_shortfalls} rows ({coloc_shortfalls/len(df)*100:.1f}%)")
    print(f"Energy Overruns (> 110% Budget): {energy_overruns} rows ({energy_overruns/len(df)*100:.1f}%)")
