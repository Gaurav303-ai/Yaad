# Yaad

Yaad is a Hinglish-first agentic meeting-to-execution system. This repository is the initial project scaffold; product behavior will be added in later milestones.

## Stack

- **Client:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui
- **Server:** Python 3.11+, FastAPI
- **Services:** Supabase, Anthropic, and optional tracker, Telegram, email, and embeddings providers

## Setup

Install the root process runner from the repository root:

```powershell
npm install
```

### Client

```powershell
cd client
npm install
Copy-Item .env.example .env.local
npm run dev
```

On macOS/Linux, use `cp .env.example .env.local` instead of `Copy-Item`.

### Server

```powershell
cd server
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
Copy-Item .env.example .env.local
uvicorn app.main:app --reload --port 8000
```

The server requires `ANTHROPIC_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY` to be set in `server/.env.local` before startup. The client uses only public `VITE_` variables; never put server secrets in the client environment.

## Environment variables

### Client (`client/.env.local`)

| Variable | Purpose |
| --- | --- |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Browser-safe Supabase publishable key |
| `VITE_API_URL` | FastAPI base URL; Vite proxies `/api` during local development |

### Server (`server/.env.local`)

| Variable | Purpose | Needed |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Anthropic server API key | Now |
| `ANTHROPIC_MODEL` | Model used for structured generation | Now |
| `SUPABASE_URL` | Supabase project URL | Now |
| `SUPABASE_SECRET_KEY` | Server-only Supabase secret key | Now |
| `EMBEDDINGS_PROVIDER`, `VOYAGE_API_KEY` | Embeddings provider configuration | Later |
| `TRACKER`, `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` | Trello tracker configuration | Later |
| `GITHUB_TOKEN`, `GITHUB_REPO` | GitHub tracker configuration | Later |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram integration | Later |
| `RESEND_API_KEY`, `DIGEST_FROM_EMAIL` | Email integration | Later |
| `APP_ENV`, `CLIENT_URL`, `CRON_SECRET`, `DEMO_MODE` | Application/deployment configuration | As needed |

See [client/.env.example](client/.env.example) and [server/.env.example](server/.env.example) for the complete variable list.

## Run both services

From the repository root, install the root runner and client dependencies, create the server virtual environment, install server requirements, and populate both local environment files. Then run:

```powershell
npm run dev
```

The client runs at `http://localhost:5173`; the API runs at `http://localhost:8000` and exposes `GET /health`.

## Deployment

- Deploy `client/` to Vercel. The included `vercel.json` rewrites client routes to `index.html`; configure the three `VITE_` variables in Vercel.
- Deploy `server/` to Render or Railway using the included `Procfile`. Configure the server environment variables in the hosting dashboard and set `CLIENT_URL` to the deployed client origin.
- Keep server credentials in the server hosting environment only. The client must use the Supabase publishable key, never the secret key.
