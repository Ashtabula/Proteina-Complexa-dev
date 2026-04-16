# Cell_4b_PDB_Processing_and_YAML_Configuration_Generation.py
# Requirement: Implement In-Place Resume. If RESUME_LAST_SESSION is enabled and validated, inherit the exact old run_id and directly target the existing historical directory without cloning or renaming files.

import os, json, yaml, shutil, time, sys, datetime, re
from pathlib import Path

print("🔍 Initializing Target Processing Engine (In-Place Resume Architecture)...")

# ---------------------------------------------------------
# 1. Base Environment Setup
# ---------------------------------------------------------
if not os.path.exists('/content/drive/MyDrive'):
    from google.colab import drive
    drive.mount('/content/drive')

BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
SETTING_FILE = BASE_DIR / 'internal_settings.json'

if not SETTING_FILE.exists():
    print("❌ Error: Global configuration file not found in root.")
    sys.exit(1)

with open(SETTING_FILE, 'r') as f:
    cfg = json.load(f)

task_name = cfg['task_name']
resume_session = bool(cfg.get('RESUME_LAST_SESSION', False))

CORE_PHYSICAL_KEYS = [
    'pdb_file', 'target_chains', 'hotspots_input',
    'binder_length_min', 'binder_length_max',
    'anchor_residues', 'global_search_boundary', 'peptide_interaction_radius'
]

# ---------------------------------------------------------
# 2. Run ID Resolution & Directory Targeting
# ---------------------------------------------------------
last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'
active_run_id = None
active_final_dir = None
is_resuming = False

if resume_session and last_run_file.exists():
    with open(last_run_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        pattern = rf"Section2_TargetPreprocess \| Run_ID: ({re.escape(task_name)}_\d+_\d+)"
        for line in reversed(lines):
            match = re.search(pattern, line)
            if match:
                candidate_run_id = match.group(1)
                hist_timestamp = candidate_run_id.split('_')[-1]
                candidate_dir = BASE_DIR / 'screening_results' / task_name / f"final_{hist_timestamp}"

                hist_setting_path = candidate_dir / 'internal_settings.json'

                if hist_setting_path.exists():
                    with open(hist_setting_path, 'r') as hf:
                        hist_cfg = json.load(hf)

                    print(f"🔄 ARCHIVE FOUND: Validating historical session [{candidate_run_id}]...")

                    # Strict validation
                    mismatches = []
                    for key in CORE_PHYSICAL_KEYS:
                        val_curr = str(cfg.get(key, '')).strip()
                        val_hist = str(hist_cfg.get(key, '')).strip()
                        if val_curr != val_hist:
                            mismatches.append(f"{key}: Current='{val_curr}' | Archive='{val_hist}'")

                    if mismatches:
                        print(f"❌ FATAL: Core physical parameters conflict with archive [{candidate_run_id}].")
                        sys.exit(1)

                    # Validation passed: IN-PLACE RESUME
                    active_run_id = candidate_run_id
                    active_final_dir = candidate_dir
                    is_resuming = True
                    print(f"✅ VALIDATION PASSED: Re-activating existing workspace for in-place continuation.")
                break

# If not resuming (or history not found), generate new
if not is_resuming:
    SESSION_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    active_run_id = f"{task_name}_{SESSION_TIMESTAMP}"
    active_final_dir = BASE_DIR / 'screening_results' / task_name / f"final_{SESSION_TIMESTAMP}"
    active_final_dir.mkdir(parents=True, exist_ok=True)

    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    with open(last_run_file, 'a', encoding='utf-8') as f:
        f.write(f"Section2_TargetPreprocess | Run_ID: {active_run_id} | Dir: {active_final_dir.name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"🆕 NEW SESSION ACTIVE: Global Run ID registered: {active_run_id}")

# ---------------------------------------------------------
# 3. Configuration Sync
# ---------------------------------------------------------
cfg['run_id'] = active_run_id
with open(SETTING_FILE, 'w') as f:
    json.dump(cfg, f, indent=4)

print(f"📂 Active Workspace: {active_final_dir.relative_to(BASE_DIR)}")

# ---------------------------------------------------------
# 4. PDB Parsing & YAML Generation
# ---------------------------------------------------------
pdb_file = cfg['pdb_file']
target_chains = cfg['target_chains']
hotspots_input = str(cfg['hotspots_input'])
binder_length_min = int(cfg['binder_length_min'])
binder_length_max = int(cfg['binder_length_max'])

TARGETS_INPUT_DIR = BASE_DIR / 'targets'
RUN_DATA_DIR = BASE_DIR / 'assets' / 'target_data' / task_name
YAML_PATH = BASE_DIR / 'configs/targets/targets_dict.yaml'

RUN_DATA_DIR.mkdir(parents=True, exist_ok=True)
raw_pdb_path = TARGETS_INPUT_DIR / pdb_file
fixed_pdb_path = RUN_DATA_DIR / f"{task_name}_fixed.pdb"

print(f"⚙️ Processing PDB: {pdb_file}...")
valid_res_nums = set()
with open(raw_pdb_path, 'r') as f:
    for line in f:
        if line.startswith('ATOM') and line[12:16].strip() == 'CA' and line[21] == target_chains:
            try: valid_res_nums.add(int(line[22:26].strip()))
            except: continue

with open(raw_pdb_path, 'r') as f_in, open(fixed_pdb_path, 'w') as f_out:
    for line in f_in:
        if line.startswith('ATOM') and line[21] == target_chains:
            try:
                if int(line[22:26].strip()) in valid_res_nums: f_out.write(line)
            except: pass
        elif line.startswith('TER'): f_out.write(line)

res_nums = sorted(list(valid_res_nums))
ranges = []
if res_nums:
    start = prev = res_nums[0]
    for n in res_nums[1:]:
        if n == prev + 1: prev = n
        else:
            ranges.append(f"{target_chains}{start}-{prev}" if start!=prev else f"{target_chains}{start}")
            start = prev = n
    ranges.append(f"{target_chains}{start}-{prev}" if start!=prev else f"{target_chains}{start}")

hotspots_list = [int(x.strip()) for x in hotspots_input.split(',') if x.strip().isdigit()]
yaml_data = {'target_dict_cfg': {
    task_name: {
        'target_input': ','.join(ranges),
        'binder_length': [binder_length_min, binder_length_max],
        'target_chains': [target_chains],
        'pdb_id': task_name,
        'source': task_name,
        'target_filename': task_name + "_fixed",
        'hotspot_residues': [f"{target_chains}{i}" for i in hotspots_list]
    }
}}

with open(YAML_PATH, 'w') as f:
    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

# ---------------------------------------------------------
# 5. Final Workspace Synchronization
# ---------------------------------------------------------
shutil.copy2(SETTING_FILE, active_final_dir / 'internal_settings.json')
shutil.copy2(YAML_PATH, active_final_dir / f'targets_dict_{active_run_id}.yaml')

print(f"💾 ARCHIVE SYNCED: Current dynamic settings securely written to {active_final_dir.name}")
print(f"🎯 SUCCESS: Ready for generation phase.")

# ==============================================================================
# Purpose: Refactored to 'In-Place Resume' architecture. Eliminates redundant directory cloning and file renaming. If resumption is validated against core physical parameters, the system directly re-activates the historical run_id and its exact physical directory, seamlessly updating only the dynamic control parameters (like max_iterations).
# Upstream Code: Section 0 JSON definition.
# Runtime Environment: Google Colab.
# Generation Time: 2026-04-13 09:11 EDT.
# Changed Lines:
# - Lines 43-73: Stripped out the `shutil.copytree` logic. Direct assignment of `active_run_id = candidate_run_id` and `active_final_dir = candidate_dir` upon successful validation.
# ==============================================================================