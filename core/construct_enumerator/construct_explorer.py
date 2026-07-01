#!/usr/bin/env python3
"""Expand language constructs via LLM prompts, generate programs per round, and stop via AST diversity.

Folder layout expected:
  construct_storage/<lang>/initial_prompt.txt
  construct_storage/<lang>/continual_prompt.txt

This writes:
  construct_storage/<lang>/zero-shot.json
  construct_storage/<lang>/<word>-shot.json  (one-shot, two-shot, ...)
  construct_storage/<lang>/all_constructs.json
  construct_storage/<lang>/generated-<word>-shot/
  construct_storage/<lang>/stat.log
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from .diversity import DiversityTracker, NUM_WORDS, language_diversity_tracker
from construct_storage.merger import merge_json_files


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    return s.strip()


def _parse_json_response(text: str) -> Dict[str, List[str]]:
    cleaned = _strip_code_fences(text)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if not m:
            raise
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            raise e

    if not isinstance(obj, dict):
        raise ValueError("Model output JSON must be an object.")

    out: Dict[str, List[str]] = {}
    for k, v in obj.items():
        if isinstance(v, list):
            out[str(k)] = [str(x).strip() for x in v if str(x).strip()]
        else:
            s = str(v).strip()
            out[str(k)] = [s] if s else []
    return out


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _format_totals(totals: Dict[str, int]) -> str:
    keys = ["nodes", "pairs", "triplets", "quadruplets", "quintuplets", "sextuplets"]
    return ", ".join(f"{k}={totals[k]}" for k in keys if k in totals)


def _format_growth(growth: Dict[str, float]) -> str:
    keys = ["nodes", "pairs", "triplets", "quadruplets", "quintuplets", "sextuplets"]
    return ", ".join(f"{k}={_pct(growth[k])}" for k in keys if k in growth)


def _log(stat_path: Path, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(f"{msg}")
    stat_path.parent.mkdir(parents=True, exist_ok=True)
    with stat_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@dataclass(frozen=True)
class StoragePaths:
    lang: str
    base_dir: Path
    initial_prompt: Path
    continual_prompt: Path
    all_constructs: Path

    @staticmethod
    def for_language(language: str) -> "StoragePaths":
        base = Path("construct_storage") / language
        return StoragePaths(
            lang=language,
            base_dir=base,
            initial_prompt=base / "initial_prompt.txt",
            continual_prompt=base / "continual_prompt.txt",
            all_constructs=base / "all_constructs.json",
        )


def _openai_client() -> OpenAI:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Put it in your environment or a .env file.")
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


def _word_for_round(round_idx: int) -> str:
    if 0 <= round_idx < len(NUM_WORDS):
        return NUM_WORDS[round_idx]
    return f"round{round_idx}"


def _growth_percentages(prev: Dict[str, int], cur: Dict[str, int]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, cur_v in cur.items():
        prev_v = prev.get(k, 0)
        if prev_v <= 0:
            out[k] = 1.0 if cur_v > 0 else 0.0
        else:
            out[k] = (cur_v - prev_v) / float(prev_v)
    return out


def _load_all_constructs(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8") or "{}"
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        return {}
    return obj


def run_enumeration(*, language: str, epsilon: float, model: str = "gpt-4", max_rounds: int = 20) -> None:
    paths = StoragePaths.for_language(language)
    if not paths.initial_prompt.is_file():
        raise FileNotFoundError(f"Missing initial prompt: {paths.initial_prompt}")
    if not paths.continual_prompt.is_file():
        raise FileNotFoundError(f"Missing continual prompt: {paths.continual_prompt}")

    client = _openai_client()
    stat_log = paths.base_dir / "stat.log"

    _log(stat_log, f"START enumeration: lang={language}, model={model}, epsilon={epsilon}, max_rounds={max_rounds}")

    # Ensure cumulative file exists.
    if not paths.all_constructs.exists():
        _write_json(paths.all_constructs, {})

    from construct_enumerator.generator import generate_programs

    # -------------------
    # Round 0 (zero-shot)
    # -------------------
    round0_word = _word_for_round(0)
    round0_json = paths.base_dir / "zero-shot.json"
    round0_out_dir = paths.base_dir / f"generated-{round0_word}-shot"

    query0 = _read_text(paths.initial_prompt)
    raw0 = _chat(client, model, query0)
    constructs0 = _parse_json_response(raw0)
    _write_json(round0_json, constructs0)

    merge_json_files(base_json=paths.all_constructs, extra_json=round0_json)

    _log(stat_log, "[round 0] generation started")
    generate_programs(
        constructs_json_path=round0_json,
        language=language,
        out_dir=round0_out_dir,
        model=model,
    )
    _log(stat_log, "[round 0] generation finished")

    # Diversity tracking
    tracker: DiversityTracker | None = language_diversity_tracker(language)
    prev_totals: Dict[str, int] | None = None
    if tracker is not None:
        prev_totals = tracker.update_from_folder(round0_out_dir)
        _log(stat_log, f"[round 0] diversity totals: {_format_totals(prev_totals)}")
    else:
        _log(stat_log, f"[round 0] diversity tracking not implemented for language '{language}'")

    # -------------------
    # Continual rounds
    # -------------------
    continual_template = _read_text(paths.continual_prompt).lstrip("\n")

    for r in range(1, max_rounds + 1):
        word = _word_for_round(r)
        round_json = paths.base_dir / f"{word}-shot.json"
        round_out_dir = paths.base_dir / f"generated-{word}-shot"

        _log(stat_log, f"[round {r}] started")

        all_constructs = _load_all_constructs(paths.all_constructs)
        query = json.dumps(all_constructs, indent=2, ensure_ascii=False) + "\n\n" + continual_template

        raw = _chat(client, model, query)
        new_constructs = _parse_json_response(raw)
        _write_json(round_json, new_constructs)

        _log(stat_log, f"[round {r}] generation started")
        generate_programs(
            constructs_json_path=round_json,
            language=language,
            out_dir=round_out_dir,
            model=model,
        )
        _log(stat_log, f"[round {r}] generation finished")

        # Decide stop based on diversity growth
        if tracker is not None and prev_totals is not None:
            totals = tracker.update_from_folder(round_out_dir)
            growth = _growth_percentages(prev_totals, totals)
            _log(stat_log, f"[round {r}] diversity totals: {_format_totals(totals)}")
            _log(stat_log, f"[round {r}] relative growth: {_format_growth(growth)}")
            stop = all(growth[k] < epsilon for k in growth)
        else:
            totals = None
            stop = False

        # Merge for next round
        merge_json_files(base_json=paths.all_constructs, extra_json=round_json)

        if totals is not None:
            prev_totals = totals

        if stop:
            _log(stat_log, f"Stopping after round {r}: all depth growth percentages fell below epsilon={epsilon}.")
            _log(stat_log, f"stat.log: {stat_log}")
            _log(stat_log, f"all_constructs.json: {paths.all_constructs}")
            _log(stat_log, "END enumeration")
            return

    _log(stat_log, f"Reached max_rounds={max_rounds} without meeting stop condition.")
    _log(stat_log, f"stat.log: {stat_log}")
    _log(stat_log, f"all_constructs.json: {paths.all_constructs}")
    _log(stat_log, "END enumeration")
