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

LIVE_LOG_DIR = BASE_DIR / 'inference' / run_id
LIVE_LOG_DIR.mkdir(parents=True, exist_ok=True)
LIVE_LOG_FILE = LIVE_LOG_DIR / f"Live_Sync_{run_id}.log"

def sync_log(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LIVE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

ISOLATED_SETTING = final_dir / 'internal_settings.json'

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)
target_chains = cfg['target_chains']
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))

generation_batches_per_ev = int(root_cfg.get('generation_batches_per_ev', 6))
base_batch_size = 8

print(f"⚙️ Evolution Configured: {generation_batches_per_ev} batches × {base_batch_size} designs per iteration.")

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

GEOMETRIC_MANIFEST = final_dir / "Geometric_Islands_Manifest.json"
GLOBAL_RANKED_FILE = final_dir / "Global_Ranked_Hotspots.json"
GLOBAL_PAE_FILE = final_dir / "Global_Hotspot_PAE_Ranking.json"

with open(GEOMETRIC_MANIFEST, 'r') as f: geo_data = json.load(f)
base_hotspots = geo_data.get("base_hotspots", [])

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

SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"
ordered_natural_resis = []
with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            ordered_natural_resis.append(line[22:26].strip())

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
                    if atom_name.startswith("H"): continue
                    chain, resi = line[21], line[22:26].strip()
                    coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])

                    if chain == target_chain:
                        if resi not in af2_target_atoms: af2_target_atoms[resi] = []
                        af2_target_atoms[resi].append(coord)
                        if atom_name == "CA":
                            try: target_plddts[resi] = float(line[60:66].strip())
                            except: target_plddts[resi] = 50.0
                    else:
                        if resi not in af2_binder_atoms: af2_binder_atoms[resi] = []
                        af2_binder_atoms[resi].append(coord)

        # Flatten binder atoms for KDTree
        b_rep = [coord for atoms in af2_binder_atoms.values() for coord in atoms]
        if not b_rep or not af2_target_atoms: continue
        
        b_tree = KDTree(b_rep)
        for nat_rid in natural_order_list:
            if nat_rid not in af2_target_atoms: continue
            
            min_dist = 999.0
            for coord in af2_target_atoms[nat_rid]:
                dists, _ = b_tree.query(coord, k=1)
                if dists < min_dist:
                    min_dist = dists
            
            plddt = target_plddts.get(nat_rid, 0.0)
            if plddt >= 70.0:  # RAISED THRESHOLD to filter spaghetti
                if min_dist < 2.5:
                    consensus[nat_rid] += -2.0 * (plddt / 100.0) # Steric Clash Penalty
                else:
                    gaussian_score = np.exp(-((min_dist - 3.8)**2) / (2 * 1.5**2))
                    consensus[nat_rid] += gaussian_score * (plddt / 100.0)
    return consensus

iteration = 1
best_ipsae = -999.0
best_active = []
kept_core_8 = []
cooldown_dict = {} # The new "Amnesia" mechanism replacing tested_history_set

if TRAJECTORY_CSV.exists() and not force_restart:
    df_traj = pd.read_csv(TRAJECTORY_CSV)
    if not df_traj.empty:
        last_row = df_traj.iloc[-1]
        iteration = int(last_row['Iteration']) + 1
        last_hotspots_str = str(last_row['Current_Hotspots'])
        active_hotspots = last_hotspots_str.split(',') if pd.notna(last_hotspots_str) else []

        details = str(last_row['Details'])
        if "Add:" in details:
            added_str = details.split("Add:")[-1].strip()
        elif "Swapped out bad candidates for:" in details:
            added_str = details.split("Swapped out bad candidates for:")[-1].strip()
        else:
            added_str = ""
            
        added_list = [x.strip() for x in added_str.split(',')] if added_str else []
        kept_core_8 = [x for x in active_hotspots if x not in added_list]

        valid_scores = pd.to_numeric(df_traj['ipSAE'], errors='coerce').dropna()
        if not valid_scores.empty:
            best_ipsae = float(valid_scores.max())
            best_idx = valid_scores.idxmax()
            if best_idx > 0:
                best_active = str(df_traj.loc[best_idx - 1, 'Current_Hotspots']).split(',')
            else:
                initial_size = min(10, len(master_pool))
                best_active = master_pool[:initial_size]

        # Rebuild Cooldown Dict with 0 cooldown for all previously tested items
        # so they immediately return to the pool
        initial_size = min(10, len(master_pool))
        for r in master_pool[:initial_size]:
            if r not in active_hotspots: cooldown_dict[r] = 0
        for hs_str in df_traj['Current_Hotspots'].dropna():
            for r in str(hs_str).split(','):
                if r not in active_hotspots: cooldown_dict[r] = 0

        msg = f"♻️ Resumed Global Evolution from Iteration {iteration} (Historical Best ipSAE: {best_ipsae:.4f})"
        print(msg)
        sync_log(msg)
    else:
        initial_size = min(10, len(master_pool))
        active_hotspots = master_pool[:initial_size]
else:
    initial_size = min(10, len(master_pool))
    active_hotspots = master_pool[:initial_size]

# Rebuild remaining_pool from master_pool minus active and cooldown items
remaining_pool = [r for r in master_pool if r not in active_hotspots and r not in cooldown_dict]

display(HTML(f"""
<div style='background: #e6f2ff; padding: 15px; border-radius: 8px; border-left: 6px solid #0056b3;'>
    <h3 style='margin-top:0; color: #004085;'>🌍 Global Evolution Initialized / Resumed</h3>
    <p><b>Total Candidates left in Substitute Pool:</b> {len(remaining_pool)}</p>
    <p><b>Current Top Lineup:</b> <code style='color: #d63384;'>{','.join(active_hotspots)}</code></p>
</div>
"""))

while True:
    # 🌟 Cooldown Expiration Mechanism
    for r in list(cooldown_dict.keys()):
        cooldown_dict[r] -= 1
        if cooldown_dict[r] <= 0:
            del cooldown_dict[r]
            if r not in active_hotspots and r not in remaining_pool:
                remaining_pool.append(r)
                msg = f"🧊 Cooldown expired for {r}. Returned to substitute pool."
                print(msg)
                sync_log(msg)

    display(HTML(f"<hr><h4 style='color: #8B008B;'>🔄 Iteration {iteration}</h4><p><b>Evaluating Active Hotspots:</b> {','.join(active_hotspots)}</p>"))
    sync_log(f"🔄 Iteration {iteration} | Active Hotspots: {','.join(active_hotspots)}")

    if yaml_path.exists():
        with open(yaml_path, 'r') as f: yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f: yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    iteration_all_results = []

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
    sync_log(f"📊 Iteration {iteration} Max ipSAE: {current_ipsae:.4f}")

    # ==========================================
    # 🧬 EVOLUTION LOGIC ROUTING WITH S.A.
    # ==========================================
    accepted_sa = False
    if current_ipsae < best_ipsae:
        temp = max(0.01, 0.1 * (0.85 ** iteration))
        acceptance_prob = np.exp((current_ipsae - best_ipsae) / temp)
        if random.random() < acceptance_prob:
            accepted_sa = True
            msg = f"🔥 SA Accepted Degraded State: {current_ipsae:.4f} < {best_ipsae:.4f} (Prob: {acceptance_prob:.2%}, T: {temp:.4f})"
            print(msg)
            sync_log(msg)
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},SA_ACCEPTED,\"Degraded but accepted\",\"{','.join(active_hotspots)}\"\n")

    if current_ipsae >= best_ipsae or accepted_sa:
        if current_ipsae >= best_ipsae:
            best_ipsae = current_ipsae
            best_active = list(active_hotspots)

        print(f"🧬 Evaluating Consensus Footprint for Top 3 structures...")
        scores = calculate_consensus_contributions(top_3_pdbs, target_chains, ordered_natural_resis)

        active_sorted = sorted(active_hotspots, key=lambda x: scores.get(x, 0), reverse=True)

        if len(active_sorted) > 2:
            kept_core_8 = active_sorted[:-2]
            dropped_list = active_sorted[-2:]
            dropped_str = ','.join(dropped_list)
            # Add to cooldown dict instead of permanent blacklist
            for d in dropped_list:
                cooldown_dict[d] = 5
        else:
            kept_core_8 = active_sorted
            dropped_str = "None"

        print(f"✂️ Dropped lowest contributing: {dropped_str} (Sent to Cooldown)")

        if not remaining_pool:
            msg = "🛑 CONVERGED: Pool exhausted. Peak performance achieved."
            print(msg)
            sync_log(msg)
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},CONVERGED_SUCCESS,Pool Exhausted,\"{','.join(best_active)}\"\n")
            break

        added = remaining_pool[:2]
        remaining_pool = remaining_pool[2:] 

        active_hotspots = kept_core_8 + added
        active_hotspots = sorted(list(set(active_hotspots)), key=lambda x: int(re.sub(r'\D', '', x)))

        msg = f"➕ Added next best candidates from pool: {','.join(added)}"
        print(msg)
        sync_log(msg)
        if not accepted_sa:
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},EVOLVED,\"Drop: {dropped_str} | Add: {','.join(added)}\",\"{','.join(active_hotspots)}\"\n")

    else:
        msg = "📉 Performance degraded. Discarding the last additions."
        print(msg)
        sync_log(msg)

        if not remaining_pool:
            msg = f"🛑 CONVERGED: All combinations exhausted. Finalizing at ipSAE {best_ipsae:.4f}"
            print(msg)
            sync_log(msg)
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},CONVERGED_DEGRADED,Reverted to best state,\"{','.join(best_active)}\"\n")
            break

        added = remaining_pool[:2]
        remaining_pool = remaining_pool[2:]

        active_hotspots = kept_core_8 + added
        active_hotspots = sorted(list(set(active_hotspots)), key=lambda x: int(re.sub(r'\D', '', x)))

        msg = f"🔀 Retrying core with next alternative additions: {','.join(added)}"
        print(msg)
        sync_log(msg)
        with open(TRAJECTORY_CSV, 'a') as f:
            f.write(f"{iteration},{current_ipsae:.4f},ROLLBACK_RETRY,\"Swapped out bad candidates for: {','.join(added)}\",\"{','.join(active_hotspots)}\"\n")

    iteration += 1

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
