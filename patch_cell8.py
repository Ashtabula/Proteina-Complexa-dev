import json

notebook_path = 'coLab/Proteina_Complexa_coLab.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "Cell_8_Top10_Complex_Visualization_Viewer_with_PDF.py" in source:
            print("Found Cell 8!")
            
            # We want to replace the fragile run_id split logic with last_runs.txt logic
            new_source = []
            skip = False
            for line in cell['source']:
                if line.startswith("run_id = cfg.get('run_id')"):
                    skip = True
                    new_source.append("import re\n")
                    new_source.append("target_chain = str(cfg.get('target_chains', 'A')).split(',')[0].strip()\n")
                    new_source.append("\n")
                    new_source.append("# ---------------------------------------------------------\n")
                    new_source.append("# 1. Robust Path Independence (Via last_runs.txt)\n")
                    new_source.append("# ---------------------------------------------------------\n")
                    new_source.append("last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'\n")
                    new_source.append("run_id = None\n")
                    new_source.append("target_dir_name = None\n")
                    new_source.append("\n")
                    new_source.append("if last_run_file.exists():\n")
                    new_source.append("    with open(last_run_file, 'r', encoding='utf-8') as f:\n")
                    new_source.append("        lines = f.readlines()\n")
                    new_source.append("        pattern = rf\"Section2_TargetPreprocess \\| Run_ID: ({re.escape(task_name)}_\\d+_\\d+) \\| Dir: (final_\\d+_\\d+)\"\n")
                    new_source.append("        for line in reversed(lines):\n")
                    new_source.append("            match = re.search(pattern, line)\n")
                    new_source.append("            if match:\n")
                    new_source.append("                run_id = match.group(1)\n")
                    new_source.append("                target_dir_name = match.group(2)\n")
                    new_source.append("                break\n")
                    new_source.append("\n")
                    new_source.append("if not run_id or not target_dir_name:\n")
                    new_source.append("    print(f\"❌ Error: No valid run history found for task [{task_name}] in last_runs.txt\")\n")
                    new_source.append("    sys.exit(1)\n")
                    new_source.append("\n")
                    new_source.append("screening_dir = BASE_DIR / 'screening_results' / task_name\n")
                    new_source.append("latest_final = screening_dir / target_dir_name\n")
                    new_source.append("LIVE_PDB_DIR = latest_final / 'AutoPilot_Live_Top10_PDBs'\n")
                    new_source.append("timestamp_str = run_id.split('_')[-1] # For bundle naming compatibility downstream\n")
                    
                elif skip and line.startswith("if not LIVE_PDB_DIR.exists():"):
                    skip = False
                    new_source.append(line)
                elif not skip:
                    new_source.append(line)
            
            cell['source'] = new_source
            print("Successfully patched Cell 8.")

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Saved notebook.")
