# Cell_15_Geometric_Surface_Patch_Scanning_Engine.py
# Requirement: Determine exposed surface residues based on anchored geometrical boundaries and sequentially process designs for derived hotspot patches. Read task_name from root, scan last_runs.txt for the correct isolated directory, and load the specific internal_settings.json from that directory to prevent cross-task contamination.
# ENHANCEMENT: Integrated "Live Top 10 Design Roster" reporting function to display the global best candidates across all processed patches after every cycle.
# ENHANCEMENT: Fixed fatal Regex truncation bug where the final directory name was prematurely cut off at the timestamp underscore.
# UPDATE: Persist ALL columns from the raw inference CSV into the master_log directly, appending patch_site and timestamp metadata without dropping any metrics.
# UPDATE: Shifted output directory creation and manifest generation into the live loop. top_hits_manifest.json and master_log.csv are dynamically built/appended inside the final timestamped directory.
# UPDATE: Implement dynamic PDB file synchronization to maintain a live directory of the Top 10 models.
# UPDATE: Enforced strict namespace separation. All output files and directories carry the 'GeoScan_' prefix.

import os, json, sys, subprocess, yaml, textwrap, shutil, time, random, csv, re
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.spatial import KDTree, Delaunay

print("🔍 Initializing Geometric Surface Scanning Engine...")

# ---------------------------------------------------------
# 1. Decoupled Configuration Loading via last_runs.txt
# ---------------------------------------------------------
BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
ROOT_SETTING = BASE_DIR / 'internal_settings.json'

if not ROOT_SETTING.exists():
    print("❌ Error: Root configuration missing. Please navigate to Section 0 and configure parameters.")
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

SCREENING_RESULTS_DIR = BASE_DIR / 'screening_results' / task_name
final_dir = SCREENING_RESULTS_DIR / target_dir_name
ISOLATED_SETTING = final_dir / 'internal_settings.json'

if not ISOLATED_SETTING.exists():
    print(f"❌ Error: Isolated configuration file missing in {final_dir.name}.")
    sys.exit(1)

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)

target_chains = cfg['target_chains']
anchor_str = str(cfg['anchor_residues'])
scan_margin = float(cfg['scan_margin'])
local_patch_radius = float(cfg['local_patch_radius'])
designs_per_patch = int(cfg['designs_per_patch'])
batch_size = int(cfg['scan_batch_size'])

print(f"✅ State Secured: Loaded settings from isolated workspace [{target_dir_name}]")
print(f"✅ Loaded global run_id: {run_id}")

anchor_res_list = [int(x.strip()) for x in anchor_str.split(',') if x.strip()]

SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

if not SOURCE_PDB_PATH.exists():
    print(f"❌ Error: Required processed PDB structure not found at {SOURCE_PDB_PATH}. Prior execution of Section 2 is mandatory.")
    sys.exit(1)

SESSION_NAME = f"GeoScan_{run_id}"
SESSION_MASTER_DIR = BASE_DIR / 'assets' / 'target_data' / SESSION_NAME
SESSION_MASTER_DIR.mkdir(parents=True, exist_ok=True)

print(f"📂 Master Scan Directory established at: {SESSION_MASTER_DIR.relative_to(BASE_DIR)}")

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

# ---------------------------------------------------------
# 2. Parse PDB for Spatial Coordinates & Amino Acid Nomenclature
# ---------------------------------------------------------
coords, res_ids, res_names = [], [], []

with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            res_names.append(line[17:20].strip())
            res_ids.append(int(line[22:26].strip()))
            coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])

coords, res_ids, res_names = np.array(coords), np.array(res_ids), np.array(res_names)
protein_kdtree = KDTree(coords)

SURFACE_NEIGHBOR_THRESHOLD = 24

# ---------------------------------------------------------
# 3. Anchor Validation & Geometric Convex Hull Construction
# ---------------------------------------------------------
anchor_coords = []
for a_res in anchor_res_list:
    if a_res in res_ids:
        idx = np.where(res_ids == a_res)[0][0]
        neighbors_10A = protein_kdtree.query_ball_point(coords[idx], r=10.0)
        if len(neighbors_10A) > SURFACE_NEIGHBOR_THRESHOLD:
            sys.exit(f"\n❌ FATAL ERROR: Specified Anchor {a_res} ({res_names[idx]}) is mathematically buried within the protein core!")
        anchor_coords.append(coords[idx])
    else:
        sys.exit(f"\n❌ FATAL ERROR: Requested Anchor Residue {a_res} cannot be mapped to target chain {target_chains}.")

if not anchor_coords:
    sys.exit("\n❌ Error: Geometry construction aborted. No validated anchor residues acquired.")

anchor_coords = np.array(anchor_coords)
shape_points = []
spacing = 1.0

n_anchors = len(anchor_coords)
if n_anchors == 1:
    shape_points = anchor_coords
elif n_anchors == 2:
    d = np.linalg.norm(anchor_coords[1] - anchor_coords[0])
    shape_points = np.linspace(anchor_coords[0], anchor_coords[1], max(2, int(d / spacing)))
elif n_anchors == 3:
    d1, d2 = np.linalg.norm(anchor_coords[1] - anchor_coords[0]), np.linalg.norm(anchor_coords[2] - anchor_coords[0])
    for u in np.linspace(0, 1, max(2, int(d1/spacing))):
        for v in np.linspace(0, 1-u, max(2, int(d2/spacing))):
            shape_points.append(anchor_coords[0] + u*(anchor_coords[1]-anchor_coords[0]) + v*(anchor_coords[2]-anchor_coords[0]))
    shape_points = np.array(shape_points)
else:
    hull = Delaunay(anchor_coords, qhull_options='QJ')
    min_b, max_b = np.min(anchor_coords, axis=0), np.max(anchor_coords, axis=0)
    grid_x, grid_y, grid_z = np.mgrid[min_b[0]:max_b[0]:spacing, min_b[1]:max_b[1]:spacing, min_b[2]:max_b[2]:spacing]
    grid_pts = np.vstack((grid_x.ravel(), grid_y.ravel(), grid_z.ravel())).T
    inside = hull.find_simplex(grid_pts) >= 0
    shape_points = grid_pts[inside]

shape_kdtree = KDTree(shape_points if shape_points.ndim == 2 else [shape_points])
candidate_indices = shape_kdtree.query_ball_tree(protein_kdtree, r=scan_margin)
candidate_idx_set = set([idx for sublist in candidate_indices for idx in sublist])

# ---------------------------------------------------------
# 4. Rigorous Topographic Filtration & Resume State Interception
# ---------------------------------------------------------
surface_residues_raw = []
for idx in candidate_idx_set:
    neighbors_10A = protein_kdtree.query_ball_point(coords[idx], r=10.0)
    if len(neighbors_10A) <= SURFACE_NEIGHBOR_THRESHOLD:
        surface_residues_raw.append(idx)

surface_residues = sorted(surface_residues_raw, key=lambda idx: res_ids[idx])

timestamp_suffix = run_id.split('_')[-1]

# Strict GeoScan Namespace applied - MIGRATED CHECKPOINT TO ISOLATED DIRECTORY
CHECKPOINT_CSV = final_dir / f'{run_id}_GeoScan_checkpoint.csv'
MASTER_LOG_CSV = final_dir / f'{run_id}_GeoScan_master_log.csv'

# Set up the live synchronized directory for physical PDB extraction
LIVE_PDB_DIR = final_dir / 'GeoScan_Live_Top10_PDBs'
LIVE_PDB_DIR.mkdir(parents=True, exist_ok=True)

print(f"📂 Live Final Artifact Directory established at: {final_dir.relative_to(BASE_DIR)}")

all_scan_results = []
global_design_pool = []
completed_res_ids = set()
existing_master_ids = set()

# Load Checkpoint (Resume State)
if CHECKPOINT_CSV.exists():
    try:
        df_checkpoint = pd.read_csv(CHECKPOINT_CSV)
        if not df_checkpoint.empty:
            all_scan_results = df_checkpoint.to_dict('records')
            for val in df_checkpoint['Center_Residue']:
                res_id_str = str(val).split('(')[0].strip()
                if res_id_str.isdigit():
                    completed_res_ids.add(int(res_id_str))
            print(f"📥 RESUME STATE DETECTED: Successfully loaded {len(completed_res_ids)} processed patches.")
    except Exception as e:
        print(f"⚠️ Warning: Checkpoint parsing error: {e}")

# Load existing Master Log to populate pool and IDs for exact resume consistency
if MASTER_LOG_CSV.exists():
    try:
        with open(MASTER_LOG_CSV, 'r', encoding='utf-8') as f_log:
            reader = csv.DictReader(f_log)
            for row in reader:
                d_id = row.get('design_id', '').strip()
                if not d_id: continue
                existing_master_ids.add(d_id)
                global_design_pool.append({
                    'id': d_id,
                    'score': float(row.get('af2folding_max_ipsae', row.get('max_ipSAE', -999.0))),
                    'ptm': float(row.get('af2folding_ptm_log', row.get('pTM', -999.0))),
                    'iptm': float(row.get('af2folding_i_ptm_log', row.get('iPTM', -999.0))),
                    'plddt': float(row.get('af2folding_plddt', row.get('pLDDT', -999.0))),
                    'rmsd': float(row.get('af2folding_rmsd', row.get('RMSD', -999.0))),
                    'reward': float(row.get('total_reward', -999.0)),
                    'dir': row.get('source_path', ''),
                    'pdb_path': row.get('pdb_path', '')
                })
        print(f"📥 MASTER LOG DETECTED: Re-synchronized {len(global_design_pool)} existing designs to leaderboard.")
    except Exception as e:
        print(f"⚠️ Warning: Master log sync error: {e}")

pending_surface_residues = [idx for idx in surface_residues if res_ids[idx] not in completed_res_ids]

# ---------------------------------------------------------
# 5. Detection Log Formatting
# ---------------------------------------------------------
print("\n" + "="*70)
print(f"🎯 ALGORITHMIC GEOMETRIC SCANNING SECTOR ESTABLISHED")
print(f"Geometry Parameters: {n_anchors} Fixed Anchors | Volumetric Expansion Margin: {scan_margin}Å")
print(f"Total Isolated Candidates: {len(surface_residues)} residues.")
print(f"Pending Execution Queue  : {len(pending_surface_residues)} residues remaining.")
print("-" * 70)

res_strings = [f"{res_ids[idx]}({res_names[idx]})" for idx in pending_surface_residues]
formatted_list = textwrap.fill(", ".join(res_strings), width=80, initial_indent="➤ ", subsequent_indent="  ")
print(formatted_list if res_strings else "➤ Queue Empty. All patches have been scanned.")
print("="*70)

if not pending_surface_residues:
    print("✅ Geometric scanning fully completed. Proceeding to final analytics.")
else:
    print("🚀 Queuing generative algorithmic pipelines targeting topographical patches...\n")

# ---------------------------------------------------------
# 6. Core Execution Loop: Patch Isolation & Candidate Synthesis
# ---------------------------------------------------------
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})

for i, idx in enumerate(pending_surface_residues, 1):
    loop_start_time = time.time()
    center_res = res_ids[idx]
    center_name = res_names[idx]

    local_neighbors = protein_kdtree.query_ball_point(coords[idx], r=local_patch_radius)
    patch_residues = sorted([res_ids[n] for n in local_neighbors])
    patch_str = ",".join(map(str, patch_residues))

    patch_run_name = f"{SESSION_NAME}_Res{center_res}"
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / patch_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)

    print(f"\n=======================================================")
    print(f"🔄 [Active Sweep {i}/{len(pending_surface_residues)}] Center Assignment: {center_res} ({center_name})")
    print(f"📂 Local Sandbox: {RUN_ISOLATED_DIR.relative_to(SESSION_MASTER_DIR)}")
    print(f"=======================================================")

    yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'
    with open(yaml_path, 'r') as f:
        yaml_data = yaml.safe_load(f)
    yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in patch_residues]
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    dynamic_seed = random.randint(1, 999999)
    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={patch_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={designs_per_patch} "
        f"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} "
        f"++generation.seed={dynamic_seed} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=False ++run_analyze=False"
    )

    process = subprocess.run(f"source env.sh && {cmd_str}", env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR), check=False)

    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{patch_run_name}'

    if process.returncode == 0:
        valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]

        if valid_csvs:
            target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
            try:
                df = pd.read_csv(target_csv)
                score_col = 'af2folding_max_ipsae' if 'af2folding_max_ipsae' in df.columns else 'total_reward'

                if score_col in df.columns:
                    df_sorted = df.sort_values(by=score_col, ascending=False)
                    top_score = df_sorted[score_col].max()

                    master_log_exists = MASTER_LOG_CSV.exists()
                    appended_count = 0
                    batch_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                    raw_fieldnames = list(df_sorted.columns)
                    master_fieldnames = ['patch_site', 'timestamp'] + raw_fieldnames
                    if 'design_id' not in master_fieldnames:
                        master_fieldnames.insert(2, 'design_id')

                    rows_to_write = []

                    for _, row in df_sorted.iterrows():
                        row_dict = row.to_dict()

                        base_d_id = str(row_dict.get('design_id', '')).strip() or f"Design_{row_dict.get('pdb_index', 0)}"
                        d_id = f"Res{center_res}_{base_d_id}"

                        if d_id in existing_master_ids: continue
                        existing_master_ids.add(d_id)

                        row_dict['design_id'] = d_id
                        row_dict['patch_site'] = f"{center_res}_{center_name}"
                        row_dict['timestamp'] = batch_timestamp
                        row_dict['source_path'] = str(inference_dir.relative_to(BASE_DIR))

                        rows_to_write.append(row_dict)

                        ipsae = float(row_dict.get(score_col, -999.0))
                        ptm = float(row_dict.get('af2folding_ptm_log', row_dict.get('complex_pTM', -999.0)))
                        iptm = float(row_dict.get('af2folding_i_ptm_log', row_dict.get('complex_ipTM', -999.0)))
                        plddt = float(row_dict.get('af2folding_plddt', row_dict.get('complex_pLDDT', -999.0)))
                        rmsd = float(row_dict.get('af2folding_rmsd', row_dict.get('binder_scRMSD_ca', -999.0)))
                        reward = float(row_dict.get('total_reward', -999.0))

                        global_design_pool.append({
                            'id': d_id, 'score': ipsae, 'ptm': ptm, 'iptm': iptm,
                            'plddt': plddt, 'rmsd': rmsd, 'reward': reward,
                            'dir': inference_dir, 'pdb_path': row_dict.get('pdb_path', '')
                        })
                        appended_count += 1

                    if rows_to_write:
                        with open(MASTER_LOG_CSV, 'a', encoding='utf-8', newline='') as f_log:
                            writer = csv.DictWriter(f_log, fieldnames=master_fieldnames, extrasaction='ignore')
                            if not master_log_exists:
                                writer.writeheader()
                            writer.writerows(rows_to_write)

                    result_entry = {'Center_Residue': f"{center_res} ({center_name})", f'Max_{score_col}': round(top_score, 4), 'Designs_Generated': len(df_sorted), 'Hotspot_Patch': patch_str}
                    all_scan_results.append(result_entry)
                    pd.DataFrame(all_scan_results).to_csv(CHECKPOINT_CSV, index=False)

                    print(f"💾 Log Aggregated: {appended_count} full-data designs recorded. Checkpoint updated.")

                    # --- DYNAMIC MANIFEST GENERATION & DELTA LIVE PDB SYNC ---
                    global_design_pool.sort(key=lambda x: x['score'], reverse=True)

                    current_top_ids = set([d['id'] for d in global_design_pool[:10]])

                    for existing_file in LIVE_PDB_DIR.glob('*.pdb'):
                        if existing_file.stem not in current_top_ids:
                            existing_file.unlink()

                    top_pdb_paths = []
                    top_scores_list = []

                    for d in global_design_pool[:10]:
                        target_d_id = d['id']
                        exact_pdb_path = d.get('pdb_path', '')
                        resolved_path = None

                        if exact_pdb_path and Path(exact_pdb_path).exists():
                            resolved_path = Path(exact_pdb_path)
                        else:
                            source_dir = Path(d['dir']) if isinstance(d.get('dir'), Path) else BASE_DIR / str(d.get('dir', ''))
                            if source_dir.exists():
                                for pdb_file in source_dir.rglob('*.pdb'):
                                    base_d_id = re.sub(r'^Res\d+_', '', target_d_id)
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

                    with open(final_dir / f'GeoScan_{task_name}_top_hits_manifest.json', 'w') as f:
                        json.dump(manifest, f, indent=4)

                    print(f"🔄 Live GeoScan_{task_name}_top_hits_manifest.json and Live PDB directory synchronized in {final_dir.name}")

                    print(f"\n🏆 Live Top 10 Design Roster (Global Index prioritized by max_ipSAE):")
                    header_format = "{:<5} | {:<26} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8}"
                    print(header_format.format("Rank", "Design_ID", "ipSAE", "pTM", "iPTM", "pLDDT", "RMSD", "Reward"))
                    print("-" * 105)
                    for rank, d in enumerate(global_design_pool[:10], 1):
                        print(header_format.format(
                            rank, d['id'], f"{d['score']:.4f}", f"{d['ptm']:.4f}",
                            f"{d['iptm']:.4f}", f"{d['plddt']:.2f}", f"{d['rmsd']:.2f}", f"{d['reward']:.4f}"
                        ))
                    print("-" * 105)

            except Exception as e:
                print(f"⚠️ Data Sync Failure for {center_res}: {e}")
        else:
            print(f"⚠️ Warning: No CSV output found in {inference_dir.name}.")
    else:
        print(f"⚠️ Alert: Pipeline crashed for {center_res}. Skipping.")

    cycle_duration = format_time(time.time() - loop_start_time)
    print(f"\n⏱️ Patch Sweep Completed in: {cycle_duration}")

    if i < len(pending_surface_residues):
        import gc; gc.collect()
        import torch
        if torch.cuda.is_available(): torch.cuda.empty_cache(); torch.cuda.ipc_collect()
        time.sleep(2)

# ---------------------------------------------------------
# 7. Final Post-Processing Report Output
# ---------------------------------------------------------
if all_scan_results:
    results_df = pd.DataFrame(all_scan_results)
    sort_col = [col for col in results_df.columns if col.startswith('Max_')][0]
    results_df = results_df.sort_values(by=sort_col, ascending=False)
    FINAL_CSV = final_dir / f'geometric_scan_results_FINAL_{run_id}.csv'
    results_df.to_csv(FINAL_CSV, index=False)
    if CHECKPOINT_CSV.exists(): os.remove(CHECKPOINT_CSV)

    if MASTER_LOG_CSV.exists():
        shutil.copy2(MASTER_LOG_CSV, final_dir / f'{task_name}_GeoScan_prediction_results.csv')

    print("\n🏆 ======================================================= 🏆")
    print("           GEOMETRIC SCANNING PROTOCOL CONCLUDED              ")
    print("🏆 ======================================================= 🏆")
    print(f"Total Patches Scanned: {len(results_df)}")
    print(f"\n📂 Comprehensive analytic report finalized: {FINAL_CSV.relative_to(BASE_DIR)}")
    print(f"📂 Prediction results synced as {task_name}_GeoScan_prediction_results.csv in: {final_dir.relative_to(BASE_DIR)}")
    print(f"📂 Global master log DETAIL registry: {MASTER_LOG_CSV.relative_to(BASE_DIR)}")
    print(f"📂 Physical PDB models retained in: {LIVE_PDB_DIR.relative_to(BASE_DIR)}")
else:
    print("\n🛑 Geometric Scanning Protocol Terminated. No viable candidates found.")

# ==============================================================================
# Purpose: Execute a geometric patch scanning engine isolated from generic global configurations. It extracts the active task_name from the root, utilizes regex to pinpoint the corresponding final output directory documented in last_runs.txt, and exclusively applies the internal_settings.json anchored within that secured location.
# Upstream Code: Architected to align with the identical namespace separation protocols established for Cell_7b (AutoPilot) and initialized by Section 2.
# Runtime Environment: Google Colab.
# Generation Time: 2026-04-13 20:43 EDT.
# Changed Lines:
# - Lines 33-35: Fixed Regex pattern matching `(final_\d+_\d+)` to properly encompass timestamp trailing numbers, preventing truncated non-existent directories.
# - Lines 129-130: Repointed Checkpoint and Master Log CSV physical assignments directly toward the resolved final_dir to fix the physical scoping leak.
# ==============================================================================