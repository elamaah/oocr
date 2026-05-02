"""Pydantic models that drive the LLM contract and post-validation.

The category list is intentionally NOT a static Literal — it lives in
config.CATEGORY_TAXONOMY so the user can edit it without touching schemas.
The OpenAI API gets a dynamic `enum` constraint via llm._strict_schema()
that walks the JSON schema and pins the category field's allowed values."""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from pydantic import BaseModel, Field

# Plain string type. Allowed values are enforced in two places:
#   1. The OpenAI structured-output schema (enum injected at request time).
#   2. category.classify(), which falls back to "other" if anything slips through.
Category = str


class LineItem(BaseModel):
    name: str = Field(description="Item name as printed on the receipt.")
    quantity: Optional[float] = Field(
        default=None,
        description="Quantity if explicitly stated. Null if absent — do not invent.",
    )
    unit_price: Optional[float] = Field(
        default=None,
        description="Per-unit price if printed. Null if only line total is shown.",
    )
    total_price: Optional[float] = Field(
        default=None,
        description="Line total (quantity * unit_price) if printed.",
    )
    raw_line: Optional[str] = Field(
        default=None,
        description="Original OCR row this item was extracted from (debug aid).",
    )


class Invoice(BaseModel):
    date: Optional[_dt.date] = Field(
        default=None,
        description="Receipt date, ISO 8601 (YYYY-MM-DD) after normalization.",
    )
    time: Optional[str] = Field(
        default=None,
        description="Receipt time in 12-hour AM/PM format, e.g. '3:50:58 PM'.",
    )
    total: Optional[float] = Field(
        default=None,
        description="Grand total as printed. Never compute or sum.",
    )
    category: Optional[Category] = Field(
        default=None,
        description="Inferred merchant category.",
    )
    items: list[LineItem] = Field(default_factory=list)


class RawInvoice(BaseModel):
    """Loose shape returned by the LLM before normalization.

    All fields are strings so the model copies values verbatim from OCR text;
    typed parsing happens in normalize.py with format inference.
    """

    date_raw: Optional[str] = Field(
        default=None,
        description="Date exactly as printed — do not reformat.",
    )
    time_raw: Optional[str] = Field(
        default=None,
        description="Time exactly as printed — do not reformat.",
    )
    total_raw: Optional[str] = Field(
        default=None,
        description="Total exactly as printed, including currency token if any.",
    )
    category: Optional[Category] = Field(
        default=None,
        description=(
            "Inferred merchant category from the receipt. Choose one: "
            "restaurant (food/meals), pharmacy (medicine), grocery (supermarket), "
            "cafe (coffee/tea), fuel (gas station), electronics, clothing, other. "
            "Use the items + any visible store name to decide."
        ),
    )
    items: list["RawLineItem"] = Field(default_factory=list)


class RawLineItem(BaseModel):
    name: str
    quantity_raw: Optional[str] = None
    unit_price_raw: Optional[str] = None
    total_price_raw: Optional[str] = None
    raw_line: Optional[str] = None


RawInvoice.model_rebuild()
