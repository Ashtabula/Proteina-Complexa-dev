# Cell_18_Automated_Hotspot_Evolution_Loop.py
# Requirement: Execute an automated loop for high-throughput generation, and dynamically evolve the target mapped hotspots based on contact distances in the generated results.
import os, json, sys, time, subprocess, csv, datetime, shutil, math, random, gc, re, yaml
from pathlib import Path
import numpy as np
from scipy.spatial import KDTree
import pandas as pd
import torch

print("🔍 Initializing Automated Hotspot Evolution Engine (Section 6)...")

# ---------------------------------------------------------
# 1. Decoupled Configuration Loading via last_runs.txt
# ---------------------------------------------------------
BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
ROOT_SETTING = BASE_DIR / 'internal_settings.json'

if not ROOT_SETTING.exists():
    print("❌ Error: Root configuration missing. Run Section 0 first.")
    sys.exit(1)

with open(ROOT_SETTING, 'r') as f:
    root_cfg = json.load(f)

task_name = root_cfg['task_name']
last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'

run_id = None
target_dir_name = None

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

if not run_id or not target_dir_name:
    print(f"❌ Error: No valid run history found for task [{task_name}]. Run Section 2 first.")
    sys.exit(1)

final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name
ISOLATED_SETTING = final_dir / 'internal_settings.json'

if not ISOLATED_SETTING.exists():
    print(f"❌ Error: Isolated configuration file missing in {final_dir.name}.")
    sys.exit(1)

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)

# Global variables
target_chains = cfg['target_chains']
base_hotspots = cfg.get('hotspots_input', '')
batch_size = int(cfg.get('batch_size', 24))

# Evolution Specific Variables
evo_designs_per_loop = int(cfg.get('evo_designs_per_loop', 48))
evo_max_iterations = int(cfg.get('evo_max_iterations', 10))
evo_max_hotspots = int(cfg.get('evo_max_hotspots', 8))
evo_update_count = int(cfg.get('evo_update_count', 2))

print(f"✅ State Secured: Loaded settings from isolated workspace [{target_dir_name}]")
print(f"🤖 Hotspot Evolution Engine Activated for Target: [{task_name}]")
print(f"🌍 Initial Hotspots: {base_hotspots}")

# ---------------------------------------------------------
# 2. Tracking Variables & Master Setup
# ---------------------------------------------------------
ALL_DESIGNS_POOL = []
GLOBAL_HITS = []
existing_master_ids = set()
max_loop_found = 0

master_log_path = final_dir / f"{run_id}_EvoPilot_master_log.csv"
LIVE_PDB_DIR = final_dir / 'EvoPilot_Live_Top10_PDBs'
LIVE_PDB_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
SESSION_NAME = f"EvoPilot_{task_name}_{SESSION_TIMESTAMP}"
SESSION_MASTER_DIR = BASE_DIR / 'assets' / 'target_data' / SESSION_NAME
SESSION_MASTER_DIR.mkdir(parents=True, exist_ok=True)
timestamp_suffix = run_id.split('_')[-1]

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})

# Start with base hotspots, converting to a python list of clean strings
active_hotspots = [x.strip() for x in base_hotspots.split(',') if x.strip()]

# ---------------------------------------------------------
# 3. Evolution Cycle Engine Loop
# ---------------------------------------------------------
global_start_time = time.time()
current_iteration = max_loop_found

# The contact distance threshold for defining a "hit" between binder and target
CONTACT_THRESHOLD = 4.5  

while current_iteration < evo_max_iterations:
    current_iteration += 1
    loop_start_time = time.time()
    batch_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_seed = random.randint(1, 1000000)
    current_run_name = f"{SESSION_NAME}_Cycle{current_iteration}"
    
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / current_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)
    
    print(f"\n=======================================================")
    print(f"🧬 Evolution Cycle [{current_iteration}/{evo_max_iterations}] Commencing...")
    print(f"🎯 Current Active Hotspots: {','.join(active_hotspots)}")
    print(f"=======================================================")

    # Force inject dynamic hotspots into complexa yaml right before runtime
    yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
            
    num_batches = math.ceil(evo_designs_per_loop / batch_size)
    total_designs = num_batches * batch_size

    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={current_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={total_designs} "
        f"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=True ++run_analyze=True ++seed={current_seed}"
    )

    process = subprocess.Popen(
        f"source env.sh && {cmd_str}",
        env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    for line in process.stdout:
        print(line, end='', flush=True)
    process.wait()
    ret_code = process.returncode

    if ret_code != 0:
        print(f"❌ Critical Warning: Underlying generation engine crashed (Error Code {ret_code})!")
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache(); torch.cuda.ipc_collect()
        time.sleep(3)
        continue

    # ---------------------------------------------------------
    # 4. Report Parsing & Logging
    # ---------------------------------------------------------
    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{current_run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]
    cycle_designs = []

    if valid_csvs:
        target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
        with open(target_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            master_fieldnames = ['session_loop', 'timestamp', 'source_path', 'design_id'] + list(reader.fieldnames)
            master_fieldnames = list(dict.fromkeys(master_fieldnames))
            rows_to_write = []

            for i, row in enumerate(reader):
                try:
                    base_d_id = row.get('design_id', '').strip() or f"Design_{row.get('pdb_index', i)}"
                    d_id = f"Cycle{current_iteration}_{base_d_id}"
                    if d_id in existing_master_ids: continue
                    existing_master_ids.add(d_id)

                    ipsae_val = float(row.get('af2folding_max_ipsae', row.get('self_complex_max_ipAE', row.get('complex_i_pAE', -999.0))))
                    ptm_val = float(row.get('af2folding_ptm_log', row.get('self_complex_pTM', row.get('complex_pTM', -999.0))))
                    iptm_val = float(row.get('af2folding_i_ptm_log', row.get('self_complex_i_pTM', row.get('complex_ipTM', -999.0))))
                    plddt_val = float(row.get('af2folding_plddt', row.get('self_complex_pLDDT', row.get('complex_pLDDT', -999.0))))
                    rmsd_val = float(row.get('af2folding_rmsd', row.get('self_binder_scRMSD_ca', row.get('binder_scRMSD_ca', -999.0))))
                    total_reward = float(row.get('total_reward', -999.0))

                    row['design_id'] = d_id; row['session_loop'] = current_iteration
                    row['timestamp'] = batch_timestamp; row['source_path'] = str(inference_dir)
                    rows_to_write.append(row)

                    design_entry = {
                        'id': d_id, 'score': ipsae_val, 'ptm': ptm_val, 'iptm': iptm_val,
                        'plddt': plddt_val, 'rmsd': rmsd_val, 'total_reward': total_reward,
                        'batch_num': current_iteration, 'idx_in_batch': i + 1,
                        'dir': str(inference_dir), 'loop': current_iteration,
                        'pdb_path': row.get('pdb_path', '')
                    }
                    ALL_DESIGNS_POOL.append(design_entry)
                    cycle_designs.append(design_entry)
                except Exception: pass

        if rows_to_write:
            file_exists = master_log_path.exists()
            with open(master_log_path, 'a', encoding='utf-8', newline='') as f_log:
                writer = csv.DictWriter(f_log, fieldnames=master_fieldnames, extrasaction='ignore')
                if not file_exists: writer.writeheader()
                writer.writerows(rows_to_write)
                
    # ---------------------------------------------------------
    # 5. Iterative Hotspot Evolution Mechanism (ipSAE-Weighted)
    # ---------------------------------------------------------
    if cycle_designs:
        print("\n🔍 Launching High-Definition ipSAE Weighted Hotspot Resolution...")
        # Sort current cycle designs by score
        cycle_designs.sort(key=lambda x: x['score'], reverse=True)
        # We will parse up to top 5 generated complexes per round to balance precision and diversity
        top_cycle_pdbs = cycle_designs[:min(len(cycle_designs), 5)]
        
        contact_scores = {} # target_res_id -> accumulated ipSAE weight score
        
        for rank, d in enumerate(top_cycle_pdbs):
            exact_pdb_path = d.get('pdb_path', '')
            resolved_path = None
            if exact_pdb_path and Path(exact_pdb_path).exists():
                resolved_path = Path(exact_pdb_path)
            else:
                source_dir = Path(d['dir'])
                if source_dir.exists():
                    for pdb_file in source_dir.rglob('*.pdb'):
                        base_d_id = re.sub(r'^Cycle\d+_', '', d['id'])
                        if base_d_id.lower() in pdb_file.name.lower() or pdb_file.name == f"{base_d_id}.pdb":
                            resolved_path = pdb_file
                            break

            if resolved_path:
                print(f"  [Parse] Rank #{rank+1} (ipSAE: {d['score']:.3f}) - {d['id']}")
                chains_coords = {}
                chains_res_ids = {}
                
                with open(resolved_path, 'r') as pdbf:
                    for line in pdbf:
                        if line.startswith("ATOM") and line[12:16].strip() in ["CA"]:
                            chain_id = line[21]
                            res_id = line[22:26].strip()
                            x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
                            
                            if chain_id not in chains_coords: chains_coords[chain_id] = []
                            chains_coords[chain_id].append([x, y, z])
                            
                            if chain_id == target_chains:
                                if res_id not in chains_res_ids: chains_res_ids[res_id] = []
                                chains_res_ids[res_id].append([x, y, z])
                
                if len(chains_coords) < 2: continue
                binder_chain = min(chains_coords.keys(), key=lambda k: len(chains_coords[k]))
                
                binder_pts = np.array(chains_coords.get(binder_chain, []))
                if binder_pts.size == 0 or target_chains not in chains_res_ids: continue
                
                binder_kdtree = KDTree(binder_pts)
                
                # Weight formula: The #1 PDB contributes 100% of its ipSAE as metric, #2 50%, #3 33%...
                base_weight = 1.0 / (rank + 1)
                
                for res_id, pts in chains_res_ids.items():
                    res_pts = np.array(pts)
                    try:
                        dists, _ = binder_kdtree.query(res_pts, k=1)
                        if np.any(dists < CONTACT_THRESHOLD):
                            # Tally score
                            score_increment = float(d['score']) * base_weight
                            contact_scores[res_id] = contact_scores.get(res_id, 0.0) + max(0, score_increment)
                    except Exception as e:
                        pass
        
        # Evolution Selection Algorithm
        new_hotspots_pool = {}
        
        # 1. Eliminate weak/dead original hotspots
        eliminated = []
        for res_id in active_hotspots:
            if contact_scores.get(res_id, 0) > 0:
                new_hotspots_pool[res_id] = contact_scores[res_id]
            else:
                eliminated.append(res_id)
                
        # 2. Integrate highly potent Neo-Hotspots based on the quota (evo_update_count)
        neo_hotspots = {k: v for k, v in contact_scores.items() if k not in active_hotspots}
        sorted_neo = sorted(neo_hotspots.keys(), key=lambda k: neo_hotspots[k], reverse=True)
        top_neo = sorted_neo[:evo_update_count]
        
        for neo_k in top_neo:
            new_hotspots_pool[neo_k] = contact_scores[neo_k]
            
        # 3. Cap Total Hotspots up to evo_max_hotspots based on ultimate combined scoring
        sorted_combined = sorted(new_hotspots_pool.keys(), key=lambda k: new_hotspots_pool[k], reverse=True)
        final_retained = sorted_combined[:evo_max_hotspots]
        
        if len(final_retained) == 0:
            print("⚠️ Total evolutionary contact collapse detected. Emergency fallback: Retaining previous layout.")
            final_retained = active_hotspots
            
        evolved_hotspots = sorted(list(final_retained), key=lambda x: int(x) if x.isdigit() else x)
        
        if eliminated:
            print(f"  [-] Weak Hotspots Eliminated: {','.join(eliminated)}")
        if top_neo:
            print(f"  [+] Neo-Hotspots Integrated : {','.join(top_neo)}")
            
        if evolved_hotspots != active_hotspots:
            print(f"🧬 [EVOLUTION DRIVEN] Hotspot landscape mutated! \n    Old: {','.join(active_hotspots)}\n    New: {','.join(evolved_hotspots)}")
            active_hotspots = evolved_hotspots
            
            with open(ISOLATED_SETTING, 'r') as f:
                updated_cfg = json.load(f)
            updated_cfg['hotspots_input'] = ','.join(active_hotspots)
            with open(ISOLATED_SETTING, 'w') as f:
                json.dump(updated_cfg, f, indent=4)
        else:
            print(f"🧬 Equilibrium Maintained. Contact structure remained resilient this cycle.")
    else:
        print("⚠️ No valid designs generated in this cycle. Evolution skipped.")

    # ---------------------------------------------------------
    # 6. Global Artifact Update
    # ---------------------------------------------------------
    ALL_DESIGNS_POOL.sort(key=lambda x: x['score'], reverse=True)
    current_top_ids = set([d['id'] for d in ALL_DESIGNS_POOL[:10]])

    for existing_file in LIVE_PDB_DIR.glob('*.pdb'):
        if existing_file.stem not in current_top_ids: existing_file.unlink()

    for d in ALL_DESIGNS_POOL[:10]:
        exact_pdb_path = d.get('pdb_path', '')
        resolved_path = None
        if exact_pdb_path and Path(exact_pdb_path).exists():
            resolved_path = Path(exact_pdb_path)
        else:
            source_dir = Path(d['dir'])
            if source_dir.exists():
                for pdb_file in source_dir.rglob('*.pdb'):
                    base_d_id = re.sub(r'^Cycle\d+_', '', d['id'])
                    if base_d_id.lower() in pdb_file.name.lower() or pdb_file.name == f"{base_d_id}.pdb":
                        resolved_path = pdb_file
                        break
        if resolved_path:
            dest_path = LIVE_PDB_DIR / f"{d['id']}.pdb"
            if not dest_path.exists(): shutil.copy2(resolved_path, dest_path)

    print("\n🏆 Live Top 10 EVOLUTION Design Roster:")
    header_format = "{:<5} | {:<16} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8} | {:<6}"
    print(header_format.format("Rank", "Design_ID", "ipSAE", "pTM", "iPTM", "pLDDT", "RMSD", "Batch"))
    print("-" * 85)
    for rank, d in enumerate(ALL_DESIGNS_POOL[:10], 1):
        print(header_format.format(
            rank, d['id'][:16], f"{d['score']:.4f}", f"{d['ptm']:.4f}", f"{d['iptm']:.4f}",
            f"{d['plddt']:.2f}", f"{d['rmsd']:.2f}Å", str(d['batch_num'])
        ))
    print("-" * 85)

    gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache(); torch.cuda.ipc_collect()

    if current_iteration < evo_max_iterations:
        print("🧹 Cycle wrap-up complete. Preparing next generation iteration...")
        time.sleep(3)

print(f"\n✅ Evolutionary Protocol Halted after {current_iteration} cycles.")
