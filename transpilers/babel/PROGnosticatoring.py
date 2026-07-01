#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

def run_cmd(cmd, cwd, timeout=None):
    """Run a command (no shell). Return (ok, stdout, stderr, returncode)."""
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (r.returncode == 0), r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        return False, (e.stdout or ""), (e.stderr or f"Timed out after {timeout}s."), -999

def safe_write(path: Path, content: str, mode="w"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8") as f:
        f.write(content)

def safe_append_line(path: Path, line: str):
    safe_write(path, line.rstrip() + "\n", mode="a")


def main():
    parser = argparse.ArgumentParser(description="Babel transpilation campaign runner")
    parser.add_argument("input_folder", help="Folder containing .js files to process")
    parser.add_argument("campaign_id", type=int, help="Used in output folder name: campaign_out_<id>")
    
    args = parser.parse_args()

    cwd = Path().resolve()
    input_dir = (cwd / args.input_folder).resolve()
    if not input_dir.is_dir():
        print(f"ERROR: Input folder not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = cwd / f"campaign_out_{args.campaign_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy babel_project/ once into the output folder
    src_babel = cwd / "babel_project"
    if not src_babel.is_dir():
        print(f"ERROR: 'babel_project/' not found in current directory: {cwd}", file=sys.stderr)
        sys.exit(1)
    dst_babel = out_dir / "babel_project"
    shutil.copytree(src_babel, dst_babel, dirs_exist_ok=True)

    deps_flag = dst_babel / ".deps_installed"

    if not deps_flag.exists():
        # Clean any copied node_modules (can be inconsistent after copy)
        nm = dst_babel / "node_modules"
        if nm.exists():
            shutil.rmtree(nm, ignore_errors=True)

        print("[setup] Installing Babel deps in campaign copy...")
        ok, out, err, rc = run_cmd(
            ["npm", "install", "--save-dev", "@babel/core@7.28.3", "@babel/cli@7.28.3", "@babel/preset-env@7.28.3"],
            cwd=dst_babel,
            timeout=600  # give installs more time than the 10s run timeout
        )

        if not ok:
            print("[setup] npm install failed inside campaign babel_project (rc=%s)" % rc)
            print(err)  # show full error on terminal
            sys.exit(1)

        # mark as done
        deps_flag.write_text("ok", encoding="utf-8")
        print("[setup] Babel deps installed.")
    else:
        print("[setup] Skipping deps install (already done).")

    # Paths inside the copied babel project
    babel_src_dir = dst_babel / "src"
    babel_dist_dir = dst_babel / "dist"
    app_js_path = babel_src_dir / "app.js"
    dist_app_js_path = babel_dist_dir / "app.js"

    # Logs
    input_js_failure_log = out_dir / "input_js_failure.txt"
    babel_crash_log = out_dir / "babel_crash.txt"
    output_js_failure_log = out_dir / "output_js_failure.txt"
    divergence_log = out_dir / "divergence_output.txt"
    summary_path = out_dir / "summary.txt"

    total_files = 0
    input_js_failure_count = 0
    babel_crash_count = 0
    output_js_failure_count = 0
    divergence_count = 0
    matched_count = 0
    valid_js_count = 0


    start_time = time.time()

    js_files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".js"])
    for js_file in js_files:
        total_files += 1
        fname = js_file.name

        # Clean previous leftovers
        for p in (app_js_path, dist_app_js_path):
            try:
                if p.exists(): p.unlink()
            except Exception:
                pass

        # Write current input into src/app.js
        try:
            content = js_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            input_js_failure_count += 1
            safe_append_line(input_js_failure_log, fname)
            print(f"[{fname}] READ ERROR -> input_js_failure", file=sys.stderr)
            continue

        babel_src_dir.mkdir(parents=True, exist_ok=True)
        app_js_path.write_text(content, encoding="utf-8", errors="ignore")

        # 1) Native run
        ok_native, out_native, err_native, rc_native = run_cmd(["node", "src/app.js"], cwd=dst_babel, timeout=10)
        if not ok_native:
            input_js_failure_count += 1
            safe_append_line(input_js_failure_log, fname)
            print(f"[{fname}] Native run failed (rc={rc_native}) -> input_js_failure")
            try:
                if app_js_path.exists(): app_js_path.unlink()
            except Exception:
                pass
            continue

        # Reaching here means native run succeeded → count as valid
        valid_js_count += 1

        # 2) Transpile with Babel
        ok_babel, out_babel, err_babel, rc_babel = run_cmd(["npx", "babel", "src", "--out-dir", "dist"], cwd=dst_babel, timeout=10)
        if not ok_babel:
            babel_crash_count += 1
            safe_append_line(babel_crash_log, fname)
            print(f"[{fname}] Babel transpilation failed (rc={rc_babel}) -> babel_crash")
            print(err_babel)   # <<< print full error to terminal
            if app_js_path.exists():
                app_js_path.unlink()
            continue

        # 3) Run transpiled output
        ok_out, out_transpiled, err_out, rc_out = run_cmd(["node", "dist/app.js"], cwd=dst_babel, timeout=10)
        if not ok_out:
            output_js_failure_count += 1
            safe_append_line(output_js_failure_log, fname)
            print(f"[{fname}] Transpiled run failed (rc={rc_out}) -> output_js_failure")
            # Cleanup
            for p in (app_js_path, dist_app_js_path):
                try:
                    if p.exists(): p.unlink()
                except Exception:
                    pass
            continue

        # Compare outputs; only save when mismatched
        if out_native != out_transpiled:
            divergence_count += 1
            # Append a detailed block: filename + both outputs
            block = []
            block.append("=" * 80)
            block.append(f"FILE: {fname}")
            block.append("-" * 80)
            block.append("[NATIVE STDOUT]")
            block.append(out_native.rstrip("\n"))
            block.append("-" * 80)
            block.append("[TRANSPILED STDOUT]")
            block.append(out_transpiled.rstrip("\n"))
            block.append("=" * 80)
            block.append("")  # trailing newline
            safe_write(divergence_log, "\n".join(block), mode="a")
            print(f"[{fname}] DIVERGENCE detected")
        else:
            matched_count += 1
            print(f"[{fname}] OK (outputs match)")

        # Cleanup
        for p in (app_js_path, dist_app_js_path):
            try:
                if p.exists(): p.unlink()
            except Exception:
                pass

    elapsed = time.time() - start_time

    def pct(x):
        return (100.0 * x / total_files) if total_files else 0.0

    # Summary
    summary = []
    summary.append(f"Campaign folder: {out_dir}")
    summary.append(f"Babel project copy: {dst_babel}")
    summary.append(f"Total valid JS programs (native run ok): {valid_js_count} ({pct(valid_js_count):.2f}%)")
    summary.append("")
    summary.append("Counters:")
    summary.append(f"  input_js_failure: {input_js_failure_count}   (see {input_js_failure_log.name})")
    summary.append(f"  babel_crash:      {babel_crash_count}   (see {babel_crash_log.name})")
    summary.append(f"  output_js_failure:{output_js_failure_count}   (see {output_js_failure_log.name})")
    summary.append(f"  divergence:       {divergence_count}   (see {divergence_log.name})")
    summary.append(f"  outputs_match:    {matched_count}")
    summary.append("")
    summary.append(f"Total time: {elapsed:.1f} seconds ({elapsed/3600:.2f} hours)")
    safe_write(summary_path, "\n".join(summary))

    print("\n=== Summary ===")
    print("\n".join(summary))

if __name__ == "__main__":
    main()
