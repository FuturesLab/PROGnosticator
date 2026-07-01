# Go2Hx Translation Fuzzing Campaign

Dependencies:
- **Go**: [install from here](https://go.dev/doc/install).
- **Go2Hx**: [install from here](https://github.com/go2hx/go2hx).


This script automates the process of: Compiling Go programs -> Translating them to Haxe using Go2Hx -> Running both versions -> Comparing outputs to detect translation divergences

---

## 🔧 How to Run

```bash
python3 PROGnosticatoring.py <input_Go_folder> <campaign_id>
```

- `<input_Go_folder>`: Directory containing PROGnosticator-generated `.go` files.
- `<campaign_id>`: A unique identifier to organize results (e.g., `1` etc.)

We here provide some sample PROGnosticator-generated Go programs in `prog_sample_programs` folder.


- You must pass two arguments when running the script:

```bash
  python3 PROGnosticatoring.py <input_Go_folder> <campaign_id>

  # for example
  python3 prog_sample_programs 1
```


---

## 📁 Output Directory Structure

The script creates a directory:

```
campaign_<campaign_id>/
```

Inside it:

### `processing/temp_<filename>/`
- Working directory for each Go file
- Contains:
  - `runner.go`: Original Go file
  - `runner_go`: Compiled Go binary
  - `golibs/`: Translated Haxe code

### `go2hx_crashes/`
- Go files that caused Go2Hx to crash or fail translation

### `go2hx_divergence/`
- Go files where:
  - The Go and translated Haxe outputs **do not match**
  - Or Haxe execution failed

---

## 📄 Log Files

- `log_go_build_failure.txt`  
  → Go files that failed to build.

- `log_go2hx_crashes.txt`  
  → Go2Hx translation failures.

- `log_bad_Go_exe.txt`  
  → Go binaries that failed to execute.

- `log_bad_go_exe.txt`  
  → Haxe binaries that failed to execute.

- `log_diverge_output.txt`  
  → Output mismatches between Go and Haxe binaries.

- `summary.txt`  
  → Count of all outcomes and total translation results.

---
