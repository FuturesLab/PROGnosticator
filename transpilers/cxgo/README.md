# PROGnosticatoring.py

# CxGo Setup

Dependencies:
- **Go**: [install from here](https://go.dev/doc/install) (version `1.20+`).
- **CxGo**: [install from here](https://github.com/gotranspile/cxgo).
- Ensure the `clang`, `go`, and `cxgo` binaries are accessible from your `$PATH`.


This script (`PROGnosticatoring.py`) automates the process of compiling C programs, transpiling them to Go using `cxgo`, and checking if the output of the C and Go programs match.

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
- `cxgo_crashes/`: C files that cause `cxgo` to crash or fail transpilation.
- `cxgo_divergence/`: C files whose C and Go outputs differ, or where Go build/runtime fails.
- Various log files:
  - `log_C_compile_error.txt`: C compilation failures.
  - `log_cxgo_crashes.txt`: cxgo transpilation failures.
  - `log_bad_c_exe.txt`: Failures during C binary execution.
  - `log_go_build_failure.txt`: Go build failures.
  - `log_bad_go_exe.txt`: Failures during Go binary execution.
  - `log_diverge_output.txt`: C vs. Go output mismatches.
  - `summary.txt`: Final summary of campaign statistics.


## Result Summary

The final summary is written to:
```
campaign_<campaign_id>/summary.txt
```