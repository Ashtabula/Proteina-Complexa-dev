# Cell_24_Live_Monitor.py
# ==============================================================================
# 📡 DUAL-CHANNEL LOGGER MONITOR (Web Keep-Alive)
# ==============================================================================
# Description:
# 终极自适应探针。自动轮询最新的 run_id，无缝切换日志，彻底规避 FileNotFoundError。
# ==============================================================================

import time, os, json, re
from pathlib import Path

print("📡 正在启动自适应 Live Monitor 探针 (防断连模式)...")

BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
ROOT_SETTING = BASE_DIR / 'internal_settings.json'
last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'
inference_dir = BASE_DIR / 'inference'

def get_latest_run_id():
    """动态解析最新的 Run ID"""
    if not ROOT_SETTING.exists(): return None
    try:
        with open(ROOT_SETTING, 'r') as f:
            task_name = json.load(f).get('task_name', '')
        if not last_run_file.exists(): return None
        
        with open(last_run_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            pattern = rf"Section2_TargetPreprocess(?:_TimeMachine)? \| Run_ID: ({re.escape(task_name)}_\d+_\d+)"
            for line in reversed(lines):
                match = re.search(pattern, line)
                if match:
                    return match.group(1)
    except Exception as e:
        return None
    return None

current_run_id = None
current_log_path = None
f_handle = None

try:
    while True:
        # 1. 动态获取当前最新的 run_id
        latest_run_id = get_latest_run_id()
        
        # 2. 如果发生了 Run_ID 的切换（例如开启了新的一轮任务）
        if latest_run_id and latest_run_id != current_run_id:
            if f_handle:
                f_handle.close()
                f_handle = None
            current_run_id = latest_run_id
            current_log_path = inference_dir / current_run_id / f"Live_Sync_{current_run_id}.log"
            print(f"\\n🔄 [探针检测到环境更新] 发现最新的执行任务: {current_run_id}")
            print(f"🔗 正在对齐新日志流: {current_log_path}\\n")
            print(f"\n🔄 [探针检测到环境更新] 发现最新的执行任务: {current_run_id}")
            print(f"🔗 正在对齐新日志流: {current_log_path}\n")

        # 3. 稳健等待：如果还没找到 run_id，或者 log_path 还没在硬盘上物理生成，安全挂起
        if not current_log_path or not current_log_path.exists():
            time.sleep(2)
            continue
            
        # 4. 首次打开文件，确保用户不丢失上下文
        if f_handle is None:
            f_handle = open(current_log_path, "r", encoding="utf-8")
            print("✅ 成功接入数据流！开始实时广播 (同时维持心跳)：\n")

        # 5. 读取新的一行
        line = f_handle.readline()
        if not line:
            # 维持 Colab 虚拟机的心跳保活
            time.sleep(1)
            continue
            
        print(line, end="", flush=True)

except KeyboardInterrupt:
    if f_handle: f_handle.close()
    print("\\n🛑 监控已由用户手动停止。")
