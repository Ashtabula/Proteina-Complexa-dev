# == CELL markdown INDEX 21 ==
# Section 7: Topological Seeding and Deep Greedy Convergence
This section introduces a two-stage automated hotspot evolution architecture:
- **Cell 19: Topological Seeding and Hybridization**: Generates non-overlapping satellite islands and forms hybrid hotspots.
- **Cell 20: Deep Greedy Convergence Loop**: Sifts through high priority hybrid islands and iteratively drops weak spots in favor of neo-hotspots until convergence.

# == CELL code INDEX 22 ==

# Cell_19_Topological_Seeding_and_Visualization.py
# Requirements:
# - Read target_fixed.pdb & extract CA and CB coordinates.
# - Dynamic Representative Atom: Use CB for side-chain representation; fallback to CA for GLY or missing atoms.
# - Calculate surface exposure using KDTree filtering (10A radius, <20 CB/CA neighbors) to preserve Alpha-helices.
# - Extract dilation ring (5-8A) around the user-provided initial hotspots.
# - Apply Greedy Minimum Set Cover (5A sphere) to establish non-overlapping satellite islands.
# - Section 7 Smart Restart: Read force_restart_section_7 to wipe old geometric manifests if triggered.
# - Export the purely geometric satellite islands to Geometric_Islands_Manifest.json.
# - Visualizations: py3Dmol showing gray mesh (SES) for target, solid orange (VDW) for core hotspots, and solid white (VDW) for new islands. Integer casting implemented for resi selectors.
# - Strictly English comments and variables.

import os
import sys
import json
import string
import re
from pathlib import Path
import numpy as np
from scipy.spatial import KDTree
import py3Dmol

# --- 1. Objective and Setup ---
print("🌍 Initializing Cell 19: Topological Seeding (CB-Anchored) and Visualization...")

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

target_chains = str(cfg.get('target_chains', 'A')).split(',')[0].strip()
base_hotspots = [str(x).strip() for x in cfg.get('hotspots_input', '').split(',') if str(x).strip()]
SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

geometric_manifest_path = final_dir / "Geometric_Islands_Manifest.json"

# --- SMART RESTART LOGIC FOR SECTION 6 ---
force_restart = bool(root_cfg.get('force_restart_section_7', False))
if force_restart:
    print("\n🗑️ [COMMAND] Force Restart Section 6 is ENABLED.")
    if geometric_manifest_path.exists():
        geometric_manifest_path.unlink()
        print("🧹 Wiped old Geometric_Islands_Manifest.json to generate fresh geometric seeds.")
else:
    print(f"\n⏭️ [RESUME] Smart Resume active. Regenerating topological surface arrays in memory...")

# --- 2. Architecture: PDB Parsing & Dynamic Representative Atom Extraction (CB/CA) ---
print("🔬 Parsing structures: Extracting CB atoms (fallback to CA for GLY)...")
ca_atoms = {}
cb_atoms = {}
res_names = {}

if not SOURCE_PDB_PATH.exists():
    print(f"❌ Error: Source PDB not found at {SOURCE_PDB_PATH}")
    sys.exit(1)

with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[21] == target_chains:
            atom_name = line[12:16].strip()
            res_id = line[22:26].strip()
            res_name = line[17:20].strip()

            if atom_name == "CA":
                ca_atoms[res_id] = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                res_names[res_id] = res_name
            elif atom_name == "CB":
                cb_atoms[res_id] = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])

# Build Representative Atoms mapping
rep_atoms = {}
for rid in ca_atoms.keys():
    if res_names.get(rid) == 'GLY':
        rep_atoms[rid] = ca_atoms[rid]  # GLY has no CB, use CA
    else:
        rep_atoms[rid] = cb_atoms.get(rid, ca_atoms[rid]) # Use CB, fallback to CA if missing

all_res_ids = list(rep_atoms.keys())
all_coords = np.array([rep_atoms[rid] for rid in all_res_ids])
hotspot_coords = np.array([rep_atoms[rid] for rid in base_hotspots if rid in rep_atoms])

# --- 3. Dilation & Filtering (Half-Sphere Exposure / HSE Vector Check) ---
print("🧮 Applying Half-Sphere Exposure (HSE) vector analysis to precisely preserve surface helices...")

ca_coords_array = np.array([ca_atoms[rid] for rid in all_res_ids])
ca_kdtree = KDTree(ca_coords_array)
surface_residues = []

for i, rid in enumerate(all_res_ids):
    ca = ca_atoms[rid]

    # 1. Establish side-chain extension vector (CB - CA)
    if res_names.get(rid) != 'GLY' and rid in cb_atoms:
        v_out = cb_atoms[rid] - ca
    else:
        # GLY fallback: calculate approximate outward vector using center of mass of 8A neighbors
        neighbors_idx = ca_kdtree.query_ball_point(ca, r=8.0)
        if len(neighbors_idx) > 1:
            local_com = np.mean(ca_coords_array[neighbors_idx], axis=0)
            v_out = ca - local_com
        else:
            v_out = np.array([0.0, 0.0, 1.0])

    # Vector normalization
    norm = np.linalg.norm(v_out)
    if norm > 1e-4:
        v_out = v_out / norm
    else:
        v_out = np.array([0.0, 0.0, 1.0])

    # 2. Count neighbors within 10A in the "forward hemisphere" of the side chain
    neighbors_idx = ca_kdtree.query_ball_point(ca, r=10.0)
    forward_neighbors = 0

    for n_idx in neighbors_idx:
        if all_res_ids[n_idx] == rid:
            continue
        vec_to_neighbor = ca_coords_array[n_idx] - ca

        # Dot product > 0 indicates the neighbor is in the forward hemisphere
        if np.dot(vec_to_neighbor, v_out) > 0:
            forward_neighbors += 1

    # 3. Core decision logic:
    # Internal residues usually have 15-25 obstructing neighbors in the forward hemisphere.
    # Surface residues (including solvent-exposed helices) have an almost empty front, typically < 12.
    if forward_neighbors < 12:
        surface_residues.append(rid)

print(f"🌊 Identified {len(surface_residues)} surface-exposed residues (Strict HSE filtration passed).")

if len(hotspot_coords) == 0:
    print("❌ Error: No valid starting hotspots found matching the PDB numbering.")
    sys.exit(1)

# Build KDTree with representative atoms (CB primary) for distance dilation
rep_coords_array = np.array([rep_atoms[rid] for rid in surface_residues])
surface_kdtree = KDTree(rep_coords_array)

hotspot_kdtree = KDTree(hotspot_coords)
dilation_candidates = []

for rid in surface_residues:
    if rid in base_hotspots:
        continue
    coord = rep_atoms[rid]
    dists, _ = hotspot_kdtree.query(coord, k=1)

    # Maintain 5A - 8A geometric dilation ring
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
        cand_coord = rep_atoms[cand]
        coverage = set()
        for other in uncovered_candidates:
            if np.linalg.norm(cand_coord - rep_atoms[other]) <= 5.0:
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

# --- 5. Export Geometric Manifest for GPU stages ---
geometric_manifest = {
    "base_hotspots": base_hotspots,
    "satellite_islands": satellite_islands
}
with open(geometric_manifest_path, 'w') as f:
    json.dump(geometric_manifest, f, indent=4)
print(f"💾 Exported Geometric Islands Manifest to {geometric_manifest_path.name}")

# --- 6. Visualizations: Mesh using py3Dmol ---
print("🎨 Rendering Topological Surface Analysis (Orange: Core Hotspots, White: Satellite Islands)")
if SOURCE_PDB_PATH.exists():
    with open(SOURCE_PDB_PATH, 'r') as f:
        pdb_data = f.read()

    viewer = py3Dmol.view(width=800, height=600)
    viewer.addModel(pdb_data, 'pdb')

    # Type cast selectors to integers to bypass py3Dmol string failure
    hotspot_resi_int = [int(re.sub(r'\D', '', str(x))) for x in base_hotspots if str(x).strip()]

    all_satellite_res = []
    for isl in satellite_islands:
        all_satellite_res.extend(isl["residues"])

    sat_resi_int = []
    if all_satellite_res:
        sat_resi_int = [int(re.sub(r'\D', '', str(x))) for x in list(set(all_satellite_res)) if str(x).strip()]

    # Target protein: Gray cartoon + Gray wireframe mesh (SES is valid for large contiguous structures)
    target_sel = {'chain': target_chains}
    viewer.setStyle(target_sel, {'cartoon': {'color': '#A9A9A9', 'opacity': 0.7}})
    viewer.addSurface(py3Dmol.SES, {'color': '#A9A9A9', 'wireframe': True, 'opacity': 0.5}, target_sel)

    # Core Hotspots: Orange cartoon + Solid Orange surface (Use VDW for fragmented sets)
    if hotspot_resi_int:
        hotspot_sel = {'chain': target_chains, 'resi': hotspot_resi_int}
        viewer.setStyle(hotspot_sel, {'cartoon': {'color': 'orange', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'orange', 'opacity': 1.0}, hotspot_sel)

    # Satellite Islands: White cartoon + Solid White surface (Use VDW for fragmented sets)
    if sat_resi_int:
        sat_sel = {'chain': target_chains, 'resi': sat_resi_int}
        viewer.setStyle(sat_sel, {'cartoon': {'color': 'gray', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'gray', 'opacity': 1.0}, sat_sel)

    viewer.zoomTo()

    try:
        from IPython.display import display
        display(viewer.show())
    except ImportError:
        viewer.show()

'''
==============================================================================
Objective: CPU-only Phase for Topological Seeding and Visualization via CB Atoms. Establishes satellite islands, meshes target, and exports geometric parameters.
           Includes Section 6 Smart Restart logic for cache invalidation.
           py3Dmol selectors strictly cast to integers and VDW algorithms applied to subsets to prevent silent render failures.
Upstream Dependencies: py3Dmol, scipy.spatial.KDTree, internal_settings.json
Runtime Environment: Google Colab (CPU compatible)
Generation Timestamp: Auto-generated via Script execution.
==============================================================================
'''

# == CELL code INDEX 23 ==
# Cell_20_Physical_Generation_and_Hybridization.py
import os, sys, json, subprocess, time, datetime, re, yaml, random, csv
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import KDTree
import py3Dmol
from IPython.display import HTML, display

# --- 1. Objective and Setup ---
print("🔥 Initializing GPU Generation, True Resume Engine, and Real-time Tracking...")

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
        pattern = rf"Section2_TargetPreprocess(?:_TimeMachine)? \| Run_ID: ({re.escape(task_name)}_\d+_\d+) \| Dir: (final_\d+_\d+)"
        for line in reversed(lines):
            match = re.search(pattern, line)
            if match:
                run_id = match.group(1)
                target_dir_name = match.group(2)
                break

if not run_id:
    print("❌ Error: Could not resolve Run_ID from last_runs.txt")
    sys.exit(1)

final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name
ISOLATED_SETTING = final_dir / 'internal_settings.json'
GEOMETRIC_MANIFEST = final_dir / "Geometric_Islands_Manifest.json"

if not GEOMETRIC_MANIFEST.exists():
    print("❌ Error: Geometric manifest not found. Run Cell 19 first.")
    sys.exit(1)

with open(ISOLATED_SETTING, 'r') as f:
    cfg = json.load(f)
with open(GEOMETRIC_MANIFEST, 'r') as f:
    geo_data = json.load(f)

# --- SMART RESTART LOGIC & SESSION IDENTITY ---
force_restart = bool(root_cfg.get('force_restart_section_7', False))
SESSION_TIMESTAMP = None

if force_restart:
    print("\n🗑️ [COMMAND] Force Restart Section 6 is ENABLED. Cleaning up previous Hybrid outputs...")
    manifest_file = final_dir / "Hybrid_Islands_Manifest.json"
    if manifest_file.exists(): manifest_file.unlink()
    for old_csv in final_dir.glob("Hybrid_Summary_*.csv"): old_csv.unlink()
else:
    print(f"\n⏭️ [RESUME] Smart Resume active. Scanning for historical Hybridization sessions...")
    existing_summaries = list(final_dir.glob("Hybrid_Summary_*.csv"))
    if existing_summaries:
        latest_summary = max(existing_summaries, key=lambda f: f.stat().st_mtime)
        match = re.search(r"Hybrid_Summary_(.*)\.csv", latest_summary.name)
        if match:
            SESSION_TIMESTAMP = match.group(1)
            print(f"🔄 True Resume: Re-attaching to historical session [{SESSION_TIMESTAMP}]")

if not SESSION_TIMESTAMP:
    SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
    print(f"🆕 New Hybridization Session initialized: [{SESSION_TIMESTAMP}]")

SESSION_NAME = f"Hybridization_{task_name}_{SESSION_TIMESTAMP}"
SUMMARY_CSV = final_dir / f"Hybrid_Summary_{SESSION_TIMESTAMP}.csv"

if not SUMMARY_CSV.exists():
    with open(SUMMARY_CSV, 'w') as f:
        f.write("Island_Name,ipSAE,Hotspot_Count,Residues\n")

HISTORY_CSV = BASE_DIR / 'screening_results' / 'history_run.csv'
if HISTORY_CSV.exists():
    try:
        updated_rows = []
        with open(HISTORY_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            if "Overall_Data_Link" not in header: header.append("Overall_Data_Link")
            link_idx = header.index("Overall_Data_Link")
            run_id_idx = header.index("Run_ID") if "Run_ID" in header else -1

            updated_rows.append(header)
            for row in reader:
                while len(row) < len(header): row.append("")
                if run_id_idx != -1 and row[run_id_idx] == run_id:
                    new_link = f"[View Hybrid Log]({SUMMARY_CSV.relative_to(BASE_DIR)})"
                    if new_link not in row[link_idx]:
                        row[link_idx] = f"{row[link_idx]} | {new_link}" if str(row[link_idx]).strip() else new_link
                updated_rows.append(row)

        with open(HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(updated_rows)
    except Exception as e:
        print(f"⚠️ Warning: Failed to update history_run.csv: {e}")

target_chains = str(cfg.get('target_chains', 'A')).split(',')[0].strip()
base_hotspots = geo_data["base_hotspots"]
satellite_islands = geo_data["satellite_islands"]
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))
generation_batches_per_island = int(root_cfg.get('generation_batches_per_island', 6))
base_batch_size = 8

print(f"⚙️ Configured to run {generation_batches_per_island} batches × {base_batch_size} designs per island.")
SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"

def fs(val, is_rmsd=False, is_plddt=False):
    if pd.isna(val) or val == -999.0: return "N/A"
    try:
        v = float(val)
        if is_rmsd: return f"{v:<8.2f}Å"
        if is_plddt: return f"{v:<8.2f}"
        return f"{v:<8.4f}"
    except: return "N/A"

# --- 2. Architecture: Sequence Mapping ---
print("🔬 Extracting biological sequence order for AF2 reverse mapping...")
ordered_natural_resis = []
with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            ordered_natural_resis.append(line[22:26].strip())

natural_to_af2 = {nat: str(i+1) for i, nat in enumerate(ordered_natural_resis)}

# --- 🌟 Spatial Patch Extraction (Surface-Aware) ---
def extract_patch_residues(pdb_path, target_chain, core_res_list, radius=6.0):
    target_coords, ca_atoms, cb_atoms, res_names, island_coords = {}, {}, {}, {}, []
    if not pdb_path or not Path(pdb_path).exists(): return core_res_list

    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM"):
                chain = line[21]
                if chain != target_chain: continue
                resi = line[22:26].strip()
                atom_name = line[12:16].strip()
                res_name = line[17:20].strip()
                coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])

                if resi not in target_coords: target_coords[resi] = []
                target_coords[resi].append(coord)
                if atom_name == "CA": ca_atoms[resi] = coord
                if atom_name == "CB": cb_atoms[resi] = coord
                res_names[resi] = res_name
                if resi in core_res_list: island_coords.append(coord)

    if not island_coords or not target_coords: return core_res_list

    island_tree = KDTree(island_coords)
    close_residues = []
    for resi, coords in target_coords.items():
        for coord in coords:
            dist, _ = island_tree.query(coord, k=1)
            if dist <= radius:
                close_residues.append(resi)
                break

    if not close_residues: return core_res_list

    all_resis = list(ca_atoms.keys())
    ca_coords_array = np.array([ca_atoms[r] for r in all_resis])
    if len(ca_coords_array) == 0: return close_residues

    ca_kdtree = KDTree(ca_coords_array)
    surface_patch = set()

    for resi in close_residues:
        if resi not in ca_atoms: continue
        ca = ca_atoms[resi]
        if res_names.get(resi) != 'GLY' and resi in cb_atoms:
            v_out = cb_atoms[resi] - ca
        else:
            neighbors_idx = ca_kdtree.query_ball_point(ca, r=8.0)
            if len(neighbors_idx) > 1:
                local_com = np.mean(ca_coords_array[neighbors_idx], axis=0)
                v_out = ca - local_com
            else: v_out = np.array([0.0, 0.0, 1.0])

        norm = np.linalg.norm(v_out)
        if norm > 1e-4: v_out = v_out / norm
        else: v_out = np.array([0.0, 0.0, 1.0])

        n_idx_all = ca_kdtree.query_ball_point(ca, r=10.0)
        forward_neighbors = sum(1 for n_idx in n_idx_all if all_resis[n_idx] != resi and np.dot(ca_coords_array[n_idx] - ca, v_out) > 0)

        if forward_neighbors < 12: surface_patch.add(resi)

    if not surface_patch: return core_res_list
    return sorted(list(surface_patch), key=lambda x: int(re.sub(r'\D', '', x)))

# --- 🌟 PAE Analysis Interface (Enhanced for Anchor Screening) ---
def analyze_hotspot_pae(inference_dir, design_id, target_hotspots, target_chain_len, natural_map):
    pae_files = list(Path(inference_dir).rglob(f"{design_id}*_pae.json"))
    if not pae_files: return {}

    try:
        with open(pae_files[0], 'r') as f:
            pae_data = json.load(f)[0]
            pae_matrix = np.array(pae_data['predicted_aligned_error'])

        spot_scores = {}
        binder_start = target_chain_len

        for spot_nat in target_hotspots:
            if spot_nat in natural_map:
                idx = int(natural_map[spot_nat]) - 1
                if idx < pae_matrix.shape[0] and binder_start < pae_matrix.shape[1]:
                    # 取出该靶点对整条多肽的所有 PAE 值
                    binder_paes = pae_matrix[idx, binder_start:]

                    # 核心筛选逻辑：只取结合最紧密（PAE最低）的前 3 个多肽氨基酸求均值
                    if len(binder_paes) >= 3:
                        best_pae = np.sort(binder_paes)[:3].mean()
                    else:
                        best_pae = np.mean(binder_paes)

                    spot_scores[spot_nat] = float(best_pae)
        return spot_scores
    except Exception as e:
        print(f"⚠️ PAE analysis failed for {design_id}: {e}")
        return {}

# --- 3. Pre-calculate Patches & Initialize Manifests ---
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})
yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'

all_target_islands = [{"name": "Isl_0", "residues": base_hotspots}] + satellite_islands
scores_manifest = {}
scores_manifest_path = final_dir / "Scores_Manifest.json"

# 🌟 初始化全局 PAE 追踪器和文件路径
global_pae_tracker = {}
GLOBAL_PAE_FILE = final_dir / "Global_Hotspot_PAE_Ranking.json"

# 如果存在历史记录，读取以支持断点续传
if GLOBAL_PAE_FILE.exists() and not force_restart:
    with open(GLOBAL_PAE_FILE, 'r') as f:
        global_pae_tracker = json.load(f)

print("\n📝 Pre-calculating surface patches for all islands...")
for isl in all_target_islands:
    name = isl["name"]
    residues = isl["residues"]
    current_patch = residues if name == 'Isl_0' else extract_patch_residues(SOURCE_PDB_PATH, target_chains, residues, radius=6.0)

    scores_manifest[name] = {
        "max_score": -999.0,
        "top_pdb": None,
        "residues": residues,
        "patch_residues": current_patch,
        "hotspot_pae_ranking": {}
    }

with open(scores_manifest_path, 'w') as f:
    json.dump(scores_manifest, f, indent=4)

# --- 4. Execution: Complexa Design Loop ---
target_chain_length = len(ordered_natural_resis)

for isl in all_target_islands:
    name = isl["name"]
    residues = scores_manifest[name]["residues"]
    patch_residues = scores_manifest[name]["patch_residues"]

    display(HTML(f"""
    <hr><h3 style='color: #8B008B;'>🚀 Initiating Island: {name}</h3>
    <p><b>Target:</b> {generation_batches_per_island} Batches (Total {generation_batches_per_island * base_batch_size} designs)<br>
    <b>Core Hotspots:</b> {','.join(residues)} | <b>6Å Patch Size (Ready for Vis):</b> <span style='color:green;'>{len(patch_residues)} Residues</span></p>
    """))

    if yaml_path.exists():
        with open(yaml_path, 'r') as f: yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in patch_residues]
        with open(yaml_path, 'w') as f: yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    for batch_idx in range(1, generation_batches_per_island + 1):
        run_name = f"{SESSION_NAME}_{name}_Batch{batch_idx}"
        inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{run_name}'

        valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()] if inference_dir.exists() else []
        best_row, batch_max_score, top_pdb = {}, -999.0, None

        if not force_restart and valid_csvs:
            print(f"\n   ⏭️ [SKIPPED] Batch {batch_idx}/{generation_batches_per_island} results found. Loading history...")
        else:
            dynamic_seed = random.randint(10000, 99999)
            cmd_str = (
                f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={run_name} "
                f"++generation.task_name={task_name} ++generation.num_designs={base_batch_size} "
                f"++generation.dataloader.batch_size={base_batch_size} ++generation.search.max_batch_size={base_batch_size} "
                f"++evaluation.dataloader.batch_size={evaluation_batch_size} ++generation.seed={dynamic_seed} "
                f"++run_filter=True ++run_evaluate=True ++evaluate.num_recycles=1 ++evaluate.pad_to_max_length=True "
                f"++evaluate.use_msa=False ++evaluate.msa_mode=single_sequence ++run_analyze=True"
            )

            print(f"\n   [Batch {batch_idx}/{generation_batches_per_island}] Processing {base_batch_size} designs (Seed: {dynamic_seed})... \n", flush=True)

            process = subprocess.Popen(
                f"source env.sh && {cmd_str}", env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in process.stdout: print(line, end='', flush=True)
            process.wait()
            print("\nDone.")

            valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]

        if valid_csvs:
            target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
            df = pd.read_csv(target_csv)
            score_col = next((col for col in ['af2folding_max_ipsae', 'max_ipSAE'] if col in df.columns), None)

            if score_col:
                df[score_col] = pd.to_numeric(df[score_col], errors='coerce')
                top_idx = df[score_col].idxmax()
                if not pd.isna(top_idx):
                    best_row = df.loc[top_idx].to_dict()
                    batch_max_score = float(best_row[score_col])
                    top_pdb = str(Path(inference_dir) / best_row.get('pdb_path', ''))
                    if not Path(top_pdb).exists():
                        potential_pdbs = list(inference_dir.rglob(f"{best_row.get('design_id', '')}*.pdb"))
                        if potential_pdbs: top_pdb = str(potential_pdbs[0])

                    # 🌟 核心：更新全局最优并扫描 PAE 排名
                    if batch_max_score > scores_manifest[name]["max_score"]:
                        scores_manifest[name]["max_score"] = batch_max_score
                        scores_manifest[name]["top_pdb"] = top_pdb

                        pae_ranks = analyze_hotspot_pae(inference_dir, best_row.get('design_id', ''), patch_residues, target_chain_length, natural_to_af2)
                        scores_manifest[name]["hotspot_pae_ranking"] = pae_ranks

                        with open(scores_manifest_path, 'w') as f:
                            json.dump(scores_manifest, f, indent=4)

        d_id = best_row.get('design_id', f'Top_{name}_B{batch_idx}')
        score_col_display = next((col for col in ['af2folding_max_ipsae', 'max_ipSAE'] if col in best_row), None)
        ipsae_val = best_row.get(score_col_display, -999.0) if score_col_display else -999.0
        ptm_val = best_row.get('af2folding_ptm_log', -999.0)
        iptm_val = best_row.get('af2folding_i_ptm_log', -999.0)
        plddt_val = best_row.get('af2folding_plddt', -999.0)
        rmsd_val = best_row.get('af2folding_rmsd', -999.0)
        reward_val = best_row.get('total_reward', -999.0)

        table_html = f"""
        <div style='background: #f8f9fa; padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #0056b3;'>
            <b style='font-size: 14px; color: #333;'>Island: {name} | Batch {batch_idx}/{generation_batches_per_island}</b>
            <pre style='margin-top: 8px; background: #fff; padding: 10px; border: 1px solid #ddd; border-radius: 4px; overflow-x: auto; color: #333;'>
Design_ID        | ipSAE    | pTM      | iPTM     | pLDDT    | RMSD       | Reward
--------------------------------------------------------------------------------------
{d_id:<16} | {fs(ipsae_val):<8} | {fs(ptm_val):<8} | {fs(iptm_val):<8} | {fs(plddt_val, is_plddt=True):<8} | {fs(rmsd_val, is_rmsd=True):<10} | {fs(reward_val):<8}
</pre>
        </div>
        """
        display(HTML(table_html))

    # ==========================================
    # 🏆 Island 生成完毕：全局热点更新与 UI 汇总输出
    # ==========================================
    if scores_manifest[name]["top_pdb"]:
        max_ipsae = scores_manifest[name]["max_score"]
        pae_dict = scores_manifest[name].get("hotspot_pae_ranking", {})

        if pae_dict:
            # 1. 更新全局 PAE 追踪器 (保留历史最低/最好的 PAE 值)
            for resi, pae_val in pae_dict.items():
                if resi not in global_pae_tracker:
                    global_pae_tracker[resi] = pae_val
                else:
                    global_pae_tracker[resi] = min(global_pae_tracker[resi], pae_val)

            # 2. 将全局追踪器排序并覆盖存盘 (给 Cell 22 准备)
            sorted_global_pae = {k: v for k, v in sorted(global_pae_tracker.items(), key=lambda item: item[1])}
            with open(GLOBAL_PAE_FILE, 'w') as f:
                json.dump(sorted_global_pae, f, indent=4)

            # 3. 构建当前 Island 的局表面板
            sorted_local_pae = sorted(pae_dict.items(), key=lambda x: x[1])
            pae_html_items = [
                f"<span style='display:inline-block; background:#fff; padding:4px 8px; border:1px solid #b8daff; border-radius:4px; margin:4px 4px 0 0; font-family:monospace;'>"
                f"<b style='color:#0056b3;'>{k}</b>: {v:.1f}</span>"
                for k, v in sorted_local_pae[:15] # 界面上最多展示前 15 个，防止刷屏
            ]

            summary_html = f"""
            <div style='background: #e9f7ef; padding: 15px; border-radius: 8px; margin: 15px 0 25px 0; border-left: 6px solid #28a745; box-shadow: 0 2px 4px rgba(0,0,0,0.05);'>
                <h4 style='margin-top:0; color: #155724; border-bottom: 1px solid #c3e6cb; padding-bottom: 8px;'>🎯 Island Completion Summary: {name}</h4>
                <p style='font-size: 16px;'><b>🏆 Maximum ipSAE:</b> <span style='color:red; font-weight:bold;'>{max_ipsae:.4f}</span></p>
                <p style='margin-bottom: 5px;'><b>🧬 Most Useful Anchor Spots (PAE to Peptide | Lower = Better):</b></p>
                <div style='line-height: 1.8;'>{''.join(pae_html_items)}</div>
                <p style='margin-top: 10px; font-size: 12px; color: #6c757d;'>💾 Global Master List updated: {len(global_pae_tracker)} total anchors tracked.</p>
            </div>
            """
            display(HTML(summary_html))
        else:
            print(f"✅ Island {name} completed. Max ipSAE: {max_ipsae:.4f} (PAE data unavailable)")

# --- 5. Hybridization & Footprint Extraction ---
print("\n🧬 Triggering Hybridization Protocol (Footprint Extraction)...")

def calculate_contributions_cb(pdb_path, target_chain, natural_order_list):
    contributions = {r: 0.0 for r in natural_order_list}
    if not pdb_path or not Path(pdb_path).exists(): return contributions

    af2_target_atoms, af2_binder_atoms = {}, {}
    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM"):
                atom_name = line[12:16].strip()
                if atom_name not in ["CA", "CB"]: continue
                chain = line[21]
                resi = line[22:26].strip()
                coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                if chain == target_chain:
                    if resi not in af2_target_atoms: af2_target_atoms[resi] = {}
                    af2_target_atoms[resi][atom_name] = coord
                else:
                    if resi not in af2_binder_atoms: af2_binder_atoms[resi] = {}
                    af2_binder_atoms[resi][atom_name] = coord

    t_rep = {natural_order_list[i]: af2_target_atoms[rid].get('CB', af2_target_atoms[rid].get('CA'))
             for i, rid in enumerate(sorted(af2_target_atoms.keys(), key=int)) if i < len(natural_order_list)}
    b_rep = [atoms.get('CB', atoms.get('CA')) for atoms in af2_binder_atoms.values()]

    if not b_rep or not t_rep: return contributions
    b_tree = KDTree(b_rep)
    for nat_rid, coord in t_rep.items():
        if coord is None: continue
        dists, _ = b_tree.query(coord, k=1)
        if dists < 6.0: contributions[nat_rid] = 1.0 / (dists + 0.1)
    return contributions

isl_0_contribs = calculate_contributions_cb(scores_manifest["Isl_0"]["top_pdb"], target_chains, ordered_natural_resis)
isl_0_active_contribs = {k: v for k, v in isl_0_contribs.items() if k in base_hotspots}
sorted_isl_0 = sorted(isl_0_active_contribs.keys(), key=lambda k: isl_0_active_contribs[k], reverse=True)
pruned_isl_0 = sorted_isl_0[:-3] if len(sorted_isl_0) > 3 else sorted_isl_0

manifest_path = final_dir / f"Hybrid_Islands_Manifest.json"
hybrid_islands = {
    "Isl_0": {
        "baseline_ipsae": scores_manifest["Isl_0"]["max_score"],
        "core_hotspots": sorted(pruned_isl_0, key=lambda x: int(re.sub(r'\D', '', x))),
        "neo_hotspots": [],
        "hybrid_hotspots": sorted(pruned_isl_0, key=lambda x: int(re.sub(r'\D', '', x)))
    }
}
with open(manifest_path, 'w') as f: json.dump(hybrid_islands, f, indent=4)

for isl in satellite_islands:
    name = isl["name"]
    max_score = scores_manifest[name]["max_score"]
    contribs = calculate_contributions_cb(scores_manifest[name]["top_pdb"], target_chains, ordered_natural_resis)

    novel_footprint_contribs = {k: v for k, v in contribs.items() if k not in pruned_isl_0 and v > 0}
    top_neo = sorted(novel_footprint_contribs.keys(), key=lambda k: novel_footprint_contribs[k], reverse=True)[:3]

    hybrid_name = name.replace("Isl_", "Isl_0")
    hybrid_residues = sorted(list(set(pruned_isl_0 + top_neo)), key=lambda x: int(re.sub(r'\D', '', x)))

    hybrid_islands[hybrid_name] = {
        "baseline_ipsae": max_score,
        "core_hotspots": pruned_isl_0,
        "neo_hotspots": top_neo,
        "hybrid_hotspots": hybrid_residues
    }

    with open(SUMMARY_CSV, 'a') as f:
        f.write(f"{hybrid_name},{max_score:.4f},{len(hybrid_residues)},\"{','.join(hybrid_residues)}\"\n")

    display(HTML(f"<b>{hybrid_name}</b> | Global Absolute ipSAE: <span style='color:red;'>{max_score:.4f}</span> | Novel Footprint (Red): {','.join(top_neo)} | Merged: {','.join(hybrid_residues)}"))
    with open(manifest_path, 'w') as f: json.dump(hybrid_islands, f, indent=4)

print(f"\n💾 Incremental Export Complete: {manifest_path.name}")

# == CELL code INDEX 24 ==
# Cell_21_Physical_Generation_Visualizations.py
# --- 5. Separate Visualizations (Real-Time Watch Mode) ---
import json
import re
from pathlib import Path
import py3Dmol
from IPython.display import HTML, display

print("\n🎨 Initiating Real-Time Watch Mode: Rendering Top Binders & Key Anchors...")

# 读取硬盘数据
scores_manifest = {}
hybrid_islands = {}

scores_manifest_path = final_dir / "Scores_Manifest.json"
manifest_path = final_dir / "Hybrid_Islands_Manifest.json"

if scores_manifest_path.exists():
    with open(scores_manifest_path, 'r') as f:
        scores_manifest = json.load(f)
    print(f"✅ Found {len(scores_manifest)} completed Islands ready for preview.")
else:
    print("⏳ Waiting for Cell 20 to finish generating the first batch...")

if manifest_path.exists():
    with open(manifest_path, 'r') as f:
        hybrid_islands = json.load(f)
else:
    print("🌱 Hybrid Manifest not yet generated. Entering Live Preview Mode...")

d3to1 = {'CYS': 'C', 'ASP': 'D', 'SER': 'S', 'GLN': 'Q', 'LYS': 'K',
         'ILE': 'I', 'PRO': 'P', 'THR': 'T', 'PHE': 'F', 'ASN': 'N',
         'GLY': 'G', 'HIS': 'H', 'LEU': 'L', 'ARG': 'R', 'TRP': 'W',
         'ALA': 'A', 'VAL': 'V', 'GLU': 'E', 'TYR': 'Y', 'MET': 'M'}

# 从全局内存中获取配置
global_ordered_resis = globals().get('ordered_natural_resis', [])
natural_to_af2 = {nat: str(i+1) for i, nat in enumerate(global_ordered_resis)} if global_ordered_resis else {}
global_base_hotspots = globals().get('base_hotspots', [])

for isl_name, data in scores_manifest.items():
    top_pdb = data.get("top_pdb")
    if not top_pdb or not Path(top_pdb).exists():
        continue

    with open(top_pdb, 'r') as f: pdb_data = f.read()

    chains_seq = {}
    first_resi_binder = None
    for line in pdb_data.split('\n'):
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            res_name = line[17:20].strip()
            chain_id = line[21]
            if chain_id not in chains_seq: chains_seq[chain_id] = ""
            chains_seq[chain_id] += d3to1.get(res_name, 'X')

    chain_lengths = {c: len(seq) for c, seq in chains_seq.items()}
    if not chain_lengths: continue
    sorted_chains = sorted(chain_lengths.keys(), key=lambda c: chain_lengths[c])
    binder_chains = [sorted_chains[0]]
    target_chain_ids = [c for c in sorted_chains[1:]]

    for line in pdb_data.split('\n'):
        if line.startswith("ATOM") and line[21] == binder_chains[0]:
            first_resi_binder = line[22:26].strip()
            break

    hybrid_name = isl_name.replace("Isl_", "Isl_0") if isl_name != "Isl_0" else "Isl_0"
    island_data = hybrid_islands.get(hybrid_name, {})

    # ==========================================
    # 🎯 核心逻辑更新：寻找 Patch 上最强的 Top 2 AA
    # ==========================================

    # 1. Global Core (Orange): 最初始的基准热点
    global_core_raw = global_base_hotspots

    # 2. Global Neo (Red): 【修改点】改为该 Island Patch 上 PAE 表现最好的前两个氨基酸
    pae_ranking = data.get("hotspot_pae_ranking", {})
    if pae_ranking:
        # 按 PAE 从低到高排序，取前 2 个作为最强锚点
        sorted_anchors = sorted(pae_ranking.items(), key=lambda x: x[1])
        neo_hs_raw = [k for k, v in sorted_anchors[:2]]
        best_pae_val = sorted_anchors[0][1] if sorted_anchors else 0
    else:
        # 如果还没跑完 PAE，则显示为空，保持严谨
        neo_hs_raw = []
        best_pae_val = "N/A"

    # 3. Island Core (Gray): 本 Island 指定的核心靶点区域
    island_core_raw = data.get("residues", [])

    # 4. Island 6A Patch (White): 扩张后的表面
    patch_resi_raw = data.get("patch_residues", [])

    # 智能翻译坐标：支持AF2重排映射
    def translate_resi(resi_list):
        res = []
        for x in resi_list:
            num_str = re.sub(r'\D', '', str(x))
            if natural_to_af2 and num_str in natural_to_af2:
                res.append(int(natural_to_af2[num_str]))
            elif num_str:
                res.append(int(num_str))
        return res

    global_core_int = translate_resi(global_core_raw)
    neo_hs_int = translate_resi(neo_hs_raw)
    island_core_int = translate_resi(island_core_raw)
    patch_resi_int = translate_resi(patch_resi_raw)

    # 取差集：染白色扩张区域（排除核心后剩下的表面部分）
    expanded_resi_int = list(set(patch_resi_int) - set(island_core_int)) if patch_resi_int else []
    first_resi_binder_int = int(re.sub(r'\D', '', str(first_resi_binder))) if first_resi_binder else None

    # HTML 面板渲染
    ipsae_val = data.get("max_score", -999.0)
    binder_seq = chains_seq.get(binder_chains[0], "N/A") if binder_chains else "N/A"
    peptide_len = len(binder_seq) if binder_seq != "N/A" else 0

    # 顶部状态条，标注出 Top 2 锚点
    anchor_info = f" | <b style='color:red;'>Top Anchors:</b> {', '.join(neo_hs_raw)}" if neo_hs_raw else ""

    html_content = f"""
    <hr>
    <h3 style='color: #0056b3;'>Island View: {isl_name}</h3>
    <div style='background: #f8f9fa; padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #28a745;'>
        <p style='margin: 5px 0;'><b>🏆 Max ipSAE:</b> <span style='color:red; font-size:16px;'>{ipsae_val:.4f}</span> | <b>Best PAE:</b> {best_pae_val}{anchor_info}</p>
        <p style='margin: 5px 0;'><b>🧬 Peptide Sequence:</b> <code style='background:#fff; padding:2px 6px; border: 1px solid #ddd; border-radius:4px; font-size:14px; color:#d63384;'>{binder_seq}</code></p>
    </div>
    <div style='font-size: 13px; color: #555; margin-bottom: 5px;'>
       <b>Color Map:</b>
       <span style='background:#333; color:white; padding:2px 5px; border-radius:3px;'>Island Core (Gray)</span>
       <span style='background:#fff; color:#333; border:1px solid #ccc; padding:2px 5px; border-radius:3px;'>6Å Patch (Ghost White)</span>
       <span style='color:orange; font-weight:bold;'>Global Core (Orange)</span>
       <span style='color:red; font-weight:bold;'>Best Anchors on Patch (Red)</span>
       <span style='color:lime; font-weight:bold;'>Peptide (Green)</span>
    </div>
    """
    display(HTML(html_content))

    viewer = py3Dmol.view(width=800, height=500)
    viewer.addModel(pdb_data, 'pdb')

    # Target Mesh
    target_sel = {'chain': target_chain_ids}
    viewer.setStyle(target_sel, {'cartoon': {'color': '#A9A9A9', 'opacity': 0.7}})
    viewer.addSurface(py3Dmol.SES, {'color': '#A9A9A9', 'wireframe': True}, target_sel)

    # 1. Global Core (Orange)
    if global_core_int:
        c_sel = {'chain': target_chain_ids, 'resi': global_core_int}
        viewer.setStyle(c_sel, {'cartoon': {'color': 'orange', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'orange', 'opacity': 1.0}, c_sel)

    # 2. Global Neo -> 现在是 Island Top 2 Anchors (Red)
    if neo_hs_int:
        n_sel = {'chain': target_chain_ids, 'resi': neo_hs_int}
        viewer.setStyle(n_sel, {'cartoon': {'color': 'red', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'red', 'opacity': 1.0}, n_sel)

    # 3. 6Å 扩张辅助面 (Ghost White)
    if expanded_resi_int:
        exp_sel = {'chain': target_chain_ids, 'resi': expanded_resi_int}
        viewer.setStyle(exp_sel, {'cartoon': {'color': 'white', 'opacity': 0.4}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'white', 'opacity': 0.3}, exp_sel)

    # 4. 当前 Island 核心 (Solid Gray)
    if island_core_int:
        sat_sel = {'chain': target_chain_ids, 'resi': island_core_int}
        viewer.setStyle(sat_sel, {'cartoon': {'color': 'gray', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'gray', 'opacity': 1.0}, sat_sel)

    # Binder (Green)
    if binder_chains:
        b_sel = {'chain': binder_chains}
        viewer.setStyle(b_sel, {'cartoon': {'color': 'lime', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.SES, {'color': 'lime', 'opacity': 1.0}, b_sel)

    # Binder N-Term (Blue) - 方便识别多肽方向
    if first_resi_binder_int and binder_chains:
        nterm_sel = {'chain': binder_chains[0], 'resi': [first_resi_binder_int]}
        viewer.setStyle(nterm_sel, {'cartoon': {'color': 'blue', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'blue', 'opacity': 1.0}, nterm_sel)

    viewer.zoomTo()

    try:
        display(viewer.show())
    except Exception:
        viewer.show()

# == CELL code INDEX 25 ==
# Cell_22_Deep_Greedy_Convergence_Loop.py
# ==============================================================================
# 🔥 GLOBAL DEEP GREEDY EVOLUTION PARADIGM
# ==============================================================================
# Requirements Met:
# - Global Pool Merge: Hardcoded base_hotspots + Global PAE rankings.
# - Initial State: Top 10 strongest amino acids.
# - Evolution Logic: Run -> Evaluate -> Drop worst 2 contributors -> Add next 2 from PAE pool.
# - Stagnation & Convergence: If ipSAE drops, discard the failed 2, keep the core 8,
#   and try the *next* 2 from the pool. Converge when the pool is exhausted.
# - Fault Tolerance & Trajectory: Real-time logging to a Global Trajectory CSV.
# - Consensus Scoring: Distance (<4.5A) + pLDDT (>50) weighting across Top 3 PDBs.
# ==============================================================================

import os, sys, json, subprocess, time, datetime, re, yaml, random, csv
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import KDTree
from IPython.display import HTML, display

print("🌌 Initiating Cell 22: Global Deep Greedy Convergence Loop...")

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
        pattern = rf"Section2_TargetPreprocess(?:_TimeMachine)? \| Run_ID: ({re.escape(task_name)}_\d+_\d+) \| Dir: (final_\d+_\d+)"
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
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))

# 次数在 section0 已定义 (generation_batches_per_ev)
generation_batches_per_ev = int(root_cfg.get('generation_batches_per_ev', 6))
base_batch_size = 8

print(f"⚙️ Evolution Configured: {generation_batches_per_ev} batches × {base_batch_size} designs per iteration.")

# --- 🌟 SMART RESTART & SESSION IDENTITY ---
force_restart = bool(root_cfg.get('force_restart_section_7', False))
SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
TRAJECTORY_CSV = final_dir / f"Global_Evolution_Trajectory_{SESSION_TIMESTAMP}.csv"
CONVERGED_MANIFEST = final_dir / f"Global_Converged_Manifest_{SESSION_TIMESTAMP}.json"

if force_restart:
    print("\n🗑️ [COMMAND] Force Restart enabled. Cleaning up previous Global Evolutions...")
    for old_json in final_dir.glob("Global_Converged_Manifest_*.json"): old_json.unlink()
    for old_csv in final_dir.glob("Global_Evolution_Trajectory_*.csv"): old_csv.unlink()

with open(TRAJECTORY_CSV, 'w') as f:
    f.write("Iteration,ipSAE,Action,Details,Current_Hotspots\n")

# --- 🌟 HISTORY CSV LINKING ---
HISTORY_CSV = BASE_DIR / 'screening_results' / 'history_run.csv'
if HISTORY_CSV.exists():
    try:
        updated_rows = []
        with open(HISTORY_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            if "Overall_Data_Link" not in header: header.append("Overall_Data_Link")
            link_idx = header.index("Overall_Data_Link")
            run_id_idx = header.index("Run_ID") if "Run_ID" in header else -1

            updated_rows.append(header)
            for row in reader:
                while len(row) < len(header): row.append("")
                if run_id_idx != -1 and row[run_id_idx] == run_id:
                    new_link = f"[View Global Evolution Log]({TRAJECTORY_CSV.relative_to(BASE_DIR)})"
                    if new_link not in row[link_idx]:
                        row[link_idx] = f"{row[link_idx]} | {new_link}" if str(row[link_idx]).strip() else new_link
                updated_rows.append(row)
        with open(HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(updated_rows)
    except Exception as e: pass

# --- 1. Load Global Data Sources ---
GEOMETRIC_MANIFEST = final_dir / "Geometric_Islands_Manifest.json"
GLOBAL_PAE_FILE = final_dir / "Global_Hotspot_PAE_Ranking.json"

with open(GEOMETRIC_MANIFEST, 'r') as f: geo_data = json.load(f)
base_hotspots = geo_data.get("base_hotspots", [])

global_pae_tracker = {}
if GLOBAL_PAE_FILE.exists():
    with open(GLOBAL_PAE_FILE, 'r') as f: global_pae_tracker = json.load(f)

# --- 2. Construct the Master Candidate Pool ---
# 逻辑：Hardcoded 热点优先级最高，排在最前面。随后根据 PAE 从低到高补齐剩余列表。
master_pool = list(base_hotspots)
for resi, pae in global_pae_tracker.items():
    if resi not in master_pool:
        master_pool.append(resi)

if not master_pool:
    print("❌ Error: Master pool is empty. Please check Cell 20 execution.")
    sys.exit(1)

# --- 3. Biological Sequence Extraction ---
SOURCE_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"
ordered_natural_resis = []
with open(SOURCE_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA" and line[21] == target_chains:
            ordered_natural_resis.append(line[22:26].strip())

# --- Core Loop Utilities ---
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})
yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'

def calculate_consensus_contributions(pdb_paths, target_chain, natural_order_list):
    consensus = {r: 0.0 for r in natural_order_list}
    valid_pdbs = [p for p in pdb_paths if p and Path(p).exists()]
    if not valid_pdbs: return consensus

    for pdb_path in valid_pdbs:
        af2_target_atoms, af2_binder_atoms, target_plddts = {}, {}, {}
        with open(pdb_path, 'r') as f:
            for line in f:
                if line.startswith("ATOM"):
                    atom_name = line[12:16].strip()
                    chain, resi = line[21], line[22:26].strip()
                    coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])

                    if chain == target_chain:
                        if atom_name in ["CA", "CB"]:
                            if resi not in af2_target_atoms: af2_target_atoms[resi] = {}
                            af2_target_atoms[resi][atom_name] = coord
                        if atom_name == "CA":
                            try: target_plddts[resi] = float(line[60:66].strip())
                            except: target_plddts[resi] = 50.0
                    else:
                        if atom_name in ["CA", "CB"]:
                            if resi not in af2_binder_atoms: af2_binder_atoms[resi] = {}
                            af2_binder_atoms[resi][atom_name] = coord

        t_rep = {natural_order_list[i]: af2_target_atoms[af2_rid].get('CB', af2_target_atoms[af2_rid].get('CA'))
                 for i, af2_rid in enumerate(sorted(af2_target_atoms.keys(), key=int)) if i < len(natural_order_list)}
        b_rep = [atoms.get('CB', atoms.get('CA')) for atoms in af2_binder_atoms.values()]

        if not b_rep or not t_rep: continue
        b_tree = KDTree(b_rep)
        for nat_rid, coord in t_rep.items():
            if coord is None: continue
            dists, _ = b_tree.query(coord, k=1)
            if dists < 4.5:
                plddt = target_plddts.get(nat_rid, 0.0)
                if plddt >= 50.0:  # 硬阈值
                    consensus[nat_rid] += (1.0 / (dists + 0.1)) * (plddt / 100.0)
    return consensus

# ==============================================================================
# 🚀 4. THE GLOBAL EVOLUTION ENGINE (Drop 2, Add 2)
# ==============================================================================

# 初始状态：抓取最好的前 10 个作为首发阵容
initial_size = min(10, len(master_pool))
active_hotspots = master_pool[:initial_size]
remaining_pool = master_pool[initial_size:]

best_ipsae = -999.0
best_active = []
kept_core_8 = []
iteration = 1

display(HTML(f"""
<div style='background: #e6f2ff; padding: 15px; border-radius: 8px; border-left: 6px solid #0056b3;'>
    <h3 style='margin-top:0; color: #004085;'>🌍 Global Evolution Initialized</h3>
    <p><b>Total Candidates in Master Pool:</b> {len(master_pool)}</p>
    <p><b>Starting Top 10 Lineup:</b> <code style='color: #d63384;'>{','.join(active_hotspots)}</code></p>
</div>
"""))

while True:
    display(HTML(f"<hr><h4 style='color: #8B008B;'>🔄 Iteration {iteration}</h4><p><b>Evaluating Active Hotspots:</b> {','.join(active_hotspots)}</p>"))

    # 1. 更新 Yaml 注入当前的 10 个靶点
    if yaml_path.exists():
        with open(yaml_path, 'r') as f: yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f: yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    iteration_all_results = []

    # 2. 生成批次循环
    for batch_idx in range(1, generation_batches_per_ev + 1):
        run_name = f"GlobalEvo_Iter{iteration}_B{batch_idx}_{SESSION_TIMESTAMP}"
        inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{run_name}'

        dynamic_seed = random.randint(10000, 99999)
        cmd_str = (
            f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={run_name} "
            f"++generation.task_name={task_name} ++generation.num_designs={base_batch_size} "
            f"++generation.dataloader.batch_size={base_batch_size} ++generation.search.max_batch_size={base_batch_size} "
            f"++evaluation.dataloader.batch_size={evaluation_batch_size} ++generation.seed={dynamic_seed} "
            f"++run_filter=True ++run_evaluate=True ++run_analyze=True"
        )

        print(f"   [Batch {batch_idx}/{generation_batches_per_ev}] Generating {base_batch_size} designs... ", flush=True)
        process = subprocess.Popen(
            f"source env.sh && {cmd_str}", env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        for line in process.stdout: print(line, end='', flush=True)
        process.wait()

        valid_csvs = list(inference_dir.rglob('*.csv'))
        if valid_csvs:
            target_csv = max(valid_csvs, key=lambda x: x.stat().st_size)
            df = pd.read_csv(target_csv)
            score_col = next((c for c in ['af2folding_max_ipsae', 'max_ipSAE'] if c in df.columns), None)
            if score_col:
                df[score_col] = pd.to_numeric(df[score_col], errors='coerce')
                df = df.dropna(subset=[score_col])
                for _, row in df.nlargest(3, score_col).iterrows():
                    iteration_all_results.append((float(row[score_col]), row.to_dict(), str(inference_dir)))

    # 3. 统计迭代最高分，抓取 Top 3 结构
    iteration_all_results.sort(key=lambda x: x[0], reverse=True)
    current_ipsae = iteration_all_results[0][0] if iteration_all_results else -999.0

    top_3_pdbs = []
    for score, row_dict, inf_dir in iteration_all_results[:3]:
        pdb_raw = row_dict.get('pdb_path', '')
        if pdb_raw:
            cand = Path(inf_dir) / pdb_raw
            if cand.exists(): top_3_pdbs.append(str(cand))

    color = "green" if current_ipsae >= best_ipsae else "red"
    display(HTML(f"<p><b>Score achieved:</b> <span style='color:{color}; font-weight:bold; font-size:16px;'>{current_ipsae:.4f}</span> (Historical Best: {best_ipsae:.4f})</p>"))

    # ==========================================
    # 🧬 EVOLUTION LOGIC ROUTING
    # ==========================================
    if current_ipsae >= best_ipsae:
        # 🌟 突破成功！接受并进化
        best_ipsae = current_ipsae
        best_active = list(active_hotspots)

        print(f"🧬 Evaluating Consensus Footprint for Top 3 structures...")
        scores = calculate_consensus_contributions(top_3_pdbs, target_chains, ordered_natural_resis)

        # 将当前的 10 个按贡献度排序
        active_sorted = sorted(active_hotspots, key=lambda x: scores.get(x, 0), reverse=True)

        # 踢出最差的 2 个，保留核心 8 个
        if len(active_sorted) > 2:
            kept_core_8 = active_sorted[:-2]
            dropped_str = ','.join(active_sorted[-2:])
        else:
            kept_core_8 = active_sorted
            dropped_str = "None"

        print(f"✂️ Dropped lowest contributing: {dropped_str}")

        # 如果替补席空了，完美收敛
        if not remaining_pool:
            print("🛑 CONVERGED: Pool exhausted. Peak performance achieved.")
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},CONVERGED_SUCCESS,Pool Exhausted,\"{','.join(best_active)}\"\n")
            break

        # 从替补席提拔 2 个新兵
        added = remaining_pool[:2]
        remaining_pool = remaining_pool[2:] # 替补池缩减

        active_hotspots = kept_core_8 + added
        active_hotspots = sorted(list(set(active_hotspots)), key=lambda x: int(re.sub(r'\D', '', x)))

        print(f"➕ Added next best candidates from pool: {','.join(added)}")
        with open(TRAJECTORY_CSV, 'a') as f:
            f.write(f"{iteration},{current_ipsae:.4f},EVOLVED,\"Drop: {dropped_str} | Add: {','.join(added)}\",\"{','.join(active_hotspots)}\"\n")

    else:
        # 📉 表现倒退！拒绝并平行替换
        print("📉 Performance degraded. Discarding the last additions.")

        # 替补席如果空了，说明所有组合都试过了，直接收敛到之前的最佳状态
        if not remaining_pool:
            print(f"🛑 CONVERGED: All combinations exhausted. Finalizing at ipSAE {best_ipsae:.4f}")
            with open(TRAJECTORY_CSV, 'a') as f:
                f.write(f"{iteration},{current_ipsae:.4f},CONVERGED_DEGRADED,Reverted to best state,\"{','.join(best_active)}\"\n")
            break

        # 核心逻辑：保持上次的 core_8 不变，直接从剩下的替补池里再抓 2 个新的试试
        added = remaining_pool[:2]
        remaining_pool = remaining_pool[2:]

        active_hotspots = kept_core_8 + added
        active_hotspots = sorted(list(set(active_hotspots)), key=lambda x: int(re.sub(r'\D', '', x)))

        print(f"🔀 Retrying core with next alternative additions: {','.join(added)}")
        with open(TRAJECTORY_CSV, 'a') as f:
            f.write(f"{iteration},{current_ipsae:.4f},ROLLBACK_RETRY,\"Swapped out bad candidates for: {','.join(added)}\",\"{','.join(active_hotspots)}\"\n")

    iteration += 1

# ==========================================
# 🏆 EXPORT FINAL RESULTS
# ==========================================
display(HTML(f"""
<div style='background: #d4edda; padding: 20px; border-radius: 8px; border-left: 6px solid #28a745; margin-top: 20px;'>
    <h2 style='margin-top:0; color: #155724;'>🏁 Global Evolution Completed</h2>
    <p style='font-size: 18px;'><b>👑 Ultimate Maximum ipSAE:</b> <span style='color:red; font-weight:bold;'>{best_ipsae:.4f}</span></p>
    <p><b>🧬 Final Optimized Anchor Lineup:</b> <code style='font-size: 16px;'>{','.join(best_active)}</code></p>
</div>
"""))

final_checkpoint = {
    "task_name": task_name,
    "final_ipsae": best_ipsae,
    "ultimate_hotspots": best_active,
    "total_iterations_taken": iteration - 1
}

with open(CONVERGED_MANIFEST, 'w') as f:
    json.dump(final_checkpoint, f, indent=4)

print(f"💾 Checkpoint saved to: {CONVERGED_MANIFEST.name}")
print(f"📊 Full Trajectory Audit available in: {TRAJECTORY_CSV.name}")

