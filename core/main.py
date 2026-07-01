#!/usr/bin/env python3
"""Entry point for construct enumeration and program generation.

Usage examples:
  #Full pipeline:
  python3 main.py -F c 0.2 2 10 --model gpt-4
  python3 main.py -F c 0.2 2 10 0.6 0.4 --model gpt-4
  
  #Enumeration only:
  python3 main.py -E c --epsilon 0.05 --model gpt-4
  python3 main.py -E c --epsilon 0.0 --max-rounds 2 --model gpt-4
  python3 main.py -C c

  #Generation only (after running enumeration at least once to get the constructs):
  python3 main.py -G c 10 --model gpt-4
  python3 main.py -G c 10 0.6 0.4 --model gpt-4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from construct_enumerator.construct_explorer import run_enumeration
from construct_oriented_program_generator.generator import run_generation

LANG_CHOICES = ("c", "go", "js", "rust", "python", "java")


def _epsilon_type(x: str) -> float:
    try:
        v = float(x)
    except ValueError as e:
        raise argparse.ArgumentTypeError("epsilon must be a number in [0, 1].") from e
    if not (0.0 <= v <= 1.0):
        raise argparse.ArgumentTypeError("epsilon must be in [0, 1].")
    return v


def _copy_all_constructs_to_generation(lang: str) -> None:
    src = Path("construct_storage") / lang / "all_constructs.json"
    dst = Path("construct_oriented_program_generator") / "language" / lang / "construct_list.json"
    if not src.is_file():
        raise FileNotFoundError(f"Missing enumeration output: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[F] copied {src} → {dst}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="Run construct enumeration (-E), program generation (-G), or full pipeline (-F).",
    )

    mx = p.add_mutually_exclusive_group(required=True)
    mx.add_argument(
        "-E",
        dest="enumerate_lang",
        choices=LANG_CHOICES,
        help="Run construct enumeration for the given language.",
    )
    mx.add_argument(
        "-G",
        dest="generate_lang",
        choices=LANG_CHOICES,
        help="Run program generation for the given language.",
    )
    mx.add_argument(
        "-F",
        dest="full_lang",
        choices=LANG_CHOICES,
        help="Run full pipeline: enumeration then generation for the given language.",
    )
    mx.add_argument(
        "-C",
        dest="clean_lang",
        choices=("c", "go", "js"),
        help="Clean enumeration artifacts for a language (generated-* folders, round JSONs, reset all_constructs.json, delete stat.log).",
    )

    # ONE positional bucket for both -G and -F.
    # argparse cannot reliably support two separate nargs="*" positionals.
    p.add_argument(
        "extras",
        nargs="*",
        help=(
            "Extra args for -G or -F.\n"
            "  -G: <max_programs> [p_two p_three]\n"
            "  -F: <epsilon> <max_rounds> <max_programs> [p_two p_three]\n"
        ),
    )

    p.add_argument(
        "--epsilon",
        type=_epsilon_type,
        default=None,
        help="Stopping threshold in [0, 1] for enumeration rounds (required for -E only).",
    )
    p.add_argument(
        "--model",
        default="gpt-4",
        help="OpenAI model name to use (default: gpt-4).",
    )
    p.add_argument(
        "--max-rounds",
        type=int,
        default=20,
        help="Maximum number of continual expansion rounds (default: 20).",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.clean_lang:
        from construct_enumerator.cleaner import clean_language

        clean_language(language=args.clean_lang)
        return 0

    # Validate epsilon for -E only (for -F it comes from extras).
    if args.enumerate_lang and args.epsilon is None:
        print("error: --epsilon is required for -E.", file=sys.stderr)
        return 2

    if args.enumerate_lang:
        run_enumeration(
            language=args.enumerate_lang,
            epsilon=args.epsilon,
            model=args.model,
            max_rounds=args.max_rounds,
        )
        return 0

    if args.generate_lang:
        # -G: <max_programs> [p_two p_three]
        if len(args.extras) not in (1, 3):
            print(
                "error: For -G, provide:\n"
                "  python main.py -G <lang> <max_programs> [p_two p_three] --model <model>\n"
                "examples:\n"
                "  python main.py -G c 10 --model gpt-4\n"
                "  python main.py -G c 10 0.6 0.4 --model gpt-4",
                file=sys.stderr,
            )
            return 2

        try:
            max_programs = int(args.extras[0])
        except ValueError:
            print("error: max_programs must be an integer.", file=sys.stderr)
            return 2

        if max_programs <= 0:
            print("error: max_programs must be > 0.", file=sys.stderr)
            return 2

        p_two = None
        p_three = None
        if len(args.extras) == 3:
            try:
                p_two = float(args.extras[1])
                p_three = float(args.extras[2])
            except ValueError:
                print("error: p_two and p_three must be numbers.", file=sys.stderr)
                return 2

        run_generation(
            language=args.generate_lang,
            model=args.model,
            max_programs=max_programs,
            p_two=p_two,
            p_three=p_three,
        )
        return 0

    if args.full_lang:
        # -F: <epsilon> <max_rounds> <max_programs> [p_two p_three]
        if len(args.extras) not in (3, 5):
            print(
                "error: For -F, provide:\n"
                "  python main.py -F <lang> <epsilon> <max_rounds> <max_programs> [p_two p_three] --model <model>\n"
                "examples:\n"
                "  python main.py -F c 0.2 2 10 --model gpt-4\n"
                "  python main.py -F c 0.2 2 10 0.6 0.4 --model gpt-4",
                file=sys.stderr,
            )
            return 2

        try:
            epsilon = _epsilon_type(args.extras[0])
            max_rounds = int(args.extras[1])
            max_programs = int(args.extras[2])
        except ValueError:
            print("error: max_rounds and max_programs must be integers.", file=sys.stderr)
            return 2

        if max_rounds <= 0:
            print("error: max_rounds must be > 0.", file=sys.stderr)
            return 2
        if max_programs <= 0:
            print("error: max_programs must be > 0.", file=sys.stderr)
            return 2

        p_two = None
        p_three = None
        if len(args.extras) == 5:
            try:
                p_two = float(args.extras[3])
                p_three = float(args.extras[4])
            except ValueError:
                print("error: p_two and p_three must be numbers.", file=sys.stderr)
                return 2

        # 1) Enumeration
        print(
            f"[F] starting enumeration: lang={args.full_lang}, epsilon={epsilon}, "
            f"max_rounds={max_rounds}, model={args.model}"
        )
        run_enumeration(
            language=args.full_lang,
            epsilon=epsilon,
            model=args.model,
            max_rounds=max_rounds,
        )
        print("[F] enumeration finished")

        # 2) Copy enumeration output into generation input
        _copy_all_constructs_to_generation(args.full_lang)

        # 3) Generation
        print(
            f"[F] starting generation: lang={args.full_lang}, max_programs={max_programs}, model={args.model}"
        )
        run_generation(
            language=args.full_lang,
            model=args.model,
            max_programs=max_programs,
            p_two=p_two,
            p_three=p_three,
        )
        print("[F] generation finished")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
