# Cell_20_Physical_Generation_and_Hybridization.py
# Requirements:
# - Load Geometric_Islands_Manifest.json from Cell 19.
# - Extract sequence order for AF2 reverse mapping.
# - Workaround Generation Logic: complexa caps at batch_size (8). We implement a Python-level 'for' loop
#   to force sequential batches per Island, configurable via 'generation_batches_per_island' in Section 0.
# - Dynamic Seed Injection: Force a unique random seed per batch to prevent identical structural clones.
# - Real-time Evaluation UI: HTML UI summary output AFTER EACH BATCH finishes.
# - Hybridization: Evaluate interface contribution using CB atoms via KDTree (<6.0A).
# - Extract Footprints: Drop 3 lowest contributors from Isl_0, add 3 highest from the novel footprint.
# - Section 7 Smart Restart: Read force_restart_section_7 to wipe old Hybrid manifests and CSVs if triggered.
# - Export to Hybrid_Islands_Manifest.json and CSV.
# - Separate Visualizations: Output each Island separately.
#
# 🔥 TIME MACHINE & TRUE RESUME UPDATE:
# - Smart Session Identity: Inherits historical SESSION_TIMESTAMP instead of generating a new one.
# - Subprocess Interception: Scans inference directories to SKIP already computed batches.
# - Global Tracker Sync: Dynamically injects the Hybrid_Summary log link into history_run.csv.
# ⚙️ CONFIGURATION UPDATE: Abstracted generation_batches_per_island to root settings.

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

# 读取 last_runs.txt (如果 Time Machine 被触发，此处读取的已经是历史锚点)
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

# --- 🌟 SMART RESTART LOGIC & SESSION IDENTITY ---
force_restart = bool(root_cfg.get('force_restart_section_7', False))
SESSION_TIMESTAMP = None

if force_restart:
    print("\n🗑️ [COMMAND] Force Restart Section 6 is ENABLED. Cleaning up previous Hybrid outputs...")
    manifest_file = final_dir / "Hybrid_Islands_Manifest.json"
    if manifest_file.exists(): manifest_file.unlink()
    for old_csv in final_dir.glob("Hybrid_Summary_*.csv"):
        old_csv.unlink()
else:
    print(f"\n⏭️ [RESUME] Smart Resume active. Scanning for historical Hybridization sessions...")
    existing_summaries = list(final_dir.glob("Hybrid_Summary_*.csv"))
    if existing_summaries:
        latest_summary = max(existing_summaries, key=lambda f: f.stat().st_mtime)
        match = re.search(r"Hybrid_Summary_(.*)\.csv", latest_summary.name)
        if match:
            SESSION_TIMESTAMP = match.group(1)
            print(f"🔄 True Resume: Re-attaching to historical session [{SESSION_TIMESTAMP}]")

# 如果没有历史记录，或者选择了重置，生成新的时间戳
if not SESSION_TIMESTAMP:
    SESSION_TIMESTAMP = datetime.datetime.now().strftime("Y%Y_M%m_D%d_H%H_M%M_S%S")
    print(f"🆕 New Hybridization Session initialized: [{SESSION_TIMESTAMP}]")

SESSION_NAME = f"Hybridization_{task_name}_{SESSION_TIMESTAMP}"
SUMMARY_CSV = final_dir / f"Hybrid_Summary_{SESSION_TIMESTAMP}.csv"

# 初始化 CSV 表头
if not SUMMARY_CSV.exists():
    with open(SUMMARY_CSV, 'w') as f:
        f.write("Island_Name,ipSAE,Hotspot_Count,Residues\n")

# --- 🌟 UPDATE history_run.csv with Master Log Link (Backfill) ---
HISTORY_CSV = BASE_DIR / 'screening_results' / 'history_run.csv'
if HISTORY_CSV.exists():
    try:
        updated_rows = []
        with open(HISTORY_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # 动态寻找 Overall_Data_Link 槽位，完美兼容带有 Top_Max_ipSAE 的 11 列新表头
            if "Overall_Data_Link" not in header:
                header.append("Overall_Data_Link")
            link_idx = header.index("Overall_Data_Link")
            run_id_idx = header.index("Run_ID") if "Run_ID" in header else -1

            updated_rows.append(header)
            for row in reader:
                while len(row) < len(header): row.append("") # 补齐防越界
                if run_id_idx != -1 and row[run_id_idx] == run_id:
                    # 回填 Markdown 链接
                    new_link = f"[View Hybrid Log]({SUMMARY_CSV.relative_to(BASE_DIR)})"
                    if new_link not in row[link_idx]:
                        row[link_idx] = f"{row[link_idx]} | {new_link}" if str(row[link_idx]).strip() else new_link
                updated_rows.append(row)
                
        with open(HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(updated_rows)
        print(f"📊 GLOBAL HISTORY: Successfully linked {SUMMARY_CSV.name} to Overall_Data_Link for Run_ID: {run_id}")
    except Exception as e:
        print(f"⚠️ Warning: Failed to update history_run.csv with masterlog link: {e}")

target_chains = str(cfg.get('target_chains', 'A')).split(',')[0].strip()
base_hotspots = geo_data["base_hotspots"]
satellite_islands = geo_data["satellite_islands"]
evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))

# --- 🌟 ABSTRACTED BATCH VARIABLES ---
# 从 Section 0 全局配置中读取生成批次数，默认值为 6
generation_batches_per_island = int(root_cfg.get('generation_batches_per_island', 6))
# 硬件/软件锁死限制，每次最多生成 8 个，保持硬编码
base_batch_size = 8  

print(f"⚙️ Configured to run {generation_batches_per_island} batches × {base_batch_size} designs per island (Total: {generation_batches_per_island * base_batch_size}).")

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

# --- 3. Execution: Complexa Design (Nested Loop with True Resume) ---
env = os.environ.copy()
env.update({'HYDRA_FULL_ERROR': '1', 'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONUNBUFFERED': '1'})
yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'

all_target_islands = [{"name": "Isl_0", "residues": base_hotspots}] + satellite_islands
# --- 🌟 NEW: Spatial Patch Extraction (Surface-Aware) ---
def extract_patch_residues(pdb_path, target_chain, core_res_list, radius=6.0):
    """提取以 core_res_list 为中心，半径 radius(Å) 内的所有 Target 表面残基 (Surface Patch)"""
    target_coords = {}
    ca_atoms = {}
    cb_atoms = {}
    res_names = {}
    island_coords = []
    
    if not pdb_path or not Path(pdb_path).exists():
        return core_res_list

    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM"):
                chain = line[21]
                if chain != target_chain: continue
                resi = line[22:26].strip()
                atom_name = line[12:16].strip()
                res_name = line[17:20].strip()
                
                coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                
                if resi not in target_coords:
                    target_coords[resi] = []
                target_coords[resi].append(coord)
                
                if atom_name == "CA": ca_atoms[resi] = coord
                if atom_name == "CB": cb_atoms[resi] = coord
                res_names[resi] = res_name
                
                if resi in core_res_list:
                    island_coords.append(coord)

    if not island_coords or not target_coords:
        return core_res_list # 降级保护

    # --- 1. 使用 KDTree 进行空间搜索 (距离过滤) ---
    island_tree = KDTree(island_coords)
    close_residues = []
    
    for resi, coords in target_coords.items():
        for coord in coords:
            dist, _ = island_tree.query(coord, k=1)
            if dist <= radius:
                close_residues.append(resi)
                break
                
    if not close_residues:
        return core_res_list

    # --- 2. 表面暴露过滤 (HSE Vector Check) ---
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
            else:
                v_out = np.array([0.0, 0.0, 1.0])
                
        norm = np.linalg.norm(v_out)
        if norm > 1e-4: v_out = v_out / norm
        else: v_out = np.array([0.0, 0.0, 1.0])
        
        n_idx_all = ca_kdtree.query_ball_point(ca, r=10.0)
        forward_neighbors = 0
        for n_idx in n_idx_all:
            if all_resis[n_idx] == resi: continue
            vec = ca_coords_array[n_idx] - ca
            if np.dot(vec, v_out) > 0:
                forward_neighbors += 1
                
        if forward_neighbors < 12:
            surface_patch.add(resi)

    if not surface_patch: return core_res_list
    return sorted(list(surface_patch), key=lambda x: int(re.sub(r'\D', '', x)))

all_target_islands = [{"name": "Isl_0", "residues": base_hotspots}] + satellite_islands
scores_manifest = {}

for isl in all_target_islands:
    name = isl["name"]
    residues = isl["residues"]
    
    # 🌟 检查表面氨基酸 (Core 不扩展，Satellite 扩展 6Å)\n
    if name == "Isl_0":\n
        patch_residues = extract_patch_residues(SOURCE_PDB_PATH, target_chains, residues, radius=0.0)\n
    else:\n
        patch_residues = extract_patch_residues(SOURCE_PDB_PATH, target_chains, residues, radius=6.0)\n
    
    display(HTML(f"<hr><h3 style='color: #8B008B;'>🚀 Initiating Island: {name}</h3><p><b>Target:</b> {generation_batches_per_island} Batches (Total {generation_batches_per_island * base_batch_size} designs)<br><b>Core Hotspots:</b> {','.join(residues)}<br><b>Surface Targets:</b> {','.join(patch_residues)} | <span style='color:green;'><b>Size:</b> {len(patch_residues)} Residues</span></p>"))

    if yaml_path.exists():
        with open(yaml_path, 'r') as f: yaml_data = yaml.safe_load(f)
        # 🌟 关键修复：将丰满的 patch_residues 传给生成模型，取代原先单薄的 residues
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in patch_residues]
        with open(yaml_path, 'w') as f: yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    island_absolute_max_score = -999.0
    island_absolute_top_pdb = None

    for batch_idx in range(1, generation_batches_per_island + 1):
        run_name = f"{SESSION_NAME}_{name}_Batch{batch_idx}"
        inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{run_name}'
        
        # 🌟 TRUE RESUME: 拦截跳过已经跑完的 Batch
        valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()] if inference_dir.exists() else []
        
        best_row = {}
        batch_max_score = -999.0
        
        if not force_restart and valid_csvs:
            print(f"\n   ⏭️ [SKIPPED] Batch {batch_idx}/{generation_batches_per_island} results found. Loading history...")
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

                    if batch_max_score > island_absolute_max_score:
                        island_absolute_max_score = batch_max_score
                        island_absolute_top_pdb = top_pdb
        else:
            # 需要生成新的
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
                f"source env.sh && {cmd_str}",
                env=env, shell=True, executable='/bin/bash', cwd=str(BASE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in process.stdout: print(line, end='', flush=True)
            process.wait()
            print("\nDone.")

            # 评估新生成的 Batch
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

                        if batch_max_score > island_absolute_max_score:
                            island_absolute_max_score = batch_max_score
                            island_absolute_top_pdb = top_pdb

        # Real-time UI Output per Batch
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

    # 保存 Island 级别的历史最佳
    scores_manifest[name] = {"max_score": island_absolute_max_score, "top_pdb": island_absolute_top_pdb, "residues": residues}

# --- 4. Hybridization & Footprint Extraction ---
print("\n🧬 Triggering Hybridization Protocol (Footprint Extraction)...")

def calculate_contributions_cb(pdb_path, target_chain, natural_order_list):
    contributions = {r: 0.0 for r in natural_order_list}
    if not pdb_path or not Path(pdb_path).exists(): return contributions

    af2_target_atoms = {}
    af2_binder_atoms = {}

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

    t_rep = {}
    target_af2_resis = sorted(af2_target_atoms.keys(), key=lambda x: int(x))

    for i, af2_rid in enumerate(target_af2_resis):
        if i < len(natural_order_list):
            nat_rid = natural_order_list[i]
            atoms = af2_target_atoms[af2_rid]
            t_rep[nat_rid] = atoms.get('CB', atoms.get('CA'))

    b_rep = []
    for af2_rid, atoms in af2_binder_atoms.items():
        b_rep.append(atoms.get('CB', atoms.get('CA')))

    if not b_rep or not t_rep: return contributions

    b_tree = KDTree(b_rep)
    for nat_rid, coord in t_rep.items():
        if coord is None: continue
        dists, _ = b_tree.query(coord, k=1)
        if dists < 6.0:
            contributions[nat_rid] = 1.0 / (dists + 0.1)

    return contributions

isl_0_contribs = calculate_contributions_cb(scores_manifest["Isl_0"]["top_pdb"], target_chains, ordered_natural_resis)
isl_0_active_contribs = {k: v for k, v in isl_0_contribs.items() if k in base_hotspots}
sorted_isl_0 = sorted(isl_0_active_contribs.keys(), key=lambda k: isl_0_active_contribs[k], reverse=True)
pruned_isl_0 = sorted_isl_0[:-3] if len(sorted_isl_0) > 3 else sorted_isl_0

hybrid_islands = {}

hybrid_islands["Isl_0"] = {
    "baseline_ipsae": scores_manifest["Isl_0"]["max_score"],
    "core_hotspots": sorted(pruned_isl_0, key=lambda x: int(re.sub(r'\D', '', x))),
    "neo_hotspots": [],
    "hybrid_hotspots": sorted(pruned_isl_0, key=lambda x: int(re.sub(r'\D', '', x)))
}

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

    html_msg = f"<b>{hybrid_name}</b> | Global Absolute ipSAE: <span style='color:red;'>{max_score:.4f}</span> | Novel Footprint (Red): {','.join(top_neo)} | Merged: {','.join(hybrid_residues)}"
    display(HTML(html_msg))

manifest_path = final_dir / f"Hybrid_Islands_Manifest.json"
with open(manifest_path, 'w') as f:
    json.dump(hybrid_islands, f, indent=4)
print(f"\n💾 Exported JSON Manifest: {manifest_path.name}")