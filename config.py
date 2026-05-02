"""Static configuration: prompts, currency tokens, category labels, rules.

No runtime logic here — only data tables that other modules import.
"""
from __future__ import annotations


# ──────────────────────────── LLM prompt ─────────────────────────────

SYSTEM_PROMPT = """You extract structured data from restaurant, pharmacy, grocery, and similar retail receipts in Arabic and English.

Rules:
- Output JSON conforming to the supplied schema. Nothing else.
- Copy values VERBATIM from the receipt as printed. Do not translate, reformat, or normalize.
- Dates and totals must be the exact substring as printed (e.g. "٠٥/١٢/٢٠٢٤", "12,50 ج.م"). Normalization happens downstream.
- If a field is absent, return null. Never invent values.
- Never sum, average, or compute totals — copy the printed total only.
- For each line item, return name and any of quantity/unit_price/total_price that are printed on that row. Use null for the rest.
- Read Arabic right-to-left as printed; preserve original digits (Arabic-Indic ٠١٢٣ or Western 0123) — do not transliterate.
- Pick exactly ONE category from the allowed list below. NEVER use a category not in the list — if the items don't clearly match anything, use "other". Match by item examples: if an item resembles one of the examples shown for a category, use that category.

{CATEGORY_GUIDE}

Inputs you may receive:
1. Always: a preprocessed image of the receipt. Read it directly.
2. Sometimes: extra OCR rows extracted by a local engine, one per line, tokens tab-separated, prefixed by row index. When provided, treat them as a hint for ambiguous digits — the image is still the primary source of truth."""


FEW_SHOT_EXAMPLES = """Example 1 — Arabic restaurant receipt:
OCR rows:
0\tمطعم الشام
1\tالتاريخ:\t٠٥/١٢/٢٠٢٤\t١٤:٣٠
2\tشاورما دجاج\t٢\t٤٥٫٠٠\t٩٠٫٠٠
3\tعصير برتقال\t١\t١٥٫٠٠\t١٥٫٠٠
4\tالاجمالي\t١٠٥٫٠٠ ج.م

Output:
{
  "date_raw": "٠٥/١٢/٢٠٢٤",
  "time_raw": "١٤:٣٠",
  "total_raw": "١٠٥٫٠٠ ج.م",
  "category": "restaurant",
  "items": [
    {"name": "شاورما دجاج", "quantity_raw": "٢", "unit_price_raw": "٤٥٫٠٠", "total_price_raw": "٩٠٫٠٠", "raw_line": "شاورما دجاج\\t٢\\t٤٥٫٠٠\\t٩٠٫٠٠"},
    {"name": "عصير برتقال", "quantity_raw": "١", "unit_price_raw": "١٥٫٠٠", "total_price_raw": "١٥٫٠٠", "raw_line": "عصير برتقال\\t١\\t١٥٫٠٠\\t١٥٫٠٠"}
  ]
}

Example 2 — English pharmacy receipt:
OCR rows:
0\tCity Pharmacy
1\t12/05/2024  10:15 AM
2\tParacetamol 500mg\tx2\t$3.50\t$7.00
3\tVitamin C\tx1\t$12.99\t$12.99
4\tTOTAL\t$19.99

Output:
{
  "date_raw": "12/05/2024",
  "time_raw": "10:15 AM",
  "total_raw": "$19.99",
  "category": "pharmacy",
  "items": [
    {"name": "Paracetamol 500mg", "quantity_raw": "x2", "unit_price_raw": "$3.50", "total_price_raw": "$7.00", "raw_line": "Paracetamol 500mg\\tx2\\t$3.50\\t$7.00"},
    {"name": "Vitamin C", "quantity_raw": "x1", "unit_price_raw": "$12.99", "total_price_raw": "$12.99", "raw_line": "Vitamin C\\tx1\\t$12.99\\t$12.99"}
  ]
}
"""


# ════════════════════ Category taxonomy (EDIT THIS) ════════════════════
#
# This is the single source of truth for categories. The LLM is constrained
# to pick exactly ONE of these keys. Add / remove / rename entries below and
# the prompt + schema validation update automatically — no other file needs
# to change.
#
# Each value is a list of EXAMPLE ITEMS that should map to that category.
# Mix Arabic and English freely. The model uses these examples as anchors:
# e.g. seeing "ice cream" or "ايس كريم" pushes it toward "restaurant".
#
# Always keep an "other" bucket as the last entry for items that genuinely
# don't fit anywhere else.

CATEGORY_TAXONOMY: dict[str, list[str]] = {
    "restaurant": [
        "meals", "shawarma", "burger", "pizza", "rice", "kebab",
        "ice cream", "ايس كريم", "وجبة", "شاورما", "كباب", "أرز",
    ],
    "pharmacy": [
        "medicine", "tablets", "syrup", "vitamins", "prescription",
        "دواء", "حبوب", "شراب", "فيتامين",
    ],
    "grocery": [
        "bread", "milk", "vegetables", "fruit", "cheese", "eggs",
        "خبز", "حليب", "خضار", "فواكه", "جبن", "بيض",
    ],
    "cafe": [
        "coffee", "tea", "espresso", "latte", "cappuccino", "pastry",
        "قهوة", "شاي", "كابتشينو", "حلويات",
    ],
    "fuel": [
        "gasoline", "diesel", "petrol", "liters",
        "بنزين", "سولار", "ديزل", "وقود",
    ],
    "electronics": [
        "phone", "laptop", "headphones", "charger", "cable",
        "هاتف", "لابتوب", "سماعات", "شاحن",
    ],
    "clothing": [
        "shirt", "pants", "dress", "shoes",
        "قميص", "بنطلون", "فستان", "حذاء",
    ],
    "other": [],
}

CATEGORIES: list[str] = list(CATEGORY_TAXONOMY.keys())


def _format_taxonomy_for_prompt() -> str:
    """Render CATEGORY_TAXONOMY into the chunk we inject into the system prompt."""
    lines = ["Allowed categories (pick exactly ONE — never invent a new one):"]
    for name, examples in CATEGORY_TAXONOMY.items():
        if examples:
            preview = ", ".join(examples[:8])
            lines.append(f'  - "{name}": e.g. {preview}')
        else:
            lines.append(f'  - "{name}": fallback when nothing else fits')
    return "\n".join(lines)


CATEGORY_PROMPT_BLOCK = _format_taxonomy_for_prompt()

# Substitute the {CATEGORY_GUIDE} placeholder in SYSTEM_PROMPT now that the
# block is built. (SYSTEM_PROMPT is defined earlier; we patch it here so
# the editable taxonomy can drive the prompt.)
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{CATEGORY_GUIDE}", CATEGORY_PROMPT_BLOCK)


# Hard rules — applied as a final override when keyword evidence is unambiguous.
# Maps a substring (lowercased) to a category. Checked against merchant name and item names.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("بنزين", "fuel"),
    ("سولار", "fuel"),
    ("ديزل", "fuel"),
    ("petrol", "fuel"),
    ("diesel", "fuel"),
    ("gasoline", "fuel"),
    ("صيدلية", "pharmacy"),
    ("صيدليه", "pharmacy"),
    ("pharmacy", "pharmacy"),
    ("drug store", "pharmacy"),
    ("مطعم", "restaurant"),
    ("restaurant", "restaurant"),
    ("كافيه", "cafe"),
    ("كافي", "cafe"),
    ("coffee", "cafe"),
    ("cafe", "cafe"),
    ("café", "cafe"),
    ("سوبر ماركت", "grocery"),
    ("بقالة", "grocery"),
    ("supermarket", "grocery"),
    ("grocery", "grocery"),
    ("hyper", "grocery"),
]


# ──────────────────────── Digit translation tables ────────────────────────

# Arabic-Indic digits → ASCII
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Persian/Eastern Arabic digits → ASCII
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
# Arabic decimal separator (٫ U+066B) → period
ARABIC_DECIMAL = str.maketrans("٫", ".")
# Arabic thousands separator (٬ U+066C) → comma
ARABIC_THOUSANDS = str.maketrans("٬", ",")
