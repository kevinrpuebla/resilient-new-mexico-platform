# check_geojson.py
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
path = BASE_DIR / "static" / "us_counties_with_risk.geojson"

print("Checking:", path)
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("OK! Top-level type:", data.get("type"))
print("Feature count:", len(data.get("features", [])))
