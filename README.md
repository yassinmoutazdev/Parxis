# Praxis

Personal AI English Learning Coach — local-first, privacy-respecting, built for intermediate+ learners who want to maintain and grow their English through deliberate practice.

## Quick Start

**Just double-click `scripts/run.bat`** — it starts both the backend and frontend in the background (no console windows), shows a small "Praxis is starting..." page while it works, and swaps it for the real app the moment both are ready.

That's it. No IDE required, no manual terminal commands, and nothing to keep open.

### What `run.bat` Does

1. Verifies `uv` and Node.js are installed
2. Syncs backend dependencies (`uv sync`) and runs database migrations (`alembic upgrade head`)
3. Installs frontend dependencies (`npm install`) if needed
4. Starts the FastAPI backend on `http://127.0.0.1:8000` and the Vite frontend on `http://localhost:5173`, both as hidden background processes
5. Opens the app in your browser once both report healthy

If something goes wrong (a missing prerequisite, a failed install, a server that never comes up), the status page explains what happened and points at the relevant log file under `logs/`.

**To stop Praxis**, double-click `scripts/stop.bat`. Since everything runs hidden, this is the only way to shut it down — closing a browser tab does not stop the servers.

---

## For Development

If you prefer running from your IDE or terminal:

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: `http://localhost:5173`

### Database

SQLite database lives at `data/praxis.db` (created automatically). Backups go to `data/backups/`.

### Vault (Obsidian Notes)

Set your vault path in Settings → Vault Path. The watcher picks up new/changed `.md` files and queues extracted items for your approval.

---

## Requirements

- **Python 3.11+** (managed via `uv`)
- **Node.js 20+** and **npm**
- **Ollama** running locally (for LLM inference) — or configure an Ollama Cloud API key in Settings

---

## Project Structure

```
Praxis/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── approvals/ # Approval queue for extracted items
│   │   ├── chat/      # Coach chat + tool calling
│   │   ├── config/    # Runtime configuration (ConfigService)
│   │   ├── dashboard/ # Dashboard overview, trends, mastery
│   │   ├── ingestion/ # Vault watcher + note processing
│   │   ├── llm/       # LLM adapters, prompts, tools
│   │   ├── proficiency/ # CEFR band calculation
│   │   ├── quizzes/   # Quiz generation + grading
│   │   ├── reports/   # Weekly reports
│   │   ├── settings/  # Settings API (vault, backup, Ollama key)
│   │   └── writing/   # Writing prompts + evaluation
│   └── pyproject.toml
├── frontend/          # React + TypeScript + Vite
│   ├── src/
│   │   ├── features/
│   │   │   ├── approvals/
│   │   │   ├── chat/
│   │   │   ├── dashboard/
│   │   │   ├── reports/
│   │   │   ├── settings/
│   │   │   └── writing/
│   │   └── shared/
│   └── package.json
├── scripts/
│   ├── run.bat        # Double-click to start everything (hidden, no console windows)
│   └── stop.bat       # Double-click to stop it
└── docs/              # Architecture, PRD, task plans
```

---

## Key Features

- **CEFR-anchored proficiency** — Weekly writing evaluations feed a hysteresis-smoothed CEFR band (A1–C2) displayed on the dashboard
- **Quiz & Writing practice** — Unified chat interface, manual or coach-triggered
- **Vault ingestion** — Point at an Obsidian vault; new notes are parsed for learnable items (collocations, idioms, phrasal verbs, grammar notes, personal examples)
- **Approval queue** — Nothing enters your learning set without your review
- **Spaced repetition** — SM-2 scheduling with time-decayed mastery scores
- **Weekly reports** — LLM-generated narrative summaries with mastery snapshots
- **Local-first** — SQLite, file-based vault watching, optional Ollama Cloud key stored in config (not `.env`)

---

## Configuration

Runtime settings (vault path, Ollama Cloud API key, review pace, etc.) are managed via the **Settings** page in the app and persisted in the database via `ConfigService`. No `.env` editing required after initial setup.

---

## License

MIT — see `LICENSE` for details.