"""OpenAI multimodal call with JSON-Schema structured outputs.

Sends the preprocessed receipt image + the geometry-aware OCR rows together,
returns the parsed RawInvoice dict."""
from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from typing import Optional

from config import CATEGORIES, FEW_SHOT_EXAMPLES, SYSTEM_PROMPT
from schema import RawInvoice


def _load_env() -> None:
    """Load OPENAI_API_KEY from .env. Uses python-dotenv if installed,
    falls back to a minimal parser so the project works whether or not
    you've activated the venv."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
        return
    except ImportError:
        pass

    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    # Try project root first, then cwd.
    for candidate in (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ):
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    os.environ.setdefault(key, value)
            return


_load_env()


DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Put it in .env or export it as an environment variable."
        )
    return OpenAI(api_key=api_key)


def _strict_schema() -> dict:
    """OpenAI strict mode requires every property to appear in 'required' and
    additionalProperties:false on every object. We rebuild Pydantic's schema
    to honor those rules. We also inject a dynamic enum constraint on the
    `category` field so the LLM is forced to pick from CATEGORIES (which the
    user can edit in config.py without touching this file)."""
    schema = RawInvoice.model_json_schema()

    def patch(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
                # Constrain `category` to the editable list in config.py.
                if "category" in node["properties"]:
                    node["properties"]["category"] = {
                        "type": ["string", "null"],
                        "enum": [*CATEGORIES, None],
                        "description": (
                            "Receipt category — must be exactly one of the "
                            "allowed values (or null if undeterminable)."
                        ),
                    }
            for v in node.values():
                patch(v)
        elif isinstance(node, list):
            for v in node:
                patch(v)

    # Inline $defs so we can patch them too.
    patch(schema)
    return schema


def _build_user_content(image_png: bytes, ocr_text: str) -> list[dict]:
    b64 = base64.b64encode(image_png).decode("ascii")
    if ocr_text:
        text_block = (
            "Local OCR rows (hint only — image is primary source):\n"
            f"```\n{ocr_text}\n```\n\n"
            "Extract the structured invoice data. Copy values verbatim — "
            "downstream code handles normalization."
        )
    else:
        text_block = (
            "Read this receipt directly from the image and extract the "
            "structured invoice data. Copy values verbatim — downstream code "
            "handles normalization."
        )
    return [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        {"type": "text", "text": text_block},
    ]


def extract(image_png: bytes, ocr_text: str = "", model: Optional[str] = None) -> dict:
    """Call OpenAI; return the validated RawInvoice as a dict."""
    client = _client()
    model_name = model or DEFAULT_MODEL

    response = client.chat.completions.create(
        model=model_name,
        temperature=0,
        max_tokens=1500,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES,
            },
            {
                "role": "user",
                "content": _build_user_content(image_png, ocr_text),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "raw_invoice",
                "strict": True,
                "schema": _strict_schema(),
            },
        },
    )

    raw_text = response.choices[0].message.content
    if not raw_text:
        raise RuntimeError("OpenAI returned empty content.")
    return json.loads(raw_text)


__all__ = ["extract", "DEFAULT_MODEL"]
