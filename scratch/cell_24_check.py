# Cell_21_Physical_Generation_Visualizations.py
# --- 5. Separate Visualizations (Real-Time Watch Mode) ---
import json
import re
from pathlib import Path
import py3Dmol
from IPython.display import HTML, display

print("\n🎨 Initiating Real-Time Watch Mode: Rendering Top Binders & Key Anchors...")

# 读取硬盘数据
scores_manifest = {}
hybrid_islands = {}

scores_manifest_path = final_dir / "Scores_Manifest.json"
manifest_path = final_dir / "Hybrid_Islands_Manifest.json"

if scores_manifest_path.exists():
    with open(scores_manifest_path, 'r') as f:
        scores_manifest = json.load(f)
    print(f"✅ Found {len(scores_manifest)} completed Islands ready for preview.")
else:
    print("⏳ Waiting for Cell 20 to finish generating the first batch...")

if manifest_path.exists():
    with open(manifest_path, 'r') as f:
        hybrid_islands = json.load(f)
else:
    print("🌱 Hybrid Manifest not yet generated. Entering Live Preview Mode...")

d3to1 = {'CYS': 'C', 'ASP': 'D', 'SER': 'S', 'GLN': 'Q', 'LYS': 'K',
         'ILE': 'I', 'PRO': 'P', 'THR': 'T', 'PHE': 'F', 'ASN': 'N',
         'GLY': 'G', 'HIS': 'H', 'LEU': 'L', 'ARG': 'R', 'TRP': 'W',
         'ALA': 'A', 'VAL': 'V', 'GLU': 'E', 'TYR': 'Y', 'MET': 'M'}

# 从全局内存中获取配置
global_ordered_resis = globals().get('ordered_natural_resis', [])
natural_to_af2 = {nat: str(i+1) for i, nat in enumerate(global_ordered_resis)} if global_ordered_resis else {}
global_base_hotspots = globals().get('base_hotspots', [])

for isl_name, data in scores_manifest.items():
    top_pdb = data.get("top_pdb")
    if not top_pdb or not Path(top_pdb).exists():
        continue

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

    # ==========================================
    # 🎯 核心逻辑更新：寻找 Patch 上最强的 Top 2 AA
    # ==========================================

    # 1. Global Core (Orange): 最初始的基准热点
    global_core_raw = global_base_hotspots

    # 2. Global Neo (Red): 【修改点】改为该 Island Patch 上 PAE 表现最好的前两个氨基酸
    pae_ranking = data.get("hotspot_pae_ranking", {})
    if pae_ranking:
        # 按 PAE 从低到高排序，取前 2 个作为最强锚点
        sorted_anchors = sorted(pae_ranking.items(), key=lambda x: x[1])
        neo_hs_raw = [k for k, v in sorted_anchors[:2]]
        best_pae_val = sorted_anchors[0][1] if sorted_anchors else 0
    else:
        # 如果还没跑完 PAE，则显示为空，保持严谨
        neo_hs_raw = []
        best_pae_val = "N/A"

    # 3. Island Core (Gray): 本 Island 指定的核心靶点区域
    island_core_raw = data.get("residues", [])

    # 4. Island 6A Patch (White): 扩张后的表面
    patch_resi_raw = data.get("patch_residues", [])

    # 智能翻译坐标：支持AF2重排映射
    def translate_resi(resi_list):
        res = []
        for x in resi_list:
            num_str = re.sub(r'\D', '', str(x))
            if natural_to_af2 and num_str in natural_to_af2:
                res.append(int(natural_to_af2[num_str]))
            elif num_str:
                res.append(int(num_str))
        return res

    global_core_int = translate_resi(global_core_raw)
    neo_hs_int = translate_resi(neo_hs_raw)
    island_core_int = translate_resi(island_core_raw)
    patch_resi_int = translate_resi(patch_resi_raw)

    # 取差集：染白色扩张区域（排除核心后剩下的表面部分）
    expanded_resi_int = list(set(patch_resi_int) - set(island_core_int)) if patch_resi_int else []
    first_resi_binder_int = int(re.sub(r'\D', '', str(first_resi_binder))) if first_resi_binder else None

    # HTML 面板渲染
    ipsae_val = data.get("max_score", -999.0)
    binder_seq = chains_seq.get(binder_chains[0], "N/A") if binder_chains else "N/A"
    peptide_len = len(binder_seq) if binder_seq != "N/A" else 0

    # 顶部状态条，标注出 Top 2 锚点
    anchor_info = f" | <b style='color:red;'>Top Anchors:</b> {', '.join(neo_hs_raw)}" if neo_hs_raw else ""

    html_content = f"""
    <hr>
    <h3 style='color: #0056b3;'>Island View: {isl_name}</h3>
    <div style='background: #f8f9fa; padding: 10px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid #28a745;'>
        <p style='margin: 5px 0;'><b>🏆 Max ipSAE:</b> <span style='color:red; font-size:16px;'>{ipsae_val:.4f}</span> | <b>Best PAE:</b> {best_pae_val}{anchor_info}</p>
        <p style='margin: 5px 0;'><b>🧬 Peptide Sequence:</b> <code style='background:#fff; padding:2px 6px; border: 1px solid #ddd; border-radius:4px; font-size:14px; color:#d63384;'>{binder_seq}</code></p>
    </div>
    <div style='font-size: 13px; color: #555; margin-bottom: 5px;'>
       <b>Color Map:</b>
       <span style='background:#333; color:white; padding:2px 5px; border-radius:3px;'>Island Core (Gray)</span>
       <span style='background:#fff; color:#333; border:1px solid #ccc; padding:2px 5px; border-radius:3px;'>6Å Patch (Ghost White)</span>
       <span style='color:orange; font-weight:bold;'>Global Core (Orange)</span>
       <span style='color:red; font-weight:bold;'>Best Anchors on Patch (Red)</span>
       <span style='color:lime; font-weight:bold;'>Peptide (Green)</span>
    </div>
    """
    display(HTML(html_content))

    viewer = py3Dmol.view(width=800, height=500)
    viewer.addModel(pdb_data, 'pdb')

    # Target Mesh
    target_sel = {'chain': target_chain_ids}
    viewer.setStyle(target_sel, {'cartoon': {'color': '#A9A9A9', 'opacity': 0.7}})
    viewer.addSurface(py3Dmol.SES, {'color': '#A9A9A9', 'wireframe': True}, target_sel)

    # 1. Global Core (Orange)
    if global_core_int:
        c_sel = {'chain': target_chain_ids, 'resi': global_core_int}
        viewer.setStyle(c_sel, {'cartoon': {'color': 'orange', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'orange', 'opacity': 1.0}, c_sel)

    # 2. Global Neo -> 现在是 Island Top 2 Anchors (Red)
    if neo_hs_int:
        n_sel = {'chain': target_chain_ids, 'resi': neo_hs_int}
        viewer.setStyle(n_sel, {'cartoon': {'color': 'red', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'red', 'opacity': 1.0}, n_sel)

    # 3. 6Å 扩张辅助面 (Ghost White)
    if expanded_resi_int:
        exp_sel = {'chain': target_chain_ids, 'resi': expanded_resi_int}
        viewer.setStyle(exp_sel, {'cartoon': {'color': 'white', 'opacity': 0.4}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'white', 'opacity': 0.3}, exp_sel)

    # 4. 当前 Island 核心 (Solid Gray)
    if island_core_int:
        sat_sel = {'chain': target_chain_ids, 'resi': island_core_int}
        viewer.setStyle(sat_sel, {'cartoon': {'color': 'gray', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'gray', 'opacity': 1.0}, sat_sel)

    # Binder (Green)
    if binder_chains:
        b_sel = {'chain': binder_chains}
        viewer.setStyle(b_sel, {'cartoon': {'color': 'lime', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.SES, {'color': 'lime', 'opacity': 1.0}, b_sel)

    # Binder N-Term (Blue) - 方便识别多肽方向
    if first_resi_binder_int and binder_chains:
        nterm_sel = {'chain': binder_chains[0], 'resi': [first_resi_binder_int]}
        viewer.setStyle(nterm_sel, {'cartoon': {'color': 'blue', 'opacity': 1.0}})
        viewer.addSurface(py3Dmol.VDW, {'color': 'blue', 'opacity': 1.0}, nterm_sel)

    viewer.zoomTo()

    try:
        display(viewer.show())
    except Exception:
        viewer.show()