import json
import re

nb_path = 'c:/Code/Structure/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Cell 3 modification
cell_3 = ''.join(nb['cells'][3]['source'])

# 1. Add force_restart under specific_resume_run_id
add_restart = """specific_resume_run_id = "" #@param {type:"string"}

# @markdown ### 🔄 Global Execution Restart
# @markdown Force a complete restart of the entire pipeline? (Ignores all existing history and generates a new Run ID)
force_restart = False #@param {type:"boolean"}"""
cell_3 = cell_3.replace('specific_resume_run_id = "" #@param {type:"string"}', add_restart)

# 2. Remove force_restart_section_7
cell_3 = re.sub(r'# @markdown Force restart Section 7 completely\? \(Ignore existing history\)\nforce_restart_section_7 = False #@param \{type:"boolean"\}\n', '', cell_3)

# 3. Update dictionary
cell_3 = cell_3.replace('"force_restart_section_7": force_restart_section_7,', '"force_restart": force_restart,')
cell_3 = cell_3.replace('Restart Sec 7 (Evolution): \\\'YES\\\' if force_restart_section_7 else \\\'NO (Resume)\\\'', 'Global Restart: \\\'YES\\\' if force_restart else \\\'NO (Resume)\\\'')

nb['cells'][3]['source'] = [line + '\n' for line in cell_3.split('\n')]
# clean up the last newline to match format if necessary
nb['cells'][3]['source'][-1] = nb['cells'][3]['source'][-1].rstrip('\n')


# Cell 11 modification
cell_11 = ''.join(nb['cells'][11]['source'])
cell_11 = cell_11.replace('force_restart_task = cfg.get("force_restart_task", False)', 'force_restart = cfg.get("force_restart", False)')
cell_11 = cell_11.replace('elif force_restart_task:', 'elif force_restart:')

nb['cells'][11]['source'] = [line + '\n' for line in cell_11.split('\n')]
nb['cells'][11]['source'][-1] = nb['cells'][11]['source'][-1].rstrip('\n')


# Cells 17, 23, 25 modification
for idx in [17, 23, 25]:
    if idx < len(nb['cells']):
        cell_source = ''.join(nb['cells'][idx]['source'])
        cell_source = cell_source.replace('force_restart_section_7', 'force_restart')
        nb['cells'][idx]['source'] = [line + '\n' for line in cell_source.split('\n')]
        nb['cells'][idx]['source'][-1] = nb['cells'][idx]['source'][-1].rstrip('\n')

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
