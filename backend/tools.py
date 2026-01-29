from __future__ import annotations

from dataclasses import dataclass


FAIR_PRICE_SPREAD_RATIO: float = 0.1
"""Ratio used to derive low/high bounds around a reference market rate."""

COUNTER_OFFER_DISCOUNT_RATIO: float = 0.1
"""Default discount applied when proposing a counter offer."""


@dataclass(frozen=True)
class MarketRate:
    """Represents a simple fair price range for a product."""

    product_name: str
    low: float
    high: float
    reference: float


def lookup_market_rates(product_name: str) -> MarketRate:
    """Return a mock fair market price range for the given product.

    In a production system this would query internal pricing data,
    vendor benchmarks, or external pricing APIs. For the MVP we use
    deterministic heuristics so behaviour is predictable and testable.
    """
    base_price = _derive_base_price(product_name)
    spread = base_price * FAIR_PRICE_SPREAD_RATIO

    low = base_price - spread
    high = base_price + spread

    return MarketRate(
        product_name=product_name,
        low=round(low, 2),
        high=round(high, 2),
        reference=round(base_price, 2),
    )


def calculate_counter_offer(current_price: float, market_rate: float) -> float:
    """Calculate the next counter-offer price given an ask and a market rate.

    The current business rule is:
    - Start from the lower of the vendor's current price and the market rate.
    - Apply a fixed discount (e.g. 10%).

    This function is intentionally pure (no I/O) so it is easy to unit test
    and to reason about when debugging negotiation behaviour.
    """
    if current_price <= 0.0:
        raise ValueError("current_price must be positive.")
    if market_rate <= 0.0:
        raise ValueError("market_rate must be positive.")

    baseline = min(current_price, market_rate)
    discounted = baseline * (1.0 - COUNTER_OFFER_DISCOUNT_RATIO)

    # Round to two decimals to mirror currency representation.
    return round(discounted, 2)


def _derive_base_price(product_name: str) -> float:
    """Internal helper to provide a deterministic base price per SaaS product.

    This keeps the mock implementation simple while avoiding hard-coded
    magic numbers at the call sites. The mapping can be extended as needed.
    """
    normalized_name = product_name.strip().lower()

    # Basic static catalogue for real SaaS subscriptions (per-seat monthly pricing).
    # These prices are illustrative and not guaranteed to match current vendor pricing.
    static_catalogue = {
        "salesforce sales cloud": 80.0,
        "salesforce service cloud": 75.0,
        "hubspot marketing hub": 60.0,
        "hubspot sales hub": 50.0,
        "microsoft 365 business standard": 15.0,
        "google workspace business standard": 12.0,
        "jira software standard": 8.0,
        "asana advanced": 25.0,
        "slack pro": 8.0,
        "slack business+": 15.0,
        "zoom pro": 15.0,
        "zoom business": 20.0,
        "zendesk support professional": 49.0,
        "zendesk support enterprise": 99.0,
        "datadog infrastructure pro": 23.0,
        "snowflake standard": 40.0,
    }

    if normalized_name in static_catalogue:
        return static_catalogue[normalized_name]

    # Fallback heuristic: length-based pricing to keep it deterministic.
    base_value = max(len(normalized_name), 1)
    return float(base_value * 10)

