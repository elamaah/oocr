import argparse
import json
import sys
from pathlib import Path

# Windows consoles default to cp1252 which can't encode Arabic.
# Force UTF-8 on stdout/stderr so any Arabic that does get printed (--print)
# doesn't crash. The default behavior writes JSON to a file, so PowerShell's
# limited Unicode rendering never matters for the result itself.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from extractor import extract_invoice_advanced


def main() -> int:
    parser = argparse.ArgumentParser(description="Multilingual invoice extractor.")
    parser.add_argument("image", help="Path to receipt image.")
    parser.add_argument("--output", "-o",
                        help="Where to write the JSON output (UTF-8). "
                             "Defaults to <image>.json next to the image.")
    parser.add_argument("--preprocess", choices=["light", "full"], default="light",
                        help="'light' (default): minimal preprocessing — best for "
                             "clean phone photos. 'full': deskew + denoise + CLAHE — "
                             "for low-quality scans.")
    parser.add_argument("--debug", action="store_true",
                        help="Save preprocessed image to debug/ for inspection.")
    parser.add_argument("--print", dest="also_print", action="store_true",
                        help="Also print the JSON to stdout (PowerShell may not "
                             "render Arabic correctly).")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else image_path.with_suffix(".json")

    print(f"Processing: {image_path}")
    result = extract_invoice_advanced(
        str(image_path),
        save_debug=args.debug,
        preprocess_mode=args.preprocess,
    )

    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote: {output_path}")

    # Compact ASCII-safe summary so PowerShell never needs to render Arabic.
    item_count = len(result.get("items") or [])
    print(
        f"  date={result.get('date')}  time={result.get('time')}  "
        f"total={result.get('total')}  category={result.get('category')}  "
        f"items={item_count}"
    )

    if args.also_print:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())