# WindSight — Wind Forecast Intelligence

A React + Python pilot dashboard for a UK electricity utility to explore national wind generation forecasts and evaluate forecast accuracy using Elexon Insights data. Built for the Gribricks Full Stack SWE challenge.

> **Data integrity note:** The app does not generate fake sample measurements. If Elexon returns no usable records or is unavailable, the dashboard shows an explicit error/empty state. Run it and verify the live API responses before recording the demo or submitting.

## Features

- React dashboard with responsive layout, forecast-versus-actual chart, error chart, interval table, CSV export, loading and error states.
- Python FastAPI backend that requests Elexon `FUELHH` and `WINDFOR` dataset streams.
- Filters actual generation to `fuelType == WIND` when that field is present.
- Selectable month/year and two forecast views: latest available vintage and day-ahead decision vintage.
- MAE, RMSE, forecast bias, matched interval count, over/under-forecast interval counts.
- Explicit error sign convention: `forecast - actual`; positive error means over-forecast.
- Dockerfiles for both services, `docker-compose.yml`, Render backend configuration and Vercel frontend configuration.
- Basic backend unit tests for response parsing and metric conventions.

## Important modelling assumption

The day-ahead view selects the latest forecast publication at or before **17:00 UTC on the day before delivery**. The challenge brief does not define an exact trading cut-off, so this is an explicit assumption that should be confirmed with the client. It is not presented as a universal UK market rule. The latest-vintage view is retrospective and can include later forecasts; use the day-ahead view when evaluating what was known before the decision.

## Project structure

```text
.
├── backend/
│   ├── app/main.py          # FastAPI routes, Elexon fetch, parsing, metrics
│   ├── tests/test_metrics.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/main.jsx         # React dashboard and charts
│   ├── src/styles.css       # Responsive UI styling
│   ├── index.html
│   ├── package.json
│   ├── vercel.json
│   └── Dockerfile
├── docker-compose.yml
├── render.yaml
└── README.md
```

## Data sources

- `FUELHH` stream: half-hourly generation outturn by fuel type; only wind records are used.
- `WINDFOR` stream: wind generation forecast records with `startTime`, `publishTime` and `generation`.
- Official Elexon API documentation: <https://bmrs.elexon.co.uk/api-documentation/endpoint>
- Elexon states its public Insights APIs do not require an API key: <https://developer.data.elexon.co.uk/>

The backend API base defaults to `https://data.elexon.co.uk/bmrs/api/v1` and can be overridden using `ELEXON_BASE_URL`.

## Run locally (without Docker)

### 1. Start the backend

Python 3.11+ recommended.

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend health: <http://localhost:8000/api/health>
Interactive API docs: <http://localhost:8000/docs>

### 2. Start the frontend in another terminal

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal (usually <http://localhost:5173>).

If the backend is hosted elsewhere, create `frontend/.env`:

```env
VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com
```

Restart the frontend after changing environment variables.

## Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

Open <http://localhost:8080>. The API will be available at <http://localhost:8000/api/health>.

## API routes

- `GET /api/health` — health check.
- `GET /api/metadata` — dataset provenance and API details.
- `GET /api/analysis?year=2026&month=1&view=day-ahead` — dashboard analysis.

Supported views: `day-ahead` and `latest`.

## Run tests

From `backend/` with dependencies installed:

```bash
pytest -q
```

## Deployment

### Backend (Render)

1. Push this repository to GitHub.
2. In Render, create a **Web Service** from the repository and set the root directory to `backend`; choose Docker runtime. `render.yaml` is included as a starting point.
3. Set `FRONTEND_ORIGINS` to the exact deployed Vercel origin, e.g. `https://your-project.vercel.app`.
4. After deploy, check `https://YOUR-BACKEND.onrender.com/api/health`.

### Frontend (Vercel)

1. Import the GitHub repository into Vercel.
2. Set Root Directory to `frontend`.
3. Add environment variable `VITE_API_BASE_URL` with the Render backend base URL, without a trailing slash.
4. Deploy, open the public URL in an incognito window and test a period.

If using free hosting, the backend may sleep between requests; wait for it to wake up and retry.

## AI tool disclosure

AI tools were used to assist with initial scaffolding, implementation, documentation and test drafting. The developer should review, run, understand and validate the code and the live data before submission.

## Before submitting

- [ ] Install dependencies and run locally.
- [ ] Confirm the live Elexon API query parameters and record schemas against the current official docs.
- [ ] Check January 2026 actual and forecast records load and matched metrics are plausible.
- [ ] Confirm the day-ahead publication cut-off matches the intended decision workflow or clearly explain the assumption.
- [ ] Run tests and fix any failures.
- [ ] Deploy frontend and backend; test both URLs in an incognito window.
- [ ] Record the two-part YouTube demo (maximum 10 minutes total) and set it to Unlisted.
- [ ] Create a public GitHub repo with an anonymous/random repository name and include the README.
- [ ] Submit the repo, deployed app and video URLs through the supplied form.

## Limitations

- The challenge's scope is national wind generation only, so the dashboard does not estimate consumer demand or issue a procurement quantity. A procurement recommendation requires demand data and other generation/market inputs that are outside the supplied brief.
- Elexon API query limits and field schemas may change. The project should be validated against live January 2026 responses before submission.
