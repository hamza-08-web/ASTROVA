# Railway backend

Deploy this repository as a Railway service with the repository root as its root directory.
`railway.json` configures Railpack, Gunicorn, and the `/api/health` startup health check.
`requirements.txt` and `.python-version` match the local model's runtime.

The runtime needs `server.py` and `ASTROVA/backend/expo_model.pkl`.
The database, virtual environment, and experimental datasets are not required.
The bundled model uses simulated features and is intended for demonstration.

After deployment, generate a public domain in Railway's service networking settings.
Verify `https://YOUR-RAILWAY-DOMAIN/api/health`, then connect the frontend to that domain.
The frontend currently uses a local API address; publishing the backend alone does not change that address.

# Vercel frontend

Keep the Vercel root directory at the repository root. `vercel.json` publishes only
`ASTROVA/frontend`, so the backend and model are not included in the static site.
