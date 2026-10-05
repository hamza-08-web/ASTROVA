# ASTROVA

Mineral intelligence dashboard with a Flask API and separate Random Forest models
for Manganese, Nickel, and Cobalt.

## Folder structure

```text
frontend/                 Website HTML, JavaScript, and CSS
backend/expo_model.pkl    Bundle of three mineral-specific models
backend/satellite.py      Copernicus satellite retrieval
backend/train_model.py    Rebuild the synthetic mineral models
tests/                    Satellite integration checks
server.py                 Flask API and local website server
requirements.txt          Python dependencies
railway.json              Railway backend deployment settings
vercel.json               Vercel frontend deployment settings
DEPLOYMENT.md             Deployment URLs and instructions
```

The hidden `.venv` folder contains the local Python environment, `.git` contains
Git history, `.gitignore` excludes local/generated files, and `.python-version`
selects the deployment's Python version.

## Run locally

From this folder:

```bash
.venv/bin/python3 -m pip install -r requirements.txt
.venv/bin/python3 server.py
```

Open http://127.0.0.1:5000. The local dashboard uses the local API;
the deployed dashboard uses Railway.

For a fresh checkout, create the environment first:

```bash
python3 -m venv .venv
```

## API

- `GET /api/health`: check backend availability.
- `POST /analyze`: analyze a mineral and coordinates.
- `GET /heatmap`: generate a demonstration prospectivity surface.

Example live analysis body (requires credentials):

```json
{"mineral": "Manganese", "latitude": 12.9716, "longitude": 77.5946, "data_source": "live"}
```

Live mode retrieves Copernicus Sentinel-2 L2A observations. Demo mode uses
simulated features. The models were trained on synthetic data, so mineral scores
and operating proposals remain experimental in both modes.

## Enable Copernicus satellite data

1. Register at https://dataspace.copernicus.eu/ and open the Sentinel Hub dashboard.
2. Under User Settings, create an OAuth client with the Client Credentials grant type.
3. In Railway, open the `astrova-backend` service's Variables and add `SH_CLIENT_ID`
   and `SH_CLIENT_SECRET`. Save/deploy the variables. Keep the secret out of GitHub
   and frontend files.
4. Select Copernicus Sentinel-2 in the dashboard and analyze a location.

The API checks the past 30 days and selects the newest daily observation with at
least 50% valid pixels in a 200 m area. Clouds, shadows, and snow are masked.
It averages six reflectance bands and NDVI/NDWI at approximately 20 m spacing.
The response includes the observation date and coverage; this is latest available
imagery, not continuous real-time video. Repeated locations are cached for 15 minutes.
Live-mode errors never silently substitute simulated data. Demo mode is explicitly selectable.

For local use, export both environment variables before starting `server.py`;
`.env.example` lists their names. The app does not automatically load `.env` files.

Documentation: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Statistical/Examples.html

Unused prototypes, training scripts, datasets, and the local database were moved
to a dated backup folder beside this project. They are not needed to run the app.

## Mineral-specific predictions

The selected mineral routes the same observed satellite bands to its own model.
Each classifier is trained only on that mineral's 1,800 synthetic samples and
labels. Raw satellite measurements are not modified to force different scores.
Distinct models can legitimately return equal scores for some inputs.

To reproduce the bundled models:

```bash
.venv/bin/python3 backend/train_model.py
```

Temporary training data is generated during training and removed afterward.
Holdout scores measure synthetic-label performance only, not geological accuracy.
