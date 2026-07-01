#!/usr/bin/env python3
import os
import sys
import time
import shutil
import subprocess
import signal
from datetime import datetime, timedelta
import re

def handle_sigint(signum, frame):
    print("\n[INFO] Ctrl+C received. Cleaning up and exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def remove_md_fences(code: str) -> str:
    lines = code.strip().splitlines()
    return "\n".join([line for line in lines if not line.strip().lower().startswith("```")]).strip()

def has_main_function(code: str) -> bool:
    return re.search(r"\b(?:int|void)\s+main\s*\(", code) is not None


def instrument_c(code: str) -> str:
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


def transpile_cxgo(temp_dir):
    try:
        subprocess.check_output("cxgo file runner.c > /dev/null 2>&1", shell=True, cwd=temp_dir, timeout=10)
        print("[DEBUG] cxgo transpilation succeeded")
        return True
    except:
        print("[DEBUG] cxgo transpilation failed")
        return False

def build_go(temp_dir):
    try:
        subprocess.check_output("go mod init my_module", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=5)
        subprocess.check_output("go mod tidy", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=5)
        subprocess.check_output("go build -o runner_go runner.go", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=10)
        print("[DEBUG] Go build succeeded")
        return os.path.join(temp_dir, "runner_go")
    except:
        print("[DEBUG] Go build failed")
        return None

def run_exe(path):
    try:
        return subprocess.check_output(path, timeout=5).decode()
    except:
        print("[DEBUG] Executable failed or timed out")
        return None

def log_event(log_path, tag, filename, elapsed):
    timestamp = time.strftime("%H:%M:%S", time.gmtime(elapsed))
    log_to_file(log_path, f"[{timestamp}] {tag} - {filename}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 PROGnosticatoring.py <input_C_folder> <campaign_id>")
        sys.exit(1)

    input_folder, campaign_id = sys.argv[1], sys.argv[2]

    base_dir = f"campaign_{campaign_id}"
    gen_c_dir = os.path.join(base_dir, "generated_C_output")
    proc_dir = os.path.join(base_dir, "processing")
    crash_dir = os.path.join(base_dir, "cxgo_crashes")
    diverge_dir = os.path.join(base_dir, "cxgo_divergence")

    for path in [base_dir, gen_c_dir, proc_dir, crash_dir, diverge_dir]:
        ensure_dir(path)

    logs = {
        "c_compile": os.path.join(base_dir, "log_C_compile_error.txt"),
        "cxgo_crash": os.path.join(base_dir, "log_cxgo_crashes.txt"),
        "bad_c_exe": os.path.join(base_dir, "log_bad_c_exe.txt"),
        "go_build": os.path.join(base_dir, "log_go_build_failure.txt"),
        "bad_go_exe": os.path.join(base_dir, "log_bad_go_exe.txt"),
        "diverge": os.path.join(base_dir, "log_diverge_output.txt"),
        "summary": os.path.join(base_dir, "summary.txt")
    }

    label_map = {
        "c_compile": "C compile failure",
        "cxgo_crash": "Cxgo crash",
        "bad_c_exe": "Bad C exe",
        "go_build": "Go build failure",
        "bad_go_exe": "Bad Go exe",
        "diverge": "Divergence",
        "equivalent_translation": "Perfect translation"
    }

    counters = {k: 0 for k in logs if k != "summary"}
    counters["equivalent_translation"] = 0

    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)
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
        clean_code = remove_md_fences(raw_code)
        instrumented_code = instrument_c(clean_code)

        with open(dst_path, "w") as f:
            f.write(instrumented_code)

        temp_dir = os.path.join(proc_dir, f"temp_{name}")
        ensure_dir(temp_dir)
        temp_c = os.path.join(temp_dir, "runner.c")
        with open(temp_c, "w") as f:
            f.write(instrumented_code)

        exe_file = os.path.join(temp_dir, "runner.out")
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n[DEBUG] Processing file: {filename}")

        if not compile_c(temp_c, exe_file):
            counters["c_compile"] += 1
            log_event(logs["c_compile"], "C_COMPILE_FAIL", filename, elapsed)
            shutil.rmtree(temp_dir)
            continue
        
        if not transpile_cxgo(temp_dir):
            counters["cxgo_crash"] += 1
            log_event(logs["cxgo_crash"], "CXGO_FAIL", filename, elapsed)
            shutil.copy(dst_path, crash_dir)
            continue

        go_bin = build_go(temp_dir)
        if not go_bin:
            counters["go_build"] += 1
            log_event(logs["go_build"], "GO_BUILD_FAIL", filename, elapsed)
            shutil.copy(dst_path, diverge_dir)
            continue

        c_out = run_exe(exe_file)
        if c_out is None:
            counters["bad_c_exe"] += 1
            log_event(logs["bad_c_exe"], "C_EXEC_FAIL", filename, elapsed)
            continue

        go_out = run_exe(go_bin)
        if go_out is None:
            counters["bad_go_exe"] += 1
            log_event(logs["bad_go_exe"], "GO_EXEC_FAIL", filename, elapsed)
            shutil.copy(dst_path, diverge_dir)
            continue

        if c_out != go_out:
            counters["diverge"] += 1
            log_event(logs["diverge"], "OUTPUT_DIVERGENCE", filename, elapsed)
            log_to_file(logs["diverge"], f"C: {c_out.strip()} | Go: {go_out.strip()}")
            shutil.copy(dst_path, diverge_dir)
            print(f"[DEBUG] Output mismatch for {filename}")
        else:
            counters["equivalent_translation"] += 1
            print(f"[DEBUG] Output matched for {filename}")

    total_runtime_hours = (datetime.now() - start_time).total_seconds() / 3600
    with open(logs["summary"], "w") as f:
        f.write(f"Campaign ID: {campaign_id}\n")
        f.write(f"Total files processed: {idx+1}\n")
        f.write(f"Total campaign runtime: {total_runtime_hours:.2f} hours\n")
        for key in counters:
            f.write(f"{label_map.get(key, key)}: {counters[key]}\n")

    print(f"\n[INFO] Finished. Summary written to {logs['summary']}")
    print(f"[INFO] Total campaign runtime: {total_runtime_hours:.2f} hours")

if __name__ == "__main__":
    main()
