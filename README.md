# ASTROVA

Mineral intelligence dashboard with a Flask API and a saved Random Forest model.

## Folder structure

```text
frontend/                 Website HTML, JavaScript, and CSS
backend/expo_model.pkl    Saved model used by the API
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

Example analysis body:

```json
{"mineral": "Manganese", "latitude": 12.9716, "longitude": 77.5946}
```

The model and satellite-like features are simulated for demonstration.
Unused prototypes, training scripts, datasets, and the local database were moved
to a dated backup folder beside this project. They are not needed to run the app.
