import os
import datetime

LOG_FILE = "历史工作记录.txt"

CURRENT_WORK = f"""
========================================
时间: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
动作: 修改并优化了用于生成 Cell 19 和 Cell 20 的 Agent Prompts。
详情: 
1. 明确了 KDTree 的 CA 原子搜索半径要求 (10Å 邻居计数半径，和后续接触算法的 4.5Å 接触半径)。
2. 去除了对生成卫星岛屿数量的硬编码，强调了算法基于环境能包围出多少个物理隔离面就动态生成多少个 (Isl A, B... 直到无处可分)。
3. 根据要求，暂时移除了全局早停 (Early stop) 的设定，强调必须完整遍历整个 JSON 里的所有杂交岛序列。
4. 提供最终英文 Prompt 以便于复制。
========================================
"""

def append_to_log():
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(CURRENT_WORK)

if __name__ == "__main__":
    append_to_log()
    print(f"Successfully updated {LOG_FILE}")
