export type EmailPayload = {
  message_id: string;
  thread_external_id: string | null;
  from_email: string;
  to_email: string;
  subject: string;
  body_text: string;
};

export type DraftResponse = {
  thread_id: string;
  status: string;
  draft_response: string;
};

export type ApproveResponse = {
  thread_id: string;
  status: string;
  final_response: string | null;
};

const DEFAULT_API_BASE_URL = "http://localhost:8000";

function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  return configured?.trim() ? configured.trim() : DEFAULT_API_BASE_URL;
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Backend error (${response.status}): ${text}`);
  }

  return (await response.json()) as T;
}

export async function submitEmail(payload: EmailPayload): Promise<DraftResponse> {
  return await requestJson<DraftResponse>("/webhook/email", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function approveThread(threadId: string): Promise<ApproveResponse> {
  return await requestJson<ApproveResponse>(`/approve/${encodeURIComponent(threadId)}`, {
    method: "POST",
  });
}

