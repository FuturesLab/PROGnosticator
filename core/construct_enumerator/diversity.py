from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set, Optional, Any, Type

NUM_WORDS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty",
]

# Add languages here:
# - key: your CLI language value
# - class_name: the class name you'd like to exist
# - module: python module that exposes language() (tree_sitter_c, tree_sitter_go, ...)
# - ext: file extension to scan
#For Rust, just uncomment the below line and make sure you have tree_sitter_rust installed and available.
_LANG_SPECS: Dict[str, Dict[str, str]] = {
    "c":  {"class_name": "CDiversityTracker",  "module": "tree_sitter_c",          "ext": ".c"},
    "go": {"class_name": "GoDiversityTracker", "module": "tree_sitter_go",         "ext": ".go"},
    "js": {"class_name": "JSDiversityTracker", "module": "tree_sitter_javascript", "ext": ".js"},
    "rust": {"class_name": "RustDiversityTracker", "module": "tree_sitter_rust", "ext": ".rs"},
    "python": {"class_name": "PythonDiversityTracker", "module": "tree_sitter_python", "ext": ".py"},
    "java": {"class_name": "JavaDiversityTracker", "module": "tree_sitter_java", "ext": ".java"},
}


def _traverse(node: Any, ancestors: list[str], counts: Dict[str, Set]) -> None:
    t = node.type
    counts["nodes"].add(t)
    if len(ancestors) >= 1:
        counts["pairs"].add((ancestors[-1], t))
    if len(ancestors) >= 2:
        counts["triplets"].add((ancestors[-2], ancestors[-1], t))
    if len(ancestors) >= 3:
        counts["quadruplets"].add((ancestors[-3], ancestors[-2], ancestors[-1], t))
    if len(ancestors) >= 5:
        counts["quintuplets"].add((ancestors[-4], ancestors[-3], ancestors[-2], ancestors[-1], t))
    if len(ancestors) >= 6:
        counts["sextuplets"].add(
            (ancestors[-5], ancestors[-4], ancestors[-3], ancestors[-2], ancestors[-1], t)
        )

    for child in node.children:
        _traverse(child, ancestors + [t], counts)


@dataclass
class DiversityTracker:
    """Cumulative diversity tracker; each update adds info from one folder."""
    counts: Dict[str, Set]

    def totals(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self.counts.items()}

    def update_from_folder(self, folder: Path) -> Dict[str, int]:
        raise NotImplementedError


class _BaseTreeSitterTracker(DiversityTracker):
    """Shared implementation for all generated trackers."""
    _ext: str
    _module_name: str

    def __init__(self) -> None:
        super().__init__(
            counts={
                "nodes": set(),
                "pairs": set(),
                "triplets": set(),
                "quadruplets": set(),
                "quintuplets": set(),
                "sextuplets": set(),
            }
        )

        from tree_sitter import Language, Parser  # type: ignore

        mod = importlib.import_module(self._module_name)
        if not hasattr(mod, "language"):
            raise RuntimeError(
                f"Module '{self._module_name}' must expose a language() function."
            )

        self._lang = Language(mod.language())
        self._parser = Parser(self._lang)

    def update_from_folder(self, folder: Path) -> Dict[str, int]:
        folder = Path(folder)
        if not folder.is_dir():
            raise FileNotFoundError(f"Folder not found: {folder}")

        for fname in sorted(folder.iterdir()):
            if not fname.is_file() or fname.suffix != self._ext:
                continue
            src_bytes = fname.read_bytes()
            tree = self._parser.parse(src_bytes)

            # Optional: skip syntax-error trees
            # if tree.root_node.has_error:
            #     continue

            _traverse(tree.root_node, [], self.counts)

        return self.totals()


# Dynamically create one tracker class per language spec and export it at module level.
_TRACKER_CLASSES: Dict[str, Type[_BaseTreeSitterTracker]] = {}

for lang, spec in _LANG_SPECS.items():
    class_name = spec["class_name"]
    module_name = spec["module"]
    ext = spec["ext"]

    cls = type(
        class_name,
        (_BaseTreeSitterTracker,),
        {
            "_module_name": module_name,
            "_ext": ext,
            "__doc__": f"Auto-generated Tree-sitter diversity tracker for '{lang}'.",
        },
    )

    _TRACKER_CLASSES[lang] = cls
    globals()[class_name] = cls  # so CDiversityTracker / GoDiversityTracker / JSDiversityTracker exist


def language_diversity_tracker(language: str) -> Optional[DiversityTracker]:
    """Factory matching the old style: returns <Lang>DiversityTracker()."""
    language = language.lower().strip()
    cls = _TRACKER_CLASSES.get(language)
    return cls() if cls else None


def register_language(language: str, *, class_name: str, module: str, ext: str) -> None:
    """Optional: allow adding new languages without editing code elsewhere."""
    if not ext.startswith("."):
        raise ValueError("ext must start with '.' (example: '.rs').")

    _LANG_SPECS[language] = {"class_name": class_name, "module": module, "ext": ext}

    cls = type(
        class_name,
        (_BaseTreeSitterTracker,),
        {"_module_name": module, "_ext": ext, "__doc__": f"Auto-generated tracker for '{language}'."},
    )
    _TRACKER_CLASSES[language] = cls
    globals()[class_name] = cls
