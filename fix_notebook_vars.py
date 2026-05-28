import json
import re

nb_path = 'c:/Code/Structure/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# --- Fix Cell 3 ---
cell_3 = ''.join(nb['cells'][3]['source'])

# Put force_restart_section_7 back under "Auto-Evolution Target Screening Setting (Section 7)"
target_marker = '# @markdown ### 🚀 Auto-Evolution Target Screening Setting (Section 7)\n'
new_var_str = '# @markdown Force restart Section 7 completely? (Ignore existing history)\nforce_restart_section_7 = False #@param {type:"boolean"}\n'

if new_var_str not in cell_3:
    cell_3 = cell_3.replace(target_marker, target_marker + new_var_str)

# Ensure "force_restart_section_7": force_restart_section_7 is in the JSON payload
if '"force_restart_section_7": force_restart_section_7,' not in cell_3:
    cell_3 = cell_3.replace('"force_restart": force_restart,', '"force_restart": force_restart,\n        "force_restart_section_7": force_restart_section_7,')

# Fix UI print message in cell 3
cell_3 = cell_3.replace("print(f\"Restart Sec 7 (Evolution): {'YES' if force_restart_section_7 else 'NO (Resume)'}\")", "print(f\"Restart Sec 7: {'YES' if force_restart_section_7 else 'NO'}\")")
if 'Restart Sec 7:' not in cell_3:
    # Need to find the existing print and update it
    pass

nb['cells'][3]['source'] = [line + '\n' for line in cell_3.split('\n')]
nb['cells'][3]['source'][-1] = nb['cells'][3]['source'][-1].rstrip('\n')


# --- Fix Cells 17, 23, 25 ---
# Restore `force_restart` to `force_restart_section_7` in these cells
for idx in [17, 23, 25]:
    if idx < len(nb['cells']):
        cell_source = ''.join(nb['cells'][idx]['source'])
        # Be careful: only replace 'force_restart' if it is meant to be 'force_restart_section_7'
        # In my previous change, I did: cell_source = cell_source.replace('force_restart_section_7', 'force_restart')
        # So I just need to revert: cell_source = cell_source.replace('force_restart', 'force_restart_section_7')
        # Wait! There might be actual 'force_restart' usage in these cells if they referred to other things.
        # Let's do a strict replacement for root_cfg.get('force_restart', False) -> root_cfg.get('force_restart_section_7', False)
        # And should_reset = force_restart or ... -> should_reset = force_restart_section_7 or ...
        
        cell_source = cell_source.replace("root_cfg.get('force_restart'", "root_cfg.get('force_restart_section_7'")
        cell_source = cell_source.replace("force_restart = bool", "force_restart_section_7 = bool")
        cell_source = cell_source.replace("should_reset = force_restart or", "should_reset = force_restart_section_7 or")
        
        nb['cells'][idx]['source'] = [line + '\n' for line in cell_source.split('\n')]
        nb['cells'][idx]['source'][-1] = nb['cells'][idx]['source'][-1].rstrip('\n')

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
