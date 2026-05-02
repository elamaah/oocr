"""Category resolution.

The LLM is responsible for picking a category as part of its structured
output. This module just sanity-checks that pick against a small keyword
rule table — if the rules clearly contradict the LLM (e.g. items contain
"بنزين" but the LLM said "other"), we override.

No local model. No HuggingFace download. No sentence-transformers."""
from __future__ import annotations

from typing import Optional

from config import CATEGORIES, CATEGORY_RULES
from schema import Invoice


def _rules_match(text: str) -> Optional[str]:
    lowered = text.lower()
    for needle, cat in CATEGORY_RULES:
        if needle.lower() in lowered:
            return cat
    return None


def classify(invoice: Invoice) -> str:
    """Resolve final category for the invoice.

    Order of precedence:
    1. Strong keyword rule hit (e.g. 'بنزين' in items → fuel).
    2. The category the LLM assigned in raw_invoice (already on the
       invoice when this is called).
    3. 'other' as a last resort.
    """
    parts = [item.name for item in invoice.items if item.name]
    blob = " | ".join(parts)

    rule_hit = _rules_match(blob) if blob else None
    if rule_hit is not None:
        return rule_hit

    if invoice.category in CATEGORIES:
        return invoice.category

    return "other"


__all__ = ["classify"]
