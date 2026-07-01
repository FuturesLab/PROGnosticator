# PROGnosticatoring.py

# Zig Translate-C Setup

Dependencies:
- **Zig**: [install from here](https://ziglang.org/download/).
- Ensure the `clang` and `zig` binaries are accessible from your `$PATH`.


This script (`PROGnosticatoring.py`) automates the process of compiling C programs, transpiling them to Zig using `Zig Translate-C`, building the Rust version, and checking if the output of the C and Zig programs match.

## Usage

- You must pass two arguments when running the script:
  ```bash
  python3 PROGnosticatoring.py <input_C_folder> <campaign_id>
  ```

- The `<input_C_folder>` should contain PROGnosticator-generated `.c` files only having defined a function `int func1()`.
We here provide some sample PROGnosticator-generated C programs in `prog_sample_programs` folder.

- You must pass two arguments when running the script:

```bash
  python3 PROGnosticatoring.py <input_C_folder> <campaign_id>

  # for example
  python3 prog_sample_programs 1
```


## Output Directory Structure

The script creates the following folders under a `campaign_<campaign_id>` directory:

- `processing/temp_<filename>/`: Temporary working directory for each file containing the C, Zig, and compiled binaries.
- `zig_translate_crashes/`: C files that caused `zig translate-c` to crash or fail.
- `zig_divergence/`: C files whose C and Zig outputs differ, or where Zig build/runtime fails.
- Various log files:
  - `log_C_compile_error.txt`: C compilation failures.
  - `log_zig_translate_crash.txt`: zig translation failures.
  - `log_zig_build_failure.txt`: Zig build failures.
  - `log_bad_c_exe.txt`: Failures during C binary execution.
  - `log_bad_zig_exe.txt`: Failures during Zig binary execution.
  - `log_diverge_output.txt`: C vs. Zig output mismatches.
  - `summary.txt`: Final summary of campaign statistics.

## Result Summary

The final summary is written to:
```
campaign_<campaign_id>/summary.txt
```