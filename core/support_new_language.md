# Supporting Other Languages

PROGnosticator currently includes ready-to-use setups for `c`, `go`, `js`, `rust`, `python`, and `java`.
To add another language, create the same prompt/config files for the new language name, for example `cpp`.

### 1. Add Enumeration Prompts

Create:

```text
construct_storage/cpp/initial_prompt.txt
construct_storage/cpp/continual_prompt.txt
construct_enumerator/generator_prompt/cpp_generator_prompt.txt
```

`cpp_generator_prompt.txt` must contain:

```text
{CONSTRUCT}
```

### 2. Add Generation Prompts

Create:

```text
construct_oriented_program_generator/language/cpp/construct_list.json
construct_oriented_program_generator/language/cpp/generator_prompt.txt
```

`generator_prompt.txt` must contain:

```text
{CONSTRUCTS}
```

### 3. Update in Source Code

For a new language such as `cpp`, update the language maps used by the generator and diversity tracker:

- `construct_enumerator/generator.py`: add `cpp` to `_LANG_TO_PROMPT` and `_LANG_TO_EXT`.
- `construct_oriented_program_generator/generator.py`: add `cpp` to `_LANG_EXT`.
- `construct_enumerator/diversity.py`: add `cpp` to `_LANG_SPECS` with its Tree-sitter module and file extension.

Example entries:

```python
# construct_enumerator/generator.py
_LANG_TO_PROMPT["cpp"] = Path("construct_enumerator/generator_prompt/cpp_generator_prompt.txt")
_LANG_TO_EXT["cpp"] = ".cpp"

# construct_oriented_program_generator/generator.py
_LANG_EXT["cpp"] = ".cpp"

# construct_enumerator/diversity.py
_LANG_SPECS["cpp"] = {
    "class_name": "CppDiversityTracker",
    "module": "tree_sitter_cpp",
    "ext": ".cpp",
}
```

Also install the matching Tree-sitter package, for example:

```bash
pip install tree-sitter-cpp
```

### 4. Run Full Pipeline

Example for C++:

```bash
python main.py -F cpp 0.2 2 10 --model gpt-4
```

This runs construct enumeration for C++ and then generates 10 C++ programs from the discovered constructs.
