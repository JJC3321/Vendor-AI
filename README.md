Negotiator-AI
============

Tail-spend SaaS negotiation agent with a LangGraph-powered backend and a React frontend.

## Backend (FastAPI + LangGraph)

- Code lives in `backend/`:
  - `backend/main.py`: FastAPI app, `/webhook/email` and `/approve/{thread_id}` endpoints.
  - `backend/graph.py`: LangGraph state machine and human-in-the-loop breakpoint.
  - `backend/models.py`, `backend/schemas.py`, `backend/tools.py`, `backend/db.py`, `backend/config.py`.
- Environment:
  - Copy `backend/.env` (or create it) and set at least:
    - `GOOGLE_API_KEY`
    - optionally `DATABASE_URL`, `ENV`, `GEMINI_MODEL_NAME` (defaults are sensible for local dev).

### Run backend (dev)

From the project root:

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## Frontend (React + Vite)

- Code lives in `frontend/`:
  - `frontend/index.html`: Vite entry.
  - `frontend/src/App.tsx`: main UI for pasting vendor emails and reviewing drafts.
  - `frontend/src/api.ts`: typed client calling the backend.
  - `frontend/src/styles.css`: minimal dark UI.
- Environment:
  - Copy `frontend/.env.example` to `frontend/.env` and set:
    - `VITE_API_BASE_URL` (default: `http://localhost:8000`).

### Run frontend (dev)

From the project root:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (usually `http://localhost:5173`).

## Human-in-the-loop flow

1. Frontend calls `POST /webhook/email` with a vendor email payload.
2. Backend:
   - Logs the email and creates a `NegotiationThread` in the database.
   - Runs the LangGraph app, which:
     - analyzes the email,
     - decides on a strategy using mock market rates,
     - drafts a reply,
     - pauses **before** the `human_review` node due to `interrupt_before=["human_review"]`.
   - Returns `thread_id`, status, and the drafted email text.
3. Frontend displays the draft and thread id; user can review and click **Approve and send**.
4. Frontend calls `POST /approve/{thread_id}`.
5. Backend resumes the graph from the paused checkpoint, records an outbound email log, and updates the negotiation status (mock “send”).

