import json

notebook_path = "coLab/Proteina_Complexa_coLab.ipynb"
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

# Locate cell 3 (Section 0)
for cell in nb["cells"]:
    if cell.get("cell_type") == "code":
        source = "".join(cell.get("source", []))
        if "Section_0_Global_Configuration_Dashboard" in source:
            # We found Cell 3.
            
            # 1. Update the Variable UI parameters
            target_ui_insertion = """scan_charged_patch = True #@param {type:"boolean"}



# ==========================================
# Execution Logic: Validation & Persistence
# ==========================================
"""
            new_ui_insertion = """scan_charged_patch = True #@param {type:"boolean"}


# ==========================================
# --- Auto-Evolution Target Screening Setting (Section 6) ---
# ==========================================
# @markdown ---
# @markdown ---
# @markdown ### 🧬 Auto-Evolution Target Screening Setting
evo_designs_per_loop = 48 #@param {type:"integer"}
evo_max_iterations = 10 #@param {type:"integer"}
evo_max_hotspots = 8 #@param {type:"integer"}
evo_update_count = 2 #@param {type:"integer"}

# ==========================================
# Execution Logic: Validation & Persistence
# ==========================================
"""
            source = source.replace(target_ui_insertion, new_ui_insertion)
            
            # 2. Update the persistence Dictionary
            target_dict_insertion = """        "scan_batch_size": scan_batch_size,
    }

    # Preserve existing run_id if it exists"""
            new_dict_insertion = """        "scan_batch_size": scan_batch_size,
        "evo_designs_per_loop": evo_designs_per_loop,
        "evo_max_iterations": evo_max_iterations,
        "evo_max_hotspots": evo_max_hotspots,
        "evo_update_count": evo_update_count,
    }

    # Preserve existing run_id if it exists"""
            source = source.replace(target_dict_insertion, new_dict_insertion)
            
            # Write back
            # Cell source must be a list of strings
            lines = source.split('\n')
            cell["source"] = [l + '\n' for l in lines[:-1]] + [lines[-1]] if lines[-1] else [l + '\n' for l in lines]
            print("Successfully patched Section 0 variables into Cell 3.")
            break

# Locate the last cell which is the Section 6 Code Block
if nb["cells"][-1]["cell_type"] == "code" and "Hotspot Evolution Engine" in "".join(nb["cells"][-1]["source"]):
    with open("scratch/cell_18_evo.py", "r", encoding="utf-8") as f:
        code_source_lines = f.readlines()
    nb["cells"][-1]["source"] = code_source_lines
    print("Successfully replaced Section 6 core loop with ipSAE Weighted Engine (Cell_18_evo).")

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2)

print("✅ Notebook overall patch operation completed!")
