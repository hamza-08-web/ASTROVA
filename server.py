from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import joblib
import pandas as pd
import math
import secrets
from pathlib import Path
from datetime import date, timedelta
from backend.satellite import sentinel, configured, SatelliteError

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__)
CORS(app)

# ============================================================
# LOAD ASTROVA AI MODEL
# ============================================================

MODEL_PATH = BASE_DIR / "backend" / "expo_model.pkl"

model_bundle = joblib.load(MODEL_PATH)
models = model_bundle["models"]
if set(models) != {"Manganese", "Nickel", "Cobalt"}:
    raise RuntimeError("The model bundle must contain all three mineral classifiers.")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def location_signal(latitude, longitude, offset=0.0):
    """
    Deterministic location-dependent signal.

    IMPORTANT:
    This prototype signal is simulated.
    It is NOT real Sentinel-2 data.

    The same coordinates always produce the same result.
    Different coordinates produce different results.
    """

    value = (
        math.sin(
            math.radians(
                latitude * 17.3
                + longitude * 11.7
                + offset
            )
        )
        * math.cos(
            math.radians(
                latitude * 9.1
                - longitude * 13.4
                + offset
            )
        )
    )

    return (value + 1.0) / 2.0


# ============================================================
# MINERAL BASE PROFILES
# ============================================================

MINERAL_PROFILES = {

    "Manganese": {
        "B2_blue": 0.20,
        "B3_green": 0.30,
        "B4_red": 0.25,
        "B8_nir": 0.40,
        "B11_swir1": 0.35,
        "B12_swir2": 0.30,
        "ndvi": 0.20,
        "ndwi": 0.10
    },

    "Nickel": {
        "B2_blue": 0.24,
        "B3_green": 0.34,
        "B4_red": 0.29,
        "B8_nir": 0.46,
        "B11_swir1": 0.41,
        "B12_swir2": 0.37,
        "ndvi": 0.24,
        "ndwi": 0.14
    },

    "Cobalt": {
        "B2_blue": 0.18,
        "B3_green": 0.27,
        "B4_red": 0.22,
        "B8_nir": 0.36,
        "B11_swir1": 0.33,
        "B12_swir2": 0.29,
        "ndvi": 0.18,
        "ndwi": 0.08
    }
}


# ============================================================
# MINERAL LOCATION SETTINGS
# ============================================================

MINERAL_SETTINGS = {

    "Manganese": {
        "max_presence": 92.0,
        "offset": 10
    },

    "Nickel": {
        "max_presence": 68.0,
        "offset": 80
    },

    "Cobalt": {
        "max_presence": 42.0,
        "offset": 160
    }
}

MINERAL_OPERATION_PROFILES = {
    "Manganese": {
        "capacity_factor": 1.00,
        "excavators": 4,
        "drills": 2,
        "loaders": 2,
        "dozers": 1,
        "water_tankers": 2,
        "activity": "Bulk extraction and haulage"
    },
    "Nickel": {
        "capacity_factor": 0.78,
        "excavators": 3,
        "drills": 3,
        "loaders": 2,
        "dozers": 2,
        "water_tankers": 3,
        "activity": "Selective extraction and grade control"
    },
    "Cobalt": {
        "capacity_factor": 0.56,
        "excavators": 2,
        "drills": 2,
        "loaders": 1,
        "dozers": 1,
        "water_tankers": 1,
        "activity": "Careful benching and stockpile sorting"
    }
}


# ============================================================
# GENERATE LOCATION-DEPENDENT FEATURES
# ============================================================

def generate_features(latitude, longitude, mineral, time_seed=0.0):

    base_features = MINERAL_PROFILES.get(
        mineral,
        MINERAL_PROFILES["Manganese"]
    ).copy()

    time_wave = 1.0 + ((math.sin((time_seed * 17.0) + latitude + longitude) + 1.0) / 2.0) * 0.35

    signal_1 = location_signal(
        latitude,
        longitude,
        0 + time_seed * 13.1
    )

    signal_2 = location_signal(
        latitude,
        longitude,
        47 + time_seed * 11.7
    )

    signal_3 = location_signal(
        latitude,
        longitude,
        113 + time_seed * 9.4
    )

    selected_features = {

        "B2_blue": clamp(
            base_features["B2_blue"]
            + (signal_1 - 0.5) * 0.08 * time_wave,
            0.05,
            0.60
        ),

        "B3_green": clamp(
            base_features["B3_green"]
            + (signal_2 - 0.5) * 0.08 * time_wave,
            0.05,
            0.70
        ),

        "B4_red": clamp(
            base_features["B4_red"]
            + (signal_3 - 0.5) * 0.08 * time_wave,
            0.05,
            0.70
        ),

        "B8_nir": clamp(
            base_features["B8_nir"]
            + (signal_1 - 0.5) * 0.12 * time_wave,
            0.05,
            0.90
        ),

        "B11_swir1": clamp(
            base_features["B11_swir1"]
            + (signal_2 - 0.5) * 0.10 * time_wave,
            0.05,
            0.80
        ),

        "B12_swir2": clamp(
            base_features["B12_swir2"]
            + (signal_3 - 0.5) * 0.10 * time_wave,
            0.05,
            0.80
        ),

        "ndvi": clamp(
            base_features["ndvi"]
            + (signal_1 - 0.5) * 0.15 * time_wave,
            -1.0,
            1.0
        ),

        "ndwi": clamp(
            base_features["ndwi"]
            + (signal_2 - 0.5) * 0.15 * time_wave,
            -1.0,
            1.0
        )
    }

    return selected_features


# ============================================================
# AI ANALYSIS
# ============================================================

def calculate_prediction(latitude, longitude, mineral, analysis_run=None, satellite_features=None):

    time_seed = 0.0
    if analysis_run is not None:
        try:
            time_seed = float(analysis_run) / 1000.0
        except (TypeError, ValueError):
            time_seed = 0.0

    selected_features = satellite_features if satellite_features is not None else generate_features(
        latitude,
        longitude,
        mineral,
        time_seed
    )

    features = pd.DataFrame([
        selected_features
    ], columns=model_bundle["feature_names"])

    model = models[mineral]

    prediction = int(
        model.predict(features)[0]
    )

    probability = model.predict_proba(
        features
    )[0][1]

    # The analysis-run key produces a small, clearly disclosed prototype
    # scenario refresh. It represents changing observation/operational context,
    # not a new geological measurement at the same location.
    variation = 0.0

    if analysis_run and satellite_features is None:
        variation = (secrets.randbelow(901) / 100) - 4.5

    calibrated_score = 10.0 + (probability * 78.0)
    prospectivity_score = round(
        clamp(calibrated_score + variation, 5.0, 88.0),
        2
    )

    if prospectivity_score >= 70:
        prospectivity = "HIGH"

    elif prospectivity_score >= 40:
        prospectivity = "MEDIUM"

    else:
        prospectivity = "LOW"

    # --------------------------------------------------------
    # LOCATION-DEPENDENT DEMO MINERAL ESTIMATE
    # --------------------------------------------------------

    settings = MINERAL_SETTINGS.get(
        mineral,
        MINERAL_SETTINGS["Manganese"]
    )

    mineral_signal = location_signal(
        latitude,
        longitude,
        settings["offset"]
    )

    secondary_signal = location_signal(
        latitude,
        longitude,
        settings["offset"] + 73
    )

    combined_signal = (
        mineral_signal * 0.65
        + secondary_signal * 0.35
    )

    if combined_signal < 0.18:

        presence_percent = 0.2

    elif combined_signal < 0.32:

        presence_percent = 8.0 + (
            (combined_signal - 0.18) / 0.14
        ) * 22.0

    elif combined_signal < 0.50:

        presence_percent = 30.0 + (
            (combined_signal - 0.32) / 0.18
        ) * 30.0

    elif combined_signal < 0.70:

        presence_percent = 60.0 + (
            (combined_signal - 0.50) / 0.20
        ) * 20.0

    else:

        presence_percent = 80.0 + (
            (combined_signal - 0.70) / 0.30
        ) * 12.0

    presence_percent = round(
        clamp(
            presence_percent,
            0.2,
            92.0
        ),
        1
    )

    if presence_percent >= 60:

        presence_status = "High estimated presence"

    elif presence_percent >= 25:

        presence_status = "Moderate estimated presence"

    elif presence_percent >= 5:

        presence_status = "Low estimated presence"

    else:

        presence_status = "Trace / very low estimated presence"

    return {
        "prediction": prediction,
        "prospectivity_score": prospectivity_score,
        "prospectivity": prospectivity,
        "scenario_variation": round(variation, 2),
        "mineral_presence_percent": presence_percent,
        "mineral_presence_status": presence_status,
        "features": selected_features
    }


# ============================================================
# HOME
# ============================================================

def build_five_day_production_plan(prospectivity_score, mineral):
    """Return a transparent prototype operating proposal for five days."""
    profile = MINERAL_OPERATION_PROFILES.get(
        mineral,
        MINERAL_OPERATION_PROFILES["Manganese"]
    )
    baseline_tonnes = (640 + (prospectivity_score * 2.8)) * profile["capacity_factor"]
    operating_adjustments = [-0.05, 0.02, 0.06, -0.03, 0.04]
    start_date = date.today()
    plan = []

    for index, adjustment in enumerate(operating_adjustments):
        planned_tonnes = round(baseline_tonnes * (1 + adjustment))
        operating_day = start_date + timedelta(days=index)
        plan.append({
            "day": f"Day {index + 1}",
            "date": operating_day.isoformat(),
            "planned_tonnes": planned_tonnes,
            "activity": (
                "Site preparation" if index == 0 else
                profile["activity"] if index < 4 else
                "Stockpile and review"
            )
        })

    return plan

@app.route("/")
def home():
    """Serve the dashboard and API from one local Flask server."""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "message": "ASTROVA AI Backend is running",
        "satellite_configured": configured()
    })


@app.route("/<path:filename>")
def frontend_asset(filename):
    """Serve dashboard assets such as style.css and script.js."""
    return send_from_directory(FRONTEND_DIR, filename)


# ============================================================
# ANALYZE REGION
# ============================================================

@app.route("/analyze", methods=["POST"])
def analyze():

    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:

        return jsonify({
            "error": "Request body must contain JSON data"
        }), 400

    try:

        mineral = str(data.get(
            "mineral",
            "Manganese"
        )).strip().title()

        latitude = float(
            data.get(
                "latitude",
                12.9716
            )
        )

        longitude = float(
            data.get(
                "longitude",
                77.5946
            )
        )

        analysis_run = str(data.get("analysis_run", ""))[:80]
        source = data.get("data_source", "live")

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid latitude or longitude"
        }), 400

    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return jsonify({"error": "Latitude must be between -90 and 90; longitude between -180 and 180."}), 400
    if mineral not in MINERAL_PROFILES or source not in ("live", "demo"):
        return jsonify({"error": "Choose a supported mineral and live or demo data source."}), 400
    satellite_features, satellite_metadata = None, None
    if source == "live":
        try:
            satellite_features, satellite_metadata = sentinel.features(latitude, longitude)
        except SatelliteError as error:
            return jsonify({"error": str(error), "data_source": "live"}), error.status

    result = calculate_prediction(
        latitude,
        longitude,
        mineral,
        analysis_run,
        satellite_features
    )

    production_plan = build_five_day_production_plan(
        result["prospectivity_score"],
        mineral
    )

    return jsonify({

        "mineral": mineral,

        "latitude": latitude,

        "longitude": longitude,

        "prediction": result["prediction"],

        "prospectivity_score": result["prospectivity_score"],

        "prospectivity": result["prospectivity"],

        "scenario_variation": result["scenario_variation"],
        "model_target": mineral,
        "data_source": source,
        "satellite": satellite_metadata,
        "model_scope": "Selected mineral's Random Forest trained on synthetic labels; mineral prospectivity and operating plans remain unvalidated prototype estimates.",

        "production_plan": production_plan,

        "production_plan_note": (
            "Prototype five-day operational proposal based on the "
            "prospectivity scenario; validate with site constraints."
        ),


        "data_type":
            "COPERNICUS SENTINEL-2 L2A OBSERVATIONS" if source == "live" else "SIMULATED LOCATION-DEPENDENT SATELLITE FEATURES",

        "features":
            result["features"],

        "message": (
            "Satellite inputs are real Sentinel-2 observations. The model was trained on synthetic data; its mineral scores and operating plans remain prototype estimates."
            if source == "live" else
            "Prototype estimate using simulated location-dependent "
            "satellite-like features. Analysis runs include a small "
            "scenario refresh and are not measured geological concentration."
        )
    })


# ============================================================
# PROSPECTIVITY HEATMAP
# ============================================================

@app.route("/heatmap", methods=["GET"])
def heatmap():

    try:

        mineral = request.args.get(
            "mineral",
            "Manganese"
        ).strip().title()

        latitude = float(
            request.args.get(
                "latitude",
                12.9716
            )
        )

        longitude = float(
            request.args.get(
                "longitude",
                77.5946
            )
        )

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid heatmap parameters"
        }), 400

    # Size of the displayed analysis area.
    if mineral not in models or not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return jsonify({"error": "Choose a supported mineral and valid coordinates."}), 400
    # Approximately a regional demonstration grid.

    step = 0.08

    radius = 4

    points = []

    for lat_index in range(
        -radius,
        radius + 1
    ):

        for lon_index in range(
            -radius,
            radius + 1
        ):

            point_latitude = (
                latitude
                + lat_index * step
            )

            point_longitude = (
                longitude
                + lon_index * step
            )

            result = calculate_prediction(
                point_latitude,
                point_longitude,
                mineral
            )

            points.append({

                "latitude":
                    round(point_latitude, 5),

                "longitude":
                    round(point_longitude, 5),

                "prospectivity":
                    result["prospectivity_score"],

                "mineral_presence":
                    result["mineral_presence_percent"]
            })

    return jsonify({

        "mineral": mineral,

        "center": {
            "latitude": latitude,
            "longitude": longitude
        },

        "points": points,

        "data_type":
            "SIMULATED LOCATION-DEPENDENT HEATMAP",

        "message":
            "Demonstration prospectivity surface. "
            "Not derived from real Sentinel-2 imagery."
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )
