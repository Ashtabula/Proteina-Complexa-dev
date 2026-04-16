import json

def patch_notebook(filepath):
    try:
        with open(filepath, 'r') as f:
            nb = json.load(f)
    except FileNotFoundError:
        return

    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            source = cell['source']
            joined_source = ''.join(source)
            if '# Section_0_Global_Configuration_Dashboard' in joined_source:
                new_source = []
                for line in source:
                    if 'RESUME_LAST_SESSION =' in line:
                        new_source.append('# @markdown ### 🔄 Execution Mode\n')
                        new_source.append('# @markdown Force restart task completely? (Ignore existing history).\n')
                        new_source.append('force_restart_task = False #@param {type:"boolean"}\n')
                    elif '"RESUME_LAST_SESSION": RESUME_LAST_SESSION' in line:
                        new_source.append('        "force_restart_task": force_restart_task,\n')
                    elif 'Resume Mode:' in line:
                        new_source.append('    print(f"Force Restart: {\'YES\' if force_restart_task else \'NO (Default Resume)\'}")\n')
                    else:
                        new_source.append(line)
                nb['cells'][i]['source'] = new_source

            if '# Cell_4b_PDB_Processing' in joined_source or 'Section2_TargetPreprocess' in joined_source:
                new_source = []
                for line in source:
                    if 'resume_session = bool(cfg.get(\'RESUME_LAST_SESSION\'' in line:
                        new_source.append('force_restart_task = bool(cfg.get(\'force_restart_task\', False))\n')
                    elif 'if resume_session and last_run_file.exists():' in line:
                        new_source.append('if not force_restart_task and last_run_file.exists():\n')
                    else:
                        new_source.append(line)
                nb['cells'][i]['source'] = new_source

    with open(filepath, 'w') as f:
        json.dump(nb, f, indent=1)

patch_notebook('Proteina_Complexa_coLab.ipynb')
patch_notebook('coLab/Proteina_Complexa_coLab.ipynb')
print("Notebooks patched successfully.")
