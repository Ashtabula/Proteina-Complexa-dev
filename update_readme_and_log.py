import datetime
import os

readme_path = '/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/README.md'
log_path = '/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/历史工作记录.txt'

readme_append = """
## 📡 双向监控与算力接管架构 (Bidirectional Live Sync)

由于蛋白质演化管线（Cell 20, 22, 24）耗时极长，纯网页端运行容易遭遇浏览器内存溢出或闲置断网回收。本项目引入了基于硬盘 I/O 的**“双向日志同步机制 (Dual-Channel Logger)”**，实现了底层算力与前端显示的代码级物理隔离。

### 核心优势
* **防断连保活**：将主要计算进程转移至本地 VS Code (通过 SSH)，网页端仅作日志拉取，完美规避前端死机。
* **双向透明**：无论从哪个终端拉起进程，另一端均可无缝接管并实时监控进度。
* **极简侵入 (Minimum Invasive)**：采用批次级（Batch-level）节点写入，不劫持底层 `sys.stdout`，不占用模型推理期的系统资源。

### 💻 工作流 A：本地终端计算，网页端监控（推荐）
这是压榨 Colab 算力的最佳实践。
1. **建立穿透**：在 Colab 网页端运行首个 Cell，建立 Cloudflare SSH 隧道。
2. **本地接管**：使用本地 VS Code 通过 SSH 连入 Colab 实例。
3. **启动管线**：在 VS Code 终端内执行核心演化代码（Cell 20/22/24）。由于是独立终端进程，即使关闭浏览器也不会中断。
4. **网页挂机**：在 Colab 网页端新建一个空白代码块，运行日志监控脚本。网页会实时滚动 VS Code 后台的战报，同时充当防止 Colab 闲置回收的心跳探针。

### 🌐 工作流 B：网页端计算，本地终端监控
1. 在 Colab 网页端直接点击运行演化代码（前端 UI 被阻塞）。
2. 在本地 VS Code 终端执行 `tail -f /path/to/Live_Sync_<run_id>.log`。
3. 在本地无缝获取不受浏览器限制的纯文本长日志流。

### 日志文件位置
所有的实时同步日志均储存于对应 Run ID 的工作目录下：
`inference/<run_id>/Live_Sync_<run_id>.log`
"""

log_append = """
### 2026-05-03 (架构文档与双向监控 Prompt 轮次)
- **Time/时间**: 2026-05-03T08:52:00-04:00 (Local)
- **Prompt/提示词指令**: 
  > 这份 README.md 更新和架构 Prompt 总结了我们刚刚敲定的双向监控工作流。你可以直接将它们复制到你的项目仓库和未来的 AI 对话上下文中... 请将以下内容追加到你的项目 README.md 中的“架构说明”或“高级用法”章节... 给 AI / 开发者的系统提示词 (Prompt)... 生成代码，完成后告诉我有什么预期效果。
- **Action/执行的操作**:
  1. 将“双向监控与算力接管架构 (Bidirectional Live Sync)”文档完整追加到了 `README.md` 的末尾。
  2. 根据全局规则，把本次操作和上下文写入了 `历史工作记录.txt` 追踪日志中。
  3. 向用户返回了针对后续 AI 对话上下文的提示词（Prompt）的效果预期。
"""

# Append to README.md
with open(readme_path, 'a', encoding='utf-8') as f:
    f.write('\n' + readme_append + '\n')

# Append to 历史工作记录.txt
with open(log_path, 'a', encoding='utf-8') as f:
    f.write('\n' + log_append + '\n')

print("Files updated successfully.")
