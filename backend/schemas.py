from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, EmailStr, Field


NegotiationStatusEnum = Literal[
    "pending_analysis",
    "analyzing",
    "strategizing",
    "drafting",
    "awaiting_human_review",
    "approved",
    "sent",
    "rejected",
]


class NegotiationState(TypedDict, total=False):
    """State container shared across LangGraph nodes.

    This is the in-memory representation of the negotiation progress and
    is persisted by LangGraph's checkpointer between node executions.
    """

    messages: list[BaseMessage]
    current_offer: Optional[float]
    target_price: Optional[float]
    status: NegotiationStatusEnum
    vendor_name: Optional[str]
    product_name: Optional[str]
    # Contact names for more personalised greetings and sign-offs.
    sender_name: Optional[str]
    recipient_name: Optional[str]
    thread_id: Optional[str]
    # Optional field to hold the drafted email reply text.
    draft_response: Optional[str]


class EmailPayload(BaseModel):
    """Incoming email webhook payload from an email provider.

    This model is used by the FastAPI `/webhook/email` endpoint to simulate
    providers like Postmark or Gmail webhooks in the MVP.
    """

    message_id: str = Field(..., description="Provider-specific message identifier.")
    thread_external_id: Optional[str] = Field(
        default=None,
        description="Provider thread/conversation id, if available.",
    )

    from_email: EmailStr = Field(..., description="Sender email address (vendor).")
    to_email: EmailStr = Field(..., description="Recipient email address.")

    subject: str = Field(..., description="Email subject line.")
    body_text: str = Field(..., description="Plain-text body of the email.")

    received_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the email was received by our system.",
    )

