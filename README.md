# Cloud Sentinel Monorepo

This repository is split into two deployable apps:

- `backend/`: Python anomaly detection service (model, parser, agents, API, CLI, tests)
- `frontend/`: Next.js dashboard UI

## Folder Structure

```text
backend/
  backend/         # Python backend package (API/CLI/service)
  agents/          # multi-agent orchestration
  model/           # transformer model + metadata
  parser/          # log parsing components
  utils/           # sequence and dataset utilities
  data/            # benchmark + raw sample logs
  tests/           # backend tests
frontend/
  app/             # Next.js app router
  components/      # UI components
  lib/             # server helpers/API client
  types/           # shared frontend types
```

## Quick Start

1. Run backend:

```bash
cd backend
uv sync
uv run python -m backend.api_server
```

2. Run frontend (new terminal):

```bash
cd frontend
npm install
npm run dev
```

3. Set frontend backend URL in `frontend/.env.local`:

```bash
BACKEND_API_BASE_URL=http://127.0.0.1:8000
```

## Deployment

- Deploy `backend/` as one service.
- Deploy `frontend/` as one service.

This separation keeps release and scaling independent for each tier.
