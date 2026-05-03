# @title 👁️🗨️ Web Monitor for VS Code Process
import time, os, json, re
from pathlib import Path

print("📡 Initializing Cell 24: Live Monitor & Keep-Alive Heartbeat...")

BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
ROOT_SETTING = BASE_DIR / 'internal_settings.json'

if not ROOT_SETTING.exists():
    print("❌ Error: Root configuration missing.")
    import sys; sys.exit(1)

with open(ROOT_SETTING, 'r') as f:
    root_cfg = json.load(f)

task_name = root_cfg['task_name']
last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'

run_id = None
if last_run_file.exists():
    with open(last_run_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        pattern = rf"Section2_TargetPreprocess(?:_TimeMachine)? \| Run_ID: ({re.escape(task_name)}_\d+_\d+) \| Dir: (final_\d+_\d+)"
        for line in reversed(lines):
            match = re.search(pattern, line)
            if match:
                run_id = match.group(1)
                break

if not run_id:
    print(f"❌ Error: Run history not found for {task_name}.")
    import sys; sys.exit(1)

# Correct Path as requested: inference/<run_id>/Live_Sync_<run_id>.log
log_path = BASE_DIR / 'inference' / run_id / f"Live_Sync_{run_id}.log"

print(f"正在监控当前运行的进度 (Run ID: {run_id})...")
print(f"🔗 日志文件路径: {log_path}\n")

if not log_path.exists():
    print("⏳ 正在等待后端演化管线 (Cell 20/21/22) 初始化日志文件...")
    while not log_path.exists():
        time.sleep(2)
    print("✅ 发现日志文件！开始接管输出流...\n")

# Python 原生 tail -f 实现，适配 Colab 输出
with open(log_path, "r", encoding="utf-8") as f:
    f.seek(0, os.SEEK_END)
    while True:
        try:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
            print(line, end="", flush=True)
        except KeyboardInterrupt:
            print("\n🛑 监控已由用户手动停止。")
            break
