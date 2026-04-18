# Proteina-Complexa-dev

## 全局历史断点追踪档案 (history_run.csv) 机制

**机制介绍**：
为了实现更加广阔和强壮的断点续传功能，我们在代码体系中引入了 `history_run.csv` 全局断点追踪文件。
该功能主要作用于程序的启动阶段（如 Section 4 / Cell 4），它负责提取并组装具有上下游连续性的会话状态。

**工作流程**：
1. 程序会自动读取上次运行的 `last_runs.txt` 状态信息（包括时间、Run ID 等）。
2. 将该信息与当前的物理核心参数（如 Task Name、筛选使用的 Program Section、多肽长度以及输入的 Hotspot 等）合并。
3. 统一将这些关键字段追加写入 `screening_results/history_run.csv`。
4. **预留接口**：对于下游演化和生成的特异性状态（如 Screening Islands, Screening Cycles, Top Max ipSAE 等），在初始化阶段（Cell 4）将留空作为占位符，为下游模块（如 Section 7 的每个迭代循环）能够无缝读取并在对应列中注入（Update）动态进度铺平了道路。

**设计目的**：
通过持久化记录一个具有连贯性的全局任务档案，使以后的程序或分析脚本都能基于 `history_run.csv` 完成智能断点续传、筛选进度恢复和数据清洗聚合，避免了多轮迭代中数据上下文的丢失。

**🔮 终极断点续传与时间机器 (Time Machine Resume)**
现在系统支持三种不同的任务启动模式：
1. **指定历史节点续传 (最高优先级)**：在顶部的 Specific_Resume_Run_ID 栏位中填入你想要恢复的历史任务 ID（例如：AR_LBD_20260418_043148）。系统将自动穿越回该任务节点，调取当时的所有物理参数、热点设置，并接着历史进度继续往下跑。**注意：填入此项后，你在面板下方修改的任何参数都会被忽略，以历史档案为准。**
2. **默认顺延续传 (推荐)**：保持 Specific_Resume_Run_ID 为空，并且不要勾选下方的 orce_restart。系统会自动寻找上一次最近运行的任务并继续。
3. **强制重新开始**：保持 Specific_Resume_Run_ID 为空，并勾选你需要重置的 orce_restart 模块。系统将开辟全新的文件夹和实验记录。
