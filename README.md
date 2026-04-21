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

**🎯 热点与孤岛扩展表面靶向 (Hotspot & Surface Patch Expansion)**
在复杂靶点的演化循环中（如 Cell 20 Deep Greedy Convergence Loop），生成的 Target 并不是简单堆叠。针对我们找到的各种卫星孤岛（Islands），系统会寻找其方圆 6Å 的附属接触面。
此步骤**严格引入了 HSE (Half-Sphere Exposure) 半球暴露校验算法**。系统仅将真实处在 6Å 半径空间内、且 `forward_neighbors < 12` 的**“真实表面氨基酸”**抽提出来作为生成模型的 Binder Target，以此过滤掉无意义的深层掩埋位点。
同时这种抽提与用户显式指定的 Core Hotspots（核心热点）彻底隔离，防止相互混淆，使得系统能够在目标表面的边缘寻找结合能力更强的周边位点以进行进化，极大提升后期突变融合的有效性。

**🌌 保持多样性的束搜索多分支演化 (Diversity-Preserving Beam Search)**
为了解决传统贪心算法在每代演化后将所有不同构象靶点强行融合进“全局热点名单”，导致生成相互矛盾的四不像目标的痛点，我们引入了 Diversity-Preserving Beam Search 机制：
1. **按结合构象聚类 (Clustering by Footprint)**: 忽略整体打分，仅提取实际抱住的靶点氨基酸集合（接触热点），用相似度算法将设计划分为不同结合构象簇。
2. **选出聚类冠军 (Select Cluster Champions)**: 在每一个簇中基于局部综合打分挑选“头狼”。
3. **基于 PAE 的分支演化 (Evolve Lineup by PAE)**: 抛弃全局统一名单，通过 PAE 矩阵和距离动态为每一只“头狼”量身定制剔除差位点、增补高潜位点的独立下一代演化路线。
4. **多分支并行与末位淘汰 (Compare & Prune)**: 分支独立生成后代，基于各分支后代的平均分进行末位淘汰或调整算力批次，实现多路线完美进化闭环。

**🛡️ 工业级容错：状态控制模块 (State Control & True Resume)**
为了支撑多分支演化管线（可能耗时数十小时甚至数天），我们在演化引擎内部署了状态拦截器：
- **Absolute Memory (绝对记忆黑名单)**: 读取历史记录中所有测试过的 `active_hotspots` 并将其锁入 `tested_history_set`。重启时绝对不会让模型将宝贵的算力浪费在验证过的无效氨基酸上，避免陷入死循环。
- **True Resume (多分支现场无缝恢复)**: 当 `force_restart_evolution = False` 时，系统自动读取 CSV，通过定位 `last_iteration` 精准重构宕机前一刻的战场形态（包括存活的 Lineups 及名单配置），实现多分支架构的断点续传。
- **Auto-Fallback (静默退回机制)**: 即使设置了非强制重开，如果系统未能找到合法的历史记录档案，将极其丝滑地自动 fallback 回“全新启动 (Fresh Start)”模式，不会触发任何报错中断。

**🧭 边缘拓扑演化引擎 (Spatial Edge Expansion Evolution)**
基于“前沿推进算法 (Advancing Front Method)”解决单纯依赖全局 PAE 排序导致的多肽构象撕裂盲区：
1. **定义核心与外缘表面 (Define Core & Surface Perimeter)**: 绝对锚定 Core Hotspots 不变，像雷达一样找出紧贴其外围的表面残基作为“外缘锚点 (Edge Anchors)”。
2. **基于锚点的空间过滤 (Anchor-based Spatial Filtering)**: 引入 KDTree 进行三维空间检索，强制筛选距离锚点在物理阈值 (如 15Å) 内的表面氨基酸，构建局部专属专属替补池。
3. **局部深度演化与收敛 (Local Evolution)**: 在每个专属池内执行小步快跑的收敛演化 (Add 2 -> Generate -> Evaluate -> Prune)，保证每次长出的多肽结构在空间上绝对连续不断裂。
4. **全局去重与 JSON 树状存储**: 彻底告别一维表格，每次演化测试后的所有残基从全局池抹除（防吃回头草），并将所有多分支演化路线记录至结构严密的 `evolution_tree.json` 演化树中以支持定点断点续传。

