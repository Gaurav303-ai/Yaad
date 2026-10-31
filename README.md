# Yaad

Yaad is a Hinglish-first agentic meeting-to-execution system. It stores and lists labelled meeting transcripts, extracts quote-verified decisions/actions/intents with meeting-relative deadlines, compares decisions against earlier memory, and presents conflicts and review items in the React client. Tracker tasks are created only after explicit human approval.

## Stack

- **Client:** React, Vite, TypeScript, Tailwind CSS, shadcn/ui
- **Server:** Python 3.11+, FastAPI
- **Services:** Supabase, Gemini, and optional tracker, Telegram, email, and embeddings providers

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

The server requires `GEMINI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY` to be set in `server/.env.local` before startup. The client uses only public `VITE_` variables; never put server secrets in the client environment.

### Apply the Supabase schema

In the Supabase Dashboard, open **SQL Editor** and run these committed migrations in order:

1. `supabase/migrations/0001_init.sql`
2. `supabase/migrations/0002_core_schema.sql`
3. `supabase/migrations/0003_conflict_memory.sql`

The second migration creates the project tables and seeds Priya, Rahul, Amit, and Neha. Run the third migration before using `POST /api/meetings/{meeting_id}/process`; it adds decision metadata and the pgvector search function. The API uses the server-only `SUPABASE_SECRET_KEY`; no database secret is exposed to the browser.

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
| `GEMINI_API_KEY` | Google Gemini server API key | Now |
| `GEMINI_MODEL` | Model used for structured generation | Now |
| `SUPABASE_URL` | Supabase project URL | Now |
| `SUPABASE_SECRET_KEY` | Server-only Supabase secret key | Now |
| `EMBEDDINGS_PROVIDER`, `VOYAGE_API_KEY` | Optional Voyage semantic search; topic filtering plus Gemini comparison is used without the key | M3 optional |
| `TRACKER` | Select `trello` or `github` | Before approving tasks |
| `TRELLO_KEY`, `TRELLO_TOKEN`, `TRELLO_LIST_ID` | Trello tracker configuration | If using Trello |
| `GITHUB_TOKEN`, `GITHUB_REPO` | GitHub tracker configuration | If using GitHub Issues |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Development long polling and approved-action reminders | Before Telegram use |
| `TELEGRAM_WEBHOOK_SECRET` | Authenticates Telegram webhook requests in production | Before production Telegram use |
| `RESEND_API_KEY`, `DIGEST_FROM_EMAIL` | Email integration | Later |
| `APP_ENV`, `CLIENT_URL`, `CRON_SECRET`, `DEMO_MODE` | Application/deployment configuration | As needed |

See [client/.env.example](client/.env.example) and [server/.env.example](server/.env.example) for the complete variable list.

In development, Telegram listens for `/approve <item-id>` and `/reject <item-id>` using long polling. In production, configure Telegram's webhook URL as `https://<server>/api/telegram/webhook` and set the matching `TELEGRAM_WEBHOOK_SECRET`. Telegram reminders are created only for approved actions; `DEMO_MODE=true` gives a newly approved action without a deadline a deadline two minutes ahead.

The review API never creates tracker work from ingestion or listing. Approve actions individually or use **Approve all actions**; rejected items leave the pending queue, and intents cannot be approved as tasks.

## Run both services

From the repository root, install the root runner and client dependencies, create the server virtual environment, install server requirements, and populate both local environment files. Then run:

```powershell
npm run dev
```

The client runs at `http://localhost:5173`; the API runs at `http://localhost:8000` and exposes `GET /health`.

## Evaluate demo extraction

With the server environment active and `GEMINI_API_KEY` set, run the extraction evaluation from `server/`:

```powershell
python scripts/eval.py
```

The script processes the four transcripts in `data/` and reports pass/fail for each expected item in `data/expected.json`.
Run `python scripts/eval.py --conflicts` to also verify the three expected cross-meeting conflicts and the paid-ads false-positive guard.

## Deployment

- Deploy `client/` to Vercel. The included `vercel.json` rewrites client routes to `index.html`; configure `VITE_API_URL` to the deployed API URL. The Supabase browser variables are only needed if a future client feature connects directly to Supabase.
- Deploy `server/` to Render or Railway using the included `Procfile`. Configure the server environment variables in the hosting dashboard and set `CLIENT_URL` to the exact deployed client origin for CORS.
- Keep server credentials in the server hosting environment only. The client must use the Supabase publishable key, never the secret key.
