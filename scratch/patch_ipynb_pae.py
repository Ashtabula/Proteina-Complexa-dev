import json

file_path = 'coLab/Proteina_Complexa_coLab.ipynb'
data = json.load(open(file_path))
changed = False
search_str = '++run_filter=True ++run_evaluate=True ++run_analyze=True'
replace_str = '++run_filter=True ++run_evaluate=True ++run_analyze=True ++evaluate.save_pae=True ++evaluate.dump_json=True ++evaluate.save_outputs=True'

for cell in data.get('cells', []):
    if cell['cell_type'] == 'code':
        for i, line in enumerate(cell['source']):
            if search_str in line:
                cell['source'][i] = line.replace(search_str, replace_str)
                changed = True

if changed:
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=1)
        f.write('\n')
    print('Notebook updated with PAE flags.')
else:
    print('No changes needed or search string not found.')
