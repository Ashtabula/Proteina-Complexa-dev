# Cell_21_Physical_Generation_Visualizations.py
# --- 5. Separate Visualizations ---
print("\n🎨 Rendering Separate Top 1 Binders for Each Island...")
d3to1 = {'CYS': 'C', 'ASP': 'D', 'SER': 'S', 'GLN': 'Q', 'LYS': 'K',
         'ILE': 'I', 'PRO': 'P', 'THR': 'T', 'PHE': 'F', 'ASN': 'N',
         'GLY': 'G', 'HIS': 'H', 'LEU': 'L', 'ARG': 'R', 'TRP': 'W',
         'ALA': 'A', 'VAL': 'V', 'GLU': 'E', 'TYR': 'Y', 'MET': 'M'}

for isl_name, data in scores_manifest.items():
    top_pdb = data.get("top_pdb")
    if not top_pdb or not Path(top_pdb).exists(): continue

    with open(top_pdb, 'r') as f: pdb_data = f.read()

    chains_seq = {}
    first_resi_binder = None
    for line in pdb_data.split('\n'):
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            res_name = line[17:20].strip()
            chain_id = line[21]
            if chain_id not in chains_seq: chains_seq[chain_id] = ""
            chains_seq[chain_id] += d3to1.get(res_name, 'X')

    chain_lengths = {c: len(seq) for c, seq in chains_seq.items()}
    if not chain_lengths: continue
    sorted_chains = sorted(chain_lengths.keys(), key=lambda c: chain_lengths[c])
    binder_chains = [sorted_chains[0]]
    target_chain_ids = [c for c in sorted_chains[1:]]

    for line in pdb_data.split('\n'):
        if line.startswith("ATOM") and line[21] == binder_chains[0]:
            first_resi_binder = line[22:26].strip()
            break

    hybrid_name = isl_name.replace("Isl_", "Isl_0") if isl_name != "Isl_0" else "Isl_0"
    island_data = hybrid_islands.get(hybrid_name, {})

    # 建立 自然编号 -> AF2序号(从1开始) 的翻译字典
    natural_to_af2 = {nat: str(i+1) for i, nat in enumerate(ordered_natural_resis)}

    core_hs_raw = island_data.get("core_hotspots", base_hotspots)
    neo_hs_raw = island_data.get("neo_hotspots", [])
    
    # 获取当前 Island 的核心靶点 (Core)
    sat_resi_raw = data.get("residues", [])
    # 获取当前 Island 扩张出来的 6Å 表面补丁 (Patch)
    patch_resi_raw = extract_patch_residues(SOURCE_PDB_PATH, target_chains, sat_resi_raw, radius=6.0)

    # 翻译核心热点和新生热点 (用于橙色/红色高亮)
    core_hs_int = [int(natural_to_af2[re.sub(r'\D', '', str(x))]) for x in core_hs_raw if re.sub(r'\D', '', str(x)) in natural_to_af2]
    neo_hs_int = [int(natural_to_af2[re.sub(r'\D', '', str(x))]) for x in neo_hs_raw if re.sub(r'\D', '', str(x)) in natural_to_af2]
    
    # 翻译本轮生成的目标 Island (核心 白色) 和 扩张的 Patch (半透明白色)
    sat_resi_int = [int(natural_to_af2[re.sub(r'\D', '', str(x))]) for x in sat_resi_raw if re.sub(r'\D', '', str(x)) in natural_to_af2]
    patch_resi_int = [int(natural_to_af2[re.sub(r'\D', '', str(x))]) for x in patch_resi_raw if re.sub(r'\D', '', str(x)) in natural_to_af2]
    # 取差集：仅仅是扩张出来的周围氨基酸（刨除核心。）
    expanded_resi_int = list(set(patch_resi_int) - set(sat_resi_int))

    first_resi_binder_int = int(re.sub(r'\D', '', str(first_resi_binder))) if first_resi_binder else None

    # --- 增强版 HTML 渲染：更新了图例，加入白色双层说明 ---
    ipsae_val = island_data.get("baseline_ipsae", data.get("max_score", -999.0))
    binder_seq = chains_seq.get(binder_chains[0], "N/A") if binder_chains else "N/A"
    peptide_len = len(binder_seq) if binder_seq != "N/A" else 0

    html_content = f"""
    <hr>
    <h3 style='color: #0056b3;'>Visualization: {isl_name} -> {hybrid_name}</h3>
    <div style='background: #f8f9fa; padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #28a745;'>
        <p style='margin: 5px 0;'><b>🏆 Max ipSAE:</b> <span style='color:red; font-size:16px;'>{ipsae_val:.4f}</span> | <b>Length:</b> {peptide_len} AA</p>
        <p style='margin: 5px 0;'><b>🧬 Peptide Sequence:</b> <code style='background:#fff; padding:2px 6px; border: 1px solid #ddd; border-radius:4px; font-size:14px; color:#d63384;'>{binder_seq}</code></p>
    </div>
    <p><b>Target:</b> Mesh | 
       <b style='background:#333; color:white; padding:2px 6px; border-radius:3px;'>Island Core: Solid White</b> | 
       <b style='background:#ccc; color:#333; padding:2px 6px; border-radius:3px;'>6Å Patch: Ghost White</b> | 
       <b>Global Core:</b> Orange | <b>Global Neo:</b> Red</p>
    """
    display(HTML(html_content))

    viewer = py3Dmol.view(width=800, height=500)
    viewer.addModel(pdb_data, 'pdb')

    # Target Mesh
    target_sel = {'chain': target_chain_ids}
    viewer.setStyle(target_sel, {'cartoon': {'color': '#A9A9A9', 'opacity': 0.7}})
    viewer.addSurface(py3Dmol.SES, {'color': '#A9A9A9', 'wireframe': True}, target_sel)

    # Global Core (Orange) & Neo (Red)
    if core_hs_int:
        c_sel = {'chain': target_chain_ids, 'resi': core_hs_int}
        viewer.setStyle(c_sel, {'cartoon': {'color': 'orange', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'orange', 'opacity': 1.0}, c_sel)

    if neo_hs_int:
        n_sel = {'chain': target_chain_ids, 'resi': neo_hs_int}
        viewer.setStyle(n_sel, {'cartoon': {'color': 'red', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'red', 'opacity': 1.0}, n_sel)

    # --- 新增 1：6Å 扩张辅助面 (半透明白色) ---
    if expanded_resi_int:
        exp_sel = {'chain': target_chain_ids, 'resi': expanded_resi_int}
        viewer.setStyle(exp_sel, {'cartoon': {'color': 'white', 'opacity': 0.4}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'white', 'opacity': 0.3}, exp_sel) # 0.3 opacity 形成类似光晕的半透明层

    # --- 新增 2：当前 Island 核心 (纯白色) ---
    if sat_resi_int:
        sat_sel = {'chain': target_chain_ids, 'resi': sat_resi_int}
        viewer.setStyle(sat_sel, {'cartoon': {'color': 'gray', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'gray', 'opacity': 1.0}, sat_sel)

    # Binder (Green)
    if binder_chains:
        b_sel = {'chain': binder_chains}
        viewer.setStyle(b_sel, {'cartoon': {'color': 'lime', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.SES, {'color': 'lime', 'opacity': 1.0}, b_sel)

    # Binder N-Term (Blue)
    if first_resi_binder_int and binder_chains:
        nterm_sel = {'chain': binder_chains[0], 'resi': [first_resi_binder_int]}
        viewer.setStyle(nterm_sel, {'cartoon': {'color': 'blue', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'blue', 'opacity': 1.0}, nterm_sel)

    viewer.zoomTo()
    
    # 强制 display 显示 3D 视图
    try:
        display(viewer.show())
    except Exception:
        viewer.show()