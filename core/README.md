# PROGnosticator Full Pipeline (-F Option)

The `-F` option runs the complete workflow:

1. Construct Usage Enumeration (-E stage)
2. Construct-oriented Program Generation (-G stage)

---

## Required Inputs (Prompts and Files)

### Enumeration Inputs

For each language (`c`, `go`, `js`, `rust`, `python`, `java`), you must provide:

1) Initial enumeration prompt (Round 0): `construct_storage/<lang>/initial_prompt.txt`

2) Continual enumeration prompt (Rounds 1..N): `construct_storage/<lang>/continual_prompt.txt`

3) Enumeration-stage generator template: `construct_enumerator/generator_prompt/<lang>_generator_prompt.txt`

- Used to generate per-construct programs during enumeration.
- Must contain `{CONSTRUCT}`.

---

### Generation Inputs

For each language, you must provide:

1) Generation prompt template: `construct_oriented_program_generator/language/<lang>/generator_prompt.txt`

- Used to generate programs based on one or more constructs.
- Must contain `{CONSTRUCTS}`.

---

## Command Format

```bash
python main.py -F <lang> <epsilon> <max_rounds> <max_programs> <p_two> <p_three> --model <model>
```

---

## Arguments

- `<lang>` : Programming language (`c`, `go`, `js`, `rust`, `java`, `python` etc.)

- `<epsilon>` : Relative growth threshold for enumeration stopping.

- `<max_rounds>` : Maximum number of continual expansion rounds.

- `<max_programs>` : Total number of multi-construct programs to generate.

- `<p_two> <p_three>` (optional)  
  Percentage split for multi-construct programs:
  - `p_two` → fraction of two-construct programs  
  - `p_three` → fraction of three-construct programs  

If percentages are not provided, defaults are: `p_two = 0.6` and `p_three = 0.4`

---

## Example (Default Percentages)

```bash
python main.py -F c 0.2 2 10 --model gpt-4
```

Meaning:

- Run enumeration for C
- Stop when relative growth < 0.2 (i.e., the total number of unique ASTs across all depths up to level 6 in round X increases by less than 20% compared to round X−1)
- Maximum 2 rounds
- Generate 10 multi-construct programs
- 60% two-construct (6 programs)
- 40% three-construct (4 programs)

---

## Example (Custom Percentages)

```bash
python main.py -F c 0.2 2 10 0.7 0.3 --model gpt-4
```

Meaning:

- Same as above
- Explicitly sets:
  - 70% two-construct (7 out of total 10 programs)
  - 30% three-construct (3 out of total 10 programs)

---

## Output Locations

### Enumeration Outputs

- `construct_storage/<lang>/all_constructs.json`
- `construct_storage/<lang>/generated-*/`
- `construct_storage/<lang>/stat.log`

### Generation Outputs

- `construct_oriented_program_generator/language/<lang>/programs/single_construct_programs/`
- `construct_oriented_program_generator/language/<lang>/programs/two_construct_programs/`
- `construct_oriented_program_generator/language/<lang>/programs/three_construct_programs/`

---


Alternatively, you can test PROGnosticator's Construct Usage Enumeration stage and Construct-oriented Program Generation stage independently using the following steps.

# Construct Usage Enumeration (-E option)

This module performs iterative construct expansion using an LLM and measures structural diversity using Tree-sitter.

---

## Required Prompts

For each language (`c`, `go`, `js`, `rust`, `python`, `java`), provide the following files:

### 1) Initial Prompt (Round 0)

Location: `construct_storage/<lang>/initial_prompt.txt`

Purpose:
- Used for construct expansion in the first round. Must return valid JSON only.
- You can provide the high-level category names and samples for each. 
- Also, you can provide how many constructs to expand per category.
- Example output:
```json
{
  "Category1": ["construct1", "construct2"],
  "Category2": ["constructA", "constructB"]
}
```

---

### 2) Continual Prompt (Rounds 1, 2, ... N)

Location: `construct_storage/<lang>/continual_prompt.txt`

Purpose:
- Used after Round 0. The system automatically prepends all_constructs.json to this prompt.
- Must return valid JSON only like previous output.

---

### 3) Generator Prompt Template for Enumeration

Location: `construct_enumerator/generator_prompt/<lang>_generator_prompt.txt`

Purpose:
- Used for generating programs per construct.
- Must contain the placeholder: `{CONSTRUCT}`. This is automatically replaced by the system.

---

## How to Run Construct Enumeration

Example for language c.

Run with maximum 2 rounds and epsilon = 0.2: `python main.py -E c --epsilon 0.2 --max-rounds 2 --model gpt-4`

Explanation:
- `-E c` → Run construct enumeration for C
- `--epsilon 0.2` → Stop when relative diversity growth < 20%
- `--max-rounds 2` → Maximum 2 continual rounds. Default is 20. 
- `--model gpt-4` → Model used. You can provide a newer model name.

For another language: `python main.py -E go --epsilon 0.1 --model gpt-4`

---

## Where to Find Results

Final enumerated constructs: `construct_storage/<lang>/all_constructs.json`

This file contains the cumulative construct list. You can reuse it later for Program Generation stage.

Generated programs per round: `construct_storage/<lang>/generated-zero-shot/` `construct_storage/<lang>/generated-one-shot` `construct_storage/<lang>/generated-two-shot/`

Statistics log: `construct_storage/<lang>/stat.log`

---

## Fresh Start (Clean Everything)

To reset a language: `python main.py -C c`

This will:
- Delete all generated-* folders, round JSON files
- Reset all_constructs.json to {}
- Remove previous statistics log

---

# Construct-oriented Program Generation (-G Option)

## Required Inputs

For each language (`c`, `go`, `js`), provide:

### Construct List File

Location: `construct_oriented_program_generator/language/<lang>/construct_list.json`

If you do Construct-Enumeration stage part, then just copy the contents of `construct_storage/<lang>/all_constructs.json` to the above file.
Format:

```json
{
  "Category1": ["usage1", "usage2"],
  "Category2": ["usageA"]
}
```

### Generator Prompt Template

Location: `construct_oriented_program_generator/language/<lang>/generator_prompt.txt`

Must contain: `{CONSTRUCTS}`. The system replaces this automatically with one or multiple constructs.

---

## Default Generation Mode

Command: `python main.py -G c 5 --model gpt-4`

Behavior:
- Generate single-construct programs for **all construct usages** in `construct_list.json`.
- Generate 5 multi-construct programs total.
- Default split:
  - 60% two-construct programs
  - 40% three-construct programs

---

## Custom Percentage Mode

Command: `python main.py -G c 10 0.7 0.3 --model gpt-4`

Behavior:
- Generate single-construct programs for all usages.
- Generate 10 multi-construct programs total.
- 70% (7 programs) use two constructs.
- 30% (3 programs) use three constructs.

---

## Where to Find Program Generation Outputs

Single construct programs: `construct_oriented_program_generator/language/<lang>/programs/single_construct_programs/`

Two-construct programs: `construct_oriented_program_generator/language/<lang>/programs/two_construct_programs/`

Three-construct programs: `construct_oriented_program_generator/language/<lang>/programs/three_construct_programs/`
