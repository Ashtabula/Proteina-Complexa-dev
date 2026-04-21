
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