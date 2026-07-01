#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import time
from datetime import datetime, timedelta
import json
import re

# Handle Ctrl+C clean exit
def handle_sigint(signum, frame):
    print("\n[INFO] Ctrl+C received. Cleaning up and exiting...")
    sys.exit(0)

# Utility functions
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def remove_md_fences(code: str) -> str:
    lines = code.strip().splitlines()
    return "\n".join([line for line in lines if not line.strip().lower().startswith("```")]).strip()

def log_to_file(path, message):
    with open(path, "a") as f:
        f.write(message + "\n")

def compile_c(code_path, exe_path):
    try:
        subprocess.check_output(
            [
                "clang", "-g", "-O1", "-Wall", "-Wextra",
                "-Werror=int-conversion",
                "-Werror=return-type",
                "-Werror=incompatible-pointer-types",
                code_path, "-o", exe_path
            ],
            stderr=subprocess.STDOUT,
            timeout=5
        )
        print("[DEBUG] C compilation succeeded")
        return True
    except subprocess.CalledProcessError as e:
        print("[DEBUG] C compilation failed")
        return False


def transpile_c2rust(temp_dir, c_file):
    temp_dir = os.path.abspath(temp_dir)
    c_file = os.path.abspath(c_file)

    compile_commands = [{
        "arguments": ["/usr/bin/clang", "-O3", c_file],
        "directory": temp_dir,
        "file": c_file
    }]
    compile_commands_path = os.path.join(temp_dir, "compile_commands.json")
    with open(compile_commands_path, "w") as f:
        json.dump(compile_commands, f)

    rust_output_dir = os.path.join(temp_dir, "rust_output")
    ensure_dir(rust_output_dir)

    try:
        cmd = f"c2rust-transpile {compile_commands_path} -e -o {rust_output_dir} --binary runner"
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=10)
        output_text = output.decode()
        if any(x in output_text for x in ["error:", "missing child", "AstNode"]):
            print("[ERROR] C2Rust semantic failure detected")
            return None
        print("[SUCCESS] Transpilation succeeded")
        return rust_output_dir
    except subprocess.TimeoutExpired:
        print("[ERROR] Transpile timeout")
        return None
    except subprocess.CalledProcessError:
        print("[ERROR] C2Rust transpile failed")
        return None

def build_rust(rust_dir):
    try:
        manifest_path = os.path.join(rust_dir, "Cargo.toml")
        subprocess.check_output(
            f"cargo build --release --manifest-path={manifest_path}",
            shell=True,
            stderr=subprocess.STDOUT,
            timeout=20
        )
        print("[SUCCESS] Rust build succeeded")
        return os.path.join(rust_dir, "target", "release", "runner")
    except subprocess.CalledProcessError as e:
        print("[ERROR] Rust build failed")
        return None
    except subprocess.TimeoutExpired:
        print("[ERROR] Rust build timed out")
        return None

def run_exe(path):
    try:
        return subprocess.check_output(path, timeout=5).decode()
    except:
        print("[ERROR] Executable failed or timed out")
        return None

def log_event(log_path, tag, filename, elapsed):
    timestamp = time.strftime("%H:%M:%S", time.gmtime(elapsed))
    log_to_file(log_path, f"[{timestamp}] {tag} - {filename}")

def has_main_function(code):
    return re.search(r"\b(?:int|void)\s+main\s*\(", code) is not None


def instrument_c(code):
    if has_main_function(code):
        return code
    return (
        "#include <stdio.h>\n"
        f"{code}\n\n"
        "int main() {\n"
        "    int res = func1();\n"
        "    printf(\"%d\", res);\n"
        "    return 0;\n"
        "}\n"
    )

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fuzz_24_campaign.py <input_C_folder> <campaign_id>")
        sys.exit(1)

    input_folder, campaign_id = sys.argv[1], sys.argv[2]

    base_dir = f"campaign_{campaign_id}"
    gen_c_dir = os.path.join(base_dir, "generated_C_output")
    proc_dir = os.path.join(base_dir, "processing")
    crash_dir = os.path.join(base_dir, "c2rust_crashes")
    diverge_dir = os.path.join(base_dir, "c2rust_divergence")
    for path in [base_dir, gen_c_dir, proc_dir, crash_dir, diverge_dir]:
        ensure_dir(path)

    logs = {
        "c_compile": os.path.join(base_dir, "log_C_compile_error.txt"),
        "c2rust_crash": os.path.join(base_dir, "log_c2rust_crashes.txt"),
        "bad_c_exe": os.path.join(base_dir, "log_bad_c_exe.txt"),
        "rust_build": os.path.join(base_dir, "log_rust_build_failure.txt"),
        "bad_rust_exe": os.path.join(base_dir, "log_bad_rust_exe.txt"),
        "diverge": os.path.join(base_dir, "log_diverge_output.txt"),
        "summary": os.path.join(base_dir, "summary.txt")
    }

    label_map = {
        "c_compile": "C compile failure",
        "c2rust_crash": "C2Rust crash",
        "bad_c_exe": "Bad C exe",
        "rust_build": "Rust build failure",
        "bad_rust_exe": "Bad Rust exe",
        "diverge": "Divergence",
        "equivalent_translation": "Perfect translation"
    }

    counters = {k: 0 for k in logs if k != "summary"}
    counters["equivalent_translation"] = 0
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=1440)

    all_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".c")])

    for idx, filename in enumerate(all_files):
        if datetime.now() > end_time:
            break

        src_path = os.path.join(input_folder, filename)
        timestamp = time.strftime("%H_%M_%S", time.gmtime((datetime.now() - start_time).total_seconds()))
        name, ext = os.path.splitext(filename)
        dst_path = os.path.join(gen_c_dir, f"{name}_{timestamp}{ext}")

        with open(src_path) as f:
            raw_code = f.read()
        
        instrumented_code = instrument_c(raw_code)
        with open(dst_path, "w") as f:
            f.write(instrumented_code)

        temp_dir = os.path.join(proc_dir, f"temp_{name}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        ensure_dir(temp_dir)

        temp_c = os.path.join(temp_dir, "runner.c")
        shutil.copyfile(dst_path, temp_c)

        exe = os.path.join(temp_dir, "runner.out")
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n[DEBUG] Processing file: {filename}")

        if not compile_c(temp_c, exe):
            counters["c_compile"] += 1
            log_event(logs["c_compile"], "C_COMPILE_FAIL", filename, elapsed)
            shutil.rmtree(temp_dir)
            continue

        rust_dir = transpile_c2rust(temp_dir, temp_c)
        if not rust_dir:
            counters["c2rust_crash"] += 1
            log_event(logs["c2rust_crash"], "C2RUST_FAIL", filename, elapsed)
            shutil.copy(dst_path, crash_dir)
            continue

        rust_bin = build_rust(rust_dir)
        if not rust_bin:
            counters["rust_build"] += 1
            log_event(logs["rust_build"], "RUST_BUILD_FAIL", filename, elapsed)
            shutil.copy(dst_path, diverge_dir)
            continue

        c_out = run_exe(exe)
        if c_out is None:
            counters["bad_c_exe"] += 1
            log_event(logs["bad_c_exe"], "C_EXEC_FAIL", filename, elapsed)
            continue

        rust_out = run_exe(rust_bin)
        if rust_out is None:
            counters["bad_rust_exe"] += 1
            log_event(logs["bad_rust_exe"], "RUST_EXEC_FAIL", filename, elapsed)
            shutil.copy(dst_path, diverge_dir)
            print(f"[DEBUG] Skipping {filename} due to Rust execution failure")
            continue

        if c_out != rust_out:
            counters["diverge"] += 1
            log_event(logs["diverge"], "OUTPUT_DIVERGENCE", filename, elapsed)
            log_to_file(logs["diverge"], f"C: {c_out.strip()} | Rust: {rust_out.strip()}")
            shutil.copy(dst_path, diverge_dir)
            print(f"[DEBUG] Output mismatch for {filename}:\n  C    → {c_out.strip()}\n  Rust → {rust_out.strip()}")
        else:
            counters["equivalent_translation"] += 1
            print(f"[DEBUG] Output matched for {filename}")
            shutil.rmtree(temp_dir)
            continue

    total_runtime_hours = (datetime.now() - start_time).total_seconds() / 3600
    with open(logs["summary"], "w") as f:
        f.write(f"Campaign ID: {campaign_id}\n")
        f.write(f"Total files processed: {idx+1}\n")
        f.write(f"Total campaign runtime: {total_runtime_hours:.2f} hours\n")
        for key in counters:
            f.write(f"{label_map.get(key, key)}: {counters[key]}\n")

    print(f"\nFinished. Summary written to {logs['summary']}")
    print(f"Total campaign runtime: {total_runtime_hours:.2f} hours")

if __name__ == "__main__":
    main()
