from __future__ import annotations

import json
from typing import Any, Dict, TypedDict, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from config import get_settings
from schemas import NegotiationState
from tools import MarketRate, calculate_counter_offer, lookup_market_rates


class GraphConfig(TypedDict):
    """Graph configuration passed via LangGraph's `config` parameter."""

    configurable: Dict[str, Any]


def _init_model() -> ChatGoogleGenerativeAI:
    """Initialise the Gemini chat model using application settings."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model_name,
        temperature=0.3,
        api_key=settings.google_api_key,
    )


MODEL = _init_model()


def analyze_node(state: NegotiationState) -> NegotiationState:
    """Node 1: Analyze the incoming email to extract core fields.

    Uses Gemini to extract:
    - vendor_name
    - product_name (SaaS subscription)
    - current_offer (price quoted)
    - sender_name (human contact at the vendor, e.g. "Bob")
    - recipient_name (our contact name, e.g. "JJ")
    """
    messages = state.get("messages", [])

    system = SystemMessage(
        content=(
            "You are an assistant that extracts structured data from vendor SaaS pricing emails. "
            "Return a JSON object with keys: vendor_name, product_name, current_offer, sender_name, recipient_name. "
            "current_offer should be a numeric price per seat per month. "
            "If a value is missing or cannot be confidently determined, use null."
        ),
    )
    prompt_messages = [system, *messages]

    response = MODEL.invoke(prompt_messages)
    content = response.content

    vendor_name = None
    product_name = None
    current_offer = None
    sender_name = None
    recipient_name = None

    def _parse_structured_payload(raw: Any) -> Dict[str, Any]:
        """Parse the model's response into a JSON dict.

        Gemini may sometimes wrap JSON in code fences or add prose. This helper
        makes a best-effort attempt to extract the first JSON object from the
        string so that fields like `product_name` are reliably captured.
        """
        if not isinstance(raw, str):
            return {}

        text = raw.strip()

        # Handle common ```json ... ``` wrapping.
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop the opening fence (and optional language tag).
            lines = lines[1:]
            # Drop a possible closing fence.
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: try to locate the first JSON object within the text.
            start_index = text.find("{")
            end_index = text.rfind("}")
            if start_index != -1 and end_index > start_index:
                try:
                    return json.loads(text[start_index : end_index + 1])
                except json.JSONDecodeError:
                    return {}
            return {}

    parsed = _parse_structured_payload(content)
    vendor_name = parsed.get("vendor_name")
    product_name = parsed.get("product_name")
    sender_name = parsed.get("sender_name")
    recipient_name = parsed.get("recipient_name")
    raw_offer = parsed.get("current_offer")
    if isinstance(raw_offer, (int, float)):
        current_offer = float(raw_offer)

    new_state: NegotiationState = {
        **state,
        "vendor_name": vendor_name,
        "product_name": product_name,
        "sender_name": sender_name,
        "recipient_name": recipient_name,
        "current_offer": current_offer,
        "status": "strategizing",
    }
    return new_state


def strategy_node(state: NegotiationState) -> NegotiationState:
    """Node 2: Devise a negotiation strategy based on market rates.

    Compares the vendor's current offer to a mocked market rate and
    decides whether to accept, reject, or counter.
    """
    product_name = state.get("product_name")
    current_offer = state.get("current_offer")

    decision = "reject"
    target_price = None
    market_rate: MarketRate | None = None

    if product_name and current_offer is not None:
        market_rate = lookup_market_rates(product_name)
        reference_rate = market_rate.reference

        if current_offer <= reference_rate * 0.9:
            decision = "accept"
            target_price = current_offer
        elif current_offer >= reference_rate * 1.2:
            decision = "counter"
            target_price = calculate_counter_offer(current_offer, reference_rate)
        else:
            decision = "counter"
            target_price = calculate_counter_offer(current_offer, reference_rate)

    decision_message = AIMessage(
        content=(
            f"Decision: {decision}. "
            f"Market reference: {market_rate.reference if market_rate else 'unknown'}. "
            f"Target price: {target_price if target_price is not None else 'none'}."
        ),
    )

    messages = state.get("messages", [])
    messages.append(decision_message)

    new_state: NegotiationState = {
        **state,
        "messages": messages,
        "target_price": target_price,
        "status": "drafting",
    }
    return new_state


def draft_node(state: NegotiationState) -> NegotiationState:
    """Node 3: Draft an email response for human review.

    This node uses the LLM to create a natural-language email response,
    but it does NOT send the email. Instead, it stores the draft in
    `draft_response` for a human to approve.
    """
    vendor_name = state.get("vendor_name") or "the vendor"
    product_name = state.get("product_name") or "the SaaS subscription"
    sender_name = state.get("sender_name")
    recipient_name = state.get("recipient_name")
    current_offer = state.get("current_offer")
    target_price = state.get("target_price")

    # Derive a high-level decision label for the drafting prompt.
    # When a numeric `target_price` exists, we prefer to counter rather than
    # send a vague rejection so the email proposes a concrete price.
    decision_summary = "counter"
    if target_price is None:
        if current_offer is not None:
            decision_summary = "reject"
    elif current_offer is not None and abs(target_price - current_offer) < 1e-6:
        decision_summary = "accept"

    instruction = SystemMessage(
        content=(
            "You are a procurement negotiation assistant drafting concise, polite emails. "
            "Draft a single email response to a vendor about SaaS pricing, using the structured "
            "fields below.\n\n"
            "If Decision is \"counter\" and a numeric target price is provided:\n"
            "- Propose that target price as a clear counter-offer (for example: "
            "\"we would be comfortable proceeding at $X per seat per month\").\n"
            "- Use the target price value exactly as provided in the context.\n"
            "- Avoid vague language like \"more competitive\" without stating a concrete price.\n\n"
            "If Decision is \"accept\":\n"
            "- Clearly confirm acceptance of the vendor's quoted price.\n\n"
            "If Decision is \"reject\" and no target price is available:\n"
            "- Politely say we cannot proceed at the current pricing and invite the vendor "
            "to return with a more competitive offer.\n\n"
            "When names are provided, use a natural greeting (for example, "
            "\"Dear {sender_name}\" or \"Dear {vendor_name} team\") and a "
            "polite sign-off that can optionally include the recipient_name.\n\n"
            "Do not mention that you are an AI system. "
            "Write the email body only, without subject line."
        ),
    )

    user_prompt_lines = [
        f"Vendor name: {vendor_name}",
        f"Product: {product_name}",
        f"Sender contact name (vendor): {sender_name or 'unknown'}",
        f"Our contact name (recipient): {recipient_name or 'unknown'}",
        f"Vendor current offer (per seat / month): {current_offer if current_offer is not None else 'unknown'}",
        f"Our target price (per seat / month): {target_price if target_price is not None else 'unknown'}",
        f"Decision: {decision_summary} (accept / reject / counter).",
        "",
        "Write the email body only, without subject line.",
    ]

    user_message = HumanMessage(content="\n".join(user_prompt_lines))

    response = MODEL.invoke([instruction, user_message])
    draft_email = cast(str, response.content)

    messages = state.get("messages", [])
    messages.append(AIMessage(content=draft_email))

    new_state: NegotiationState = {
        **state,
        "messages": messages,
        "draft_response": draft_email,
        "status": "awaiting_human_review",
    }
    return new_state


def human_review_node(state: NegotiationState) -> NegotiationState:
    """Node 4: Human review placeholder.

    This node is intentionally a no-op: all side effects are handled
    by the API layer. The key human-in-the-loop behaviour is configured
    through LangGraph's `interrupt_before` setting when compiling the graph.

    With `interrupt_before=["human_review"]`, the graph will PAUSE before
    executing this node. That means:
    - The agent can draft an email (`draft_node`) and update the state.
    - Execution stops before any further action (such as sending the email).
    - A human must explicitly approve by calling `/approve/{thread_id}` in the
      API layer, which resumes the graph from this interruption point.
    """
    return state


def build_graph() -> Any:
    """Build and compile the LangGraph state machine for negotiations."""
    builder = StateGraph(NegotiationState)

    builder.add_node("analyze", analyze_node)
    builder.add_node("strategy", strategy_node)
    builder.add_node("draft", draft_node)
    builder.add_node("human_review", human_review_node)

    builder.set_entry_point("analyze")
    builder.add_edge("analyze", "strategy")
    builder.add_edge("strategy", "draft")
    builder.add_edge("draft", "human_review")

    # MemorySaver acts as an in-memory checkpointer. Each `thread_id` provided
    # via LangGraph's `config` is used to persist and later resume the state.
    checkpointer = MemorySaver()

    # HUMAN-IN-THE-LOOP MECHANISM:
    # ----------------------------
    # `interrupt_before=["human_review"]` ensures that when the graph reaches
    # the edge leading to the `human_review` node, it stops and returns control
    # to the caller. The API layer then exposes this pause via `/webhook/email`
    # (initial run) and resumes only when `/approve/{thread_id}` is invoked.
    app = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )
    return app

