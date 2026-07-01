from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from dotenv import load_dotenv
from openai import OpenAI


_LANG_EXT = {"c": ".c", "go": ".go", "js": ".js", "rust": ".rs", "python": ".py", "java": ".java"}


def _openai_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set (env var or .env).")
    return OpenAI(api_key=api_key)


def _chat(client: OpenAI, model: str, query: str, *, max_retries: int = 3) -> str:
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": query}],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    assert last_err is not None
    raise last_err


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    return s.strip()


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _default_paths(language: str) -> tuple[Path, Path, Path]:
    """Returns (lang_root, construct_list.json, generator_prompt.txt)."""
    lang_root = Path("construct_oriented_program_generator") / "language" / language
    return lang_root, lang_root / "construct_list.json", lang_root / "generator_prompt.txt"

def _constructs_blob(constructs: Sequence[str]) -> str:
    # Keep it predictable. The prompt decides how to interpret.
    return "\n".join(constructs)


def _build_query(template: str, constructs: Sequence[str]) -> str:
    return template.replace("{CONSTRUCTS}", _constructs_blob(constructs))


def _write_program(out_path: Path, code: str) -> None:
    out_path.write_text(code.rstrip() + "\n", encoding="utf-8")


def _load_construct_list(path: Path) -> Tuple[Dict[str, List[str]], List[str]]:
    """
    Accept ONLY:
      {"Category": ["usage1", "usage2", ...], ...}

    Returns:
      (by_category, flattened_deduped)
    """
    if not path.is_file():
        raise FileNotFoundError(f"Missing construct list JSON: {path}")

    obj: Any = json.loads(path.read_text(encoding="utf-8") or "{}")
    if not isinstance(obj, dict):
        raise ValueError("construct_list.json must be a JSON object: {category: [usages...], ...}")

    by_cat: Dict[str, List[str]] = {}
    for k, v in obj.items():
        if not isinstance(v, list):
            raise ValueError(f"Value for category '{k}' must be a list of strings.")
        items = [str(x).strip() for x in v if str(x).strip()]
        by_cat[str(k)] = items

    # Flatten and dedupe while preserving order (across categories)
    flat: List[str] = []
    for items in by_cat.values():
        flat.extend(items)

    seen = set()
    flat_deduped: List[str] = []
    for x in flat:
        if x in seen:
            continue
        seen.add(x)
        flat_deduped.append(x)

    return by_cat, flat_deduped


def _generate_single_exhaustive(
    *,
    client: OpenAI,
    model: str,
    template: str,
    out_dir: Path,
    ext: str,
    by_category: Dict[str, List[str]],
) -> int:
    _ensure_dir(out_dir)
    count = 0

    def safe(s: str) -> str:
        s = re.sub(r"\s+", "_", s.strip())
        s = re.sub(r"[^a-zA-Z0-9_]+", "", s)
        return s[:60] if s else "Category"

    for cat, items in by_category.items():
        cat_name = safe(cat)
        for i, construct in enumerate(items):
            query = _build_query(template, [construct])
            code = _chat(client, model, query)
            code = _strip_code_fences(code)

            out_path = out_dir / f"{cat_name}_{i}{ext}"
            _write_program(out_path, code)
            count += 1

    return count


def _generate_batch(
    *,
    client: OpenAI,
    model: str,
    template: str,
    out_dir: Path,
    ext: str,
    picks: List[List[str]],
    prefix: str,
) -> int:
    _ensure_dir(out_dir)
    count = 0
    for i, constructs in enumerate(picks):
        query = _build_query(template, constructs)
        code = _chat(client, model, query)
        code = _strip_code_fences(code)

        out_path = out_dir / f"{prefix}_{i}{ext}"
        _write_program(out_path, code)
        count += 1
    return count


def run_generation(
    *,
    language: str,
    model: str,
    max_programs: int,
    p_two: float | None = None,
    p_three: float | None = None,
    construct_list_path: str | None = None,
    prompt_path: str | None = None,
    seed: int | None = None,
) -> None:
    """
    Your spec:

    - Single-construct programs:
        Generate one program for every construct usage in construct_list.json
        (for each category, for each construct string). Exhaustive.

    - Multi-construct programs:
        Generate `max_programs` total, split into:
            floor(max_programs * p_two)   two-construct programs
            floor(max_programs * p_three) three-construct programs

      Defaults (when user does NOT provide percentages):
        p_two = 0.6, p_three = 0.4

    Input defaults:
      language/<lang>/construct_list.json
      language/<lang>/generator_prompt.txt

    Output:
      language/<lang>/programs/single_construct_programs/
      language/<lang>/programs/two_construct_programs/
      language/<lang>/programs/three_construct_programs/
    """
    language = language.lower().strip()
    if language not in _LANG_EXT:
        raise ValueError(f"Unsupported language: {language}")

    if max_programs <= 0:
        raise ValueError("max_programs must be > 0")

    if seed is not None:
        random.seed(seed)

    lang_root, default_list, default_prompt = _default_paths(language)
    list_path = Path(construct_list_path) if construct_list_path else default_list
    gen_prompt_path = Path(prompt_path) if prompt_path else default_prompt

    by_cat, constructs_flat = _load_construct_list(list_path)
    if not constructs_flat:
        raise ValueError(f"No constructs found in: {list_path}")

    template = _read_text(gen_prompt_path)
    ext = _LANG_EXT[language]

    # Default split
    if p_two is None and p_three is None:
        p_two, p_three = 0.6, 0.4

    if p_two is None or p_three is None:
        raise ValueError("Provide both p_two and p_three, or provide neither (use defaults).")

    if not (0.0 <= p_two <= 1.0) or not (0.0 <= p_three <= 1.0):
        raise ValueError("p_two and p_three must be in [0, 1].")

    two_n = int(max_programs * p_two)
    three_n = int(max_programs * p_three)

    programs_root = lang_root / "programs"
    single_dir = programs_root / "single_construct_programs"
    two_dir = programs_root / "two_construct_programs"
    three_dir = programs_root / "three_construct_programs"

    client = _openai_client()

    print(f"Language={language}, model={model}")
    print(f"Construct list: {list_path}")
    print(f"Generator prompt: {gen_prompt_path}")
    print(f"Single programs = ALL constructs in json")
    print(f"Multi programs: total={max_programs}, two={two_n} ({p_two:.2f}), three={three_n} ({p_three:.2f})")

    # 1) Exhaustive single-construct generation
    print("Starting single-construct programs (exhaustive)...")
    single_count = _generate_single_exhaustive(
        client=client,
        model=model,
        template=template,
        out_dir=single_dir,
        ext=ext,
        by_category=by_cat,
    )
    print(f"Finished single-construct programs: {single_count} → {single_dir}")

    # Picks for multi programs (use the flattened pool)
    def pick_k(k: int) -> List[str]:
        if len(constructs_flat) >= k:
            return random.sample(constructs_flat, k)
        return [random.choice(constructs_flat) for _ in range(k)]

    two_picks = [pick_k(2) for _ in range(two_n)]
    three_picks = [pick_k(3) for _ in range(three_n)]

    # 2) Two-construct programs
    print("Starting two-construct programs...")
    two_count = _generate_batch(
        client=client,
        model=model,
        template=template,
        out_dir=two_dir,
        ext=ext,
        picks=two_picks,
        prefix="two",
    )
    print(f"Finished two-construct programs: {two_count} → {two_dir}")

    # 3) Three-construct programs
    print("Starting three-construct programs...")
    three_count = _generate_batch(
        client=client,
        model=model,
        template=template,
        out_dir=three_dir,
        ext=ext,
        picks=three_picks,
        prefix="three",
    )
    print(f"Finished three-construct programs: {three_count} → {three_dir}")
