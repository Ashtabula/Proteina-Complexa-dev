import json
with open('c:/Code/Structure/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, cell in enumerate(nb['cells']):
    source = "".join(cell.get('source', []))
    if 'restart' in source.lower():
        print(f'--- Cell {i} ---')
        print(source)
