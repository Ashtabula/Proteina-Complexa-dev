import os
from datetime import datetime

log_file = 'c:/Code/Structure/Proteina-Complexa-dev/历史工作记录.txt'
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

log_content = f"""
================================================================================
时间: {current_time}
用户 Prompt:
重新review代码， 还是需要一个全局的restart， 这样可以开始一个新的run_id。 现在是不是用run_id来控制项目？ 20， 22， 24的单独restart仍然保留， 但是20,22, 24的restart不重置run_id， 我的观察对么？
读工作历史文档， 我要的不是restart section7， 是把这个变量提到最前面， 彻底restart 整个流程。 因为用户可能用GFP tourial 然后也需要彻底restart。 你就改成 force_restart， 然后赋值给section2的restart变量。 # @markdown Force restart Section 7 completely? (Ignore existing history) force_restart_section_7 = False #@param {{type:"boolean"}}

操作记录:
1. 确认了用户的观察是正确的：run_id 确实作为全局控制项目的主键，并且局部重启功能（如 Cell 20, 22, 24）不会重置 run_id，只清空当前 run_id 的对应数据。
2. 修改了 `Proteina_Complexa_coLab.ipynb`：
   - **Cell 3 (Dashboard):** 移除了 `force_restart_section_7` 变量，在 `Time Machine / Global Resume` 模块下新增了全局级别的 `force_restart` 变量（勾选框形式），将其提到了更靠前、符合全局语义的位置。
   - 更新了 UI 参数持久化逻辑（`write_settings_to_disk`），保存 `force_restart` 状态而非旧变量。
   - **Cell 11 (Section 2 - Target Preprocess):** 修改了原本判断历史存档的逻辑，将原本隐式的 `force_restart_task` 替换为从 UI 获取的 `force_restart`。当检测到 `force_restart=True` 时，代码会跳过历史检查并生成全新的 `run_id` 和对应文件夹，实现真正的全局重新开始。
   - **Cell 17/23/25:** 将残留的 `force_restart_section_7` 变量引用均替换为 `force_restart`，以保持变量命名的一致性和逻辑正确性。
3. 更新了本地 `历史工作记录.txt` 记录。
"""

with open(log_file, 'a', encoding='utf-8') as f:
    f.write(log_content)
