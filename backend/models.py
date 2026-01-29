from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class NegotiationStatus(str, Enum):
    """Database-level status for a negotiation thread.

    This mirrors, but is decoupled from, the in-memory LangGraph status enum.
    """

    PENDING_ANALYSIS = "pending_analysis"
    ANALYZING = "analyzing"
    STRATEGIZING = "strategizing"
    DRAFTING = "drafting"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    APPROVED = "approved"
    SENT = "sent"
    REJECTED = "rejected"


class EmailDirection(str, Enum):
    """Direction of an email relative to the Vendor AI system."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class NegotiationThread(SQLModel, table=True):
    """Persistent representation of a negotiation flow with a vendor."""

    id: Optional[int] = Field(default=None, primary_key=True)

    # LangGraph thread identifier used to resume executions.
    thread_id: str = Field(index=True, unique=True)

    vendor_name: Optional[str] = Field(default=None, index=True)
    product_name: Optional[str] = Field(default=None, index=True)

    current_offer: Optional[float] = Field(default=None, ge=0.0)
    target_price: Optional[float] = Field(default=None, ge=0.0)

    status: NegotiationStatus = Field(
        sa_column_kwargs={"nullable": False},
        default=NegotiationStatus.PENDING_ANALYSIS,
    )

    last_email_subject: Optional[str] = Field(default=None)
    last_email_body: Optional[str] = Field(default=None)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"nullable": False},
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"nullable": False},
    )


class EmailLog(SQLModel, table=True):
    """Minimal record of inbound and outbound emails for a negotiation."""

    id: Optional[int] = Field(default=None, primary_key=True)

    negotiation_thread_id: int = Field(
        foreign_key="negotiationthread.id",
        index=True,
    )

    direction: EmailDirection = Field(
        sa_column_kwargs={"nullable": False},
    )

    subject: str = Field(sa_column_kwargs={"nullable": False})
    body: str = Field(sa_column_kwargs={"nullable": False})

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"nullable": False},
    )

