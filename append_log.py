import datetime
log_entry = f'''
=========================================
Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Prompt Details: 另外， 不是一个batch输出8个么， 怎么一个batch就输出了36个？我知道设置是一个batch36个，但是系统只输出了8个。 另外， 把每次踢掉2个这个大循环的名字改叫iterate x， 以避免误解 (batch n ->  round x, x*n=48 here -> evolve iterate y)
Actions Taken:
1. 修改了 coLab/Proteina_Complexa_coLab.ipynb 中的 Section 6 循环名：
   - 将原来导致混淆的 `Evolution Generation [Round X]: N/48 designs` 改为了 `Evolution Generation [Iterate X - Round Y]: N/48 designs`。
   - 大循环也就是热点演化的周期（每攒够 48 个设计演化一次）被改名为 `Iterate`（迭代）。
   - 小循环也就是生成每个批次的过程被改名为 `Round`（轮次）。所以控制台现在的输出看起来会是：`Evolution Generation [Iterate 1 - Round 1]: 0/48` 接着是 `[Iterate 1 - Round 2]: 8/48` 等。
2. 修复了 Design 生成数量统计（“明明只有8个却增加了36个”的问题）：
   - 将强行每次给 `designs_in_current_iterate` 直接加上 `generation_batch_size` (36) 的错误逻辑修改为：实际解析得到多少个有效 PDB CSV 报告（`len(batch_designs)`），计数器就真正增加多少。现在进度条能精准匹配因为内存或配置限制导致单个批次实际输出量不足 36 的情况。
'''
with open('/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/历史工作记录.txt', 'a', encoding='utf-8') as f:
    f.write(log_entry)
