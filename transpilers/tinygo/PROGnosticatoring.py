import os
import sys
import shutil
import subprocess
import re
from datetime import datetime, timedelta

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def log_to_file(path, message):
    with open(path, "a") as f:
        f.write(message + "\n")

def has_main_function(code):
    return re.search(r"\bfunc\s+main\s*\(", code) is not None


def instrument_go(code):
    if has_main_function(code):
        return code
    return (
        f"{code}\n\n"
        "   func main() {\n"
        "   res := func1()\n"
        "   fmt.Println(res)\n"
        "}\n"
    )

def build_go(temp_dir):
    try:
        #subprocess.check_output("go mod init my_module", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=5)
        #subprocess.check_output("go mod tidy", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=5)
        subprocess.check_output("go build -o runner_go runner.go", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=10)
        #print("[DEBUG] Go build succeeded")
        return os.path.join(temp_dir, "runner_go")
    except subprocess.TimeoutExpired:
        #print("[DEBUG] Go build timed out")
        return None
    except subprocess.CalledProcessError as e:
        #print("[DEBUG] Go build failed with error:\n", e.output.decode())
        return None

def build_tinygo(temp_dir):
    try:
        subprocess.check_output("tinygo build -target wasi -o runner.wasm runner.go", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=10)
        #print("[DEBUG] TinyGo build (WASM) succeeded")
        return os.path.join(temp_dir, "runner.wasm")
    except subprocess.TimeoutExpired:
        #print("[DEBUG] TinyGo build (WASM) timed out")
        return None
    except subprocess.CalledProcessError as e:
        #print("[DEBUG] TinyGo build failed with error:\n", e.output.decode())
        return None

def run_binary(binary_path, cwd=None):
    try:
        output = subprocess.check_output(binary_path, shell=True, stderr=subprocess.STDOUT, timeout=5, cwd=cwd)
        return output.decode("utf-8").strip()
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError:
        return None

def run_wasm(wasm_path, cwd):
    try:
        output = subprocess.check_output("wasmtime runner.wasm", shell=True, stderr=subprocess.STDOUT, timeout=5, cwd=cwd)
        return output.decode("utf-8").strip()
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError:
        return None

if __name__ == "__main__":
    input_folder, campaign_id = sys.argv[1], sys.argv[2]

    base_dir = f"campaign_{campaign_id}"
    proc_dir = os.path.join(base_dir, "processing")
    crash_dir = os.path.join(base_dir, "tinygo_crashes")
    diverge_dir = os.path.join(base_dir, "tinygo_divergence")

    for path in [base_dir, proc_dir, crash_dir, diverge_dir]:
        ensure_dir(path)

    logs = {
        "Go_build": os.path.join(base_dir, "log_go_build_failure.txt"),
        "TinyGo_build": os.path.join(base_dir, "log_tinygo_build_failure.txt"),
        "bad_go_exe": os.path.join(base_dir, "log_bad_Go_exe.txt"),
        "wasm_crash": os.path.join(base_dir, "log_wasm_crash.txt"),
        "diverge": os.path.join(base_dir, "log_diverge_output.txt"),
        "summary": os.path.join(base_dir, "summary.txt")
    }

    label_map = {
        "Go_build": "Go build failure",
        "TinyGo_build": "TinyGo build failure",
        "bad_go_exe": "Bad Go exe",
        "wasm_crash": "WASM runtime failure",
        "diverge": "Divergence",
        "equivalent_translation": "Perfect match between Go and WASM"
    }

    counters = {k: 0 for k in logs if k != "summary"}
    counters["equivalent_translation"] = 0

    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)
    all_files = sorted([f for f in os.listdir(input_folder) if f.endswith(".go")])

    for go_file in all_files:
        go_path = os.path.join(input_folder, go_file)
        temp_name = f"temp_{go_file[:-3]}"
        temp_dir = os.path.join(proc_dir, temp_name)
        ensure_dir(temp_dir)

        runner_go_path = os.path.join(temp_dir, "runner.go")
        shutil.copy(go_path, runner_go_path)

        with open(runner_go_path, "r") as f:
            raw_code = f.read()
        instrumented_code = instrument_go(raw_code)
        with open(runner_go_path, "w") as f:
            f.write(instrumented_code)

        #print(f"[DEBUG] Processing {go_file}")
        go_binary = build_go(temp_dir)

        if not go_binary:
            log_to_file(logs["Go_build"], go_file)
            #print(f"[DEBUG] Logged Go build failure for {go_file}")
            counters["Go_build"] += 1
            continue

        wasm_binary = build_tinygo(temp_dir)
        if not wasm_binary:
            log_to_file(logs["TinyGo_build"], go_file)
            #print(f"[DEBUG] Logged TinyGo (WASM) build failure for {go_file}")
            counters["TinyGo_build"] += 1
            continue

        go_out = run_binary(f"./runner_go", cwd=temp_dir)
        if go_out is None:
            log_to_file(logs["bad_go_exe"], go_file)
            #print(f"[DEBUG] Logged bad Go execution for {go_file}")
            counters["bad_go_exe"] += 1
            continue

        wasm_out = run_wasm(wasm_binary, cwd=temp_dir)
        if wasm_out is None:
            log_to_file(logs["wasm_crash"], f"{go_file} - WASM runtime error")
            #print(f"[DEBUG] Failed to execute WASM binary for {go_file}")
            counters["wasm_crash"] += 1
            continue

        if go_out != wasm_out:
            log_to_file(logs["diverge"], f"{go_file}\nGo: {go_out}\nWASM: {wasm_out}\n")
            #print(f"[DEBUG] Output mismatch for {go_file}, logged divergence")
            counters["diverge"] += 1
        else:
            #print(f"[DEBUG] Outputs match for {go_file}, Go and WASM are consistent")
            counters["equivalent_translation"] += 1

    with open(logs["summary"], "w") as f:
        for k, v in counters.items():
            f.write(f"{label_map.get(k, k)}: {v}\n")

    print("[DEBUG] Campaign completed.")
