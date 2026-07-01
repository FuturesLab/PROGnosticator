from __future__ import annotations

import json
import shutil
from pathlib import Path


def clean_language(*, language: str) -> None:
    base = Path("construct_storage") / language
    if not base.is_dir():
        raise FileNotFoundError(f"Language storage folder not found: {base}")

    all_constructs = base / "all_constructs.json"

    # 1) Delete generated-* folders
    for p in base.iterdir():
        if p.is_dir() and p.name.startswith("generated-"):
            shutil.rmtree(p)
            print(f"deleted folder: {p}")

    # 2) Delete *.json except all_constructs.json
    for p in base.iterdir():
        if p.is_file() and p.suffix == ".json" and p.name != "all_constructs.json":
            p.unlink()
            print(f"deleted file: {p}")
    # 3) Delete stat.log if exists
    stat_log = base / "stat.log"
    if stat_log.exists():
        stat_log.unlink()
        print(f"deleted file: {stat_log}")

    # 3) Reset all_constructs.json contents to {}
    all_constructs.parent.mkdir(parents=True, exist_ok=True)
    all_constructs.write_text(json.dumps({}, indent=2) + "\n", encoding="utf-8")
    print(f"reset file: {all_constructs} (now {{}})")
