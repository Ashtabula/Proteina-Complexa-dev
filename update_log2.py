import os
from datetime import datetime

log_file = 'c:/Code/Structure/Proteina-Complexa-dev/历史工作记录.txt'
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

log_content = f"""
================================================================================
时间: {current_time}
用户 Prompt:
不， 检查并重新更改代码， 变量 force_resart 更改全局重新生成run_id变量。  force_restart_section_7 更改 section7的restart status变量，force_restart_evo 更改 cell24 evolution restart 变量。

操作记录:
1. 修正了先前的误解。用户希望**保留**所有的重置变量，分别控制不同层级的复位逻辑，而不是全局替换。
2. 重新修改了 `Proteina_Complexa_coLab.ipynb`：
   - **Cell 3 (Dashboard)**:
     - 恢复了 `force_restart_section_7 = False`，保留在 "Auto-Evolution Target Screening Setting (Section 7)" 选项区下。
     - 确保 `force_restart`（用于控制全局 Run ID，在 Time Machine 下方）和 `force_restart_section_7`、`force_restart_evo` 一同正确保存至底层 JSON 文件。
   - **Cell 17, 23, 25 (Section 7相关)**:
     - 撤销了上一次的错误替换，将这些部分原本被改坏的 `force_restart` 改回为对应的局部重置变量 `force_restart_section_7`。
   - **Cell 11 (Section 2 - Target Preprocess)**:
     - 保持使用 `force_restart` 变量来决定是否生成全新的 `run_id`，从而保证全局维度的彻底重启逻辑依旧有效。
3. 更新了本地 `历史工作记录.txt` 记录。
"""

with open(log_file, 'a', encoding='utf-8') as f:
    f.write(log_content)
