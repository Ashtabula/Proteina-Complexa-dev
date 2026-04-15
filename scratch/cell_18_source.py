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

target_threshold = float(cfg['target_threshold'])
target_success_count = int(cfg['target_success_count'])
designs_per_loop = int(cfg['designs_per_loop'])
max_iterations = int(cfg['max_iterations'])
batch_size = int(cfg['batch_size'])
target_chains = cfg['target_chains']
base_hotspots = cfg.get('hotspots_input', '')

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

while current_iteration < max_iterations and len(GLOBAL_HITS) < target_success_count:
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
    print(f"🧬 Evolution Cycle [{current_iteration}/{max_iterations}] Commencing...")
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
            
    num_batches = math.ceil(designs_per_loop / batch_size)
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
                    if ipsae_val >= target_threshold and not any(h['id'] == d_id for h in GLOBAL_HITS):
                        GLOBAL_HITS.append(design_entry)
                except Exception: pass

        if rows_to_write:
            file_exists = master_log_path.exists()
            with open(master_log_path, 'a', encoding='utf-8', newline='') as f_log:
                writer = csv.DictWriter(f_log, fieldnames=master_fieldnames, extrasaction='ignore')
                if not file_exists: writer.writeheader()
                writer.writerows(rows_to_write)
                
    # ---------------------------------------------------------
    # 5. Iterative Hotspot Evolution Mechanism
    # ---------------------------------------------------------
    if cycle_designs:
        print("\n🔍 Launching PDB Space Topographic Analytics for Hotspot Evolution...")
        # Sort current cycle designs by score, pick top 3
        cycle_designs.sort(key=lambda x: x['score'], reverse=True)
        top_cycle_pdbs = cycle_designs[:3]
        
        contact_tally = {} # target_res_id -> contact count
        
        for d in top_cycle_pdbs:
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
                # Parse structure manually to find distances
                chains_coords = {}
                chains_res_ids = {} # lists of unique residues
                
                with open(resolved_path, 'r') as pdbf:
                    for line in pdbf:
                        if line.startswith("ATOM") and line[12:16].strip() in ["CA", "CB", "CG"]:
                            chain_id = line[21]
                            res_id = line[22:26].strip()
                            x = float(line[30:38])
                            y = float(line[38:46])
                            z = float(line[46:54])
                            
                            if chain_id not in chains_coords:
                                chains_coords[chain_id] = []
                            chains_coords[chain_id].append([x, y, z])
                            
                            if chain_id == target_chains:
                                if res_id not in chains_res_ids:
                                    chains_res_ids[res_id] = []
                                chains_res_ids[res_id].append([x, y, z])
                
                # Determine Binder Chain (shortest chain array)
                if len(chains_coords) < 2: continue
                binder_chain = min(chains_coords.keys(), key=lambda k: len(chains_coords[k]))
                target_chain = target_chains
                
                binder_pts = np.array(chains_coords[binder_chain])
                if binder_pts.size == 0 or target_chain not in chains_res_ids: continue
                
                binder_kdtree = KDTree(binder_pts)
                
                for res_id, pts in chains_res_ids.items():
                    res_pts = np.array(pts)
                    try:
                        dists, _ = binder_kdtree.query(res_pts, k=1)
                        if np.any(dists < CONTACT_THRESHOLD):
                            contact_tally[res_id] = contact_tally.get(res_id, 0) + 1
                    except Exception as e:
                        pass
        
        # Evolution Logic:
        new_hotspots_set = set()
        for res_id in active_hotspots:
            if contact_tally.get(res_id, 0) >= 1:
                new_hotspots_set.add(res_id)
        
        for res_id, count in contact_tally.items():
            if count >= 2:
                new_hotspots_set.add(res_id)
                
        if len(new_hotspots_set) < 3:
            sorted_contacts = sorted(contact_tally.keys(), key=lambda k: contact_tally[k], reverse=True)
            for tk in sorted_contacts[:5]:
                new_hotspots_set.add(tk)
                
        if len(new_hotspots_set) > 0:
            evolved_hotspots = sorted(list(new_hotspots_set), key=lambda x: int(x) if x.isdigit() else x)
            if evolved_hotspots != active_hotspots:
                print(f"🧬 [EVOLUTION DRIVEN] Hotspot landscape mutated! \n    Old: {','.join(active_hotspots)}\n    New: {','.join(evolved_hotspots)}")
                active_hotspots = evolved_hotspots
                
                with open(ISOLATED_SETTING, 'r') as f:
                    updated_cfg = json.load(f)
                updated_cfg['hotspots_input'] = ','.join(active_hotspots)
                with open(ISOLATED_SETTING, 'w') as f:
                    json.dump(updated_cfg, f, indent=4)
            else:
                print(f"🧬 Optimal Spot Retained. No mutation applied this cycle.")
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

    if len(GLOBAL_HITS) >= target_success_count:
        print(f"\n🎉 Threshold Attained! Successfully assimilated {target_success_count} top structures under dynamic hotspots.")
        break

    if current_iteration < max_iterations:
        print("🧹 Cycle wrap-up complete. Preparing next generation iteration...")
        time.sleep(3)

print("\n✅ Evolutionary Protocol Executed Successfully.")
