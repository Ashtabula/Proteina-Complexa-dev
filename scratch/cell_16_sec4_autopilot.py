# Cell_7b_Autonomous_Generation_Loop.py
# Requirement: Execute an automated loop for high-throughput generation and evaluation. Read task_name from root, scan last_runs.txt for the correct isolated directory.
# ENHANCEMENT: Fixed fatal Regex truncation bug where the final directory name was prematurely cut off at the timestamp underscore (e.g., final_20260414 instead of final_20260414_003553).
# ENHANCEMENT: Fixed fatal ID collision bug where sequential batches outputting identical base 'design_id's were erroneously skipped by the global existing_master_ids deduplication set.
# UPDATE: Implemented dynamic 'Cycle{X}_' prefix injection during CSV parsing to ensure global uniqueness, alongside Regex-based stripping during live PDB synchronization.

import os, json, sys, time, subprocess, csv, datetime, shutil, math, random, gc, re
from pathlib import Path
import torch

print("🔍 Initializing Auto-Pilot Engine...")

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
        # [BUG FIX]: Updated Regex from (final_\d+) to (final_\d+_\d+) to correctly capture the full timestamped directory name
        pattern = rf"Section2_TargetPreprocess \| Run_ID: ({re.escape(task_name)}_\d+_\d+) \| Dir: (final_\d+_\d+)"
        for line in reversed(lines):
            match = re.search(pattern, line)
            if match:
                run_id = match.group(1)
                target_dir_name = match.group(2)
                break

if not run_id or not target_dir_name:
    print(f"❌ Error: No valid run history found for task [{task_name}] in last_runs.txt. Run Section 2 first.")
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

print(f"✅ State Secured: Loaded settings from isolated workspace [{target_dir_name}]")
print(f"🤖 Auto-Pilot Engine Activated for Target: [{task_name}]")
print(f"🎯 Objective Strategy: Capture {target_success_count} qualified hits surpassing threshold {target_threshold}.")
print(f"🔄 Loop Matrix: Designing {designs_per_loop} structures per cycle (Maximum threshold: {max_iterations} cycles).")

# ---------------------------------------------------------
# 2. Tracking Variables, Logging & Master Hierarchy Setup
# ---------------------------------------------------------
ALL_DESIGNS_POOL = []
GLOBAL_HITS = []
existing_master_ids = set()
max_loop_found = 0

master_log_path = final_dir / f"{run_id}_AutoPilot_master_log.csv"
LIVE_PDB_DIR = final_dir / 'AutoPilot_Live_Top10_PDBs'
LIVE_PDB_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

if not SOURCE_PDB_PATH.exists():
    print(f"❌ Error: Required source PDB structure not found at {SOURCE_PDB_PATH}.")
    sys.exit(1)

SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
SESSION_NAME = f"AutoPilot_{task_name}_{SESSION_TIMESTAMP}"
SESSION_MASTER_DIR = BASE_DIR / 'assets' / 'target_data' / SESSION_NAME
SESSION_MASTER_DIR.mkdir(parents=True, exist_ok=True)

timestamp_suffix = run_id.split('_')[-1]

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})

# ---------------------------------------------------------
# 3. State Hydration (Breakpoint Resume Protocol)
# ---------------------------------------------------------
if master_log_path.exists():
    try:
        with open(master_log_path, 'r', encoding='utf-8') as f_log:
            reader = csv.DictReader(f_log)
            for row in reader:
                d_id = row.get('design_id', '').strip()
                if not d_id: continue
                existing_master_ids.add(d_id)

                try:
                    session_loop = int(row.get('session_loop', 0))
                    max_loop_found = max(max_loop_found, session_loop)
                except ValueError:
                    session_loop = 0

                ipsae_val = float(row.get('af2folding_max_ipsae', row.get('max_ipSAE', row.get('self_complex_max_ipAE', row.get('complex_i_pAE', -999.0)))))
                ptm_val = float(row.get('af2folding_ptm_log', row.get('pTM', row.get('self_complex_pTM', row.get('complex_pTM', -999.0)))))
                iptm_val = float(row.get('af2folding_i_ptm_log', row.get('iPTM', row.get('self_complex_i_pTM', row.get('complex_ipTM', -999.0)))))
                plddt_val = float(row.get('af2folding_plddt', row.get('pLDDT', row.get('self_complex_pLDDT', row.get('complex_pLDDT', -999.0)))))
                rmsd_val = float(row.get('af2folding_rmsd', row.get('RMSD', row.get('self_binder_scRMSD_ca', row.get('binder_scRMSD_ca', -999.0)))))
                total_reward = float(row.get('total_reward', -999.0))

                design_entry = {
                    'id': d_id, 'score': ipsae_val, 'ptm': ptm_val, 'iptm': iptm_val,
                    'plddt': plddt_val, 'rmsd': rmsd_val, 'total_reward': total_reward,
                    'batch_num': session_loop, 'idx_in_batch': 0,
                    'dir': row.get('source_path', ''),
                    'pdb_path': row.get('pdb_path', '')
                }
                ALL_DESIGNS_POOL.append(design_entry)
                if ipsae_val >= target_threshold:
                    if not any(h['id'] == d_id for h in GLOBAL_HITS):
                        GLOBAL_HITS.append(design_entry)

        print(f"📥 RESUME STATE DETECTED: Synchronized {len(ALL_DESIGNS_POOL)} historical designs. Highest loop completed: {max_loop_found}")
    except Exception as e:
        print(f"⚠️ Warning: Master log parsing error during hydration: {e}")

# ---------------------------------------------------------
# 4. High-Throughput Engine Execution Loop
# ---------------------------------------------------------
global_start_time = time.time()
current_iteration = max_loop_found

while current_iteration < max_iterations and len(GLOBAL_HITS) < target_success_count:
    current_iteration += 1
    loop_start_time = time.time()
    batch_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current_seed = random.randint(1, 1000000)
    print(f"\n🔑 DEBUG: Seed used for Cycle {current_iteration} = {current_seed}")

    current_run_name = f"{SESSION_NAME}_Cycle{current_iteration}"
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / current_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)

    print(f"\n=======================================================")
    print(f"🔄 Auto-Pilot Cycle Iteration [{current_iteration}/{max_iterations}] Commencing...")
    print(f"📂 Cycle Sandbox: {RUN_ISOLATED_DIR.relative_to(SESSION_MASTER_DIR)}")
    print(f"=======================================================")

    num_batches = math.ceil(designs_per_loop / batch_size)
    total_designs = num_batches * batch_size

    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={current_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={total_designs} "
        f"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=True ++run_analyze=True ++seed={current_seed}"
    )

    print(f"🔥 Transmitting execution command to the underlying engine (Seed: {current_seed})...")

    iter_start_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🕒 Cycle {current_iteration} Start Time: {iter_start_str}")
    if current_iteration > (max_loop_found + 1):
        avg_cycle_time = (time.time() - global_start_time) / (current_iteration - max_loop_found - 1)
        remaining_cycles = max_iterations - current_iteration + 1
        eta_seconds = avg_cycle_time * remaining_cycles
        eta_str = (datetime.datetime.now() + datetime.timedelta(seconds=eta_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        print(f"⏳ Estimated Time of Completion (ETA) for max cycles: {eta_str}")
    else:
        print(f"⏳ Estimated Time of Completion (ETA): Calculating after current cycle...")

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
        time.sleep(3)
        continue

    # ---------------------------------------------------------
    # 5. Report Parsing & Dynamic Leaderboard
    # ---------------------------------------------------------
    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{current_run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]

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
                    # [BUG FIX]: Namespace injection to prevent silent design dropping across identical cycles
                    base_d_id = row.get('design_id', '').strip() or f"Design_{row.get('pdb_index', i)}"
                    d_id = f"Cycle{current_iteration}_{base_d_id}"

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
                    row['session_loop'] = current_iteration
                    row['timestamp'] = batch_timestamp
                    row['source_path'] = str(inference_dir)
                    rows_to_write.append(row)

                    design_entry = {
                        'id': d_id, 'score': ipsae_val, 'ptm': ptm_val, 'iptm': iptm_val,
                        'plddt': plddt_val, 'rmsd': rmsd_val, 'total_reward': total_reward,
                        'batch_num': current_iteration, 'idx_in_batch': i + 1,
                        'dir': str(inference_dir), 'loop': current_iteration,
                        'pdb_path': row.get('pdb_path', '')
                    }
                    ALL_DESIGNS_POOL.append(design_entry)
                    new_entries_this_cycle += 1

                    if ipsae_val >= target_threshold:
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

    # ---------------------------------------------------------
    # 6. Cycle Summary, Live Manifest & Metrics Display
    # ---------------------------------------------------------
    cycle_duration = format_time(time.time() - loop_start_time)
    print(f"\n⏱️ Cycle {current_iteration} Operational Duration: {cycle_duration}")
    print(f"📈 Verified Candidates Captured (ipSAE >= {target_threshold}): {len(GLOBAL_HITS)} / {target_success_count}")

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
                    # [BUG FIX]: Prefix dynamic stripping to resolve physical PDBs locally
                    base_d_id = re.sub(r'^Cycle\d+_', '', target_d_id)
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

    with open(final_dir / f'AutoPilot_{task_name}_top_hits_manifest.json', 'w') as f:
        json.dump(manifest, f, indent=4)

    print(f"🔄 Live AutoPilot_{task_name}_top_hits_manifest.json and Live PDB directory synchronized in {final_dir.name}")

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

    if current_iteration < max_iterations:
        print("🧹 Buffer memory cleared. Entering brief thermal cool-down before subsequent cycle initiation...")
        time.sleep(5)

# ---------------------------------------------------------
# 7. Final Execution Post-Mortem Output
# ---------------------------------------------------------
print(f"\n🛑 Auto-Pilot execution state terminated.")
if len(GLOBAL_HITS) >= target_success_count:
    print(f"🏆 OBJECTIVE COMPLETED: Hit quota satisfied yielding {len(GLOBAL_HITS)} high-affinity models.")
else:
    print(f"⚠️ MAXIMUM ITERATIONS TRIGGERED: Algorithm halted with {len(GLOBAL_HITS)} viable candidates isolated over {current_iteration} execution cycles.")

if master_log_path.exists():
    shutil.copy2(master_log_path, final_dir / f'{task_name}_AutoPilot_prediction_results.csv')

print(f"✅ Prediction results synced as {task_name}_AutoPilot_prediction_results.csv in: {final_dir.relative_to(BASE_DIR)}")
print(f"📂 Persistent Master Log registry accessible via: {master_log_path.relative_to(BASE_DIR)}")
print(f"📂 Physical PDB models retained in: {LIVE_PDB_DIR.relative_to(BASE_DIR)}")

# ==============================================================================
# Purpose: Decoupled Auto-Pilot looping execution engine with robust Regex workspace resolution and strict Namespace Collision injection tracking.
# Upstream Code: Section 2 directory generation and internal_settings.json isolation.
# Runtime Environment: Google Colab.
# Generation Time: 2026-04-13 20:37 EDT.
# Changed Lines:
# - Lines 33-35: Fixed Regex pattern matching `(final_\d+_\d+)` to properly encompass timestamp trailing numbers, preventing truncated non-existent directories.
# - Lines 217-219: Implemented dynamic ID prefix injection `d_id = f"Cycle{current_iteration}_{base_d_id}"` ensuring persistent master log arrays do not silently drop subsequent batch duplicates.
# - Lines 294-297: RegEx `re.sub` dynamically slices prefix assignments prior to filesystem PDB globbing.
# ==============================================================================