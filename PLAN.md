## Negotiator-AI MVP – Plan

### 1. Folder / Module Structure

- **Project root**
  - `PLAN.md` – this document.
  - `.env` – environment variables (e.g. `GOOGLE_API_KEY`, `ENV`, `DATABASE_URL`).
  - `requirements.txt` – Python dependencies (FastAPI, LangGraph, SQLModel, etc.).
  - `main.py` – FastAPI application entrypoint and API routes.
  - `graph.py` – LangGraph graph definition and node implementations.
  - `models.py` – SQLModel ORM models (DB entities).
  - `schemas.py` – Pydantic models and TypedDict state for the agent.
  - `tools.py` – Agent tools for use inside the LangGraph nodes (market lookup, counter offer, etc.).
  - `config.py` – Configuration helpers (loading `.env`, building `DATABASE_URL`, Gemini settings).
  - `db.py` – Database session and engine creation (SQLite for dev, PostgreSQL for prod).

### 2. Data Models

- **In `schemas.py`**
  - `NegotiationStatusEnum` – Literal type or `Enum` (`"pending_analysis" | "analyzing" | "strategizing" | "drafting" | "awaiting_human_review" | "approved" | "sent" | "rejected"`).
  - `NegotiationState` – `TypedDict` for LangGraph state:
    - `messages: list[BaseMessage]` (LangChain messages; initially a single system+user email message).
    - `current_offer: float | None`
    - `target_price: float | None`
    - `status: NegotiationStatusEnum`
    - `vendor_name: str | None`
    - `product_name: str | None`
    - `thread_id: str | None` (maps LangGraph thread to DB negotiation thread).
  - `EmailPayload` – Pydantic model representing incoming email webhook:
    - `message_id: str`
    - `thread_external_id: str | None` (email provider thread/conversation id).
    - `from_email: str`
    - `to_email: str`
    - `subject: str`
    - `body_text: str`
    - `received_at: datetime`

- **In `models.py` (SQLModel)**
  - `NegotiationThread` – main negotiation record:
    - `id: int` (PK, auto)
    - `thread_id: str` (LangGraph thread id, unique)
    - `vendor_name: str | None`
    - `product_name: str | None`
    - `current_offer: float | None`
    - `target_price: float | None`
    - `status: str`
    - `last_email_subject: str | None`
    - `last_email_body: str | None`
    - `created_at: datetime`
    - `updated_at: datetime`
  - `EmailLog` – optional log of inbound/outbound emails (MVP: minimal fields):
    - `id: int` (PK)
    - `negotiation_thread_id: int` (FK → `NegotiationThread.id`)
    - `direction: str` (`"inbound"` | `"outbound"`)
    - `subject: str`
    - `body: str`
    - `created_at: datetime`

### 3. Agent Tools (`tools.py`)

- **`lookup_market_rates(product_name: str) -> dict[str, float]`**
  - Mock implementation returning a fair price range for a given product.
  - Example response: `{"product_name": product_name, "low": 90.0, "high": 110.0, "reference": 100.0}`.
  - Internally uses simple rule-based logic or a static dictionary.

- **`calculate_counter_offer(current_price: float, market_rate: float) -> float`**
  - Deterministic pricing logic for the next offer.
  - MVP rule: propose `max(market_rate * 0.9, current_price * 0.9)` or a similar simple rule.
  - Include type hints and basic validation (e.g., non-negative prices).

### 4. LangGraph Workflow (`graph.py`)

- **4.1. Setup**
  - Initialize Gemini client via LangChain:
    - `from langchain_google_genai import ChatGoogleGenerativeAI`
    - `model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.4, api_key=GOOGLE_API_KEY_FROM_CONFIG)`
  - Define `NegotiationState` as the graph state type.
  - Build the graph using `StateGraph[NegotiationState]`.

- **4.2. Nodes**
  - **Node 1: `analyze_node(state: NegotiationState) -> NegotiationState`**
    - Input: initial state with `messages` containing the raw email body.
    - Use Gemini to extract:
      - `vendor_name`
      - `product_name`
      - `current_offer` (price quoted)
    - Update `status` to `"strategizing"`.
  - **Node 2: `strategy_node(state: NegotiationState) -> NegotiationState`**
    - Use `lookup_market_rates(product_name)` to get `market_rate`.
    - Compare `current_offer` vs. `market_rate`.
    - Decide on an action: `"accept" | "reject" | "counter"`.
    - If `"counter"`, call `calculate_counter_offer`.
    - Store decision (e.g., in `state.messages` as a tool result or in a dedicated field) and set `status` to `"drafting"`.
  - **Node 3: `draft_node(state: NegotiationState) -> NegotiationState`**
    - Use Gemini to draft an email reply:
      - If `"accept"`: polite acceptance and confirmation.
      - If `"reject"`: polite decline.
      - If `"counter"`: propose counter price and justification referencing market rates.
    - Attach draft text to the state (e.g., as the latest assistant `AIMessage` or a `draft_response: str` field).
    - Set `status` to `"awaiting_human_review"`.
  - **Node 4: `human_review_node(state: NegotiationState) -> NegotiationState`**
    - This node itself does not send an email.
    - It simply represents a graph breakpoint where execution pauses for human approval.
    - `status` remains `"awaiting_human_review"` until `/approve/{thread_id}` is called.

- **4.3. Edges and Interrupt / Human-in-the-loop**
  - Define a linear path:
    - `start` → `analyze_node` → `strategy_node` → `draft_node` → `human_review_node`.
  - Configure LangGraph with `interrupt_before=["human_review_node"]`.
    - When the graph reaches `human_review_node`, execution pauses and returns control to the API.
    - The paused state (including the drafted email) is checkpointed using LangGraph's built-in persistence.
  - Each run is associated with a `thread_id`:
    - On `/webhook/email`, create a new LangGraph thread and persist `thread_id` in `NegotiationThread`.
    - On `/approve/{thread_id}`, resume the graph from the paused checkpoint; the graph can have a final node (e.g., `send_email_node`) that is only invoked after approval.
  - For the MVP, **actual email sending can be mocked** (e.g., printing to logs or storing the approved text in `EmailLog`).

### 5. API Layer (`main.py`)

- **FastAPI app setup**
  - Create `app = FastAPI(title="Negotiator-AI")`.
  - Dependency-inject DB sessions using `SessionLocal` from `db.py`.
  - Initialize the LangGraph app and a checkpointer at startup (e.g., SQLite-backed).

- **Endpoints**
  - **`POST /webhook/email`**
    - Body: `EmailPayload`.
    - Steps:
      1. Persist initial `NegotiationThread` + an inbound `EmailLog`.
      2. Build initial `NegotiationState` (set `status="pending_analysis"`).
      3. Start a new graph run:
         - Create a `thread_id` (from LangGraph) and save it to the DB.
         - Invoke the graph until it hits the `human_review_node` interrupt.
      4. Return:
         - `thread_id`
         - current `status` (`"awaiting_human_review"`)
         - drafted email text for the human to review.
  - **`POST /approve/{thread_id}`**
    - Path param: `thread_id` (LangGraph thread id).
    - Optional body: approval metadata (e.g., `approved_by`, optional edits to the draft).
    - Steps:
      1. Fetch the corresponding `NegotiationThread` from DB; ensure it is in `"awaiting_human_review"`.
      2. Resume the LangGraph run from the paused checkpoint for this `thread_id`, continuing beyond the `human_review_node`.
      3. In the final node (e.g., `send_email_node`), perform the side-effect (mock email send and log as outbound `EmailLog`), update `NegotiationThread.status` to `"sent"` or `"rejected"`.
      4. Return updated negotiation status and the final email body that was "sent".

- **Notes on Human-in-the-loop**
  - The `interrupt_before=["human_review_node"]` configuration ensures:
    - The model never sends an email without human approval.
    - The agent stops after drafting.
    - A human (via dashboard or other UI) inspects and approves the draft using `thread_id`.
  - Comments in `graph.py` and `main.py` will clearly document:
    - Where the interrupt happens.
    - How `thread_id` maps a DB negotiation to a LangGraph run.
    - That `/approve/{thread_id}` is the only way to resume execution past the human review step.

### 6. Typing and Code Quality

- Use Python 3.11+ type hints everywhere (mypy-friendly):
  - `from __future__ import annotations` when helpful.
  - Avoid `Any` where possible; use `TypedDict`, `Literal`, and generics.
- Keep business logic (tools, strategy) pure and side-effect free; DB and IO handled in `main.py` / `db.py` / final send node.
- Follow the provided clean code rules (no magic numbers, clear naming, small focused functions).

### 7. Implementation Order After Plan Approval

1. Implement strongly typed models in `schemas.py` and `models.py`.
2. Implement tools in `tools.py`.
3. Implement DB setup in `db.py` and configuration in `config.py`.
4. Implement LangGraph workflow in `graph.py` (with clear human-in-the-loop comments).
5. Implement FastAPI app and endpoints in `main.py`.
6. Add `requirements.txt` and a minimal `README` if needed.

