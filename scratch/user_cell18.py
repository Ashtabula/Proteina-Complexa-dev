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
generation_batch_size = int(root_cfg.get('generation_batch_size', 36))
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))

# Evolution Specific Variables
evo_designs_per_loop = int(root_cfg.get('evo_designs_per_loop', 48))
evo_max_hotspots = int(root_cfg.get('evo_max_hotspots', 8))
evo_update_count = int(root_cfg.get('evo_update_count', 2))
evo_target_threshold = float(root_cfg.get('evo_target_threshold', 0.85))
evo_strict_rmsd_filter = root_cfg.get('evo_strict_rmsd_filter', True)

# Hit Quota and Limits
target_success_count = int(root_cfg.get('target_success_count', 1))
max_iterations = int(root_cfg.get('max_iterations', 50))

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

active_hotspots = [x.strip() for x in base_hotspots.split(',') if x.strip()]
prev_iterate_state = None

# ---------------------------------------------------------
# 3. Evolution Cycle Engine Loop
# ---------------------------------------------------------
global_start_time = time.time()
CONTACT_THRESHOLD = 4.5  

evolution_iterate = 1
generation_round = 1
designs_in_current_iterate = 0
iterate_designs = []

while True:
    loop_start_time = time.time()
    batch_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_seed = random.randint(1, 1000000)
    current_run_name = f"{SESSION_NAME}_Iterate{evolution_iterate}_Round{generation_round}"
    
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / current_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    if not SOURCE_PDB_PATH.exists():
        print(f"❌ Critical Error: Source PDB not found at {SOURCE_PDB_PATH}")
        sys.exit(1)
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)
    
    print(f"\n=======================================================")
    print(f"🧬 Evolution Generation [Round {evolution_iterate}]: {designs_in_current_iterate}/{evo_designs_per_loop} designs Commencing...")
    print(f"🎯 Current Active Hotspots: {','.join(active_hotspots)}")
    print(f"=======================================================")

    yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={current_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={generation_batch_size} "
        f"++generation.dataloader.batch_size={generation_batch_size} ++generation.search.max_batch_size={generation_batch_size} ++evaluation.dataloader.batch_size={evaluation_batch_size} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=True ++evaluate.num_recycles=1 ++evaluate.pad_to_max_length=True ++evaluate.use_msa=False ++evaluate.msa_mode=single_sequence ++run_analyze=True ++seed={current_seed}"
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
    # 4. Report Parsing & Dynamic Leaderboard
    # ---------------------------------------------------------
    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{current_run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]
    batch_designs = []

    if valid_csvs:
        target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
        with open(target_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            raw_fieldnames = list(reader.fieldnames)

            master_fieldnames = ['session_loop', 'timestamp', 'source_path'] + raw_fieldnames
            if 'design_id' not in master_fieldnames:
                master_fieldnames.insert(3, 'design_id')

            new_entries_this_cycle = 0
            rows_to_write = []

            for i, row in enumerate(reader):
                try:
                    # [MODIFIED]: Retained Iterate_Round namespace to prevent multi-batch ID collisions
                    base_d_id = row.get('design_id', '').strip() or f"Design_{row.get('pdb_index', i)}"
                    d_id = f"Iterate{evolution_iterate}_Round{generation_round}_{base_d_id}"

                    if d_id in existing_master_ids:
                        continue
                    existing_master_ids.add(d_id)

                    ipsae_val = float(row.get('af2folding_max_ipsae', row.get('self_complex_max_ipAE', row.get('complex_i_pAE', -999.0))))
                    ptm_val = float(row.get('af2folding_ptm_log', row.get('self_complex_pTM', row.get('complex_pTM', -999.0))))
                    iptm_val = float(row.get('af2folding_i_ptm_log', row.get('self_complex_i_pTM', row.get('complex_ipTM', -999.0))))
                    plddt_val = float(row.get('af2folding_plddt', row.get('self_complex_pLDDT', row.get('complex_pLDDT', -999.0))))
                    rmsd_val = float(row.get('af2folding_rmsd', row.get('self_binder_scRMSD_ca', row.get('binder_scRMSD_ca', -999.0))))
                    total_reward = float(row.get('total_reward', -999.0))

                    row['design_id'] = d_id
                    row['session_loop'] = evolution_iterate
                    row['timestamp'] = batch_timestamp
                    row['source_path'] = str(inference_dir)
                    rows_to_write.append(row)

                    design_entry = {
                        'id': d_id, 'score': ipsae_val, 'ptm': ptm_val, 'iptm': iptm_val,
                        'plddt': plddt_val, 'rmsd': rmsd_val, 'total_reward': total_reward,
                        'batch_num': evolution_iterate, 'idx_in_batch': i + 1,
                        'dir': str(inference_dir), 'loop': evolution_iterate,
                        'pdb_path': row.get('pdb_path', '')
                    }
                    ALL_DESIGNS_POOL.append(design_entry)
                    batch_designs.append(design_entry)
                    new_entries_this_cycle += 1

                    if ipsae_val >= evo_target_threshold:
                        if not any(h['id'] == d_id for h in GLOBAL_HITS):
                            GLOBAL_HITS.append(design_entry)
                except Exception:
                    pass

        if rows_to_write:
            file_exists = master_log_path.exists()
            with open(master_log_path, 'a', encoding='utf-8', newline='') as f_log:
                writer = csv.DictWriter(f_log, fieldnames=master_fieldnames, extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                writer.writerows(rows_to_write)

            print(f"📝 {new_entries_this_cycle} full-data designs appended to live master log: {master_log_path.name}")
    else:
        print("⚠️ Warning: Pipeline succeeded, but no valid CSV output files were found.")

    if batch_designs:
        iterate_designs.extend(batch_designs)
        designs_in_current_iterate += len(batch_designs)
    else:
        designs_in_current_iterate += generation_batch_size

    generation_round += 1

    # Check if we have generated enough designs for one evolution iterate
    if designs_in_current_iterate < evo_designs_per_loop:
        continue  

    # ---------------------------------------------------------
    # 5. Iterative Hotspot Evolution Mechanism (ipSAE-Weighted)
    # ---------------------------------------------------------
    if iterate_designs:
        print(f"\n🧬 Evolution Target {evo_designs_per_loop}/{evo_designs_per_loop} Reached! Selecting highest models to evolve hotspots...")
        cycle_designs = iterate_designs
        print("\n🔍 Launching High-Definition ipSAE Weighted Hotspot Resolution...")
        if evo_strict_rmsd_filter:
            cycle_designs = [d for d in cycle_designs if d.get('rmsd', -999.0) != -999.0 and d.get('rmsd', 999.0) < 10.0]
        
        cycle_designs.sort(key=lambda x: x['score'], reverse=True)
        top_cycle_pdbs = cycle_designs[:min(len(cycle_designs), 5)]
        contact_scores = {} 
        
        for rank, d in enumerate(top_cycle_pdbs):
            exact_pdb_path = d.get('pdb_path', '')
            resolved_path = None
            if exact_pdb_path and Path(exact_pdb_path).exists():
                resolved_path = Path(exact_pdb_path)
            else:
                source_dir = Path(d['dir'])
                if source_dir.exists():
                    for pdb_file in source_dir.rglob('*.pdb'):
                        base_d_id = re.sub(r'^Iterate\d+_Round\d+_', '', d['id'])
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
                base_weight = 1.0 / (rank + 1)
                
                for res_id, pts in chains_res_ids.items():
                    res_pts = np.array(pts)
                    try:
                        dists, _ = binder_kdtree.query(res_pts, k=1)
                        if np.any(dists < CONTACT_THRESHOLD):
                            score_increment = float(d['score']) * base_weight
                            contact_scores[res_id] = contact_scores.get(res_id, 0.0) + max(0, score_increment)
                    except Exception as e:
                        pass
        
        current_iterate_best = cycle_designs[0]['score'] if cycle_designs else 0.0
        use_rollback = (
            prev_iterate_state is not None and
            current_iterate_best < prev_iterate_state['best_score']
        )

        if use_rollback:
            print(f"\n⚠️  [REGRESSION DETECTED] Iterate best ipSAE ({current_iterate_best:.4f}) < "
                  f"Previous best ({prev_iterate_state['best_score']:.4f})")
            print("   ↩️  Initiating Rollback: reverting to previous hotspot config...")
            rb_hotspots = prev_iterate_state['active_hotspots']
            rb_scores   = prev_iterate_state['contact_scores']
            rb_neo      = prev_iterate_state['neo_sorted']

            rb_cur_scores  = {r: rb_scores.get(r, 0.0) for r in rb_hotspots}
            rb_sorted_list = sorted(rb_cur_scores.keys(), key=lambda k: rb_cur_scores[k], reverse=True)

            drop_count        = min(evo_update_count, max(0, len(rb_hotspots) - 2))
            retained_hotspots = rb_sorted_list[:-drop_count] if drop_count > 0 else list(rb_sorted_list)
            alt_start = drop_count
            top_neo   = rb_neo[alt_start : alt_start + drop_count]

            print(f"   [ROLLBACK] Base config : {','.join(rb_hotspots)}")
            _score_ref = rb_scores
        else:
            neo_hotspots = {k: v for k, v in contact_scores.items() if k not in active_hotspots}
            sorted_neo   = sorted(neo_hotspots.keys(), key=lambda k: neo_hotspots[k], reverse=True)

            prev_iterate_state = {
                'active_hotspots': list(active_hotspots),
                'contact_scores':  dict(contact_scores),
                'neo_sorted':      sorted_neo,
                'best_score':      current_iterate_best,
            }
            print(f"   📸 Snapshot saved (best={current_iterate_best:.4f}) for regression guard.")

            current_scores = {r: contact_scores.get(r, 0.0) for r in active_hotspots}
            sorted_current = sorted(current_scores.keys(), key=lambda k: current_scores[k], reverse=True)

            drop_count        = min(evo_update_count, max(0, len(active_hotspots) - 2))
            retained_hotspots = sorted_current[:-drop_count] if drop_count > 0 else list(sorted_current)
            eliminated        = sorted_current[-drop_count:]  if drop_count > 0 else []
            top_neo = sorted_neo[:drop_count]
            _score_ref = contact_scores

        final_retained = list(retained_hotspots) + list(top_neo)
        if len(final_retained) > evo_max_hotspots:
            all_scores = {r: _score_ref.get(r, 0.0) for r in final_retained}
            final_retained = sorted(final_retained, key=lambda k: all_scores[k], reverse=True)[:evo_max_hotspots]
        
        if len(final_retained) == 0:
            final_retained = active_hotspots
            
        evolved_hotspots = sorted(list(final_retained), key=lambda x: int(x) if x.isdigit() else x)
        
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

    # ---------------------------------------------------------
    # 6. Cycle Summary, Live Manifest & Metrics Display
    # ---------------------------------------------------------
    cycle_duration = format_time(time.time() - loop_start_time)
    print(f"\n⏱️ Cycle {evolution_iterate} Operational Duration: {cycle_duration}")
    print(f"📈 Verified Candidates Captured (ipSAE >= {evo_target_threshold}): {len(GLOBAL_HITS)} / {target_success_count}")

    ALL_DESIGNS_POOL.sort(key=lambda x: x['score'], reverse=True)

    current_top_ids = set([d['id'] for d in ALL_DESIGNS_POOL[:10]])

    for existing_file in LIVE_PDB_DIR.glob('*.pdb'):
        if existing_file.stem not in current_top_ids:
            existing_file.unlink()

    top_pdb_paths = []
    top_scores_list = []

    for d in ALL_DESIGNS_POOL[:10]:
        target_d_id = d['id']
        exact_pdb_path = d.get('pdb_path', '')
        resolved_path = None

        if exact_pdb_path and Path(exact_pdb_path).exists():
            resolved_path = Path(exact_pdb_path)
        else:
            source_dir = Path(d['dir'])
            if source_dir.exists():
                for pdb_file in source_dir.rglob('*.pdb'):
                    # [MODIFIED]: Regex adapted for Iterate_Round collision-proof namespace
                    base_d_id = re.sub(r'^Iterate\d+_Round\d+_', '', target_d_id)
                    if base_d_id.lower() in pdb_file.name.lower() or pdb_file.name == f"{base_d_id}.pdb":
                        resolved_path = pdb_file
                        break

        if resolved_path:
            top_pdb_paths.append(str(resolved_path.relative_to(BASE_DIR)))
            dest_path = LIVE_PDB_DIR / f"{target_d_id}.pdb"
            if not dest_path.exists():
                shutil.copy2(resolved_path, dest_path)
        else:
            top_pdb_paths.append(f"NOT_FOUND_{target_d_id}")

        top_scores_list.append(d['score'])

    manifest = {
        "run_id": run_id,
        "timestamp": timestamp_suffix,
        "top_pdb_paths": top_pdb_paths,
        "scores": top_scores_list
    }

    with open(final_dir / f'EvoPilot_{task_name}_top_hits_manifest.json', 'w') as f:
        json.dump(manifest, f, indent=4)

    print(f"🔄 Live EvoPilot_{task_name}_top_hits_manifest.json and Live PDB directory synchronized in {final_dir.name}")

    print("\n🏆 Live Top 10 Design Roster (Global Index prioritized by max_ipSAE):")
    header_format = "{:<5} | {:<16} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8} | {:<6} | {:<6}"
    print(header_format.format("Rank", "Design_ID", "ipSAE", "pTM", "iPTM", "pLDDT", "RMSD", "Reward", "Batch", "Index"))
    print("-" * 109)

    for rank, d in enumerate(ALL_DESIGNS_POOL[:10], 1):
        print(header_format.format(
            rank, d['id'][:16], f"{d['score']:.4f}", f"{d['ptm']:.4f}", f"{d['iptm']:.4f}",
            f"{d['plddt']:.2f}", f"{d['rmsd']:.2f}Å", f"{d['total_reward']:.4f}",
            str(d['batch_num']), str(d['idx_in_batch'])
        ))
    print("-" * 109)

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

    if len(GLOBAL_HITS) >= target_success_count:
        print(f"\n🎉 Threshold Attained! Successfully assimilated {target_success_count} rigorously vetted structural models.")
        break

    if evolution_iterate >= max_iterations:
        break

    print("🧹 Buffer memory cleared. Entering brief thermal cool-down before subsequent cycle initiation...")
    evolution_iterate += 1
    generation_round = 1
    designs_in_current_iterate = 0
    iterate_designs = []
    time.sleep(5)

# ---------------------------------------------------------
# 7. Final Execution Post-Mortem Output
# ---------------------------------------------------------
print(f"\n🛑 Auto-Pilot execution state terminated.")
if len(GLOBAL_HITS) >= target_success_count:
    print(f"🏆 OBJECTIVE COMPLETED: Hit quota satisfied yielding {len(GLOBAL_HITS)} high-affinity models.")
else:
    print(f"⚠️ MAXIMUM ITERATIONS TRIGGERED: Algorithm halted with {len(GLOBAL_HITS)} viable candidates isolated over {evolution_iterate} execution cycles.")

if master_log_path.exists():
    shutil.copy2(master_log_path, final_dir / f'{task_name}_EvoPilot_prediction_results.csv')

print(f"✅ Prediction results synced as {task_name}_EvoPilot_prediction_results.csv in: {final_dir.relative_to(BASE_DIR)}")
print(f"📂 Persistent Master Log registry accessible via: {master_log_path.relative_to(BASE_DIR)}")
print(f"📂 Physical PDB models retained in: {LIVE_PDB_DIR.relative_to(BASE_DIR)}")
