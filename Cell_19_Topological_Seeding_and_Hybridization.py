# Cell_19_Topological_Seeding_and_Hybridization.py
# Requirements:
# - Read target_fixed.pdb & extract CA coordinates.
# - Calculate Surface Convex Hull of initial hotspots & Dilation (5-8A).
# - KDTree filtering (10A radius, <20 CA neighbors) for surface exposure.
# - Greedy Minimum Set Cover (5A sphere) to establish dynamic satellite islands (Isl_A, Isl_B...).
# - Run 48 generation designs for Isl_0 and all newly discovered Satellite Islands using complexa design.
# - Hybridization: KDTree (<4.5A) to drop 3 lowest from Isl_0, add 3 highest from each Satellite, merge to Hybrid Islands.
# - Export to Hybrid Islands JSON manifest.
# - Visualizations: py3Dmol showing orange for hotspots and white for new islands on the protein mesh surface.

import os, sys, json, subprocess, time, datetime, csv, string, re, shutil
from pathlib import Path
import numpy as np
from scipy.spatial import KDTree
import py3Dmol

# --- 1. Objective and Setup ---
# Objective: Broad-spectrum topology exploration, satellite island seeding, and hybridization.
# Upstream Dependencies: internal_settings.json, complexa design shell, valid target_fixed.pdb
print("🌍 Initializing Cell 19: Topological Seeding and Hybridization...")

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
ISOLATED_SETTING = final_dir / 'internal_settings.json'

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)

target_chains = cfg['target_chains']
base_hotspots = [x.strip() for x in cfg.get('hotspots_input', '').split(',') if x.strip()]
generation_batch_size = 48 # Explicit setting per requirements
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))
SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
SESSION_NAME = f"TopoSeeding_{task_name}_{SESSION_TIMESTAMP}"
SESSION_MASTER_DIR = BASE_DIR / 'assets' / 'target_data' / SESSION_NAME
SESSION_MASTER_DIR.mkdir(parents=True, exist_ok=True)

# --- 2. Architecture: PDB Parsing & CA coordinate extraction ---
print("🔬 Parsing target structures and calculating topologies...")
ca_atoms = {}
hotspot_ca = {}

with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            res_id = line[22:26].strip()
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            ca_atoms[res_id] = np.array([x, y, z])
            if res_id in base_hotspots:
                hotspot_ca[res_id] = ca_atoms[res_id]

all_res_ids = list(ca_atoms.keys())
all_coords = np.array([ca_atoms[rid] for rid in all_res_ids])
hotspot_coords = np.array([hotspot_ca[rid] for rid in base_hotspots if rid in hotspot_ca])

# --- 3. Dilation & Filtering (Exposure Check) ---
global_kdtree = KDTree(all_coords)
surface_residues = []

# Filter for surface exposure (10A radius, < 20 CA neighbors)
for i, rid in enumerate(all_res_ids):
    neighbors = global_kdtree.query_ball_point(all_coords[i], r=10.0)
    if len(neighbors) < 20:
        surface_residues.append(rid)

print(f"🌊 Identified {len(surface_residues)} surface-exposed residues.")

hotspot_kdtree = KDTree(hotspot_coords)
dilation_candidates = []

for rid in surface_residues:
    if rid in base_hotspots:
        continue
    coord = ca_atoms[rid]
    dists, _ = hotspot_kdtree.query(coord, k=1)
    if 5.0 <= dists <= 8.0:
        dilation_candidates.append(rid)

print(f"🪐 Extracted {len(dilation_candidates)} candidates in the 5Å - 8Å dilation ring.")

# --- 4. Island Generation (Greedy Minimum Set Cover, 5A radius) ---
uncovered_candidates = set(dilation_candidates)
satellite_islands = []
alphabet = string.ascii_uppercase

while uncovered_candidates:
    best_center = None
    best_coverage = set()
    
    for cand in uncovered_candidates:
        cand_coord = ca_atoms[cand]
        coverage = set()
        for other in uncovered_candidates:
            if np.linalg.norm(cand_coord - ca_atoms[other]) <= 5.0:
                coverage.add(other)
        if len(coverage) > len(best_coverage):
            best_coverage = coverage
            best_center = cand
            
    if best_center:
        idx = len(satellite_islands)
        suffix = alphabet[idx] if idx < 26 else f"X{idx}"
        isl_name = f"Isl_{suffix}"
        satellite_islands.append({
            "name": isl_name,
            "center": best_center,
            "residues": list(best_coverage)
        })
        uncovered_candidates -= best_coverage
    else:
        break

print(f"🏝️ Generated {len(satellite_islands)} dynamically distributed Satellite Islands.")

# --- 5. Execution: Complexa Design (48 Gen per Island) ---
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})

import yaml
yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'

all_target_islands = [{"name": "Isl_0", "residues": base_hotspots}] + satellite_islands
scores_manifest = {} # Store island generation performance

for isl in all_target_islands:
    name = isl["name"]
    residues = isl["residues"]
    print(f"\n🚀 Initiating Generation Batch for {name} ({len(residues)} residues) - {','.join(residues)}")
    
    # Write config
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in residues]
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    run_name = f"{SESSION_NAME}_{name}"
    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs=48 "
        f"++generation.dataloader.batch_size=48 ++generation.search.max_batch_size=48 ++evaluation.dataloader.batch_size={evaluation_batch_size} "
        f"++run_filter=True ++run_evaluate=True ++evaluate.num_recycles=1 ++evaluate.pad_to_max_length=True ++evaluate.use_msa=False ++evaluate.msa_mode=single_sequence ++run_analyze=True"
    )

    process = subprocess.Popen(
        f"source env.sh && {cmd_str}",
        env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    for line in process.stdout:
        print(line, end='', flush=True)
    process.wait()
    
    # Locate max ipSAE score and top PDB for the island
    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]
    max_score = 0.0
    top_pdb = None
    
    if valid_csvs:
        target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
        df = pd.read_csv(target_csv)
        score_col = next((col for col in ['af2folding_max_ipsae', 'self_complex_max_ipAE', 'complex_i_pAE'] if col in df.columns), None)
        if score_col:
            top_row = df.loc[df[score_col].idxmax()]
            max_score = float(top_row[score_col])
            top_pdb = top_row.get('pdb_path', None)
    
    scores_manifest[name] = {"max_score": max_score, "top_pdb": top_pdb, "residues": residues}

# --- 6. Hybridization (KDTree < 4.5A mapping) ---
print("\n🧬 Triggering Hybridization Protocol...")

def calculate_contributions(pdb_path, res_list):
    # Calculate contact contributions of given residues against binder using KDTree
    contributions = {r: 0.0 for r in res_list}
    if not pdb_path or not Path(pdb_path).exists(): return contributions
    
    t_coords, b_coords = {}, []
    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                c, r, x, y, z = line[21], line[22:26].strip(), float(line[30:38]), float(line[38:46]), float(line[46:54])
                if c == target_chains:
                    t_coords[r] = [x, y, z]
                else:
                    b_coords.append([x, y, z])
                    
    if not b_coords: return contributions
    b_tree = KDTree(b_coords)
    
    for rid in res_list:
        if rid in t_coords:
            dists, _ = b_tree.query(t_coords[rid], k=1)
            if dists < 4.5:
                contributions[rid] = 1.0 / (dists + 0.1)  # Proxy for score contribution
    return contributions

isl_0_contribs = calculate_contributions(scores_manifest["Isl_0"]["top_pdb"], base_hotspots)
sorted_isl_0 = sorted(isl_0_contribs.keys(), key=lambda k: isl_0_contribs[k], reverse=True)
pruned_isl_0 = sorted_isl_0[:-3] if len(sorted_isl_0) > 3 else sorted_isl_0

hybrid_islands = {}
for isl in satellite_islands:
    name = isl["name"]
    res_list = isl["residues"]
    contribs = calculate_contributions(scores_manifest[name]["top_pdb"], res_list)
    top_neo = sorted(contribs.keys(), key=lambda k: contribs[k], reverse=True)[:3]
    
    hybrid_name = name.replace("Isl_", "Isl_0")
    hybrid_residues = list(set(pruned_isl_0 + top_neo))
    hybrid_islands[hybrid_name] = {
        "baseline_ipsae": scores_manifest[name]["max_score"],
        "hybrid_hotspots": hybrid_residues
    }
    print(f"🔗 Hybridized {hybrid_name}: {','.join(hybrid_residues)} (Baseline ipSAE: {scores_manifest[name]['max_score']:.3f})")

# --- 7. Export JSON Manifest ---
manifest_path = final_dir / f"Hybrid_Islands_Manifest_{SESSION_TIMESTAMP}.json"
with open(manifest_path, 'w') as f:
    json.dump(hybrid_islands, f, indent=4)
print(f"💾 Exported Hybrid Islands Manifest: {manifest_path}")

# --- 8. Visualizations: Mesh using py3Dmol ---
print("🎨 Rendering Topological Surface Analysis (Orange: Hotspots, White: New Islands)")
with open(SOURCE_PDB_PATH, 'r') as f:
    pdb_data = f.read()

viewer = py3Dmol.view(width=800, height=600)
viewer.addModel(pdb_data, 'pdb')
viewer.setStyle({'cartoon': {'color': 'gray'}})

# Original Hotspots -> Orange
viewer.addSurface(py3Dmol.VDW, {'opacity': 0.8, 'color': 'orange'}, {'chain': target_chains, 'resi': base_hotspots})

# New Satellite Islands -> White
all_satellite_res = []
for isl in satellite_islands:
    all_satellite_res.extend(isl["residues"])
    
if all_satellite_res:
    viewer.addSurface(py3Dmol.VDW, {'opacity': 0.8, 'color': 'white'}, {'chain': target_chains, 'resi': list(set(all_satellite_res))})

viewer.zoomTo()
# viewer.show() # Uncomment via Colab environment to display inline.

'''
Block Comment:
Objective: Topological Seeding, Sets Cover Island Extraction, and Generation of Hybrid Hotspots.
Upstream Dependencies: complexa, pandas, py3Dmol, scipy.spatial
Runtime Environment: Colab / Linux High-Performance GPU Workspace
Timestamp: Auto-generated via Script execution.
'''
