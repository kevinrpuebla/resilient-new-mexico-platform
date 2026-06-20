# nri_backend.py
import pandas as pd

class NRIDataset:
    def __init__(self, csv_path: str):
        # CountyFIPS is the unique county ID column in FEMA's CSV
        self.df = pd.read_csv(csv_path, encoding="utf-8", dtype={"CountyFIPS": str})

    def list_counties(self, limit=5000):
        # These column names must match EXACTLY what's in the CSV header
        cols = [
            "CountyFIPS",
            "CountyName",
            "StateAbbr",
            "OverallRiskScore",
            "OverallRiskRating",
        ]
        return self.df[cols].head(limit).to_dict(orient="records")

    def get_county(self, geoid: str):
        # geoid here is the CountyFIPS code as a string
        row = self.df[self.df["CountyFIPS"] == geoid]
        if row.empty:
            return None
        r = row.iloc[0]

        # Return a cleaned-up JSON-friendly dict
        return {
            "CountyFIPS": r["CountyFIPS"],
            "CountyName": r["CountyName"],
            "StateAbbr": r["StateAbbr"],
            "OverallRiskScore": float(r["OverallRiskScore"]),
            "OverallRiskRating": r["OverallRiskRating"],
            "ExpectedAnnualLossScore": float(r["ExpectedAnnualLossScore"]),
            "SocialVulnerabilityScore": float(r["SocialVulnerabilityScore"]),
            "CommunityResilienceScore": float(r["CommunityResilienceScore"]),
        }
