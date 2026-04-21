"""
Spatial Edge Expansion Evolution Engine
(边缘拓扑演化引擎: 核心锚定 + 表面外缘拓扑展开)

这个模块实现了一种基于“前沿推进算法 (Advancing Front Method)”的多肽演化架构，
解决单纯依赖全局 PAE 排序导致的空间连续性断裂和多肽构象撕裂问题。
"""

import os
import json
import numpy as np
from scipy.spatial import KDTree
from typing import List, Dict, Set, Tuple, Any

class ProteinStructure:
    """模拟靶点蛋白结构的 3D 几何特征与表面掩码"""
    def __init__(self, coordinates: Dict[int, np.ndarray], surface_mask: Set[int]):
        self.coordinates = coordinates    # residue_id -> 3D coordinates (x,y,z)
        self.surface_mask = surface_mask  # 绝对暴露于表面的残基集合 (例如通过 SASA 计算)

class EvolutionTreeManager:
    """管理树状数据结构 (JSON Checkpointing) 的读写器"""
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.tree_data = {
            "Core_Hotspots": [],
            "Anchors": {}
        }
        
    def load_tree(self) -> Dict:
        if os.path.exists(self.json_path):
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.tree_data = json.load(f)
        return self.tree_data
        
    def save_tree(self):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.tree_data, f, indent=4, ensure_ascii=False)
            
    def update_anchor_result(self, anchor_id: int, result_list: List[Dict]):
        # 存储当前 Anchor 节点下的 Top 3 结果叶子
        self.tree_data["Anchors"][str(anchor_id)] = result_list
        self.save_tree()

def step1_define_perimeter(core_hotspots: Set[int], structure: ProteinStructure) -> List[int]:
    """
    步骤 1：定义核心与外缘表面 (Define Core & Surface Perimeter)
    寻找包围在 Core Hotspots 势力范围最外缘的一圈表面氨基酸作为“外缘锚点 (Edge Anchors)”。
    """
    edge_anchors = []
    # 模拟逻辑: 遍历所有表面残基，找到那些不在 Core 内部，但是紧贴着 Core 的边界残基
    for res_id in structure.surface_mask:
        if res_id not in core_hotspots:
            # 简化算法：若该残基距离某个 core_hotspot 物理距离在 8Å 以内，则算作外围锚点
            for core_id in core_hotspots:
                if core_id in structure.coordinates:
                    dist = np.linalg.norm(structure.coordinates[res_id] - structure.coordinates[core_id])
                    if dist < 8.0:
                        edge_anchors.append(res_id)
                        break
    return edge_anchors

def step2_spatial_filtering(anchor_id: int, structure: ProteinStructure, global_pae_pool: Dict[int, float], threshold_distance: float = 15.0) -> List[int]:
    """
    步骤 2：基于锚点的空间过滤 (Anchor-based Spatial Filtering)
    利用 KDTree 实现 O(log N) 级三维雷达扫描，找出锚点周围阈值距离内的所有候选点，
    并只保留表面氨基酸，最后按 PAE 潜力排序。
    """
    candidate_ids = list(global_pae_pool.keys())
    if not candidate_ids:
        return []
        
    candidate_coords = [structure.coordinates[cid] for cid in candidate_ids]
    
    # 1. 构建空间 KD 树进行快速邻域检索
    kdtree = KDTree(candidate_coords)
    anchor_coord = structure.coordinates[anchor_id]
    
    # 2. 以锚点为圆心，查询 15Å (约5个氨基酸步长) 半径球体内的替补索引
    indices_within_radius = kdtree.query_ball_point(anchor_coord, threshold_distance)
    
    local_pool = []
    for idx in indices_within_radius:
        res_id = candidate_ids[idx]
        # 3. 双重过滤：必须在球体内 且 必须是表面暴露的
        if res_id in structure.surface_mask:
            local_pool.append(res_id)
            
    # 4. 局部专属池按 PAE 质量排序 (值越低代表预测误差越小/结合潜力越强)
    local_pool.sort(key=lambda x: global_pae_pool[x])
    
    return local_pool

def step3_local_evolution(anchor_id: int, core_hotspots: Set[int], local_pool: List[int]) -> List[Dict]:
    """
    步骤 3：局部深度演化至收敛 (Local Evolution to Convergence)
    在锚点专属池中玩“贪吃蛇”，稳扎稳打：补入2个最好点 -> 跑生成 -> 如果变差踢掉 -> 换下2个。
    """
    current_lineup = set(core_hotspots)
    top_results = []
    
    pool_queue = local_pool.copy()
    best_score = -999.0
    stagnation_counter = 0
    
    # 当池子里还有足够弹药，且未达到连续停滞上限时继续
    while len(pool_queue) >= 2 and stagnation_counter < 3:
        add_1 = pool_queue.pop(0)
        add_2 = pool_queue.pop(0)
        
        # 核心绝对不可变，每次追加局部锚点周围的 2 个点
        test_lineup = current_lineup.union({add_1, add_2})
        
        # --- [Mock] 触发 Generative Model (AF2) 推理 ---
        mock_score = np.random.uniform(50, 100) # 模拟得到综合 pLDDT 或 ipSAE 评分
        
        if mock_score > best_score:
            best_score = mock_score
            current_lineup = test_lineup  # 成功收编这两个点
            stagnation_counter = 0
            
            # 存入结果缓存，维持 Top 3
            top_results.append({
                "lineup": list(current_lineup),
                "score": float(mock_score)
            })
            top_results = sorted(top_results, key=lambda x: x["score"], reverse=True)[:3]
        else:
            # 分数未提升，抛弃这两个残基
            stagnation_counter += 1
            
    return top_results

def spatial_edge_expansion_engine(
    core_hotspots: Set[int], 
    structure: ProteinStructure, 
    global_pae_pool: Dict[int, float], 
    json_path: str = "evolution_tree.json",
    force_restart_evolution: bool = False
):
    """
    主引擎：全局去重与步进 (Global Pruning & Step Forward)
    负责驱动雷达扫描、调用局部演化、并持久化维护 JSON 演化树。
    """
    print("--- 初始化边缘拓扑演化引擎 (Edge Expansion) ---")
    tree_manager = EvolutionTreeManager(json_path)
    
    # --- [State Control / 断点续传] ---
    if force_restart_evolution or not os.path.exists(json_path):
        print(">> 执行 Hard Reset：全新启动，栽下新的演化树根 (Core Hotspots)...")
        if os.path.exists(json_path):
            os.remove(json_path)
        tree_manager.tree_data["Core_Hotspots"] = list(core_hotspots)
        tree_manager.save_tree()
    else:
        print(">> 执行 True Resume：从 JSON 演化树无缝恢复现场...")
        tree_manager.load_tree()
        
    completed_anchors = set([int(k) for k in tree_manager.tree_data["Anchors"].keys()])
    
    # 1. 雷达扫描出包围圈锚点
    edge_anchors = step1_define_perimeter(core_hotspots, structure)
    print(f"📡 探测到 {len(edge_anchors)} 个可用的外缘锚点...")
    
    # 2. 锚点轮盘驱动
    for anchor_id in edge_anchors:
        if anchor_id in completed_anchors:
            print(f"⏭️ 锚点 {anchor_id} 的演化枝丫已经收敛，跳过。")
            continue
            
        print(f"\n📍 开始针对锚点 {anchor_id} 进行深耕演化...")
        
        # 3. 筛选它的专属战区弹药库 (KDTree)
        local_pool = step2_spatial_filtering(anchor_id, structure, global_pae_pool)
        print(f"   该锚点 15Å 半径专属战区候选池大小: {len(local_pool)}")
        
        # 4. 执行局部攻坚战
        top_results = step3_local_evolution(anchor_id, core_hotspots, local_pool)
        
        # 5. 挂载 JSON 树叶节点
        if top_results:
            tree_manager.update_anchor_result(anchor_id, top_results)
            print(f"💾 锚点 {anchor_id} 局部演化完成，Top 3 结果已挂载至演化树。")
            
        # 6. 全局去重 (核心防重复设计：用过的无论好坏，从全局池销毁)
        deleted_count = 0
        for tested_res in local_pool:
            if tested_res in global_pae_pool:
                del global_pae_pool[tested_res]
                deleted_count += 1
        print(f"   🧹 清理全局弹药库：已消耗 {deleted_count} 个战区残基点。")
                
    print("\n✅ 所有前沿阵地推进完毕，边缘拓扑演化闭环！")
    return tree_manager.tree_data
