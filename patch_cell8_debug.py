import json

notebook_path = 'coLab/Proteina_Complexa_coLab.ipynb'
try:
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
        for cell in nb['cells']:
            if cell['cell_type'] == 'code':
                source = "".join(cell['source'])
                if "Cell_8" in source:
                    # Let's replace Cell 8 totally to include massive debug print statements
                    if "target_dir_name" in source:
                        new_source = []
                        for line in cell['source']:
                            if line.startswith("if last_run_file.exists():"):
                                new_source.append("print(f'🔍 DEBUG: BASE_DIR = {BASE_DIR}')\n")
                                new_source.append("print(f'🔍 DEBUG: task_name = {task_name}')\n")
                                new_source.append("print(f'🔍 DEBUG: last_run_file = {last_run_file}')\n")
                                new_source.append(line)
                            elif line.startswith("        lines = f.readlines()"):
                                new_source.append(line)
                                new_source.append("        print(f'🔍 DEBUG: Found {len(lines)} lines in last_runs.txt')\n")
                            elif line.startswith("                target_dir_name = match.group(2)"):
                                new_source.append(line)
                                new_source.append("                print(f'🔍 DEBUG: Match Found! run_id = {run_id}, target_dir_name = {target_dir_name}')\n")
                            elif line.startswith("if not LIVE_PDB_DIR.exists():"):
                                new_source.append(line)
                            else:
                                new_source.append(line)
                                
                        cell['source'] = new_source
                
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2)
    print("Debug patched.")
except Exception as e:
    print(e)
