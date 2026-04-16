import os
import datetime

LOG_FILE = "历史工作记录.txt"

CURRENT_WORK = f"""
========================================
时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
动作: 修改配置逻辑 (Section 0 / Cell 3) 与启动逻辑 (Section 2 / Cell 4b)。
详情: 
1. 通过 Python JSON 解析处理，成功替换了 Notebook 中的 `RESUME_LAST_SESSION`。
2. Section 0 现在最顶端加入了：
   `force_restart_task = False #@param {{type:"boolean"}}`
3. Section 2 现在被改造为：默认继承最近一次对应任务的目录（续传）；但只要勾选了 `force_restart_task = True`，就会绕过校验，从零生成新的环境。
========================================
"""

def append_to_log():
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(CURRENT_WORK)

if __name__ == "__main__":
    append_to_log()
    print(f"Successfully updated {LOG_FILE}")
