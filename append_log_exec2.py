import os

log_path = '/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/历史工作记录.txt'

log_append = """
### 2026-05-03 (双向日志路径修复与自动追踪 ID 轮次)
- **Time/时间**: 2026-05-03T08:59:00-04:00 (Local)
- **Prompt/提示词指令**: 
  > 检查代码，是否cell20, 22,24都加入了这一功能， 心跳探针... 需要把runid换成current正在跑的id，以监控目前的进度，20，22，24哪个cell在跑，输出如何。 更新代码。
- **Action/执行的操作**:
  1. 修复了 Cell 20, 21, 22 中 `sync_log` 生成的物理位置，使其严格指向 `inference/<run_id>/Live_Sync_<run_id>.log`（若目录不存在则自动创建），修复了之前指向最终 screening_results 目录的小问题。
  2. 对前台挂机监控程序 `Cell_24_Live_Monitor.py` 进行了全自动改造：自动解析项目 `last_runs.txt` 来挂载当前处于 active 状态的最新 `run_id`，去掉了原本硬编码写死的逻辑。现在无论后端后台是跑到 20, 21 还是 22 阶段，前端都能自动找到正在运行的 Run ID，并实现无缝监控输出。
"""

with open(log_path, 'a', encoding='utf-8') as f:
    f.write('\n' + log_append + '\n')

print("Log appended.")
