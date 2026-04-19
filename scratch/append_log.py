import sys

log_file = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/历史工作记录.txt"
new_entry = """
### 2026-04-19 (Bug Fix 轮次 - Deprecation Warning)
- **Time/时间**: 2026-04-19T18:47:00-04:00 (Local)
- **Prompt/提示词指令**: 
  > /usr/local/lib/python3.12/dist-packages/jupyter_client/session.py:203: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
- **Action/执行的操作**:
  1. 分析发现这是运行环境底层 `jupyter_client` (或依赖库) 因 Python 3.12 升级引发的 `DeprecationWarning`。
  2. 在 `Proteina_Complexa_coLab.ipynb` 的 Section 0 全局配置初始化模块顶部，注入了 `warnings.filterwarnings` 来全局屏蔽此类警告，以保持执行日志输出的清爽、避免干扰开发视野。
"""

with open(log_file, "a", encoding="utf-8") as f:
    f.write(new_entry)
