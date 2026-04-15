
# Cell_8_Top10_Complex_Visualization_Viewer_with_PDF.py
# User Requirement:
# 1. Color the first amino acid of the peptide (binder) blue.
# 2. Make the PyMOL PDF output images match the py3Dmol output (Target: mesh; Peptide: solid green; Hotspots: solid orange).
# 3. Output the entire code. Do not suppress intermediate output.

import os, json, sys, shutil, time, math, re, csv
from pathlib import Path
import py3Dmol
from IPython.display import display, HTML

# ---------------------------------------------------------
# 0. Dependency Resolution
# ---------------------------------------------------------
dependencies_needed = []
try:
    from fpdf import FPDF
except ImportError:
    dependencies_needed.append("fpdf")

try:
    import pymol
except ImportError:
    dependencies_needed.append("pymol-open-source")

if dependencies_needed:
    print(f"📦 Installing missing dependencies: {', '.join(dependencies_needed)}...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + dependencies_needed)
    from fpdf import FPDF
    import pymol

try:
    from google.colab import files
except ImportError:
    pass

# Amino Acid Mapping
d3to1 = {'CYS': 'C', 'ASP': 'D', 'SER': 'S', 'GLN': 'Q', 'LYS': 'K',
         'ILE': 'I', 'PRO': 'P', 'THR': 'T', 'PHE': 'F', 'ASN': 'N',
         'GLY': 'G', 'HIS': 'H', 'LEU': 'L', 'ARG': 'R', 'TRP': 'W',
         'ALA': 'A', 'VAL': 'V', 'GLU': 'E', 'TYR': 'Y', 'MET': 'M'}

# ---------------------------------------------------------
# 1. Configuration and Robust Path Setup (via last_runs.txt)
# ---------------------------------------------------------
BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')
SETTING_FILE = BASE_DIR / 'internal_settings.json'
LOCAL_TEMP_DIR = Path('/content/temp_pymol_renders')
LOCAL_TEMP_DIR.mkdir(parents=True, exist_ok=True)

if not SETTING_FILE.exists():
    print("❌ Error: internal_settings.json not found.")
    sys.exit(1)

with open(SETTING_FILE, 'r') as f:
    cfg = json.load(f)

task_name = cfg['task_name']
target_chain_config = str(cfg.get('target_chains', 'A')).split(',')[0].strip()

# ----- Robust Directory Resolution -----
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
    print(f"❌ Error: No valid run history found for task [{task_name}] in last_runs.txt")
    sys.exit(1)

screening_dir = BASE_DIR / 'screening_results' / task_name
latest_final = screening_dir / target_dir_name
LIVE_PDB_DIR = latest_final / 'AutoPilot_Live_Top10_PDBs'
timestamp_str = run_id.split('_')[-1] # For bundle naming compatibility downstream

if not LIVE_PDB_DIR.exists():
    print(f"❌ Error: Live PDB directory not found at {LIVE_PDB_DIR}")
    sys.exit(1)

# ---------------------------------------------------------
# 2. Structural Subtraction Mapping & AF2 Numbering Translator
# ---------------------------------------------------------
FIXED_PDB_PATH = BASE_DIR / 'assets' / 'target_data' / task_name / f"{task_name}_fixed.pdb"
chain_to_af2_map = {}

with open(FIXED_PDB_PATH, 'r') as f:
    for line in f:
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            chain = line[21]; resi = line[22:26].strip()
            if chain not in chain_to_af2_map:
                chain_to_af2_map[chain] = []
            chain_to_af2_map[chain].append(resi)

af2_mapping = {}
if target_chain_config in chain_to_af2_map:
    orig_resis = chain_to_af2_map[target_chain_config]
    af2_mapping = {orig: str(i + 1) for i, orig in enumerate(orig_resis)}

display(HTML(f"<h2>--- Auto-Pilot Top 10 Visualization: [{run_id}] ---</h2>"))

# ---------------------------------------------------------
# 3. Initialize Staging Directory & PDF
# ---------------------------------------------------------
bundle_name = f"{task_name}_{timestamp_str}_autopilot"
PACK_STAGING = Path(f"/content/{bundle_name}")
if PACK_STAGING.exists(): shutil.rmtree(PACK_STAGING)
PACK_STAGING.mkdir(parents=True, exist_ok=True)

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.set_font("Arial", style='B', size=16)
pdf.cell(0, 20, txt=f"Proteina-Complexa Auto-Pilot Report", ln=True, align='C')
pdf.set_font("Arial", size=12)
pdf.cell(0, 10, txt=f"Task: {task_name} | ID: {run_id}", ln=True, align='C')
pdf.line(10, 40, 200, 40)
pdf.ln(15)

# --- Preload CSV Metrics for HTML Display ---
design_metrics = {}
master_log_csv = latest_final / f"{run_id}_AutoPilot_master_log.csv"
if master_log_csv.exists():
    with open(master_log_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            design_metrics[row.get('design_id', '').strip()] = row

# ---------------------------------------------------------
# 4. Processing Loop: PDB Extraction, Rendering & PDF Construction
# ---------------------------------------------------------
pymol.pymol_argv = ['pymol', '-c']
try: pymol.finish_launching()
except: pass

live_pdbs = sorted(list(LIVE_PDB_DIR.glob('*.pdb')))

for idx, target_pdb in enumerate(live_pdbs, 1):
    d_id = target_pdb.stem
    shutil.copy2(target_pdb, PACK_STAGING / f"Top_{idx}_{target_pdb.name}")

    with open(target_pdb, 'r') as f:
        pdb_data = f.read()

    chains_seq = {}
    first_resi_binder = None
    for line in pdb_data.split('\n'):
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            res_name = line[17:20].strip(); chain_id = line[21]
            if chain_id not in chains_seq: chains_seq[chain_id] = ""
            chains_seq[chain_id] += d3to1.get(res_name, 'X')

    chain_lengths = {c: len(seq) for c, seq in chains_seq.items()}
    sorted_chains = sorted(chain_lengths.keys(), key=lambda c: chain_lengths[c])
    binder_chains = [sorted_chains[0]]
    target_chain_ids = [c for c in sorted_chains[1:]]

    # Extract the exact starting residue number for the binder chain for py3Dmol mapping
    for line in pdb_data.split('\n'):
        if line.startswith("ATOM") and line[21] == binder_chains[0]:
            first_resi_binder = line[22:26].strip()
            break

    # -------------------------------------------------------
    # 4a. HTML Advanced Evaluation Data UI Output
    # -------------------------------------------------------
    peptide_len = len(chains_seq[binder_chains[0]]) if binder_chains else 0
    met = design_metrics.get(d_id, {})

    def safe_f(v):
        try: return float(v)
        except: return -999.0

    def fs(val, is_rmsd=False, is_plddt=False):
        if val == -999.0: return "N/A"
        if is_rmsd: return f"{val:<8.2f}Å"
        if is_plddt: return f"{val:<8.2f}"
        return f"{val:<8.4f}"

    ipsae_val = safe_f(met.get('af2folding_max_ipsae', met.get('self_complex_max_ipAE', met.get('complex_i_pAE', -999.0))))
    ptm_val   = safe_f(met.get('af2folding_ptm_log', met.get('self_complex_pTM', met.get('complex_pTM', -999.0))))
    iptm_val  = safe_f(met.get('af2folding_i_ptm_log', met.get('self_complex_i_pTM', met.get('complex_ipTM', -999.0))))
    plddt_val = safe_f(met.get('af2folding_plddt', met.get('self_complex_pLDDT', met.get('complex_pLDDT', -999.0))))
    rmsd_val  = safe_f(met.get('af2folding_rmsd', met.get('self_binder_scRMSD_ca', met.get('binder_scRMSD_ca', -999.0))))
    reward_val= safe_f(met.get('total_reward', -999.0))
    batch_val = met.get('session_loop', met.get('batch_num', 'N/A'))
    idx_val   = met.get('pdb_index', met.get('idx_in_batch', 'N/A'))

    table_html = f"""
    <div style='background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
        <b style='font-size: 16px; color: #0056b3;'>[{idx}] Design: {d_id}</b><br>
        <b style='color: #28a745; font-size: 14px;'>Target Pipeline | Peptide Length: {peptide_len} AA</b>
        <pre style='margin-top: 10px; background: #fff; padding: 12px; border: 1px solid #ddd; border-radius: 4px; overflow-x: auto; color: #333;'>
Design_ID        | ipSAE    | pTM      | iPTM     | pLDDT    | RMSD       | Reward   | Batch  | Index
------------------------------------------------------------------------------------------------------------------
{d_id:<16} | {fs(ipsae_val):<8} | {fs(ptm_val):<8} | {fs(iptm_val):<8} | {fs(plddt_val, is_plddt=True):<8} | {fs(rmsd_val, is_rmsd=True):<10} | {fs(reward_val):<8} | {batch_val:<6} | {idx_val:<6}
</pre>
    </div>
    """
    display(HTML(table_html))

    if task_name == "GFP":
        mapped_hotspots = ['39', '40', '41', '73', '74', '200', '201', '202', '203', '204']
    else:
        cfg_hotspots = cfg.get('hotspots_input', '')
        raw_hotspots = [x.strip() for x in str(cfg_hotspots).split(',') if x.strip() and x != 'nan']
        mapped_hotspots = [af2_mapping.get(orig, orig) for orig in raw_hotspots]

    # 4b. PDF Page Content
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(0, 8, txt=f"Hit Index [{idx}]: {d_id} (Length: {peptide_len} AA)", ln=True)
    pdf.set_font("Courier", style='B', size=9)
    for bc in binder_chains:
        pdf.multi_cell(0, 5, txt=f"Binder Sequence (Chain {bc}): {chains_seq[bc]}")
    pdf.ln(4)

    # 4c. PyMOL Headless Render with Orientation
    img_path = LOCAL_TEMP_DIR / f"render_{idx}.png"
    pymol.cmd.reinitialize()
    pymol.cmd.load(str(target_pdb), 'complex')
    pymol.cmd.hide('everything', 'all')

    # Target rendering: Cartoon + Mesh
    target_sel = 'chain ' + '+'.join(target_chain_ids)
    pymol.cmd.show('cartoon', target_sel)
    pymol.cmd.color('gray80', target_sel)
    pymol.cmd.show('mesh', target_sel)

    # Hotspots rendering: Solid Surface
    match_c = target_chain_ids[0] if target_chain_ids else 'A'
    if mapped_hotspots:
        hotspot_sel = f"resi {'+'.join(mapped_hotspots)} and chain {match_c}"
        pymol.cmd.color('orange', hotspot_sel)
        pymol.cmd.show('surface', hotspot_sel)

    # Binder rendering: Solid Surface
    for bc in binder_chains:
        binder_sel = f"chain {bc}"
        pymol.cmd.show('cartoon', binder_sel)
        pymol.cmd.color('green', binder_sel)
        pymol.cmd.show('surface', binder_sel)
        # Color N-term blue
        pymol.cmd.color('blue', f"first chain {bc}")

    if binder_chains and target_chain_ids:
        pymol.cmd.pseudoatom("com_t", selection='chain ' + '+'.join(target_chain_ids))
        pymol.cmd.pseudoatom("com_b", selection='chain ' + '+'.join(binder_chains))

        try:
            t_c = pymol.cmd.get_model("com_t").atom[0].coord
            b_c = pymol.cmd.get_model("com_b").atom[0].coord
            dx, dy, dz = b_c[0]-t_c[0], b_c[1]-t_c[1], b_c[2]-t_c[2]
            ty = math.degrees(math.atan2(-dx, dz))
            new_dz = -dx * math.sin(math.radians(ty)) + dz * math.cos(math.radians(ty))
            tx = math.degrees(math.atan2(dy, new_dz))
            pymol.cmd.center("all")
            pymol.cmd.turn("y", ty); pymol.cmd.turn("x", tx)
            pymol.cmd.delete("com_t"); pymol.cmd.delete("com_b")
        except Exception as e:
            pass

    pymol.cmd.bg_color('white')
    pymol.cmd.png(str(img_path), width=800, height=600, ray=0)
    time.sleep(0.5)

    if img_path.exists():
        pdf.image(str(img_path), x=15, y=None, w=180)
        os.remove(img_path)

    # 4d. py3Dmol Frontend - Safe Logic rendering
    viewer = py3Dmol.view(width=800, height=500)
    viewer.addModel(pdb_data, 'pdb')

    viewer.setStyle({'chain': target_chain_ids}, {'cartoon': {'color': '#A9A9A9', 'opacity': 0.7}})
    viewer.addSurface(py3Dmol.SES, {'color': '#A9A9A9', 'wireframe': True}, {'chain': target_chain_ids})

    if mapped_hotspots:
        h_sel = {'chain': target_chain_ids, 'resi': mapped_hotspots}
        viewer.setStyle(h_sel, {'cartoon': {'color': 'orange', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.SES, {'color': 'orange', 'opacity': 1.0}, h_sel)

    viewer.setStyle({'chain': binder_chains}, {'cartoon': {'color': 'lime', 'opacity': 1.0}})
    viewer.addSurface(py3Dmol.SES, {'color': 'lime', 'opacity': 1.0}, {'chain': binder_chains})

    if first_resi_binder:
        b_first_sel = {'chain': binder_chains[0], 'resi': first_resi_binder}
        viewer.setStyle(b_first_sel, {'cartoon': {'color': 'blue', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.SES, {'color': 'blue', 'opacity': 1.0}, b_first_sel)

    viewer.zoomTo(); viewer.show()

# ---------------------------------------------------------
# 5. Final Assembly: PDF, CSVs, Parameters, and ZIP
# ---------------------------------------------------------
# 5a. Save PDF to Staging
report_path = PACK_STAGING / f"{bundle_name}_Report.pdf"
pdf.output(str(report_path))

pred_csv = latest_final / f"{task_name}_AutoPilot_prediction_results.csv"
if not pred_csv.exists(): pred_csv = latest_final / "prediction_results.csv"

if pred_csv.exists(): shutil.copy2(pred_csv, PACK_STAGING / f"{task_name}_final_results.csv")
if master_log_csv.exists(): shutil.copy2(master_log_csv, PACK_STAGING / f"{run_id}_full_history_log.csv")

param_json = latest_final / 'internal_settings.json'
param_yaml = latest_final / f'targets_dict_{run_id}.yaml'
if param_json.exists(): shutil.copy2(param_json, PACK_STAGING / f"{run_id}_internal_settings.json")
if param_yaml.exists(): shutil.copy2(param_yaml, PACK_STAGING / f"{run_id}_targets_dict.yaml")

# 5c. Create ZIP Archive
zip_out_base = screening_dir / bundle_name
shutil.make_archive(str(zip_out_base), 'zip', str(PACK_STAGING))
final_zip_path = Path(str(zip_out_base) + ".zip")

# 5d. Cleanup
shutil.rmtree(PACK_STAGING)
if LOCAL_TEMP_DIR.exists(): shutil.rmtree(LOCAL_TEMP_DIR)

print(f"\n✅ All artifacts bundled into single ZIP: {final_zip_path.name}")
display(HTML(f"<div style='color: #155724; background-color: #d4edda; padding: 10px; border-radius: 5px; margin-top: 20px;'><b>📥 Download Ready:</b><br>{final_zip_path.relative_to(BASE_DIR)}</div>"))

try:
    files.download(str(final_zip_path))
except: pass

# Purpose: Generate top 10 complex visualizations, align PyMOL PDF output style with HTML py3Dmol (Mesh target, Solid green peptide, Solid orange hotspots, Blue N-terminus), and bundle artifacts.
# Upstream code: Design generation pipeline and PDB complex folding/docking step.
# Run environment: Google Colab / Jupyter Notebook with PyMOL and py3Dmol.
# Generation time: 2026-04-14 16:17 EDT.
# Changed lines:
# - Line 140-144: Added logic to extract the exact starting residue number (`first_resi_binder`) from the PDB for py3Dmol compatibility.
# - Line 213-217: Updated PyMOL target rendering to use `show('mesh', ...)` instead of `hide('everything', ...)`.
# - Line 221-224: Updated PyMOL hotspots rendering to use `show('surface', ...)` for solid appearance.
# - Line 227-232: Updated PyMOL binder rendering to use `show('surface', ...)` and `color('blue', f"first chain {bc}")`.
# - Line 275-278: Added `setStyle` and `addSurface` in py3Dmol logic to explicitly color `first_resi_binder` blue.