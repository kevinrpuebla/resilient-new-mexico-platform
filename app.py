# app.py
from flask import Flask, jsonify, request
from pathlib import Path
from nri_backend import NRIDataset
from risk_logic import simulate_adjusted_risk

app = Flask(__name__)

nri = NRIDataset("NRI_Table_Tribal_Counties.csv")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@app.route("/nm_tracts_geojson")
def nm_tracts_geojson():
    path = STATIC_DIR / "nm_tracts_with_risk.geojson"
    if not path.exists():
        return "GeoJSON not found. Run static/prep_nm_geojson.py first.", 404
    return app.send_static_file("nm_tracts_with_risk.geojson")


@app.route("/")
def index():
    return """
    <!doctype html>
    <html>
    <head>
        <title>New Mexico Risk, Renewables & Fusion Map</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossorigin=""
        />
        <style>
          body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
          #map { width: 100vw; height: 100vh; }
          .info {
            position: absolute;
            top: 10px;
            left: 10px;
            padding: 8px 12px;
            background: white;
            border-radius: 4px;
            box-shadow: 0 0 5px rgba(0,0,0,0.3);
            z-index: 1000;
            font-size: 13px;
            max-width: 360px;
          }
          .controls {
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            background: white;
            border-radius: 4px;
            box-shadow: 0 0 5px rgba(0,0,0,0.3);
            z-index: 1000;
            font-size: 13px;
            max-width: 280px;
          }
          #legend {
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 10px;
            line-height: 1.4;
            border-radius: 4px;
            box-shadow: 0 0 5px rgba(0,0,0,0.3);
            font-size: 12px;
            z-index: 1000;
          }
          #legend i {
            width: 18px;
            height: 12px;
            display: inline-block;
            margin-right: 4px;
          }
          .scenario-box {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 8px 12px;
            border-radius: 4px;
            box-shadow: 0 0 5px rgba(0,0,0,0.3);
            font-size: 12px;
            z-index: 1000;
            max-width: 260px;
          }
          button.sim-btn {
            margin-top: 4px;
            margin-right: 4px;
            font-size: 12px;
          }
        </style>
    </head>
    <body>
        <div id="map"></div>

        <div class="info" id="infoBox">
          <b>New Mexico Climate Risk, Solar Panels, Wind Turbines & Fusion Suitability</b><br>
          Hover a tract to see risk, renewables, fusion readiness, and AI advice.
        </div>

        <div class="controls">
          <label for="hazardSelect"><b>Color by:</b></label><br>
          <select id="hazardSelect">
            <option value="fusion">Fusion suitability (recommended)</option>
            <option value="solar">Solar Panel suitability</option>
            <option value="wind">Wind Turbine suitability</option>
            <option value="overall">Overall risk</option>
            <option value="drought">Drought risk</option>
            <option value="wildfire">Wildfire risk</option>
            <option value="flood">Flood risk (blue)</option>
          </select>
          <hr>
          <b>Simulate event:</b><br>
          <button id="btnNoScenario" class="sim-btn">None</button>
          <button id="btnWildfireSim" class="sim-btn">Wildfire: Dry year</button>
          <button id="btnFloodSim" class="sim-btn">Flash flood: Extreme storm</button>
        </div>

        <div id="legend">
          <b>Color Scale</b><br>
          <div><i id="leg5"></i> 80 – 100 (highest)</div>
          <div><i id="leg4"></i> 60 – 80 (very high)</div>
          <div><i id="leg3"></i> 40 – 60 (high)</div>
          <div><i id="leg2"></i> 20 – 40 (moderate)</div>
          <div><i id="leg1"></i> 10 – 20 (low)</div>
          <div><i id="leg0"></i> 0 – 10 (very low)</div>
          <div><i id="legN"></i> No data</div>
        </div>

        <div class="scenario-box" id="scenarioBox">
          <b>Scenario:</b> None<br>
          High-scoring tracts (&gt; 60) for current layer: calculating...
        </div>

        <script
          src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
          integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
          crossorigin="">
        </script>

        <script>
        // ---------- COLOR PALETTES ----------

        // Default risk palette (reds/orange/yellow)
        function getRiskColor(score) {
          if (score === null || score === undefined || isNaN(score)) return '#cccccc';
          if (score > 80) return '#800026';
          if (score > 60) return '#BD0026';
          if (score > 40) return '#E31A1C';
          if (score > 20) return '#FD8D3C';
          if (score > 10) return '#FEB24C';
          return '#FED976';
        }

        // Flood palette (blue only so water looks like water)
        function getFloodColor(score) {
          if (score === null || score === undefined || isNaN(score)) return '#cccccc';
          if (score > 80) return '#08306b';
          if (score > 60) return '#08519c';
          if (score > 40) return '#2171b5';
          if (score > 20) return '#4292c6';
          if (score > 10) return '#6baed6';
          return '#c6dbef';
        }

        // Fusion palette (greens)
        function getFusionColor(score) {
          if (score === null || score === undefined || isNaN(score)) return '#eeeeee';
          if (score > 80) return '#00441b';
          if (score > 60) return '#238b45';
          if (score > 40) return '#41ab5d';
          if (score > 20) return '#74c476';
          if (score > 10) return '#a1d99b';
          return '#c7e9c0';
        }

        // Solar Panel palette (black/gray)
        function getSolarColor(score) {
          if (score === null || score === undefined || isNaN(score)) return '#eeeeee';
          if (score > 80) return '#000000';
          if (score > 60) return '#252525';
          if (score > 40) return '#636363';
          if (score > 20) return '#969696';
          if (score > 10) return '#c7c7c7';
          return '#f0f0f0';
        }

        // Wind Turbine palette (purple)
        function getWindColor(score) {
          if (score === null || score === undefined || isNaN(score)) return '#eeeeee';
          if (score > 80) return '#3c096c';
          if (score > 60) return '#5a189a';
          if (score > 40) return '#8b3dff';
          if (score > 20) return '#b37dff';
          if (score > 10) return '#d0b7ff';
          return '#f2e5ff';
        }

        // Wrapper depending on which layer is selected
        var currentHazard = "fusion";

        function getColor(score) {
          if (currentHazard === "flood")  return getFloodColor(score);
          if (currentHazard === "fusion") return getFusionColor(score);
          if (currentHazard === "solar")  return getSolarColor(score);
          if (currentHazard === "wind")   return getWindColor(score);
          // solar, wind handled above; others use risk palette
          return getRiskColor(score);
        }

        function updateLegendColors() {
          var colors;
          if (currentHazard === "flood") {
            colors = ['#c6dbef','#6baed6','#4292c6','#2171b5','#08519c','#08306b'];
          } else if (currentHazard === "fusion") {
            colors = ['#c7e9c0','#a1d99b','#74c476','#41ab5d','#238b45','#00441b'];
          } else if (currentHazard === "solar") {
            // grayscale for solar panels
            colors = ['#f0f0f0','#c7c7c7','#969696','#636363','#252525','#000000'];
          } else if (currentHazard === "wind") {
            // purple scale for wind turbines
            colors = ['#f2e5ff','#d0b7ff','#b37dff','#8b3dff','#5a189a','#3c096c'];
          } else {
            colors = ['#FED976','#FEB24C','#FD8D3C','#E31A1C','#BD0026','#800026'];
          }
          document.getElementById('leg0').style.background = colors[0];
          document.getElementById('leg1').style.background = colors[1];
          document.getElementById('leg2').style.background = colors[2];
          document.getElementById('leg3').style.background = colors[3];
          document.getElementById('leg4').style.background = colors[4];
          document.getElementById('leg5').style.background = colors[5];
          document.getElementById('legN').style.background = '#cccccc';
        }

        // ---------- SCENARIO LOGIC (DROUGHT / FLOOD / WILDFIRE) ----------

        var currentScenario = "none";  // 'none' | 'wildfire_dry' | 'flood_extreme'
        var infoBox = document.getElementById('infoBox');
        var scenarioBox = document.getElementById('scenarioBox');
        var geojson = null;
        var allFeatures = [];

        // Hazards interact:
        //  - Dry year: wildfire ↑, drought ↑
        //  - Extreme storm: flood ↑, drought ↓
        function applyScenario(score, hazardKey) {
          if (score === null || score === undefined || isNaN(score)) return score;
          let s = score;

          if (currentScenario === "wildfire_dry") {
            if (hazardKey === "wildfire") s = score * 1.4;  // +40%
            if (hazardKey === "drought")  s = score * 1.2;  // +20%
          }

          if (currentScenario === "flood_extreme") {
            if (hazardKey === "flood")   s = score * 1.6;   // +60%
            if (hazardKey === "drought") s = score * 0.75;  // -25%
          }

          if (s > 100) s = 100;
          if (s < 0)   s = 0;
          return s;
        }

        function getScoreForHazard(p) {
          if (!p) return null;

          // Energy / fusion layers: no scenario applied (they're siting suitability)
          if (currentHazard === "solar")  return p.SolarSuitability;
          if (currentHazard === "wind")   return p.WindSuitability;
          if (currentHazard === "fusion") return p.FusionSuitability;

          var base = null;
          var key = currentHazard;
          if (currentHazard === "drought")      base = p.DroughtRiskScore;
          else if (currentHazard === "wildfire") base = p.WildfireRiskScore;
          else if (currentHazard === "flood")    base = p.FloodRiskScore;
          else base = p.OverallRiskScore;

          return applyScenario(base, key);
        }

        function style(feature) {
          var p = feature.properties;
          var score = getScoreForHazard(p);

          var borderColor = '#333';
          var weight = 0.5;
          var fillOpacity = 0.7;

          // Solar Panel & Wind Turbine & Fusion:
          // highlight best zones and fade out weaker ones
          if ((currentHazard === "solar" || currentHazard === "wind" || currentHazard === "fusion")
              && score !== null && !isNaN(score)) {

            if (score >= 75) {
              if (currentHazard === "fusion") {
                borderColor = '#00441b';   // dark green
              } else if (currentHazard === "solar") {
                borderColor = '#000000';   // black for top solar panel areas
              } else if (currentHazard === "wind") {
                borderColor = '#3c096c';   // deep purple for top wind turbine areas
              }
              weight = 2;
              fillOpacity = 0.9;
            } else if (score < 40) {
              // lower suitability: fade them
              borderColor = '#bbbbbb';
              weight = 0.3;
              fillOpacity = 0.3;
            }
          }

          return {
            fillColor: getColor(score),
            weight: weight,
            opacity: 1,
            color: borderColor,
            fillOpacity: fillOpacity
          };
        }

        // ---------- HOVER & AI EXPLANATION ----------

        function highlightFeature(e) {
          var layer = e.target;
          layer.setStyle({
            weight: 2.5,
            color: '#000',
            fillOpacity: 0.95
          });

          var p = layer.feature.properties;
          var overall = (p.OverallRiskScore ?? "N/A");
          var drought = (p.DroughtRiskScore ?? "N/A");
          var wildfire = (p.WildfireRiskScore ?? "N/A");
          var flood = (p.FloodRiskScore ?? "N/A");
          var eal = (p.ExpectedAnnualLossScore ?? "N/A");
          var sv = (p.SocialVulnerabilityScore ?? "N/A");
          var cr = (p.CommunityResilienceScore ?? "N/A");
          var solar = (p.SolarSuitability ?? "N/A");
          var wind = (p.WindSuitability ?? "N/A");
          var fusion = (p.FusionSuitability ?? "N/A");

          infoBox.innerHTML =
            '<b>Tract GEOID:</b> ' + (p.GEOID || 'N/A') + '<br>' +
            '<b>County FIPS:</b> ' + ((p.STATEFP || '') + (p.COUNTYFP || '')) + '<br>' +
            '<b><u>Risk scores</u></b><br>' +
            'Overall: ' + overall + '<br>' +
            'Drought: ' + drought + '<br>' +
            'Wildfire: ' + wildfire + '<br>' +
            'Flood: ' + flood + '<br>' +
            '<b><u>Community factors</u></b><br>' +
            'Expected Annual Loss: ' + eal + '<br>' +
            'Social Vulnerability: ' + sv + '<br>' +
            'Community Resilience: ' + cr + '<br>' +
            '<b><u>Energy suitability</u></b><br>' +
            'Solar Panel: ' + solar + '<br>' +
            'Wind Turbine: ' + wind + '<br>' +
            'Fusion: ' + fusion + '<br>' +
            '<i>AI: analyzing this tract for fusion & renewables...</i>';

          fetch('/ai_recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              overall_risk: p.OverallRiskScore,
              drought_risk: p.DroughtRiskScore,
              wildfire_risk: p.WildfireRiskScore,
              flood_risk: p.FloodRiskScore,
              eal_score: p.ExpectedAnnualLossScore,
              social_vulnerability: p.SocialVulnerabilityScore,
              community_resilience: p.CommunityResilienceScore,
              fusion_suitability: p.FusionSuitability,
              solar_suitability: p.SolarSuitability,
              wind_suitability: p.WindSuitability
            })
          })
          .then(res => res.json())
          .then(data => {
            infoBox.innerHTML += '<br><b>AI Recommendation:</b><br>' +
              (data.message || 'No recommendation.');
          })
          .catch(err => {
            console.error('AI recommend error:', err);
          });
        }

        function resetHighlight(e) {
          if (geojson) geojson.resetStyle(e.target);
        }

        function onEachFeature(feature, layer) {
          layer.on({
            mouseover: highlightFeature,
            mouseout: resetHighlight
          });
        }

        function prettyScenarioName() {
          if (currentScenario === "wildfire_dry") return "Wildfire – Dry Year";
          if (currentScenario === "flood_extreme") return "Flash Flood – Extreme Storm";
          return "None";
        }

        function prettyHazardName() {
          if (currentHazard === "overall") return "Overall Risk";
          if (currentHazard === "drought") return "Drought Risk";
          if (currentHazard === "wildfire") return "Wildfire Risk";
          if (currentHazard === "flood") return "Flood Risk";
          if (currentHazard === "solar") return "Solar Panel Suitability";
          if (currentHazard === "wind") return "Wind Turbine Suitability";
          if (currentHazard === "fusion") return "Fusion Suitability";
          return currentHazard;
        }

        function updateScenarioStats() {
          if (!allFeatures || allFeatures.length === 0) {
            scenarioBox.innerHTML = '<b>Scenario:</b> ' + prettyScenarioName() +
              '<br>No data loaded yet.';
            return;
          }
          var high = 0;
          var veryHigh = 0;
          allFeatures.forEach(function(f) {
            var p = f.properties || {};
            var s = getScoreForHazard(p);
            if (s === null || s === undefined || isNaN(s)) return;
            if (s > 80) veryHigh += 1;
            else if (s > 60) high += 1;
          });
          scenarioBox.innerHTML =
            '<b>Scenario:</b> ' + prettyScenarioName() + '<br>' +
            '<b>Layer:</b> ' + prettyHazardName() + '<br>' +
            'High (&gt; 60): ' + high + '<br>' +
            'Very high (&gt; 80): ' + veryHigh +
            (currentHazard === "fusion"
              ? "<br><i>Darker green areas are the most recommended fusion sites in the state.</i>"
              : currentHazard === "solar"
                ? "<br><i>Darker black/gray areas are the most recommended Solar Panel zones.</i>"
                : currentHazard === "wind"
                  ? "<br><i>Darker purple areas are the most recommended Wind Turbine zones.</i>"
                  : "");
        }

        // ---------- MAP INIT ----------

        var map = L.map('map').setView([34.5, -106], 6.3);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 18,
          attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        fetch('/nm_tracts_geojson')
          .then(res => res.json())
          .then(data => {
            allFeatures = data.features || [];
            geojson = L.geoJson(data, {
              style: style,
              onEachFeature: onEachFeature
            }).addTo(map);
            updateLegendColors();
            updateScenarioStats();
          })
          .catch(err => {
            console.error('Error loading GeoJSON:', err);
            infoBox.innerHTML = 'Error loading NM tracts data.';
          });

        // ---------- UI CONTROLS ----------

        document.getElementById('hazardSelect').addEventListener('change', function(e) {
          currentHazard = e.target.value;
          if (geojson) geojson.setStyle(style);
          updateLegendColors();
          updateScenarioStats();
        });

        document.getElementById('btnNoScenario').addEventListener('click', function() {
          currentScenario = "none";
          if (geojson) geojson.setStyle(style);
          updateScenarioStats();
        });

        document.getElementById('btnWildfireSim').addEventListener('click', function() {
          currentScenario = "wildfire_dry";
          if (geojson) geojson.setStyle(style);
          updateScenarioStats();
        });

        document.getElementById('btnFloodSim').addEventListener('click', function() {
          currentScenario = "flood_extreme";
          if (geojson) geojson.setStyle(style);
          updateScenarioStats();
        });
        </script>
    </body>
    </html>
    """


@app.route("/ai_recommend", methods=["POST"])
def ai_recommend():
    payload = request.json or {}

    def safe_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    overall = safe_float(payload.get("overall_risk"))
    drought = safe_float(payload.get("drought_risk"))
    wildfire = safe_float(payload.get("wildfire_risk"))
    flood = safe_float(payload.get("flood_risk"))
    eal = safe_float(payload.get("eal_score"))
    sv = safe_float(payload.get("social_vulnerability"))
    cr = safe_float(payload.get("community_resilience"))
    fusion_s = safe_float(payload.get("fusion_suitability"))
    solar_s = safe_float(payload.get("solar_suitability"))
    wind_s = safe_float(payload.get("wind_suitability"))

    messages = []

    # Hazard / risk mitigation
    if drought is not None and drought > 60:
        messages.append("Drought risk is high — prioritize water storage, conservation, and drought-tolerant crops.")
    if wildfire is not None and wildfire > 60:
        messages.append("Wildfire risk is elevated — create defensible space, fuel breaks, and evacuation plans.")
    if flood is not None and flood > 60:
        messages.append("Flood risk is high — upgrade drainage, protect critical infrastructure, and avoid new development in flood zones.")
    if overall is not None and overall > 60:
        messages.append("Overall risk is high — coordinate multi-hazard planning with local emergency management.")

    if sv is not None and sv > 60:
        messages.append("Social vulnerability is high — focus on support for low-income, elderly, and isolated residents.")
    if cr is not None and cr < 40:
        messages.append("Community resilience is low — invest in training, communication networks, and mutual aid groups.")
    if eal is not None and eal > 60:
        messages.append("Expected annual loss is high — consider mitigation grants and infrastructure upgrades.")

    # Energy + fusion siting hints (why here vs other areas)
    if fusion_s is not None:
        if fusion_s >= 80 and (overall is None or overall < 60):
            messages.append(
                "Fusion suitability is very strong here — cooler conditions and manageable risk make this tract a top candidate compared to more exposed parts of New Mexico."
            )
        elif fusion_s >= 80:
            messages.append(
                "Fusion suitability is very strong, but risk is non-trivial — this is a promising fusion site if you pair it with robust hazard mitigation."
            )
        elif fusion_s >= 60:
            messages.append(
                "Fusion suitability is good — this could host advanced energy or fusion-adjacent facilities if key risks are addressed."
            )
        elif fusion_s < 40:
            messages.append(
                "Fusion suitability is relatively low — other tracts with higher fusion scores and less climate pressure would be better for large fusion projects."
            )

    if solar_s is not None:
        if solar_s >= 80:
            messages.append(
                "Solar Panel potential is excellent — this area is well-suited for utility-scale or community solar compared to cloudier or more constrained regions."
            )
        elif solar_s >= 60:
            messages.append(
                "Solar Panel potential is solid — good candidate for distributed rooftop or parking-lot solar on homes, schools, and public buildings."
            )

    if wind_s is not None:
        if wind_s >= 80:
            messages.append(
                "Wind Turbine resource is very strong — this tract stands out for large wind farms or hybrid wind–solar projects."
            )
        elif wind_s >= 60:
            messages.append(
                "Wind Turbine resource is decent — consider mid-sized turbines or pairing wind with Solar Panels for more stable output."
            )

    if not messages:
        messages.append(
            "Risk and energy scores are moderate — maintain existing protections and look for opportunities to add small-scale renewables and resilient infrastructure."
        )

    return jsonify({"message": " ".join(messages)})


@app.route("/simulate_risk", methods=["POST"])
def simulate_risk_route():
    payload = request.json or {}

    eal = payload.get("eal_score")
    sv = payload.get("social_vulnerability")
    cr = payload.get("community_resilience")
    sv_delta = payload.get("sv_delta_pct", 0.0)
    cr_delta = payload.get("cr_delta_pct", 0.0)

    adjusted = simulate_adjusted_risk(eal, sv, cr, sv_delta, cr_delta)

    return jsonify({
        "adjusted_risk_score": adjusted
    })


if __name__ == "__main__":
    app.run(debug=True)
