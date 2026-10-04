# Railway backend

Deploy this repository as a Railway service with the repository root as its root directory.
`railway.json` configures Railpack, Gunicorn, and the `/api/health` startup health check.
`requirements.txt` and `.python-version` match the local model's runtime.

The runtime needs `server.py` and `ASTROVA/backend/expo_model.pkl`.
The database, virtual environment, and experimental datasets are not required.
The bundled model uses simulated features and is intended for demonstration.

The public backend is `https://astrova-backend-production.up.railway.app`.
Verify `/api/health` for availability. Deployed frontend pages use this API;
local previews use Flask at `http://127.0.0.1:5000`.

# Vercel frontend

Keep the Vercel root directory at the repository root. `vercel.json` publishes only
`ASTROVA/frontend`, so the backend and model are not included in the static site.

Frontend: https://astrova-frontend-pearl.vercel.app/
Railway project: https://railway.com/project/cac7fb8e-1bcf-4e59-ab89-3219a2d8d77f
