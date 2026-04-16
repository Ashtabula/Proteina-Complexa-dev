import os
import datetime

LOG_FILE = "历史工作记录.txt"

CURRENT_WORK = f"""
========================================
时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
动作: 开始处理更改 Section 0 (配置项) 与 Section 2 (预处理逻辑) 的需求。
详情: 
1. 在 Section 0 中新增变量 `force_restart_task`。
2. 在 Section 0 中移除之前的 `resume_run` 或相关续传配置选项。
3. 在 Section 2 中修改逻辑：默认尝试续传 (找寻最后的 final_xxx_yyy 目录)，只有当 `force_restart_task` 为 True 时，才强制生成全新的时间戳目录并从头开始覆盖式计算。
========================================
"""

def append_to_log():
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(CURRENT_WORK)

if __name__ == "__main__":
    append_to_log()
    print(f"Successfully updated {LOG_FILE}")
