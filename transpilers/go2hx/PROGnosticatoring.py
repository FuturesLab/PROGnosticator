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
        subprocess.check_output("go build -o runner_go runner.go", shell=True, cwd=temp_dir, stderr=subprocess.STDOUT, timeout=5)
        #print("[DEBUG] Go build succeeded")
        return os.path.join(temp_dir, "runner_go")
    except subprocess.TimeoutExpired:
        #print("[DEBUG] Go build timed out")
        return None
    except subprocess.CalledProcessError as e:
        #print("[DEBUG] Go build failed with error:\n", e.output.decode())
        return None

def run_binary(binary_path, cwd=None):
    try:
        output = subprocess.check_output(binary_path, shell=True, stderr=subprocess.STDOUT, timeout=5, cwd=cwd)
        return output.decode("utf-8").strip()
    except subprocess.TimeoutExpired:
        #print(f"[DEBUG] Running binary {binary_path} timed out")
        return None
    except subprocess.CalledProcessError as e:
        #print(f"[DEBUG] Running binary {binary_path} failed with error:\n", e.output.decode())
        return None

def translate_go2hx(temp_dir):
    try:
        subprocess.check_output("haxelib run go2hx runner.go > /dev/null 2>&1",
                                shell=True, cwd=temp_dir,
                                stderr=subprocess.STDOUT, timeout=15)
        
        golibs_path = os.path.join(temp_dir, "golibs")
        if not os.path.isdir(golibs_path):
            return False
        return True
    except subprocess.TimeoutExpired:
        return False
    except subprocess.CalledProcessError:
        return False

def run_haxe(golibs_dir):
    try:
        output = subprocess.check_output("haxe --main _internal.Runner -lib go2hx --interp", shell=True, cwd=golibs_dir, stderr=subprocess.STDOUT, timeout=10)
        return output.decode("utf-8").strip()
    except subprocess.TimeoutExpired:
        #print("[DEBUG] Running Haxe binary timed out")
        return None
    except subprocess.CalledProcessError as e:
        #print("[DEBUG] Running Haxe binary failed with error:\n", e.output.decode())
        return None

if __name__ == "__main__":
    input_folder, campaign_id = sys.argv[1], sys.argv[2]

    base_dir = f"campaign_{campaign_id}"
    proc_dir = os.path.join(base_dir, "processing")
    crash_dir = os.path.join(base_dir, "go2hx_crashes")
    diverge_dir = os.path.join(base_dir, "go2hx_divergence")

    for path in [base_dir, proc_dir, crash_dir, diverge_dir]:
        ensure_dir(path)

    logs = {
        "Go_build": os.path.join(base_dir, "log_go_build_failure.txt"),
        "go2hx_crash": os.path.join(base_dir, "log_go2hx_crashes.txt"),
        "bad_go_exe": os.path.join(base_dir, "log_bad_Go_exe.txt"),
        "bad_haxe_exe": os.path.join(base_dir, "log_bad_go_exe.txt"),
        "diverge": os.path.join(base_dir, "log_diverge_output.txt"),
        "summary": os.path.join(base_dir, "summary.txt")
    }

    label_map = {
        "go_build": "Go build failure",
        "go2hx_crash": "Go2Hx crash",
        "bad_c_exe": "Bad C exe",
        "bad_go_exe": "Bad Go exe",
        "diverge": "Divergence",
        "equivalent_translation": "Perfect translation"
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

        # Read, instrument, and overwrite
        with open(runner_go_path, "r") as f:
            original_code = f.read()

        instrumented_code = instrument_go(original_code)

        with open(runner_go_path, "w") as f:
            f.write(instrumented_code)

        #print(f"[DEBUG] Processing {go_file}")
        go_binary = build_go(temp_dir)

        if not go_binary:
            log_to_file(logs["Go_build"], go_file)
            #print(f"[DEBUG] Logged Go build failure for {go_file}")
            counters["Go_build"] += 1
            continue

        if not translate_go2hx(temp_dir):
            log_to_file(logs["go2hx_crash"], go_file)
            #print(f"[DEBUG] Logged Go2Hx crash for {go_file}")
            counters["go2hx_crash"] += 1
            continue

        go_out = run_binary(f"./runner_go", cwd=temp_dir)
        if go_out is None:
            log_to_file(logs["bad_go_exe"], go_file)
            #print(f"[DEBUG] Logged bad Go execution for {go_file}")
            counters["bad_go_exe"] += 1
            continue

        haxe_out = run_haxe(os.path.join(temp_dir, "golibs"))
        if haxe_out is None:
            log_to_file(logs["bad_haxe_exe"], go_file)
            #print(f"[DEBUG] Logged bad Haxe execution for {go_file}")
            counters["bad_haxe_exe"] += 1
            continue

        if go_out != haxe_out:
            log_to_file(logs["diverge"], f"{go_file}\nGo: {go_out}\nHaxe: {haxe_out}\n")
            #print(f"[DEBUG] Output mismatch for {go_file}, logged divergence")
            counters["diverge"] += 1
            shutil.copy(go_path, os.path.join(diverge_dir, go_file))
        else:
            #print(f"[DEBUG] Outputs match for {go_file}, translation successful")
            counters["equivalent_translation"] += 1

    with open(logs["summary"], "w") as f:
        for k, v in counters.items():
            f.write(f"{label_map.get(k, k)}: {v}\n")

    print("[DEBUG] Campaign completed.")