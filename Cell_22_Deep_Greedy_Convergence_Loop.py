# Cell_22_Deep_Greedy_Convergence_Loop.py
# ==============================================================================
# 🔥 GLOBAL DEEP GREEDY EVOLUTION PARADIGM (With True Resume)
# ==============================================================================
# Requirements Met:
# - Global Pool Merge: Hardcoded base_hotspots + Global PAE rankings.
# - Initial State: Top 10 strongest amino acids.
# - Evolution Logic: Run -> Evaluate -> Drop worst 2 contributors -> Add next 2 from PAE pool.
# - Stagnation & Convergence: If ipSAE drops, discard the failed 2, keep the core 8,
#   and try the *next* 2 from the pool. Converge when the pool is exhausted.
# - Fault Tolerance & Trajectory: Real-time logging to a Global Trajectory CSV.
# - Consensus Scoring: Distance (<4.5A) + pLDDT (>50) weighting across Top 3 PDBs.
# - True Resume: Absolute memory preservation across kernel crashes (Tested_History_Set).
# ==============================================================================

import os, sys, json, subprocess, time, datetime, re, yaml, random, csv
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import KDTree
from IPython.display import HTML, display

print("🌌 Initiating Cell 22: Global Deep Greedy Convergence Loop...")

BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
ROOT_SETTING = BASE_DIR / 'internal_settings.json'

if not ROOT_SETTING.exists():
    print("❌ Error: Root configuration missing.")
    sys.exit(1)

with open(ROOT_SETTING, 'r') as f:
    root_cfg = json.load(f)

task_name = root_cfg['task_name']
last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'

run_id, target_dir_name = None, None
if last_run_file.exists():
    with open(last_run_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        pattern = rf"Section2_TargetPreprocess(?:_TimeMachine)? \| Run_ID: ({re.escape(task_name)}_\d+_\d+) \| Dir: (final_\d+_\d+)"
        for line in reversed(lines):
            match = re.search(pattern, line)
            if match:
                run_id = match.group(1)
                target_dir_name = match.group(2)
                break

if not run_id:
    print(f"❌ Error: Run history not found for {task_name}.")
    sys.exit(1)

final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name
ISOLATED_SETTING = final_dir / 'internal_settings.json'

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)
target_chains = cfg['target_chains']
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))

# 次数在 section0 已定义 (generation_batches_per_ev)
generation_batches_per_ev = int(root_cfg.get('generation_batches_per_ev', 6))
base_batch_size = 8

print(f"⚙️ Evolution Configured: {generation_batches_per_ev} batches × {base_batch_size} designs per iteration.")

# --- 🌟 SMART RESTART & SESSION IDENTITY (修复了全局时间戳断点记忆) ---
force_restart = bool(root_cfg.get('force_restart_section_7', False))
SESSION_TIMESTAMP = None

if force_restart:
    print("\n🗑️ [COMMAND] Force Restart enabled. Cleaning up previous Global Evolutions...")
    for old_json in final_dir.glob("Global_Converged_Manifest_*.json"): old_json.unlink()
    for old_csv in final_dir.glob("Global_Evolution_Trajectory_*.csv"): old_csv.unlink()
else:
    existing_trajectories = list(final_dir.glob("Global_Evolution_Trajectory_*.csv"))
    if existing_trajectories:
        latest_traj = max(existing_trajectories, key=lambda f: f.stat().st_mtime)
        match = re.search(r"Global_Evolution_Trajectory_(.*)\.csv", latest_traj.name)
        if match:
            SESSION_TIMESTAMP = match.group(1)
            print(f"🔄 True Resume: Re-attaching to historical global evolution session [{SESSION_TIMESTAMP}]")

if not SESSION_TIMESTAMP:
    SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
    print(f"🆕 New Global Evolution Session initialized: [{SESSION_TIMESTAMP}]")

TRAJECTORY_CSV = final_dir / f"Global_Evolution_Trajectory_{SESSION_TIMESTAMP}.csv"
CONVERGED_MANIFEST = final_dir / f"Global_Converged_Manifest_{SESSION_TIMESTAMP}.json"

if not TRAJECTORY_CSV.exists():
    with open(TRAJECTORY_CSV, 'w') as f:
        f.write("Iteration,ipSAE,Action,Details,Current_Hotspots\n")

# --- 🌟 HISTORY CSV LINKING ---
HISTORY_CSV = BASE_DIR / 'screening_results' / 'history_run.csv'
if HISTORY_CSV.exists():
    try:
        updated_rows = []
        with open(HISTORY_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            if "Overall_Data_Link" not in header: header.append("Overall_Data_Link")
            link_idx = header.index("Overall_Data_Link")
            run_id_idx = header.index("Run_ID") if "Run_ID" in header else -1

            updated_rows.append(header)
            for row in reader:
                while len(row) < len(header): row.append("")
                if run_id_idx != -1 and row[run_id_idx] == run_id:
                    new_link = f"[View Global Evolution Log]({TRAJECTORY_CSV.relative_to(BASE_DIR)})"
                    if new_link not in row[link_idx]:
                        row[link_idx] = f"{row[link_idx]} | {new_link}" if str(row[link_idx]).strip() else new_link
                updated_rows.append(row)
        with open(HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(updated_rows)
    except Exception as e: pass

# --- 1. Load Global Data Sources ---
GEOMETRIC_MANIFEST = final_dir / "Geometric_Islands_Manifest.json"
GLOBAL_RANKED_FILE = final_dir / "Global_Ranked_Hotspots.json"
GLOBAL_PAE_FILE = final_dir / "Global_Hotspot_PAE_Ranking.json" # Fallback

with open(GEOMETRIC_MANIFEST, 'r') as f: geo_data = json.load(f)
base_hotspots = geo_data.get("base_hotspots", [])

# --- 2. Construct the Master Candidate Pool ---
# 逻辑：Hardcoded 热点优先级最高，排在最前面。随后根据 PAE 从低到高补齐剩余列表。
master_pool = list(base_hotspots)

if GLOBAL_RANKED_FILE.exists():
    with open(GLOBAL_RANKED_FILE, 'r') as f:
        ranked_data = json.load(f)
        for resi in ranked_data.get("ranked_list", []):
            if resi not in master_pool: master_pool.append(resi)
elif GLOBAL_PAE_FILE.exists():
    with open(GLOBAL_PAE_FILE, 'r') as f:
        global_pae_tracker = json.load(f)
        for resi, pae in global_pae_tracker.items():
            if resi not in master_pool: master_pool.append(resi)

if not master_pool:
    print("❌ Error: Master pool is empty. Please check Cell 20 execution.")
    sys.exit(1)

# --- 3. Biological Sequence Extraction ---
SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"
ordered_natural_resis = []
with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            ordered_natural_resis.append(line[22:26].strip())

# --- Core Loop Utilities ---
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})
yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'

def calculate_consensus_contributions(pdb_paths, target_chain, natural_order_list):
    consensus = {r: 0.0 for r in natural_order_list}
    valid_pdbs = [p for p in pdb_paths if p and Path(p).exists()]
    if not valid_pdbs: return consensus

    for pdb_path in valid_pdbs:
        af2_target_atoms, af2_binder_atoms, target_plddts = {}, {}, {}
        with open(pdb_path, 'r') as f:
            for line in f:
                if line.startswith("ATOM"):
                    atom_name = line[12:16].strip()
                    chain, resi = line[21], line[22:26].strip()
                    coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])

                    if chain == target_chain:
                        if atom_name in ["CA", "CB"]:
                            if resi not in af2_target_atoms: af2_target_atoms[resi] = {}
                            af2_target_atoms[resi][atom_name] = coord
                        if atom_name == "CA":
                            try: target_plddts[resi] = float(line[60:66].strip())
                            except: target_plddts[resi] = 50.0
                    else:
                        if atom_name in ["CA", "CB"]:
                            if resi not in af2_binder_atoms: af2_binder_atoms[resi] = {}
                            af2_binder_atoms[resi][atom_name] = coord

        t_rep = {natural_order_list[i]: af2_target_atoms[af2_rid].get('CB', af2_target_atoms[af2_rid].get('CA'))
                 for i, af2_rid in enumerate(sorted(af2_target_atoms.keys(), key=int)) if i < len(natural_order_list)}
        b_rep = [atoms.get('CB', atoms.get('CA')) for atoms in af2_binder_atoms.values()]

        if not b_rep or not t_rep: continue
        b_tree = KDTree(b_rep)
        for nat_rid, coord in t_rep.items():
            if coord is None: continue
            dists, _ = b_tree.query(coord, k=1)
            if dists < 4.5:
                plddt = target_plddts.get(nat_rid, 0.0)
                if plddt >= 50.0:  # 硬阈值
                    consensus[nat_rid] += (1.0 / (dists + 0.1)) * (plddt / 100.0)
    return consensus

# ==============================================================================
# 🚀 4. THE GLOBAL EVOLUTION ENGINE (具备完整断点记忆的 Drop 2, Add 2)
# ==============================================================================

iteration = 1
best_ipsae = -999.0
best_active = []
kept_core_8 = []
tested_history_set = set() # 记录已经被拉上场测试过的氨基酸，防止重复

# 🌟 核心状态恢复引擎 (Perfect State Recovery)
if TRAJECTORY_CSV.exists() and not force_restart:
    df_traj = pd.read_csv(TRAJECTORY_CSV)
    if not df_traj.empty:
        # 1. 恢复迭代次数
        last_row = df_traj.iloc[-1]
        iteration = int(last_row['Iteration']) + 1

        # 2. 恢复待测试阵容 (接力棒：将最后一行记录的名单作为这一轮的初始阵容)
        last_hotspots_str = str(last_row['Current_Hotspots'])
        active_hotspots = last_hotspots_str.split(',') if pd.notna(last_hotspots_str) else []

        # 3. 🛡️ 完美重构 kept_core_8 (解决 2 个残基退化 Bug)
        # 通过解析最后一步的 Details 动作，剥离出新加入的残基，剩下的自然就是核心 8 个！
        details = str(last_row['Details'])
        if "Add:" in details:
            added_str = details.split("Add:")[-1].strip()
        elif "Swapped out bad candidates for:" in details:
            added_str = details.split("Swapped out bad candidates for:")[-1].strip()
        else:
            added_str = ""
            
        added_list = [x.strip() for x in added_str.split(',')] if added_str else []
        kept_core_8 = [x for x in active_hotspots if x not in added_list]

        # 4. 👑 精准定位历史最高分及对应的 best_active
        valid_scores = pd.to_numeric(df_traj['ipSAE'], errors='coerce').dropna()
        if not valid_scores.empty:
            best_ipsae = float(valid_scores.max())
            best_idx = valid_scores.idxmax()
            
            # 核心逻辑：第 N 行创下的最高分，其实是测试第 N-1 行生成的阵容得来的！
            if best_idx > 0:
                best_active = str(df_traj.loc[best_idx - 1, 'Current_Hotspots']).split(',')
            else:
                # 如果第一行就创下了最高分，说明最高分是初始首发阵容创造的
                initial_size = min(10, len(master_pool))
                best_active = master_pool[:initial_size]

        # 5. 🧱 补齐所有的测试历史黑名单 (包含初代隐藏名单)
        initial_size = min(10, len(master_pool))
        tested_history_set.update(master_pool[:initial_size]) # 补齐初代遗漏
        for hs_str in df_traj['Current_Hotspots'].dropna():
            tested_history_set.update(str(hs_str).split(','))

        print(f"♻️ Resumed Global Evolution from Iteration {iteration} (Historical Best ipSAE: {best_ipsae:.4f})")
        print(f"🛡️ Reconstructed Core-8 Guard: {','.join(kept_core_8)}")
    else:
        # CSV 存在但为空的降级处理
        initial_size = min(10, len(master_pool))
        active_hotspots = master_pool[:initial_size]
        tested_history_set.update(active_hotspots)
else:
    # 全新启动
    initial_size = min(10, len(master_pool))
    active_hotspots = master_pool[:initial_size]
    tested_history_set.update(active_hotspots)

# 重建替补池：Master Pool 减去所有已经测试过的残基
remaining_pool = [r for r in master_pool if r not in tested_history_set]

display(HTML(f"""
<div style='background: #e6f2ff; padding: 15px; border-radius: 8px; border-left: 6px solid #0056b3;'>
    <h3 style='margin-top:0; color: #004085;'>🌍 Global Evolution Initialized / Resumed</h3>
    <p><b>Total Candidates left in Substitute Pool:</b> {len(remaining_pool)}</p>
    <p><b>Current Top Lineup:</b> <code style='color: #d63384;'>{','.join(active_hotspots)}</code></p>
</div>
"""))

while True:
    display(HTML(f"<hr><h4 style='color: #8B008B;'>🔄 Iteration {iteration}</h4><p><b>Evaluating Active Hotspots:</b> {','.join(active_hotspots)}</p>"))

    # 1. 更新 Yaml 注入当前的靶点
    if yaml_path.exists():
        with open(yaml_path, 'r') as f: yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f: yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    iteration_all_results = []

    # 2. 生成批次循环
    for batch_idx in range(1, generation_batches_per_ev + 1):
        run_name = f"GlobalEvo_Iter{iteration}_B{batch_idx}_{SESSION_TIMESTAMP}"
        inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{run_name}'

        dynamic_seed = random.randint(10000, 99999)
        cmd_str = (
            f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={run_name} "
            f"++generation.task_name={task_name} ++generation.num_designs={base_batch_size} "
            f"++generation.dataloader.batch_size={base_batch_size} ++generation.search.max_batch_size={base_batch_size} "
            f"++evaluation.dataloader.batch_size={evaluation_batch_size} ++generation.seed={dynamic_seed} "
            f"++run_filter=True ++run_evaluate=True ++run_analyze=True"
        )

        print(f"   [Batch {batch_idx}/{generation_batches_per_ev}] Generating {base_batch_size} designs... ", flush=True)
        process = subprocess.Popen(
            f"source env.sh && {cmd_str}", env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        for line in process.stdout: print(line, end='', flush=True)
        process.wait()

        valid_csvs = list(inference_dir.rglob('*.csv'))
        if valid_csvs:
            target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
            df = pd.read_csv(target_csv)
            score_col = next((c for c in ['af2folding_max_ipsae', 'max_ipSAE'] if c in df.columns), None)
            if score_col:
                df[score_col] = pd.to_numeric(df[score_col], errors='coerce')
                df = df.dropna(subset=[score_col])
                for _, row in df.nlargest(3, score_col).iterrows():
                    iteration_all_results.append((float(row[score_col]), row.to_dict(), str(inference_dir)))

    # 3. 统计迭代最高分，抓取 Top 3 结构
    iteration_all_results.sort(key=lambda x: x[0], reverse=True)
    current_ipsae = iteration_all_results[0][0] if iteration_all_results else -999.0

    top_3_pdbs = []
    for score, row_dict, inf_dir in iteration_all_results[:3]:
        pdb_raw = row_dict.get('pdb_path', '')
        if pdb_raw:
            cand = Path(inf_dir) / pdb_raw
            if cand.exists(): top_3_pdbs.append(str(cand))

    color = "green" if current_ipsae >= best_ipsae else "red"
    display(HTML(f"<p><b>Score achieved:</b> <span style='color:{color}; font-weight:bold; font-size:16px;'>{current_ipsae:.4f}</span> (Historical Best: {best_ipsae:.4f})</p>"))

    # ==========================================
    # 🧬 EVOLUTION LOGIC ROUTING
    # ==========================================
    if current_ipsae >= best_ipsae and current_ipsae > -900.0:
        # 🌟 突破成功！接受并进化
        best_ipsae = current_ipsae
        best_active = list(active_hotspots)

        print(f"🧬 Evaluating Consensus Footprint for Top 3 structures...")
        scores = calculate_consensus_contributions(top_3_pdbs, target_chains, ordered_natural_resis)

        # 将当前的阵容按贡献度排序
        active_sorted = sorted(active_hotspots, key=lambda x: scores.get(x, 0), reverse=True)

        # 踢出最差的 2 个，保留核心 8 个
        if len(active_sorted) > 2:
            kept_core_8 = active_sorted[:-2]
            dropped_str = ','.join(active_sorted[-2:])
        else:
            kept_core_8 = active_sorted
            dropped_str = "None"

        print(f"✂️ Dropped lowest contributing: {dropped_str}")

        # 如果替补席空了，完美收敛
        if not remaining_pool:
            print("🛑 CONVERGED: Pool exhausted. Peak performance achieved.")
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},CONVERGED_SUCCESS,Pool Exhausted,\"{','.join(best_active)}\"\n")
            break

        # 从替补席提拔 2 个新兵
        added = remaining_pool[:2]
        remaining_pool = remaining_pool[2:] # 替补池缩减
        tested_history_set.update(added)    # 记录已上场

        active_hotspots = kept_core_8 + added
        active_hotspots = sorted(list(set(active_hotspots)), key=lambda x: int(re.sub(r'\D', '', x)))

        print(f"➕ Added next best candidates from pool: {','.join(added)}")
        with open(TRAJECTORY_CSV, 'a') as f:
            f.write(f"{iteration},{current_ipsae:.4f},EVOLVED,\"Drop: {dropped_str} | Add: {','.join(added)}\",\"{','.join(active_hotspots)}\"\n")

    else:
        # 📉 表现倒退！拒绝并平行替换
        print("📉 Performance degraded. Discarding the last additions.")

        # 替补席如果空了，说明所有组合都试过了，直接收敛到之前的最佳状态
        if not remaining_pool:
            print(f"🛑 CONVERGED: All combinations exhausted. Finalizing at ipSAE {best_ipsae:.4f}")
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},CONVERGED_DEGRADED,Reverted to best state,\"{','.join(best_active)}\"\n")
            break

        # 核心逻辑：保持上次的 core_8 不变，直接从剩下的替补池里再抓 2 个新的试试
        added = remaining_pool[:2]
        remaining_pool = remaining_pool[2:]
        tested_history_set.update(added)

        active_hotspots = kept_core_8 + added
        active_hotspots = sorted(list(set(active_hotspots)), key=lambda x: int(re.sub(r'\D', '', x)))

        print(f"🔀 Retrying core with next alternative additions: {','.join(added)}")
        with open(TRAJECTORY_CSV, 'a') as f:
            f.write(f"{iteration},{current_ipsae:.4f},ROLLBACK_RETRY,\"Swapped out bad candidates for: {','.join(added)}\",\"{','.join(active_hotspots)}\"\n")

    iteration += 1

# ==========================================
# 🏆 EXPORT FINAL RESULTS
# ==========================================
display(HTML(f"""
<div style='background: #d4edda; padding: 20px; border-radius: 8px; border-left: 6px solid #28a745; margin-top: 20px;'>
    <h2 style='margin-top:0; color: #155724;'>🏁 Global Evolution Completed</h2>
    <p style='font-size: 18px;'><b>👑 Ultimate Maximum ipSAE:</b> <span style='color:red; font-weight:bold;'>{best_ipsae:.4f}</span></p>
    <p><b>🧬 Final Optimized Anchor Lineup:</b> <code style='font-size: 16px;'>{','.join(best_active)}</code></p>
</div>
"""))

final_checkpoint = {
    "task_name": task_name,
    "final_ipsae": best_ipsae,
    "ultimate_hotspots": best_active,
    "total_iterations_taken": iteration - 1
}

with open(CONVERGED_MANIFEST, 'w') as f:
    json.dump(final_checkpoint, f, indent=4)

print(f"💾 Checkpoint saved to: {CONVERGED_MANIFEST.name}")
print(f"📊 Full Trajectory Audit available in: {TRAJECTORY_CSV.name}")
