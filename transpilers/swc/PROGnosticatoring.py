#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

TIMEOUT = 10  # seconds per run

def run_cmd(cmd, cwd, timeout=TIMEOUT):
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
    parser = argparse.ArgumentParser(description="SWC transpilation campaign runner")
    parser.add_argument("input_folder", help="Folder containing .js files to process")
    parser.add_argument("campaign_id", type=int, help="Used in output folder name: swc_out_<id>")
    args = parser.parse_args()

    cwd = Path().resolve()
    input_dir = (cwd / args.input_folder).resolve()
    if not input_dir.is_dir():
        print(f"ERROR: Input folder not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = cwd / f"swc_out_{args.campaign_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy swc_project/ once into the output folder
    src_swc = cwd / "swc_project"
    if not src_swc.is_dir():
        print(f"ERROR: 'swc_project/' not found in current directory: {cwd}", file=sys.stderr)
        sys.exit(1)
    dst_swc = out_dir / "swc_project"
    shutil.copytree(src_swc, dst_swc, dirs_exist_ok=True)

    # One-time deps install
    deps_flag = dst_swc / ".deps_installed"
    if not deps_flag.exists():
        nm = dst_swc / "node_modules"
        if nm.exists():
            shutil.rmtree(nm, ignore_errors=True)

        print("[setup] Installing SWC deps in campaign copy...")
        ok, out, err, rc = run_cmd(
            ["npm", "i", "-D", "@swc/cli@1.13.5", "@swc/core@1.13.5"],
            cwd=dst_swc,
            timeout=600,
        )
        if not ok:
            print("[setup] npm install failed inside swc_project (rc=%s)" % rc)
            print(err)
            sys.exit(1)

        deps_flag.write_text("ok", encoding="utf-8")
        print("[setup] SWC deps installed.")
    else:
        print("[setup] Skipping deps install (already done).")

    # Paths inside swc_project
    input_js_path = dst_swc / "input.js"
    output_js_path = dst_swc / "output.js"

    # Logs
    input_js_failure_log = out_dir / "input_js_failure.txt"
    swc_crash_log = out_dir / "swc_crash.txt"
    output_js_failure_log = out_dir / "output_js_failure.txt"
    divergence_log = out_dir / "divergence_output.txt"
    summary_path = out_dir / "summary.txt"

    total_files = 0
    valid_js_count = 0
    input_js_failure_count = 0
    swc_crash_count = 0
    output_js_failure_count = 0
    divergence_count = 0
    matched_count = 0

    start_time = time.time()

    js_files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".js"])
    for js_file in js_files:
        total_files += 1
        fname = js_file.name

        # Cleanup leftovers
        for p in (input_js_path, output_js_path):
            try:
                if p.exists(): p.unlink()
            except Exception:
                pass

        # Copy current input into input.js
        try:
            content = js_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            input_js_failure_count += 1
            safe_append_line(input_js_failure_log, fname)
            print(f"[{fname}] READ ERROR -> input_js_failure")
            continue

        input_js_path.write_text(content, encoding="utf-8", errors="ignore")

        # 1) Native run
        ok_native, out_native, err_native, rc_native = run_cmd(["node", "input.js"], cwd=dst_swc)
        if not ok_native:
            input_js_failure_count += 1
            safe_append_line(input_js_failure_log, fname)
            print(f"[{fname}] Native run failed (rc={rc_native}) -> input_js_failure")
            print(err_native)
            continue
        valid_js_count += 1

        # 2) SWC transpilation
        ok_swc, out_swc, err_swc, rc_swc = run_cmd(
            ["npx", "swc", "input.js", "-o", "output.js", "--config-file", ".swcrc"],
            cwd=dst_swc
        )
        if not ok_swc:
            swc_crash_count += 1
            safe_append_line(swc_crash_log, fname)
            print(f"[{fname}] SWC transpilation failed (rc={rc_swc}) -> swc_crash")
            print(err_swc)
            continue

        # 3) Run transpiled output
        ok_out, out_transpiled, err_out, rc_out = run_cmd(["node", "output.js"], cwd=dst_swc)
        if not ok_out:
            output_js_failure_count += 1
            safe_append_line(output_js_failure_log, fname)
            print(f"[{fname}] Transpiled run failed (rc={rc_out}) -> output_js_failure")
            print(err_out)
            continue

        # 4) Compare outputs
        if out_native != out_transpiled:
            divergence_count += 1
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
            block.append("")
            safe_write(divergence_log, "\n".join(block), mode="a")
            print(f"[{fname}] DIVERGENCE detected")
        else:
            matched_count += 1
            print(f"[{fname}] OK (outputs match)")

    elapsed = time.time() - start_time
    def pct(x): return (100.0 * x / total_files) if total_files else 0.0

    # Summary
    summary = []
    summary.append(f"Campaign folder: {out_dir}")
    summary.append(f"SWC project copy: {dst_swc}")
    summary.append(f"Total JS files processed: {total_files}")
    summary.append("")
    summary.append(f"Total valid JS programs (native run ok): {valid_js_count} ({pct(valid_js_count):.2f}%)")
    summary.append("")
    summary.append("Counters:")
    summary.append(f"  input_js_failure: {input_js_failure_count}   ({pct(input_js_failure_count):.2f}%) (see {input_js_failure_log.name})")
    summary.append(f"  swc_crash:       {swc_crash_count}   ({pct(swc_crash_count):.2f}%) (see {swc_crash_log.name})")
    summary.append(f"  output_js_failure:{output_js_failure_count}   ({pct(output_js_failure_count):.2f}%) (see {output_js_failure_log.name})")
    summary.append(f"  divergence:      {divergence_count}   ({pct(divergence_count):.2f}%) (see {divergence_log.name})")
    summary.append(f"  outputs_match:   {matched_count}   ({pct(matched_count):.2f}%)")
    summary.append("")
    summary.append(f"Total time: {elapsed:.1f} seconds ({elapsed/3600:.2f} hours)")

    safe_write(summary_path, "\n".join(summary))
    print("\n=== Summary ===")
    print("\n".join(summary))

if __name__ == "__main__":
    main()
