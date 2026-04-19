import json

with open("coLab/Proteina_Complexa_coLab.ipynb", "r") as f:
    nb = json.load(f)

for idx, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "    # 🌟 计算 6Å Patch" in source and "Initiating Island:" in source:
            lines = cell['source']
            new_lines = []
            for i, line in enumerate(lines):
                if line.strip().startswith("# 🌟 计算 6Å Patch："):
                    new_lines.append(line)
                    indent = line[:len(line) - len(line.lstrip())]
                    new_lines.append(indent + "if name == 'Isl_0':\n")
                    new_lines.append(indent + "    patch_residues = residues\n")
                    new_lines.append(indent + "else:\n")
                    new_lines.append(indent + "    patch_residues = extract_patch_residues(SOURCE_PDB_PATH, target_chains, residues, radius=6.0)\n")
                elif "patch_residues" in line and "if name ==" not in line and "extract_patch_residues(" not in line and line not in new_lines: # Ensure we didn't double inject
                    new_lines.append(line)
                else:
                    if not line.strip().startswith("if name == 'Isl_0':") and "patch_residues = " not in line:
                        new_lines.append(line)
            
            # just rebuild to be safe
            clean_lines = []
            skip = False
            for line in lines:
                if line.strip().startswith("# 🌟 计算 6Å Patch："):
                    clean_lines.append(line)
                    indent = line[:len(line) - len(line.lstrip())]
                    clean_lines.append(indent + "if name == 'Isl_0':\n")
                    clean_lines.append(indent + "    patch_residues = residues\n")
                    clean_lines.append(indent + "else:\n")
                    clean_lines.append(indent + "    patch_residues = extract_patch_residues(SOURCE_PDB_PATH, target_chains, residues, radius=6.0)\n")
                else:
                    clean_lines.append(line)
            cell['source'] = clean_lines
            print(f"Patched cell {idx}")

with open("coLab/Proteina_Complexa_coLab.ipynb", "w") as f:
    json.dump(nb, f, indent=1)
