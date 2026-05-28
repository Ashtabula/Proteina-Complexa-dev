import os, sys, json, subprocess, time, datetime, re, shutil
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import KDTree
import yaml
import csv

print("🧭 Initializing Cell 21: Spatial Edge Beam Search Engine...")

BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
ROOT_SETTING = BASE_DIR / 'internal_settings.json'

if not ROOT_SETTING.exists():
    print("❌ Error: Root configuration missing.")
    sys.exit(1)

with open(ROOT_SETTING, 'r') as f:
    root_cfg = json.load(f)

task_name = root_cfg['task_name']
force_restart_evolution = root_cfg.get('force_restart_evolution', False)
evo_max_hotspots = int(root_cfg.get('evo_max_hotspots', 8))
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))

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
base_hotspots = [x.strip() for x in cfg.get('hotspots_input', '').split(',') if x.strip()]
SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
SESSION_NAME = f"SpatialBeam_{task_name}_{SESSION_TIMESTAMP}"

yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})

print("🔬 Parsing target structures and calculating topologies...")
ca_atoms = {}
with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            res_id = line[22:26].strip()
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            ca_atoms[res_id] = np.array([x, y, z])

all_res_ids = list(ca_atoms.keys())
all_coords = np.array([ca_atoms[rid] for rid in all_res_ids])

global_kdtree = KDTree(all_coords)
surface_mask = set()
for i, rid in enumerate(all_res_ids):
    neighbors = global_kdtree.query_ball_point(all_coords[i], r=10.0)
    if len(neighbors) < 20:
        surface_mask.add(rid)

print(f"🌊 Identified {len(surface_mask)} surface-exposed residues.")

EVOLUTION_TREE_JSON = final_dir / "evolution_tree.json"
BEAM_SEARCH_CSV = final_dir / "beam_search_state.csv"

def save_tree(tree_data):
    with open(EVOLUTION_TREE_JSON, 'w', encoding='utf-8') as f:
        json.dump(tree_data, f, indent=4, ensure_ascii=False)

def load_tree():
    if EVOLUTION_TREE_JSON.exists():
        with open(EVOLUTION_TREE_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"Core_Hotspots": base_hotspots, "Anchors": {}}

def save_state_to_csv(csv_path, anchor_id, iteration, active_branches, tested_history_set):
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['anchor_id', 'iteration', 'branch_id', 'score', 'active_hotspots', 'tested_history'])
        
        tested_str = ";".join(map(str, sorted(list(tested_history_set))))
        for i, branch in enumerate(active_branches):
            hotspots_str = ";".join(map(str, sorted(list(branch['lineup']))))
            writer.writerow([
                anchor_id,
                iteration,
                f"Branch_{i}",
                branch['score'],
                hotspots_str,
                tested_str
            ])

def load_state_from_csv(csv_path, target_anchor_id):
    if not os.path.exists(csv_path):
        return 1, [], set()
        
    tested_history_set = set()
    last_iteration = 0
    lineup_dict = {} 
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['tested_history']:
                history_list = row['tested_history'].split(';')
                tested_history_set.update(x for x in history_list if x)
                
            if row['anchor_id'] == str(target_anchor_id):
                iter_num = int(row['iteration'])
                if iter_num > last_iteration:
                    last_iteration = iter_num
                    
                if iter_num not in lineup_dict:
                    lineup_dict[iter_num] = []
                    
                hotspots_str = row['active_hotspots'].strip()
                hotspots = [x for x in hotspots_str.split(';') if x]
                lineup_dict[iter_num].append({
                    'lineup': hotspots,
                    'score': float(row['score'])
                })
            
    active_branches = lineup_dict.get(last_iteration, [])
    start_iteration = last_iteration + 1 if last_iteration > 0 else 1
    return start_iteration, active_branches, tested_history_set

def get_edge_anchors(core_hotspots, ca_dict, surface_set):
    edge_anchors = []
    core_coords = np.array([ca_dict[rid] for rid in core_hotspots if rid in ca_dict])
    if len(core_coords) == 0: return []
    core_kdtree = KDTree(core_coords)
    
    for res_id in surface_set:
        if res_id not in core_hotspots:
            dist, _ = core_kdtree.query(ca_dict[res_id], k=1)
            if dist < 8.0:
                edge_anchors.append(res_id)
    return edge_anchors

def run_generation_and_score(run_name, active_hotspots):
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
            
    return current_max_score, top_pdb

def calculate_residue_contributions(pdb_path, res_list):
    scores = {}
    if not pdb_path or not Path(pdb_path).exists(): return scores
    t_coords, b_coords = {}, []
    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM"):
                atom_name = line[12:16].strip()
                if atom_name.startswith("H"): continue
                c, r, x, y, z = line[21], line[22:26].strip(), float(line[30:38]), float(line[38:46]), float(line[46:54])
                if c == target_chains:
                    if r not in t_coords: t_coords[r] = []
                    t_coords[r].append([x, y, z])
                else:
                    b_coords.append([x, y, z])
    if not b_coords: return scores
    b_tree = KDTree(b_coords)
    for rid in res_list:
        if rid in t_coords:
            min_dist = 999.0
            for coord in t_coords[rid]:
                dists, _ = b_tree.query(coord, k=1)
                if dists < min_dist: min_dist = dists
            
            if min_dist < 2.5:
                scores[rid] = -2.0 # Steric Clash Penalty
            else:
                scores[rid] = np.exp(-((min_dist - 3.8)**2) / (2 * 1.5**2))
    return scores

def compute_jaccard_similarity(set1, set2):
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

print("\n--- State Control & Resume ---")
if force_restart_evolution or not EVOLUTION_TREE_JSON.exists():
    print(">> Hard Reset Initiated: Generating Ground Zero...")
    if EVOLUTION_TREE_JSON.exists(): os.remove(EVOLUTION_TREE_JSON)
    if BEAM_SEARCH_CSV.exists(): os.remove(BEAM_SEARCH_CSV)
    tree_data = {"Core_Hotspots": base_hotspots, "Anchors": {}}
    save_tree(tree_data)
else:
    print(">> True Resume Active: Reconstructing battlefield from JSON and CSV...")
    tree_data = load_tree()

completed_anchors = set(tree_data["Anchors"].keys())
edge_anchors = get_edge_anchors(base_hotspots, ca_atoms, surface_mask)
print(f"📡 Detected {len(edge_anchors)} Edge Anchors surrounding the Core.")

global_tested_history = set(base_hotspots)
for anc, results in tree_data["Anchors"].items():
    global_tested_history.add(anc)
    for r in results:
        global_tested_history.update(r['lineup'])

for anchor_id in edge_anchors:
    if anchor_id in completed_anchors:
        print(f"⏭️ Anchor {anchor_id} already converged in history. Skipping.")
        continue
        
    msg = f"📍 === Initiating Spatial Edge Expansion for Anchor {anchor_id} ==="
    print(f"\n{msg}")
    sync_log(msg)
    
    start_iteration, active_branches, csv_history = load_state_from_csv(BEAM_SEARCH_CSV, anchor_id)
    global_tested_history.update(csv_history)
    
    candidate_coords = []
    candidate_ids = []
    for rid in surface_mask:
        if rid not in global_tested_history and rid in ca_atoms:
            candidate_ids.append(rid)
            candidate_coords.append(ca_atoms[rid])
            
    if not candidate_ids and not active_branches:
        print(f"⚠️ Global pool exhausted around Anchor {anchor_id}. Skipping.")
        continue
        
    local_pool = []
    if candidate_ids:
        local_kdtree = KDTree(candidate_coords)
        idx_within_15 = local_kdtree.query_ball_point(ca_atoms[anchor_id], 15.0)
        local_pool = [candidate_ids[i] for i in idx_within_15]
        local_pool.sort(key=lambda rid: np.linalg.norm(ca_atoms[rid] - ca_atoms[anchor_id]))
        
    print(f"   Anchor {anchor_id} Local 15A Pool size: {len(local_pool)}")
    
    if not active_branches:
        print(">> Fresh start for this anchor.")
        current_lineup = list(set(base_hotspots).union({anchor_id}))
        active_branches = [{'lineup': current_lineup, 'score': -999.0}]
    else:
        print(f">> True Resume Mid-Anchor: Restoring {len(active_branches)} active branches at iteration {start_iteration}.")
        
    stagnation_counter = 0
    iteration = start_iteration
    top_results = list(active_branches)
    
    while len(local_pool) >= 2 and stagnation_counter < 3:
        add_1, add_2 = local_pool.pop(0), local_pool.pop(0)
        global_tested_history.update([add_1, add_2])
        
        generated_designs = []
        
        for b_idx, branch in enumerate(active_branches):
            test_lineup = list(set(branch['lineup'] + [add_1, add_2]))
            print(f"\n   [Iter {iteration} | Branch {b_idx}] Testing Lineup: {','.join(test_lineup)}")
            
            run_name = f"EdgeExp_Anc{anchor_id}_Iter{iteration}_B{b_idx}_{SESSION_TIMESTAMP}"
            current_max_score, top_pdb = run_generation_and_score(run_name, test_lineup)
            msg = f"   [Iter {iteration} | Branch {b_idx}] Max ipSAE Score: {current_max_score:.4f}"
            print(msg)
            sync_log(msg)
            
            contribs = calculate_residue_contributions(top_pdb, test_lineup)
            footprint = set(r for r, c in contribs.items() if c > 0)
            
            protect_list = set(base_hotspots).union({anchor_id})
            if len(test_lineup) > evo_max_hotspots:
                non_protected = [r for r in test_lineup if r not in protect_list]
                non_protected_sorted = sorted(non_protected, key=lambda x: contribs.get(x, 0), reverse=True)
                num_to_keep = max(0, evo_max_hotspots - len(protect_list))
                kept_non_protected = non_protected_sorted[:num_to_keep]
                new_lineup = list(protect_list) + kept_non_protected
            else:
                new_lineup = list(test_lineup)
            
            generated_designs.append({
                "parent_score": branch['score'],
                "parent_lineup": branch['lineup'],
                "new_lineup": new_lineup,
                "score": current_max_score,
                "footprint": footprint
            })
            
        clusters = {}
        cluster_counter = 1
        for d in generated_designs:
            assigned = False
            for cid, c_designs in clusters.items():
                rep_footprint = c_designs[0]["footprint"]
                sim = compute_jaccard_similarity(d["footprint"], rep_footprint)
                if sim >= 0.3: # Relaxed Jaccard threshold from 0.4 to 0.3 to preserve more diversity
                    clusters[cid].append(d)
                    assigned = True
                    break
            if not assigned:
                clusters[f"Cluster_{cluster_counter}"] = [d]
                cluster_counter += 1
                
        msg = f"   🧬 Diversity-Preserving Phase: Grouped into {len(clusters)} unique binding conformations."
        print(msg)
        sync_log(msg)
        
        new_branches = []
        improved = False
        
        for cid, c_designs in clusters.items():
            champion = sorted(c_designs, key=lambda x: x["score"], reverse=True)[0]
            
            if champion["score"] > champion["parent_score"]:
                improved = True
                new_branches.append({
                    "lineup": champion["new_lineup"],
                    "score": champion["score"]
                })
            else:
                new_branches.append({
                    "lineup": champion["parent_lineup"],
                    "score": champion["parent_score"]
                })
                
        if improved:
            stagnation_counter = 0
        else:
            stagnation_counter += 1
            msg = f"   📉 Degradation across all diverse branches. Stagnation Count: {stagnation_counter}/3"
            print(msg)
            sync_log(msg)
            
        active_branches = sorted(new_branches, key=lambda x: x["score"], reverse=True)[:3]
        top_results = list(active_branches)
        
        save_state_to_csv(BEAM_SEARCH_CSV, anchor_id, iteration, active_branches, global_tested_history)
        
        iteration += 1
        
    if top_results:
        tree_data["Anchors"][anchor_id] = top_results
        save_tree(tree_data)
        msg = f"💾 Anchor {anchor_id} Converged. Top Results Checkpointed in JSON."
        print(msg)
        sync_log(msg)
        
    global_tested_history.add(anchor_id)
    for res in candidate_ids:
        if res in local_pool:
            global_tested_history.add(res)

print("\n🏁 Full Spatial Edge Beam Search traversal completed.")
print("✅ All Edge Anchors processed successfully.")
