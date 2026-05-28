import json

nb_path = 'c:/Code/Structure/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

cell_17 = ''.join(nb['cells'][17]['source'])
cell_17 = cell_17.replace('if force_restart:', 'if force_restart_section_7:')
cell_17 = cell_17.replace('Read force_restart to wipe', 'Read force_restart_section_7 to wipe')

nb['cells'][17]['source'] = [line + '\n' for line in cell_17.split('\n')]
nb['cells'][17]['source'][-1] = nb['cells'][17]['source'][-1].rstrip('\n')

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
