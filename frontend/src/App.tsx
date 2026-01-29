import { useMemo, useState } from "react";
import { approveThread, submitEmail } from "./api";

type DraftState =
  | { kind: "idle" }
  | { kind: "drafting" }
  | { kind: "awaiting_human_review"; threadId: string; status: string; draft: string }
  | { kind: "approving"; threadId: string; status: string; draft: string }
  | { kind: "sent"; threadId: string; status: string; finalResponse: string }
  | { kind: "error"; message: string };

type EmailForm = {
  fromEmail: string;
  toEmail: string;
  subject: string;
  bodyText: string;
};

// Initial form values are empty so the example content is shown as
// placeholders only (visual suggestions), not as actual filled values.
const DEFAULT_EMAIL: EmailForm = {
  fromEmail: "",
  toEmail: "",
  subject: "",
  bodyText: "",
};

export function App() {
  const [form, setForm] = useState<EmailForm>(DEFAULT_EMAIL);
  const [draftState, setDraftState] = useState<DraftState>({ kind: "idle" });

  const canDraft = useMemo(() => draftState.kind !== "drafting" && draftState.kind !== "approving", [draftState.kind]);
  const canApprove = useMemo(
    () => draftState.kind === "awaiting_human_review",
    [draftState.kind],
  );

  async function onDraft() {
    setDraftState({ kind: "drafting" });
    try {
      const res = await submitEmail({
        message_id: `frontend-${Date.now()}`,
        thread_external_id: null,
        from_email: form.fromEmail.trim() || "vendor@example.com",
        to_email: form.toEmail.trim() || "you@company.com",
        subject: form.subject.trim() || "Quote for Salesforce Sales Cloud seats",
        body_text:
          form.bodyText.trim() ||
          "Hi,\n\nHere is our quote for Salesforce Sales Cloud at $80 per seat per month for 50 seats.\n\nBest,\nVendor",
      });

      setDraftState({
        kind: "awaiting_human_review",
        threadId: res.thread_id,
        status: res.status,
        draft: res.draft_response,
      });
    } catch (error) {
      setDraftState({ kind: "error", message: String(error) });
    }
  }

  async function onApprove() {
    if (draftState.kind !== "awaiting_human_review") {
      return;
    }

    setDraftState({
      kind: "approving",
      threadId: draftState.threadId,
      status: draftState.status,
      draft: draftState.draft,
    });

    try {
      const res = await approveThread(draftState.threadId);
      setDraftState({
        kind: "sent",
        threadId: res.thread_id,
        status: res.status,
        finalResponse: res.final_response ?? "",
      });
    } catch (error) {
      setDraftState({ kind: "error", message: String(error) });
    }
  }

  function onReset() {
    setForm(DEFAULT_EMAIL);
    setDraftState({ kind: "idle" });
  }

  const statusText =
    draftState.kind === "idle"
      ? "idle"
      : draftState.kind === "drafting"
        ? "drafting..."
        : draftState.kind === "approving"
          ? "approving..."
          : draftState.kind === "awaiting_human_review"
            ? draftState.status
            : draftState.kind === "sent"
              ? draftState.status
              : "error";

  const threadId =
    draftState.kind === "awaiting_human_review" ||
    draftState.kind === "approving" ||
    draftState.kind === "sent"
      ? draftState.threadId
      : "—";

  const outputText =
    draftState.kind === "awaiting_human_review"
      ? draftState.draft
      : draftState.kind === "sent"
        ? draftState.finalResponse
        : draftState.kind === "error"
          ? draftState.message
          : "Draft will appear here after analysis.";

  return (
    <div className="page">
      <header>
        <h1>Negotiator-AI</h1>
        <p>Tail-spend SaaS negotiation agent with human-in-the-loop email approval.</p>
      </header>

      <main className="card">
        <div className="pill">
          <span className="dot" />
          <span>Live negotiation sandbox</span>
        </div>

        <div className="grid">
          <section>
            <h2>1. Paste vendor email</h2>
            <p className="small">
              The backend analyzes the email, looks up mock market rates for the SaaS product, and drafts a reply.
            </p>

            <div className="field-group">
              <label htmlFor="from-email">From (vendor)</label>
              <input
                id="from-email"
                type="email"
                value={form.fromEmail}
                placeholder="vendor@example.com"
                onChange={(e) => setForm((prev) => ({ ...prev, fromEmail: e.target.value }))}
              />
            </div>

            <div className="field-group">
              <label htmlFor="to-email">To (you)</label>
              <input
                id="to-email"
                type="email"
                value={form.toEmail}
                placeholder="you@company.com"
                onChange={(e) => setForm((prev) => ({ ...prev, toEmail: e.target.value }))}
              />
            </div>

            <div className="field-group">
              <label htmlFor="subject">Subject</label>
              <input
                id="subject"
                type="text"
                value={form.subject}
                placeholder="Quote for Salesforce Sales Cloud seats"
                onChange={(e) => setForm((prev) => ({ ...prev, subject: e.target.value }))}
              />
            </div>

            <div className="field-group">
              <label htmlFor="body">Email body</label>
              <textarea
                id="body"
                value={form.bodyText}
                placeholder={
                  "Hi,\n\nHere is our quote for Salesforce Sales Cloud at $80 per seat per month for 50 seats.\n\nBest,\nVendor"
                }
                onChange={(e) => setForm((prev) => ({ ...prev, bodyText: e.target.value }))}
              />
            </div>

            <div className="button-row">
              <button className="primary" onClick={() => onDraft()} disabled={!canDraft}>
                Analyze and draft
              </button>
              <button className="secondary" type="button" onClick={() => onReset()} disabled={!canDraft}>
                Reset
              </button>
            </div>
          </section>

          <section>
            <h2>2. Review & approve draft</h2>
            <p className="small">The agent pauses before sending. You must approve before the draft is sent.</p>

            <div className="status">
              Status: <strong>{statusText}</strong>
            </div>
            <div className="small thread-row">
              Thread ID: <span>{threadId}</span>
            </div>

            <h2 className="draft-title">Draft reply</h2>
            <pre className="output">{outputText}</pre>

            <div className="button-row">
              <button className="primary" onClick={() => onApprove()} disabled={!canApprove}>
                Approve and send
              </button>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

