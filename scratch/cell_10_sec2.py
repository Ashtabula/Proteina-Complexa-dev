
# Cell_18_Evolutionary_Algorithm_Pilot_(EvoPilot).py
# Requirement: Execute an automated evolutionary loop with true selection, mutation (hotspot updating), and a ROLLBACK mechanism to prevent generation degradation.
# ENHANCEMENT: Restructured to Dual-Loop Architecture (Iterate for Evolution, Round for Batch Generation) to ensure 48 designs are fully collected before evolving.
# ENHANCEMENT: Integrated rigorous KDTree <4.5A atomic contact scoring for objective weak hotspot elimination and neo-hotspot discovery.
# UPDATE: Implemented dynamic 'Iterate{X}_Round{Y}_' prefix injection during CSV parsing to ensure global uniqueness and correct chronological mapping.
# UPDATE: Integrated True Evolutionary Feedback Loop with Regression Detection [ROLLBACK] logic.
# UPDATE: Live In-Loop py3Dmol Visualization Rendering. Displays the Top 1 structure after every generation with Target(Mesh), Binder(Green), Base Hotspots(Orange), Neo-Hotspots(Red), and Binder N-Term(Blue).
# UPDATE: Fixed critical coordinate pollution bug in Neo-Hotspot discovery. Mapped AF2 generation coordinates backward to Natural ground-truth coordinates before injecting into the evolutionary pool.

import os, json, sys, time, subprocess, csv, datetime, shutil, math, random, gc, re, yaml
from pathlib import Path
import numpy as np
from scipy.spatial import KDTree
import torch
import py3Dmol
from IPython.display import display, HTML

print("🔍 Initializing True EvoPilot Engine (Iterate/Round Architecture)...")

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
    print(f"❌ Error: No valid run history found for task [{task_name}] in last_runs.txt. Run Section 2 first.")
    sys.exit(1)

final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name
ISOLATED_SETTING = final_dir / 'internal_settings.json'
YAML_PATH = final_dir / f'targets_dict_{run_id}.yaml'

if not ISOLATED_SETTING.exists():
    print(f"❌ Error: Isolated configuration file missing in {final_dir.name}.")
    sys.exit(1)

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)

target_threshold = float(cfg.get('evo_target_threshold', cfg.get('target_threshold', 0.85)))
target_success_count = int(cfg.get('evo_target_success_count', cfg.get('target_success_count', 10)))
designs_per_loop = int(cfg.get('evo_designs_per_loop', cfg.get('designs_per_loop', 48)))
max_iterations = int(cfg.get('evo_max_iterations', cfg.get('max_iterations', 10)))
batch_size = int(cfg.get('generation_batch_size', 8))

evo_max_hotspots = int(cfg.get('evo_max_hotspots', 8))
evo_update_count = int(cfg.get('evo_update_count', 2))
evo_strict_rmsd_filter = bool(cfg.get('evo_strict_rmsd_filter', True))

target_chain = str(cfg.get('target_chains', 'A')).split(',')[0].strip()
initial_hotspots_input = str(cfg.get('hotspots_input', ''))

print(f"✅ State Secured: Loaded settings from isolated workspace [{target_dir_name}]")
print(f"🤖 EvoPilot Engine Activated for Target: [{task_name}]")
print(f"🎯 Objective: Capture {target_success_count} hits (Threshold: {target_threshold}).")
print(f"🔄 Evolution: {designs_per_loop} designs/Iterate (Max {max_iterations} Iterates).")

# ---------------------------------------------------------
# 2. Tracking Variables & Master Hierarchy Setup
# ---------------------------------------------------------
ALL_DESIGNS_POOL = []
GLOBAL_HITS = []
existing_master_ids = set()

evolution_iterate = 1
generation_round = 1
designs_in_current_iterate = 0

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

# ---------------------------------------------------------
# 3. State Hydration (Dual-Loop Resume Protocol)
# ---------------------------------------------------------
if master_log_path.exists():
    try:
        max_iterate_found = 1
        max_round_found = 0

        with open(master_log_path, 'r', encoding='utf-8') as f_log:
            reader = csv.DictReader(f_log)
            for row in reader:
                d_id = row.get('design_id', '').strip()
                if not d_id: continue
                existing_master_ids.add(d_id)

                match = re.search(r'^Iterate(\d+)_Round(\d+)_', d_id)
                it_val, rd_val = 1, 0
                if match:
                    it_val = int(match.group(1))
                    rd_val = int(match.group(2))
                    max_iterate_found = max(max_iterate_found, it_val)
                    if it_val == max_iterate_found:
                        max_round_found = max(max_round_found, rd_val)

                hs_str = row.get('active_hotspots', '')
                hs_list = [int(x) for x in hs_str.split(',') if x.strip().isdigit()] if hs_str else []

                ipsae_val = float(row.get('af2folding_max_ipsae', row.get('max_ipSAE', -999.0)))
                design_entry = {
                    'id': d_id, 'score': ipsae_val,
                    'ptm': float(row.get('af2folding_ptm_log', row.get('pTM', -999.0))),
                    'iptm': float(row.get('af2folding_i_ptm_log', row.get('iPTM', -999.0))),
                    'plddt': float(row.get('af2folding_plddt', row.get('pLDDT', -999.0))),
                    'rmsd': float(row.get('af2folding_rmsd', row.get('RMSD', -999.0))),
                    'total_reward': float(row.get('total_reward', -999.0)),
                    'iterate': it_val, 'round': rd_val,
                    'dir': row.get('source_path', ''),
                    'pdb_path': row.get('pdb_path', ''),
                    'hotspots': hs_list
                }
                ALL_DESIGNS_POOL.append(design_entry)
                if ipsae_val >= target_threshold and not any(h['id'] == d_id for h in GLOBAL_HITS):
                    GLOBAL_HITS.append(design_entry)

        evolution_iterate = max_iterate_found
        generation_round = max_round_found + 1 if max_round_found > 0 else 1
        designs_in_current_iterate = len([d for d in ALL_DESIGNS_POOL if d.get('iterate') == evolution_iterate])

        print(f"📥 RESUME STATE DETECTED: Jumped to Iterate {evolution_iterate}, Round {generation_round} ({designs_in_current_iterate} designs collected in this Iterate).")
    except Exception as e:
        print(f"⚠️ Warning: Master log parsing error during hydration: {e}")

# ---------------------------------------------------------
# 4. Evolutionary Execution Loop (Iterate & Round System)
# ---------------------------------------------------------
global_start_time = time.time()

active_hotspots = [int(x.strip()) for x in initial_hotspots_input.split(',') if x.strip().isdigit()]
prev_iterate_state = None

# Restore Hotspot Memory if resuming
if evolution_iterate > 1:
    gen_pool = [d for d in ALL_DESIGNS_POOL if d['iterate'] == evolution_iterate]
    if gen_pool and gen_pool[0].get('hotspots'):
        active_hotspots = gen_pool[0]['hotspots']
    print(f"🧠 Hotspot Memory Restored: {','.join(map(str, active_hotspots))}")

while evolution_iterate <= max_iterations and len(GLOBAL_HITS) < target_success_count:

    # -----------------------------------------------------------------
    # A. SELECTION, MUTATION & ROLLBACK (Triggered ONLY when designs collected)
    # -----------------------------------------------------------------
    if designs_in_current_iterate >= designs_per_loop:
        print(f"\n🧪 Iterate {evolution_iterate} Accumulation Complete ({designs_in_current_iterate} designs). Executing Evaluation...")

        gen_pool = [d for d in ALL_DESIGNS_POOL if d['iterate'] == evolution_iterate]
        top_1_for_viz = None
        neo_highlight = []
        base_highlight = list(active_hotspots)

        if evo_strict_rmsd_filter:
            gen_pool = [d for d in gen_pool if d['rmsd'] != -999.0 and d['rmsd'] <= 10.0]

        if not gen_pool:
            print("⚠️ All designs failed RMSD filter. Forcing dummy score to prevent crash.")
            current_iterate_best = -999.0
        else:
            current_iterate_best = max([d['score'] for d in gen_pool])

        # [ROLLBACK DETECTION]
        if prev_iterate_state is not None and current_iterate_best < prev_iterate_state['best_score']:
            print(f"⚠️ Regression Detected (Max Score {current_iterate_best:.4f} < Previous {prev_iterate_state['best_score']:.4f})")
            print(f"⏪ [ROLLBACK] Reverting to Iterate {evolution_iterate - 1} configuration.")

            active_hotspots = list(prev_iterate_state['active_hotspots'])
            neo_candidates = prev_iterate_state['neo_sorted']
            drop_count = min(evo_update_count, max(0, len(active_hotspots) - 2))

            if drop_count > 0:
                active_hotspots = active_hotspots[:-drop_count]
                new_neos = neo_candidates[drop_count : drop_count * 2]
                active_hotspots.extend(new_neos)
                neo_highlight = list(new_neos)

            active_hotspots = sorted(list(set(active_hotspots)))
            base_highlight = [h for h in active_hotspots if h not in neo_highlight]
            print(f"👉 Rollback interface map: {','.join(map(str, active_hotspots))}")

        # [MUTATION PATH] (KDTree Spatial Analysis)
        elif gen_pool:
            print(f"🧬 [MUTATION] Analyzing atomic contacts for Neo-Hotspots...")
            contact_scores = {}
            top_5 = sorted(gen_pool, key=lambda x: x['score'], reverse=True)[:5]
            if top_5: top_1_for_viz = top_5[0]

            # [CRITICAL]: Build AF2 -> Natural Mapping from Source PDB
            af2_to_natural_map = {}
            if SOURCE_PDB_PATH.exists():
                orig_resis = []
                with open(SOURCE_PDB_PATH, 'r') as f_orig:
                    for line in f_orig:
                        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chain:
                            orig_resis.append(int(line[22:26].strip()))
                af2_to_natural_map = {i + 1: orig for i, orig in enumerate(orig_resis)}

            for rank_idx, d in enumerate(top_5):
                pdb_path = final_dir / 'EvoPilot_Live_Top10_PDBs' / f"{d['id']}.pdb"
                if not pdb_path.exists(): continue

                chains = {}
                for line in open(pdb_path):
                    if line.startswith("ATOM") and line[12:16].strip() == "CA":
                        c = line[21]
                        if c not in chains: chains[c] = []
                        chains[c].append((int(line[22:26].strip()), np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])))

                if len(chains) >= 2:
                    sorted_chains = sorted(chains.keys(), key=lambda c: len(chains[c]))
                    binder_ca = [x[1] for x in chains[sorted_chains[0]]]

                    target_ca = {}
                    for c in sorted_chains[1:]:
                        for res_id, coord in chains[c]: target_ca[res_id] = coord

                    if binder_ca and target_ca:
                        b_tree = KDTree(binder_ca)
                        for res_id, coord in target_ca.items():
                            if b_tree.query(coord, k=1)[0] < 4.5:
                                # [REVERSE TRANSLATION]: AF2 coordinate mapped back to Natural Truth
                                natural_res_id = af2_to_natural_map.get(res_id)
                                if natural_res_id:
                                    contact_scores[natural_res_id] = contact_scores.get(natural_res_id, 0.0) + d['score'] * (1.0 / (rank_idx + 1))

            all_contact_res = [x[0] for x in sorted(contact_scores.items(), key=lambda x: x[1], reverse=True)]
            current_active_scores = sorted([(res, contact_scores.get(res, 0.0)) for res in active_hotspots], key=lambda x: x[1], reverse=True)
            neo_sorted = [res for res in all_contact_res if res not in active_hotspots and contact_scores[res] > 0.0]

            prev_iterate_state = {
                'best_score': current_iterate_best,
                'active_hotspots': list(active_hotspots),
                'contact_scores': contact_scores,
                'neo_sorted': neo_sorted
            }

            drop_count = min(evo_update_count, max(0, len(active_hotspots) - 2))
            if drop_count > 0:
                survivors = [x[0] for x in current_active_scores[:-drop_count]]
                neo_highlight = neo_sorted[:drop_count]
                active_hotspots = sorted(list(set(survivors + neo_highlight)))
                base_highlight = survivors
            print(f"👉 New target interface map: {','.join(map(str, active_hotspots))}")

        # Synchronize dynamic YAML for next iterate
        if YAML_PATH.exists():
            with open(YAML_PATH, 'r') as f:
                yaml_data = yaml.safe_load(f)
            yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chain}{r}" for r in active_hotspots]
            with open(YAML_PATH, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        # -------------------------------------------------------------
        # IN-LOOP py3Dmol TOP 1 VISUALIZATION FOR EVO PILOT (AF2 Mapping Fixed)
        # -------------------------------------------------------------
        if top_1_for_viz:
            display(HTML(f"<h3>📸 Evolutionary Top 1 Snapshot | Iterate: {evolution_iterate} | ID: {top_1_for_viz['id']}</h3>"))
            top_1_path = final_dir / 'EvoPilot_Live_Top10_PDBs' / f"{top_1_for_viz['id']}.pdb"

            if top_1_path.exists():
                af2_mapping = {}
                if SOURCE_PDB_PATH.exists():
                    orig_resis = []
                    with open(SOURCE_PDB_PATH, 'r') as f_orig:
                        for line in f_orig:
                            if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chain:
                                orig_resis.append(line[22:26].strip())
                    af2_mapping = {int(orig): str(i + 1) for i, orig in enumerate(orig_resis)}

                mapped_base_highlight = [af2_mapping[x] for x in base_highlight if x in af2_mapping]
                mapped_neo_highlight = [af2_mapping[x] for x in neo_highlight if x in af2_mapping]

                with open(top_1_path, 'r') as f: pdb_str = f.read()

                seq_lens = {}
                b_first_resi = None
                for line in pdb_str.split('\n'):
                    if line.startswith("ATOM") and line[12:16].strip() == "CA":
                        c = line[21]
                        if c not in seq_lens: seq_lens[c] = 0
                        seq_lens[c] += 1

                sc = sorted(seq_lens.keys(), key=lambda x: seq_lens[x])
                b_chain = [sc[0]] if sc else []
                t_chains = sc[1:] if len(sc)>1 else []

                if b_chain:
                    for line in pdb_str.split('\n'):
                        if line.startswith("ATOM") and line[21] == b_chain[0]:
                            b_first_resi = line[22:26].strip()
                            break

                viewer = py3Dmol.view(width=800, height=500)
                viewer.addModel(pdb_str, 'pdb')

                if t_chains:
                    viewer.setStyle({'chain': t_chains}, {'cartoon': {'color': '#A9A9A9', 'opacity': 0.7}})
                    viewer.addSurface(py3Dmol.SES, {'color': '#A9A9A9', 'wireframe': True}, {'chain': t_chains})

                if t_chains and mapped_base_highlight:
                    viewer.setStyle({'chain': t_chains[0], 'resi': mapped_base_highlight}, {'cartoon': {'color': 'orange', 'opacity': 1.0}})
                    viewer.addSurface(py3Dmol.SES, {'color': 'orange', 'opacity': 1.0}, {'chain': t_chains[0], 'resi': mapped_base_highlight})

                if t_chains and mapped_neo_highlight:
                    viewer.setStyle({'chain': t_chains[0], 'resi': mapped_neo_highlight}, {'cartoon': {'color': 'red', 'opacity': 1.0}})
                    viewer.addSurface(py3Dmol.SES, {'color': 'red', 'opacity': 1.0}, {'chain': t_chains[0], 'resi': mapped_neo_highlight})

                if b_chain:
                    viewer.setStyle({'chain': b_chain}, {'cartoon': {'color': 'lime', 'opacity': 1.0}})
                    viewer.addSurface(py3Dmol.SES, {'color': 'lime', 'opacity': 1.0}, {'chain': b_chain})

                if b_chain and b_first_resi:
                    viewer.setStyle({'chain': b_chain[0], 'resi': b_first_resi}, {'cartoon': {'color': 'blue', 'opacity': 1.0}})
                    viewer.addSurface(py3Dmol.SES, {'color': 'blue', 'opacity': 1.0}, {'chain': b_chain[0], 'resi': b_first_resi})

                viewer.zoomTo(); viewer.show()

        evolution_iterate += 1
        generation_round = 1
        designs_in_current_iterate = 0

        print("🧹 Evolution calculations complete. Entering brief thermal cool-down before next Generation Cycle...")
        time.sleep(5)
        continue

    # -----------------------------------------------------------------
    # B. GENERATION ROUND (Batch Execution)
    # -----------------------------------------------------------------
    loop_start_time = time.time()
    batch_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_seed = random.randint(1, 1000000)

    current_run_name = f"{SESSION_NAME}_Iter{evolution_iterate}_Rnd{generation_round}"
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / current_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)

    print(f"\n=======================================================")
    print(f"🔄 Evolution Generation [Iterate {evolution_iterate} - Round {generation_round}]: {designs_in_current_iterate}/{designs_per_loop} designs collected.")
    print(f"📂 Round Sandbox: {RUN_ISOLATED_DIR.relative_to(SESSION_MASTER_DIR)}")
    print(f"=======================================================")

    designs_to_run = min(batch_size, designs_per_loop - designs_in_current_iterate)

    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={current_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={designs_to_run} "
        f"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=True ++run_analyze=True ++seed={current_seed}"
    )

    print(f"🔥 Transmitting generation command (Generating {designs_to_run} structures, Seed: {current_seed})...")

    process = subprocess.Popen(
        f"source env.sh && {cmd_str}",
        env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    for line in process.stdout: print(line, end='', flush=True)
    process.wait()

    if process.returncode != 0:
        print(f"❌ Warning: Engine crashed (Error Code {process.returncode})! Retrying in next cycle.")
        time.sleep(3)
        continue

    # ---------------------------------------------------------
    # C. CSV Parsing & Tracking
    # ---------------------------------------------------------
    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{current_run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]

    if valid_csvs:
        target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
        with open(target_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            master_fieldnames = ['session_loop', 'timestamp', 'source_path', 'active_hotspots'] + list(reader.fieldnames)
            if 'design_id' not in master_fieldnames: master_fieldnames.insert(3, 'design_id')

            new_entries = 0
            rows_to_write = []

            for i, row in enumerate(reader):
                try:
                    base_d_id = row.get('design_id', '').strip() or f"Design_{row.get('pdb_index', i)}"
                    d_id = f"Iterate{evolution_iterate}_Round{generation_round}_{base_d_id}"

                    if d_id in existing_master_ids: continue
                    existing_master_ids.add(d_id)

                    ipsae_val = float(row.get('af2folding_max_ipsae', row.get('max_ipSAE', -999.0)))

                    row['design_id'] = d_id
                    row['session_loop'] = evolution_iterate
                    row['timestamp'] = batch_timestamp
                    row['source_path'] = str(inference_dir)
                    row['active_hotspots'] = ','.join(map(str, active_hotspots))
                    rows_to_write.append(row)

                    design_entry = {
                        'id': d_id, 'score': ipsae_val,
                        'ptm': float(row.get('af2folding_ptm_log', -999.0)),
                        'iptm': float(row.get('af2folding_i_ptm_log', -999.0)),
                        'plddt': float(row.get('af2folding_plddt', -999.0)),
                        'rmsd': float(row.get('af2folding_rmsd', -999.0)),
                        'total_reward': float(row.get('total_reward', -999.0)),
                        'iterate': evolution_iterate, 'round': generation_round,
                        'dir': str(inference_dir), 'pdb_path': row.get('pdb_path', ''),
                        'hotspots': list(active_hotspots)
                    }
                    ALL_DESIGNS_POOL.append(design_entry)
                    new_entries += 1
                    designs_in_current_iterate += 1

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
    # D. Live Top 10 Synchronization
    # ---------------------------------------------------------
    ALL_DESIGNS_POOL.sort(key=lambda x: x['score'], reverse=True)
    current_top_ids = set([d['id'] for d in ALL_DESIGNS_POOL[:10]])

    for existing_file in LIVE_PDB_DIR.glob('*.pdb'):
        if existing_file.stem not in current_top_ids: existing_file.unlink()

    top_pdb_paths, top_scores_list = [], []
    for d in ALL_DESIGNS_POOL[:10]:
        target_d_id = d['id']
        resolved_path = None
        source_dir = Path(d['dir'])
        if source_dir.exists():
            for pdb_file in source_dir.rglob('*.pdb'):
                base_d_id = re.sub(r'^Iterate\d+_Round\d+_', '', target_d_id)
                if base_d_id.lower() in pdb_file.name.lower() or pdb_file.name == f"{base_d_id}.pdb":
                    resolved_path = pdb_file
                    break

        if resolved_path:
            top_pdb_paths.append(str(resolved_path.relative_to(BASE_DIR)))
            dest_path = LIVE_PDB_DIR / f"{target_d_id}.pdb"
            if not dest_path.exists(): shutil.copy2(resolved_path, dest_path)
        else:
            top_pdb_paths.append(f"NOT_FOUND_{target_d_id}")
        top_scores_list.append(d['score'])

    manifest = {
        "run_id": run_id, "timestamp": timestamp_suffix,
        "active_hotspots_state": active_hotspots,
        "top_pdb_paths": top_pdb_paths, "scores": top_scores_list
    }
    with open(final_dir / f'EvoPilot_{task_name}_top_hits_manifest.json', 'w') as f:
        json.dump(manifest, f, indent=4)

    print("\n🏆 Live Top 10 Design Roster (Global Index prioritized by max_ipSAE):")
    header_format = "{:<5} | {:<22} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8} | {:<8} | {:<5} | {:<5}"
    print(header_format.format("Rank", "Design_ID", "ipSAE", "pTM", "iPTM", "pLDDT", "RMSD", "Reward", "Iter", "Round"))
    print("-" * 115)
    for rank, d in enumerate(ALL_DESIGNS_POOL[:10], 1):
        print(header_format.format(
            rank, d['id'][:22], f"{d['score']:.4f}", f"{d['ptm']:.4f}", f"{d['iptm']:.4f}",
            f"{d['plddt']:.2f}", f"{d['rmsd']:.2f}Å", f"{d['total_reward']:.4f}",
            str(d['iterate']), str(d['round'])
        ))
    print("-" * 115)

    generation_round += 1
    gc.collect()
    if torch.cuda.is_available(): torch.cuda.empty_cache(); torch.cuda.ipc_collect()

# ---------------------------------------------------------
# 7. Final Output
# ---------------------------------------------------------
print(f"\n🛑 EvoPilot execution state terminated.")
if len(GLOBAL_HITS) >= target_success_count:
    print(f"🏆 OBJECTIVE COMPLETED: Hit quota satisfied yielding {len(GLOBAL_HITS)} high-affinity models.")
else:
    print(f"⚠️ MAXIMUM ITERATIONS TRIGGERED: Algorithm halted with {len(GLOBAL_HITS)} viable candidates isolated over {evolution_iterate} execution cycles.")

if master_log_path.exists():
    shutil.copy2(master_log_path, final_dir / f'{task_name}_EvoPilot_prediction_results.csv')

print(f"✅ Prediction results synced in: {final_dir.relative_to(BASE_DIR)}")

# ==============================================================================
# Purpose: Execute a true Evolutionary Loop with dynamic hotspot mutation, definitive [ROLLBACK] mechanism, and an embedded py3Dmol visualizer. Ensures absolute fidelity of the mutation system by reverse-mapping AF2 sequentially generated coordinates back to the unalterable Natural Ground Truth numbering established in the source PDB.
# Upstream Code: Ported core visualization hierarchy and AF2 dictionary mapping translation from Cell 8.
# Runtime Environment: Google Colab.
# Generation Time: 2026-04-16 14:10 EDT.
# Changed Lines:
# - Lines 285-305: Established the `af2_to_natural_map` dictionary right before KDTree spatial querying. Added `[REVERSE TRANSLATION]` block to safely convert AlphaFold's arbitrary `res_id` back to its original biological coordinate `natural_res_id` before accruing contact scores. This completely isolates the evolutionary tracking from index pollution.
# ==============================================================================