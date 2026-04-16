# Section_0_Global_Configuration_Dashboard.py
# Requirement: Save global parameters to the configuration file immediately before invoking the interactive file upload widget, preventing the parameter saving process from being blocked or bypassed if no file is uploaded.
# UPDATE: Added RESUME_LAST_SESSION boolean toggle for session management and checkpoint continuity.

# @title 🎯 Section_0_Global_Configuration_Dashboard { display-mode: "form" }
# @markdown Complete this dashboard **ONCE**. All settings are persistently saved to your Google Drive.

import os, json, shutil, sys
from pathlib import Path
from IPython.display import display, HTML

# ==========================================
# 0. Infrastructure & Google Drive Mount
# ==========================================
if not os.path.exists('/content/drive/MyDrive'):
    from google.colab import drive
    print("🔄 Mounting Google Drive for persistent storage...")
    drive.mount('/content/drive')

BASE_DIR = Path('/content/drive/MyDrive/Proteina-Complexa')

# --- Path Configuration ---
ROOT_DIR = "/content/drive/MyDrive/Proteina-Complexa"
BACKUP_DIR = "/content/drive/MyDrive/Proteina_Subfolder_Backups"
UV_CACHE_TAR = os.path.join(BACKUP_DIR, "uv_build_cache.tar")
ENV_FILE = os.path.join(ROOT_DIR, ".env")

# --- Source Repository Detection and Cloning ---
if not os.path.exists('/content/drive/MyDrive/Proteina-Complexa/pyproject.toml'):
    print(f">>> Source repository not detected. Executing initial clone to {ROOT_DIR}...")
    !git clone https://github.com/Geauga/Proteina-Complexa-coLab {ROOT_DIR}
else:
    print(f">>> Source repository already exists at {ROOT_DIR}. Skipping clone step.")

TARGETS_DIR = BASE_DIR / 'targets'
TARGETS_DIR.mkdir(parents=True, exist_ok=True)
SETTING_FILE = BASE_DIR / 'internal_settings.json'
# @markdown ---
# @markdown ---
# ==========================================
# --- Configuration for Environment Setup & Cache (Cell 3) ---
# ==========================================
# @markdown ### 💾 Environment & Cache Settings
# @markdown **[Accelerate Startup]** Enable Google Drive backup for the build cache?
# @markdown > *Note: The very first run will be slightly slower (1-2 mins) to package the backup; subsequent startups will be lightning fast.*
enable_cache_backup = True # @param {type:"boolean"}

# ==========================================
# --- Hardware Memory VRAM Limits ---
# ==========================================
# @markdown ### 💻 Hardware Memory Limits (VRAM Limit)
# @markdown Set this lower if you encounter OOM (Out Of Memory). This is shared across evaluating and generating sections (Section 3, 4, 6).
generation_batch_size = 36 #@param {type:"integer"}
# @markdown **[AF2 Evaluation Batch]** Safe limit: 1. Evaluator uses massive memory. Keep at 1 for 16GB GPUs, or max 2-3 for A100. Over 3 will OOM.
evaluation_batch_size = 1 #@param {type:"integer"}

# ==========================================
# --- Configuration for Target Setup & Processing (Cell 4) ---
# ==========================================
# @markdown ---
# @markdown ---
# @markdown ### 📁 Target File Selection
UPLOAD_NEW_PDB = False #@param {type:"boolean"}
pdb_file_name = "AR_LBD_ChainB_5JJM.pdb" #@param {type:"string"}

# @markdown ### 🧬 Target Definition
task_name = "AR_LBD" #@param {type:"string"}
target_chains = "B" #@param {type:"string"}
# @markdown ---
# @markdown ---
# @markdown ### 🔁 Session Management (Resume Execution)
# @markdown Toggle this ON to inherit the previous Run ID and append to existing directories (prevents low-score overwriting during restarts).
RESUME_LAST_SESSION = False #@param {type:"boolean"}
# @markdown ---
# @markdown ---
run_filter = True #@param {type:"boolean"}
run_evaluate = True #@param {type:"boolean"}
run_analyze = True #@param {type:"boolean"}

# @markdown ---
# @markdown ---
# @markdown ### 🎯 Interaction Hotspots (Comma separated)
hotspots_input = "681,682,752,754, 755, 756, 757, 758, 759, 760,763,764,766, 767" #@param {type:"string"}

# @markdown ### 📏 Binder Peptide Length
binder_length_min = 20 #@param {type:"integer"}
binder_length_max = 50 #@param {type:"integer"}
# @markdown ---
# @markdown ---
# @markdown ### 🎯 Auto-Pilot Screening Configuration (Section 4)
target_threshold = 0.85 #@param {type:"number"}
target_success_count = 10 #@param {type:"integer"}
max_iterations = 30 #@param {type:"integer"}

designs_per_loop = 36 #@param {type:"integer"}



# ==========================================
# --- Geometric Surface Scanning Config (Section 6) ---
# ==========================================
# @markdown ---
# @markdown ---
# @markdown ### 📐 Geometric Surface Scanning
anchor_residues = "752, 753, 755, 756, 757, 758, 759, 761, 764, 767" #@param {type:"string"}
global_search_boundary = 6 #@param {type:"number"}
peptide_interaction_radius = 15 #@param {type:"number"}
scan_batch_size = 24 #@param {type:"integer"}
designs_per_patch = 24 #@param {type:"integer"}
# ==========================================
# --- Automated Multi-Dimensional Surface Scanning (Cell 11) ---
# ==========================================
# @markdown ---
# @markdown ---
# @markdown ### 🔬 Automated Groove & Pocket Discovery
scan_shallow_groove = True #@param {type:"boolean"}
scan_deep_pocket = True #@param {type:"boolean"}
scan_hydrophobic_patch = True #@param {type:"boolean"}
scan_charged_patch = True #@param {type:"boolean"}


# ==========================================
# --- Auto-Evolution Target Screening Setting (Section 6) ---
# ==========================================
# @markdown ---
# @markdown ---
# @markdown ### 🧬 Auto-Evolution Target Screening Setting
evo_designs_per_loop = 48 #@param {type:"integer"}
evo_max_hotspots = 8 #@param {type:"integer"}
evo_update_count = 2 #@param {type:"integer"}
evo_target_threshold = 0.85 #@param {type:"number"}
# @markdown Strict Geometric Confinement (Filter High RMSD before Evolution Selection)
evo_strict_rmsd_filter = True #@param {type:"boolean"}

# ==========================================
# Execution Logic: Validation & Persistence
# ==========================================
import ipywidgets as widgets
from IPython.display import clear_output

final_pdb_name = pdb_file_name

def write_settings_to_disk(pdb_name):
    settings = {
        "enable_cache_backup": enable_cache_backup,
        "pdb_file": pdb_name,
        "task_name": task_name,
        "target_chains": target_chains,
        "RESUME_LAST_SESSION": RESUME_LAST_SESSION,
        "hotspots_input": hotspots_input,
        "binder_length_min": binder_length_min,
        "binder_length_max": binder_length_max,
        "run_filter": run_filter,
        "run_evaluate": run_evaluate,
        "run_analyze": run_analyze,
        "target_threshold": target_threshold,
        "target_success_count": target_success_count,
        "designs_per_loop": designs_per_loop,
        "max_iterations": max_iterations,
        "generation_batch_size": generation_batch_size,
        "evaluation_batch_size": evaluation_batch_size,
        "anchor_residues": anchor_residues,
        # MAPPED UI VARIABLES TO BACKWARD COMPATIBLE JSON KEYS
        "scan_margin": global_search_boundary,
        "local_patch_radius": peptide_interaction_radius,
        "designs_per_patch": designs_per_patch,
        "scan_batch_size": scan_batch_size,
        "evo_designs_per_loop": evo_designs_per_loop,
                "evo_max_hotspots": evo_max_hotspots,
        "evo_update_count": evo_update_count,
        "evo_target_threshold": evo_target_threshold,
        "evo_strict_rmsd_filter": evo_strict_rmsd_filter,
    }

    # Preserve existing run_id if it exists to allow proper resumption
    if SETTING_FILE.exists():
        try:
            with open(SETTING_FILE, 'r') as f:
                old_cfg = json.load(f)
                if 'run_id' in old_cfg:
                    settings['run_id'] = old_cfg['run_id']
        except Exception:
            pass

    with open(SETTING_FILE, 'w') as f:
        json.dump(settings, f, indent=4)
    print(f"\n✅ SETTINGS REGISTERED")
    print(f"Task Name  : {task_name}")
    print(f"Target PDB : {pdb_name} (Chain: {target_chains})")
    print(f"Resume Mode: {'ACTIVE' if RESUME_LAST_SESSION else 'DISABLED'}")
    print("💾 Data saved. The backend engines will seamlessly inherit these unified configurations.")

# Immediately save parameters regardless of upload status to prevent blocking.
write_settings_to_disk(final_pdb_name)

if UPLOAD_NEW_PDB:
    display(HTML('<p style="font-size:16px; font-weight:bold; color:#E32636;">👉 PLEASE UPLOAD YOUR PDB FILE (Settings have been saved):</p>'))

    upload_widget = widgets.FileUpload(accept='.pdb', multiple=False, description='Upload PDB')
    cancel_button = widgets.Button(description='Cancel & Clear', button_style='danger', icon='trash')
    out_log = widgets.Output()

    upload_state = {"current_file": None}

    def process_upload(change):
        with out_log:
            if upload_widget.value:
                # Handle data structures for both ipywidgets v7 and v8
                val = upload_widget.value
                if isinstance(val, dict):
                    filename = list(val.keys())[0]
                    content = val[filename]['content']
                else:
                    filename = val[0]['name']
                    content = val[0]['content']

                file_path = TARGETS_DIR / filename
                with open(file_path, "wb") as f:
                    f.write(content)

                upload_state["current_file"] = file_path
                print(f"File '{filename}' uploaded successfully to target directory.")

                # Re-save settings with the newly uploaded filename
                write_settings_to_disk(filename)

    def clear_upload(b):
        with out_log:
            clear_output()
            if upload_state["current_file"] and os.path.exists(upload_state["current_file"]):
                os.remove(upload_state["current_file"])
                print(f"Deleted physical file: {upload_state['current_file'].name}")
                upload_state["current_file"] = None

            # Reset widget value safely based on version type
            upload_widget.value = {} if isinstance(upload_widget.value, dict) else ()
            if hasattr(upload_widget, '_counter'):
                upload_widget._counter = 0

            print("Upload canceled and cleared. Ready for new file.")

    upload_widget.observe(process_upload, names='value')
    cancel_button.on_click(clear_upload)

    display(widgets.VBox([widgets.HBox([upload_widget, cancel_button]), out_log]))

# ==============================================================================
# Purpose: Resolve the issue where saving global parameters was dependent on the completion of the file upload action. This decoupling ensures UI parameter changes (like `max_iterations`) are immediately persisted to disk before initiating the widget listeners.
# Upstream Code: Section 0 Dashboard Native Logic
# Runtime Environment: Google Colab.
# Generation Time: 2026-04-11 12:53 EDT.
# Changed Lines:
# - Inserted Lines 71-74: Added RESUME_LAST_SESSION variable for UI toggle.
# - Line 116: Added RESUME_LAST_SESSION to the persistent payload dictionary.
# - Lines 134-142: Safely read existing internal_settings.json to preserve the previous run_id across executions if it exists, enabling the resume functionality.
# ==============================================================================