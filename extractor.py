"""Thin orchestrator: image → preprocessing → LLM → normalize → category.

gpt-4o reads the preprocessed image directly and produces the structured
data; OpenCV preprocessing handles deskew/contrast for low-quality scans.
"""
from __future__ import annotations

import category
import llm
import normalize
import preprocessing


def extract_invoice_advanced(
    image_path: str,
    save_debug: bool = False,
    preprocess_mode: str = "light",
) -> dict:
    """End-to-end extraction. Returns a JSON-serializable dict matching the
    Invoice schema in schema.py.

    preprocess_mode:
      - 'light' (default): minimal preprocessing — best for clean phone photos.
      - 'full': aggressive deskew + denoise + CLAHE — for poor-quality scans.
    """
    _img_array, img_png = preprocessing.preprocess(
        image_path, save_debug=save_debug, mode=preprocess_mode,
    )

    raw = llm.extract(img_png)
    invoice = normalize.validate(raw)
    invoice.category = category.classify(invoice)

    return invoice.model_dump(mode="json")


__all__ = ["extract_invoice_advanced"]
