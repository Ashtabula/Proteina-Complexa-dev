# Cell_20_Deep_Greedy_Convergence_Loop.py
# Requirements:
# - Load the Hybrid Islands JSON manifest.
# - Sort Hybrid Islands descending by baseline ipSAE score.
# - Iterate through the sorted queue sequentially.
# - For each island, generate 48 designs using complexa design.
# - Greedy Convergence: KDTree (<4.5A) contribution. Drop worst 2 current, add best 2 neo-hotspots found.
# - Termination loop per branch: Rollback if ipSAE drops. If rollback fails, mark converged, log Top 1, move to next.
# - Do NOT global early-stop; process all islands.

import os, sys, json, subprocess, time, datetime, re, shutil
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import KDTree

print("🌌 Initializing Cell 20: Deep Greedy Convergence Loop...")

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
        pattern = rf"Section2_TargetPreprocess \| Run_ID: ({re.escape(task_name)}_\d+_\d+) \| Dir: (final_\d+_\d+)"
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

# --- Bidirectional Live Sync (Dual-Channel Logger) ---
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

# --- 1. Find and Load the Latest Manifest ---
manifests = list(final_dir.glob("Hybrid_Islands_Manifest_*.json"))
if not manifests:
    print(f"❌ Error: No Hybrid Islands Manifest found in {final_dir}. Run Cell 19 first.")
    sys.exit(1)

latest_manifest = max(manifests, key=os.path.getmtime)
with open(latest_manifest, 'r') as f:
    hybrid_islands_data = json.load(f)

print(f"📦 Loaded Manifest: {latest_manifest.name}")

# --- 2. Sort Hybrid Islands (Descending baseline ipSAE) ---
sorted_queue = sorted(
    hybrid_islands_data.items(),
    key=lambda x: x[1].get('baseline_ipsae', 0.0),
    reverse=True
)

print(f"🎯 Scheduled Execution Priority:")
for k, v in sorted_queue:
    print(f"   [{k}] - Baseline ipSAE: {v.get('baseline_ipsae', 0.0):.3f}")

# --- Core Loop Utilities ---
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})
yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'

def calculate_residue_contributions(pdb_path, active_list):
    # KDTree (<4.5A) calculation for both active targets and entire surface
    scores = {}
    if not pdb_path or not Path(pdb_path).exists(): return scores
    
    t_coords, b_coords = {}, []
    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                c, r, x, y, z = line[21], line[22:26].strip(), float(line[30:38]), float(line[38:46]), float(line[46:54])
                if c == target_chains:
                    t_coords[r] = [x, y, z]
                else:
                    b_coords.append([x, y, z])
                    
    if not b_coords: return scores
    b_tree = KDTree(b_coords)
    
    for rid, coord in t_coords.items():
        dists, _ = b_tree.query(coord, k=1)
        if dists < 4.5:
            scores[rid] = 1.0 / (dists + 0.1)
    return scores

# --- 3. Deep Greedy Convergence Loop ---
SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")

for island_name, island_data in sorted_queue:
    print(f"\n==================================================")
    print(f"🔱 Initiating Convergence Loop for {island_name}")
    print(f"==================================================")
    
    active_hotspots = list(island_data['hybrid_hotspots'])
    highest_ipsae_state = 0.0
    stagnation_rollback_state = None
    iteration = 1
    
    while True:
        msg = f"🔄 [{island_name} - Iteration {iteration}] Active Hotspots: {','.join(active_hotspots)}"
        print(f"\n{msg}")
        sync_log(msg)
        run_name = f"ConvergeLoop_{island_name}_Iter{iteration}_{SESSION_TIMESTAMP}"
        
        if yaml_path.exists():
            with open(yaml_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
            yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
            with open(yaml_path, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        cmd_str = (
            f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={run_name} "
            f"++generation.task_name={task_name} ++generation.num_designs=48 "
            f"++generation.dataloader.batch_size=48 ++generation.search.max_batch_size=48 ++evaluation.dataloader.batch_size={evaluation_batch_size} "
            f"++run_filter=True ++run_evaluate=True ++evaluate.num_recycles=1 ++evaluate.pad_to_max_length=True ++evaluate.use_msa=False ++evaluate.msa_mode=single_sequence ++run_analyze=True "
            f"++evaluate.save_pae=True ++evaluate.dump_json=True ++evaluate.save_outputs=True"
        )

        process = subprocess.Popen(
            f"source env.sh && {cmd_str}",
            env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        for line in process.stdout: print(line, end='', flush=True)
        process.wait()

        # Parse output max ipSAE
        inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{run_name}'
        valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]
        
        current_max_score = 0.0
        top_pdb = None
        
        if valid_csvs:
            target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
            df = pd.read_csv(target_csv)
            score_col = next((c for c in ['af2folding_max_ipsae', 'self_complex_max_ipAE', 'complex_i_pAE'] if c in df.columns), None)
            if score_col:
                top_row = df.loc[df[score_col].idxmax()]
                current_max_score = float(top_row[score_col])
                top_pdb = top_row.get('pdb_path', None)

        msg = f"📊 {island_name} Iter {iteration} Max ipSAE: {current_max_score:.4f}"
        print(msg)
        sync_log(msg)
        
        # --- 4. Rollback and Termination Logic ---
        if current_max_score < highest_ipsae_state:
            msg = f"📉 Notice: Performance degraded from {highest_ipsae_state:.4f} to {current_max_score:.4f}."
            print(msg)
            sync_log(msg)
            if stagnation_rollback_state and stagnation_rollback_state['tried_rollback']:
                msg = f"🛑 Rollback recovery failed. {island_name} is marked as CONVERGED (Local Minima)."
                print(msg)
                sync_log(msg)
                print(f"🔒 Final Top State for {island_name} achieved ipSAE {highest_ipsae_state:.4f}")
                # Store top structure logic goes here...
                break 
            
            msg = "🔙 Triggering Rollback..."
            print(msg)
            sync_log(msg)
            active_hotspots = stagnation_rollback_state['hotspots']
            
            # Alternative: drop 2 worst, add 3rd/4th best instead of 1st/2nd best.
            all_scores = stagnation_rollback_state['scores']
            neo = [r for r in all_scores.keys() if r not in active_hotspots]
            neo_sorted = sorted(neo, key=lambda x: all_scores[x], reverse=True)
            active_sorted = sorted(active_hotspots, key=lambda x: all_scores.get(x, 0), reverse=True)
            
            active_hotspots = active_sorted[:-2] if len(active_hotspots) > 2 else active_hotspots
            active_hotspots.extend(neo_sorted[2:4]) # use alternative neo
            
            stagnation_rollback_state['tried_rollback'] = True
            iteration += 1
            print(f"🔀 Retrying loop with alternative configuration: {','.join(active_hotspots)}")
            continue

        # Valid progress made
        highest_ipsae_state = current_max_score
        
        # --- 5. Greedy Convergence Modification ---
        scores = calculate_residue_contributions(top_pdb, active_hotspots)
        stagnation_rollback_state = {
            'hotspots': list(active_hotspots),
            'scores': scores,
            'tried_rollback': False
        }
        
        neo_pool = [r for r in scores.keys() if r not in active_hotspots]
        neo_sorted = sorted(neo_pool, key=lambda x: scores[x], reverse=True)
        active_sorted = sorted(active_hotspots, key=lambda x: scores.get(x, 0), reverse=True)
        
        if len(active_sorted) > 2:
            dropped = active_sorted[-2:]
            active_hotspots = active_sorted[:-2]
            print(f"✂️ Dropped lowest contributing: {','.join(dropped)}")
            
        added = neo_sorted[:2]
        active_hotspots.extend(added)
        active_hotspots = list(set(active_hotspots))
        msg = f"➕ Absorbed highest contributing candidates: {','.join(added)}"
        print(msg)
        sync_log(msg)
        
        iteration += 1

print("\n🏁 Full Deep Greedy Convergence Loop traversal completed.")
print("✅ All Hybrid Islands processed successfully.")

'''
Block Comment:
Objective: Deep Greedy Convergence Loop iterating through Hybrid Island priorities.
Upstream Dependencies: complexa, pandas, scipy.spatial, Cell_19 Output JSON
Runtime Environment: Colab / Linux High-Performance GPU Workspace
Timestamp: Auto-generated via Script execution.
'''
