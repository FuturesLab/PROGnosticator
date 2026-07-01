# PROGnosticatoring.py

# C2Rust Setup

Dependencies:
- **Cargo**: [install from here](https://www.rust-lang.org/tools/install).
- **C2Rust**: [install from here](https://github.com/immunant/c2rust).
- Ensure the `clang`, `cargo`, and `c2rust` binaries are accessible from your `$PATH`.

This script (`PROGnosticatoring.py`) automates the process of compiling C programs, transpiling them to Rust using `c2rust`, and checking if the output of the C and Rust programs match.

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

- `generated_C_output/`: Instrumented C files with a `main()` calling `func1()`.
- `processing/temp_<filename>/`: Temporary working directory for each file.
- `c2rust_crashes/`: C files that cause c2rust to crash.
- `c2rust_divergence/`: C files whose C and Rust outputs differ.
- Various log files:
  - `log_C_compile_error.txt`
  - `log_c2rust_crashes.txt`
  - `log_bad_c_exe.txt`
  - `log_rust_build_failure.txt`
  - `log_bad_rust_exe.txt`
  - `log_diverge_output.txt`
  - `summary.txt`

## Result Summary

The final summary is written to:
```
campaign_<campaign_id>/summary.txt
```