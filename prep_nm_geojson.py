# static/prep_nm_geojson.py
import json
from pathlib import Path
import pandas as pd
import random

BASE_DIR = Path(__file__).resolve().parent.parent
FEMA_CSV = BASE_DIR / "NRI_Table_Tribal_Counties.csv"
TRACTS_GEOJSON = BASE_DIR / "nm_tracts.geojson.json"
OUTPUT_GEOJSON = BASE_DIR / "static" / "nm_tracts_with_risk.geojson"


def build_nm_tracts_with_risk():
    print("Reading FEMA NRI CSV from:", FEMA_CSV)
    df = pd.read_csv(FEMA_CSV, encoding="utf-8")

    # Columns we care about
    needed_cols = [
        "COUNTYFIPS",
        "STATEABBRV",
        "RISK_SCORE",
        "RISK_RATNG",
        "EAL_SCORE",
        "SOVI_SCORE",
        "RESL_SCORE",
        "DRGT_RISKS",
        "WFIR_RISKS",
        "RFLD_RISKS",
    ]
    df = df[needed_cols].rename(columns={
        "COUNTYFIPS": "CountyFIPS",
        "STATEABBRV": "StateAbbr",
        "RISK_SCORE": "OverallRiskScore",
        "RISK_RATNG": "OverallRiskRating",
        "EAL_SCORE": "ExpectedAnnualLossScore",
        "SOVI_SCORE": "SocialVulnerabilityScore",
        "RESL_SCORE": "CommunityResilienceScore",
        "DRGT_RISKS": "DroughtRiskScore",
        "WFIR_RISKS": "WildfireRiskScore",
        "RFLD_RISKS": "FloodRiskScore",
    })

    # Only New Mexico rows
    df_nm = df[df["StateAbbr"] == "NM"].copy()
    print("Rows for NM:", len(df_nm))

    # County-level lookup: full 5-digit FIPS '35xxx'
    lookup = {}
    for _, row in df_nm.iterrows():
        county3 = str(row["CountyFIPS"]).zfill(3)
        fips5 = "35" + county3
        lookup[fips5] = {
            "OverallRiskScore": float(row["OverallRiskScore"]) if pd.notna(row["OverallRiskScore"]) else None,
            "OverallRiskRating": row["OverallRiskRating"],
            "ExpectedAnnualLossScore": float(row["ExpectedAnnualLossScore"]) if pd.notna(row["ExpectedAnnualLossScore"]) else None,
            "SocialVulnerabilityScore": float(row["SocialVulnerabilityScore"]) if pd.notna(row["SocialVulnerabilityScore"]) else None,
            "CommunityResilienceScore": float(row["CommunityResilienceScore"]) if pd.notna(row["CommunityResilienceScore"]) else None,
            "DroughtRiskScore": float(row["DroughtRiskScore"]) if pd.notna(row["DroughtRiskScore"]) else None,
            "WildfireRiskScore": float(row["WildfireRiskScore"]) if pd.notna(row["WildfireRiskScore"]) else None,
            "FloodRiskScore": float(row["FloodRiskScore"]) if pd.notna(row["FloodRiskScore"]) else None,
        }

    print("Built lookup for NM counties:", len(lookup))

    # Load NM tracts GeoJSON
    print("Reading NM tracts GeoJSON from:", TRACTS_GEOJSON)
    with open(TRACTS_GEOJSON, "r", encoding="utf-8") as f:
        geo = json.load(f)

    missing = 0

    for feature in geo["features"]:
        props = feature.get("properties", {})
        state_fp = str(props.get("STATEFP", "")).zfill(2)
        county_fp = str(props.get("COUNTYFP", "")).zfill(3)
        fips = state_fp + county_fp  # '35xxx'

        risk = lookup.get(fips)

        if not risk:
            # County not present in FEMA tribal table → create synthetic-but-realistic values
            missing += 1

            base = random.uniform(30, 60)  # baseline medium risk
            drought = base + random.uniform(10, 25)   # drought generally higher in NM
            wildfire = base + random.uniform(0, 10)
            flood = base - random.uniform(5, 20)      # flood generally lower inland
            eal = base + random.uniform(-10, 10)
            sv = random.uniform(20, 70)
            cr = random.uniform(30, 80)

            risk = {
                "OverallRiskScore": round((drought + wildfire + flood) / 3, 1),
                "OverallRiskRating": "Synthetic Estimate",
                "ExpectedAnnualLossScore": round(eal, 1),
                "SocialVulnerabilityScore": round(sv, 1),
                "CommunityResilienceScore": round(cr, 1),
                "DroughtRiskScore": round(drought, 1),
                "WildfireRiskScore": round(wildfire, 1),
                "FloodRiskScore": max(round(flood, 1), 0),
            }

        # Apply risk to tract
        props.update(risk)

        # --- Add renewable + fusion suitability based on lat/lon (tract centroid) ---
        # INTPTLAT / INTPTLON look like "+34.1234" and "-106.1234"
        try:
            lat = float(props.get("INTPTLAT", 0))
            lon = float(props.get("INTPTLON", 0))
        except (TypeError, ValueError):
            lat, lon = 0.0, 0.0

        # Solar: best around southern NM (~31–33°N), degrade as you go north
        solar = 80 - abs(lat - 32.5) * 5  # 32.5N is near the sunny southern band
        solar += random.uniform(-5, 5)    # small noise
        solar = max(0, min(100, solar))

        # Wind: best in eastern high plains (~lon -103 to -104), weaker to the west
        wind = 80 - abs(lon + 103.5) * 10  # lon around -103.5 is good
        wind += random.uniform(-5, 5)
        wind = max(0, min(100, wind))

        props["SolarSuitability"] = round(solar, 1)
        props["WindSuitability"] = round(wind, 1)

        # --- Fusion suitability ---
        # Heuristic:
        # - Cooler (more northern) → slightly better (for cooling & comfort)
        # - Lower overall risk → better
        # - Lower drought → better (less water stress)
        overall = props.get("OverallRiskScore")
        drought_risk = props.get("DroughtRiskScore")

        try:
            overall = float(overall) if overall is not None else None
        except (TypeError, ValueError):
            overall = None

        try:
            drought_risk = float(drought_risk) if drought_risk is not None else None
        except (TypeError, ValueError):
            drought_risk = None

        # Normalize to [0,1]
        cool_factor = (lat - 31.0) / (37.0 - 31.0)  # 31–37°N for NM-ish
        cool_factor = max(0.0, min(1.0, cool_factor))

        if overall is None:
            overall_factor = 0.5
        else:
            overall_factor = 1.0 - max(0.0, min(1.0, overall / 100.0))  # lower risk = closer to 1

        if drought_risk is None:
            drought_factor = 0.5
        else:
            drought_factor = 1.0 - max(0.0, min(1.0, drought_risk / 100.0))

        fusion_score = 100.0 * (
            0.4 * cool_factor +
            0.35 * overall_factor +
            0.25 * drought_factor
        )
        fusion_score = max(0.0, min(100.0, fusion_score))

        props["FusionSuitability"] = round(fusion_score, 1)

    print(f"Filled {missing} tracts with synthetic risk values.")

    OUTPUT_GEOJSON.parent.mkdir(exist_ok=True)
    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(geo, f)

    print("✅ Wrote merged NM GeoJSON with risk + renewable + fusion suitability to:", OUTPUT_GEOJSON)


if __name__ == "__main__":
    build_nm_tracts_with_risk()
