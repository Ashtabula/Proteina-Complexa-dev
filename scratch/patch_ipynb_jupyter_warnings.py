import json

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code':
        source = cell.get('source', [])
        is_section_0 = any("Section_0_Global_Configuration_Dashboard.py" in line for line in source)
        if is_section_0:
            for i, line in enumerate(source):
                if line == "import os, json, shutil, sys\n":
                    # Insert the new code right after this import
                    new_lines = [
                        "import warnings\n",
                        "warnings.filterwarnings('ignore', category=DeprecationWarning)\n"
                    ]
                    source.insert(i+1, new_lines[0])
                    source.insert(i+2, new_lines[1])
                    print("Successfully injected warnings filter into Section 0 configuration.")
                    break
            break

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Notebook updated.")
