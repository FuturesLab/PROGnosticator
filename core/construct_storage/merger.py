#!/usr/bin/env python3
import json
import argparse
from pathlib import Path


def _dedupe_preserve_order(items):
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def merge_dicts(base: dict, extra: dict, *, dedupe_lists: bool = True) -> dict:
    for k, v in extra.items():
        if k in base and isinstance(base[k], list) and isinstance(v, list):
            base[k].extend(v)
            if dedupe_lists:
                base[k] = _dedupe_preserve_order(base[k])
        else:
            base[k] = v
    return base


def merge_json_files(base_json: Path, extra_json: Path, output: Path | None = None) -> Path:
    """
    Import-friendly merge:
    - merges extra_json into base_json
    - writes to `output` if provided, else overwrites base_json
    """
    base_json = Path(base_json)
    extra_json = Path(extra_json)

    if base_json.exists():
        base = json.loads(base_json.read_text(encoding="utf-8") or "{}")
    else:
        base = {}

    extra = json.loads(extra_json.read_text(encoding="utf-8"))

    if not isinstance(base, dict) or not isinstance(extra, dict):
        raise ValueError("Both JSON files must contain objects (dict at top level).")

    merged = merge_dicts(base, extra, dedupe_lists=True)

    out_path = Path(output) if output else base_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Merge second JSON into the first, in place by default."
    )
    parser.add_argument("base_json", help="Path to the base JSON file (will be modified)")
    parser.add_argument("extra_json", help="Path to the JSON file whose values will be added")
    parser.add_argument(
        "-o", "--output",
        help="Optional path to write merged JSON. Defaults to modifying base_json in place.",
        default=None
    )
    args = parser.parse_args()

    out = merge_json_files(args.base_json, args.extra_json, args.output)
    print(f"Merged JSON written to {out}")


if __name__ == "__main__":
    main()
