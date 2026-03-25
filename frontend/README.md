# Cloud Sentinel Frontend

Production-oriented Next.js dashboard for the cloud anomaly backend.

## What this frontend does

- Lets users submit logs as:
  - JSON array payload
  - plain line-based logs
- Proxies requests through Next.js route handlers:
  - `POST /api/analyze`
  - `GET /api/health`
- Displays:
  - anomaly score + decision
  - LLM explanation
  - policy actions
  - compatibility + telemetry
  - raw JSON response

## Environment

Create `.env.local` in `frontend/`:

```bash
BACKEND_API_BASE_URL=http://127.0.0.1:8000
```

## Run locally

From `frontend/`:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Backend requirement

Run the backend API in parallel (from repo root):

```bash
cd backend
uv sync
uv run python -m backend.api_server
```

## Production checks

```bash
npm run lint
npm run typecheck
npm run build
```
