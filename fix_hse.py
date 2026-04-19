import json
import re

nb_path = "coLab/Proteina_Complexa_coLab.ipynb"

with open(nb_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

new_func = """# --- 🌟 NEW: Spatial Patch Extraction (Surface-Aware) ---
def extract_patch_residues(pdb_path, target_chain, core_res_list, radius=6.0):
    \"\"\"提取以 core_res_list 为中心，半径 radius(Å) 内的所有 Target 表面残基 (Surface Patch)\"\"\"
    target_coords = {}
    ca_atoms = {}
    cb_atoms = {}
    res_names = {}
    island_coords = []
    
    if not pdb_path or not Path(pdb_path).exists():
        return core_res_list

    with open(pdb_path, 'r') as f:
        for line in f:
            if line.startswith("ATOM"):
                chain = line[21]
                if chain != target_chain: continue
                resi = line[22:26].strip()
                atom_name = line[12:16].strip()
                res_name = line[17:20].strip()
                
                coord = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                
                if resi not in target_coords:
                    target_coords[resi] = []
                target_coords[resi].append(coord)
                
                if atom_name == "CA": ca_atoms[resi] = coord
                if atom_name == "CB": cb_atoms[resi] = coord
                res_names[resi] = res_name
                
                if resi in core_res_list:
                    island_coords.append(coord)

    if not island_coords or not target_coords:
        return core_res_list # 降级保护

    # --- 1. 使用 KDTree 进行空间搜索 (距离过滤) ---
    island_tree = KDTree(island_coords)
    close_residues = []
    
    for resi, coords in target_coords.items():
        for coord in coords:
            dist, _ = island_tree.query(coord, k=1)
            if dist <= radius:
                close_residues.append(resi)
                break
                
    if not close_residues:
        return core_res_list

    # --- 2. 表面暴露过滤 (HSE Vector Check) ---
    all_resis = list(ca_atoms.keys())
    ca_coords_array = np.array([ca_atoms[r] for r in all_resis])
    if len(ca_coords_array) == 0: return close_residues
    
    ca_kdtree = KDTree(ca_coords_array)
    surface_patch = set()
    
    for resi in close_residues:
        if resi not in ca_atoms: continue
        ca = ca_atoms[resi]
        
        if res_names.get(resi) != 'GLY' and resi in cb_atoms:
            v_out = cb_atoms[resi] - ca
        else:
            neighbors_idx = ca_kdtree.query_ball_point(ca, r=8.0)
            if len(neighbors_idx) > 1:
                local_com = np.mean(ca_coords_array[neighbors_idx], axis=0)
                v_out = ca - local_com
            else:
                v_out = np.array([0.0, 0.0, 1.0])
                
        norm = np.linalg.norm(v_out)
        if norm > 1e-4: v_out = v_out / norm
        else: v_out = np.array([0.0, 0.0, 1.0])
        
        n_idx_all = ca_kdtree.query_ball_point(ca, r=10.0)
        forward_neighbors = 0
        for n_idx in n_idx_all:
            if all_resis[n_idx] == resi: continue
            vec = ca_coords_array[n_idx] - ca
            if np.dot(vec, v_out) > 0:
                forward_neighbors += 1
                
        if forward_neighbors < 12:
            surface_patch.add(resi)

    if not surface_patch: return core_res_list
    return sorted(list(surface_patch), key=lambda x: int(re.sub(r'\\D', '', x)))
"""

for idx, cell in enumerate(nb.get("cells", [])):
    if cell.get("cell_type") == "code":
        src = "".join(cell.get("source", []))
        if "def extract_patch_residues" in src and "Initiating Island" in src:
            # We will use regex to replace the function definition
            pattern = re.compile(r'# --- 🌟 NEW: Spatial Patch Extraction.*?def extract_patch_residues.*?(?=\nall_target_islands = )', re.DOTALL)
            match = pattern.search(src)
            if match:
                src = src[:match.start()] + new_func + src[match.end():]
                # convert back to lines
                lines = [line + '\n' for line in src.split('\n')]
                if lines and lines[-1] == '\n':
                    lines.pop()
                if lines:
                    lines[-1] = lines[-1].rstrip('\n')
                cell["source"] = lines
                print("Successfully updated HSE function!")
                break
            else:
                print("Function definition not found via regex!")
                # maybe definition header is different. Let's try broader match
                pattern2 = re.compile(r'def extract_patch_residues.*?(?=\nall_target_islands = )', re.DOTALL)
                match2 = pattern2.search(src)
                if match2:
                    src = src[:match2.start()] + new_func[new_func.find('def '):] + src[match2.end():]
                    lines = [line + '\n' for line in src.split('\n')]
                    if lines and lines[-1] == '\n': lines.pop()
                    if lines: lines[-1] = lines[-1].rstrip('\n')
                    cell["source"] = lines
                    print("Successfully updated HSE function (broad match)!")
                    break

with open(nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write('\n')

