from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv
from openai import OpenAI


# Prompt file locations
# To support another language, just add the corresponding prompt file and uncomment the relevant lines in the code.
_LANG_TO_PROMPT = {
    "c": Path("construct_enumerator/generator_prompt/c_generator_prompt.txt"),
    "go": Path("construct_enumerator/generator_prompt/go_generator_prompt.txt"),
    "js": Path("construct_enumerator/generator_prompt/js_generator_prompt.txt"),
    "rust": Path("construct_enumerator/generator_prompt/rust_generator_prompt.txt"),
    "python": Path("construct_enumerator/generator_prompt/python_generator_prompt.txt"),
    "java": Path("construct_enumerator/generator_prompt/java_generator_prompt.txt"),
}

_LANG_TO_EXT = {
    "c": ".c",
    "go": ".go",
    "js": ".js",
    "rust": ".rs",
    "python": ".py",
    "java": ".java",
}


def _openai_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
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
        except Exception as e:  # noqa
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


def _safe_name(s: str) -> str:
    s = str(s)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"[^a-zA-Z0-9_]+", "", s)
    return s[:80] if s else "Category"


def _load_constructs(path: Path) -> Dict[str, List[str]]:
    raw = path.read_text(encoding="utf-8")
    obj: Any = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError(f"Constructs JSON must be an object: {path}")

    out: Dict[str, List[str]] = {}
    for k, v in obj.items():
        if isinstance(v, list):
            out[str(k)] = [str(x) for x in v]
        else:
            out[str(k)] = [str(v)]
    return out


def generate_programs(
    *,
    constructs_json_path: Path,
    language: str,
    out_dir: Path,
    model: str = "gpt-4",
) -> None:
    """
    Generate one program per construct using the corresponding language template.
    """

    language = language.lower().strip()
    if language not in _LANG_TO_PROMPT:
        raise ValueError(f"Unsupported language: {language}")

    prompt_path = _LANG_TO_PROMPT[language]
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Missing prompt template: {prompt_path}")

    template = prompt_path.read_text(encoding="utf-8")
    ext = _LANG_TO_EXT[language]

    constructs_json_path = Path(constructs_json_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    constructs = _load_constructs(constructs_json_path)
    client = _openai_client()

    for category, items in constructs.items():
        safe_cat = _safe_name(category)

        for i, construct in enumerate(items):
            query = template.replace("{CONSTRUCT}", construct)

            code = _chat(client, model, query)
            code = _strip_code_fences(code)

            out_path = out_dir / f"{safe_cat}_{i}{ext}"
            out_path.write_text(code + "\n", encoding="utf-8")

            #print(f"→ {out_path}")
