"""
Diversity-Preserving Beam Search Engine
(保持多样性的束搜索多分支演化引擎)

本模块实现了“先聚类 -> 选头狼 -> 独立演化名单 -> 再次决斗”的进化闭环。
解决了传统贪心算法因为强制融合所有不同构象靶点，导致生成相互矛盾的四不像目标的致命痛点。
"""

import numpy as np
from typing import List, Dict, Set, Optional

# ==========================================
# 数据结构定义
# ==========================================
class PeptideDesign:
    """多肽设计数据结构，包含打分与结合特征"""
    def __init__(self, design_id: str, sequence: str, footprint: Set[int], score: float, pae_matrix: np.ndarray, parent_lineup: str = None):
        self.design_id = design_id
        self.sequence = sequence
        self.footprint = footprint         # 接触热点集合：实际抱住了靶点上的哪些氨基酸 (例如: {12, 15, 34})
        self.score = score                 # 综合打分：如 ipSAE 或 pLDDT，分数越高越好
        self.pae_matrix = pae_matrix       # PAE矩阵：用于评估残基间相互作用的预测误差
        self.parent_lineup = parent_lineup # 记录其父代分支 (如 Lineup_A)

class Lineup:
    """演化名单分支数据结构"""
    def __init__(self, lineup_id: str, champion: PeptideDesign, active_hotspots: Set[int]):
        self.lineup_id = lineup_id
        self.champion = champion           # 本分支的“头狼”
        self.active_hotspots = active_hotspots # 为头狼量身定制的下一代热点名单
        self.performance_history: List[float] = [] # 记录后代的平均分历史

# ==========================================
# 步骤 1：按结合构象聚类 (Clustering by Footprint)
# ==========================================
def compute_jaccard_similarity(set1: Set[int], set2: Set[int]) -> float:
    """计算两个接触热点集合的 Jaccard 相似度"""
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def step1_cluster_by_footprint(designs: List[PeptideDesign], similarity_threshold: float = 0.4) -> Dict[str, List[PeptideDesign]]:
    """
    不看整体打分，仅基于每个设计实际抱住的氨基酸集合（Footprint）进行聚类。
    将 N 个设计划分为不同的结合构象簇（如：簇A主攻左口袋，簇B主攻右口袋）。
    """
    clusters: Dict[str, List[PeptideDesign]] = {}
    cluster_counter = 1
    
    for design in designs:
        assigned = False
        # 尝试加入已有的结合构象簇
        for cluster_id, cluster_designs in clusters.items():
            # 使用簇内的第一个设计作为代表，计算构象相似度
            rep_footprint = cluster_designs[0].footprint
            sim = compute_jaccard_similarity(design.footprint, rep_footprint)
            
            if sim >= similarity_threshold:
                clusters[cluster_id].append(design)
                assigned = True
                break
        
        # 如果跟谁都不像，则开辟新的构象簇
        if not assigned:
            new_cluster_id = f"Cluster_{chr(64 + cluster_counter)}" # Cluster_A, Cluster_B...
            clusters[new_cluster_id] = [design]
            cluster_counter += 1
            
    return clusters

# ==========================================
# 步骤 2：选出聚类冠军 (Select Cluster Champions)
# ==========================================
def step2_select_cluster_champions(clusters: Dict[str, List[PeptideDesign]]) -> List[PeptideDesign]:
    """
    在划分好的每一个簇中，基于综合打分（ipSAE）进行局部内部排序，
    挑选出每个构象派系的第一名作为“头狼”。
    """
    champions = []
    for cluster_id, cluster_designs in clusters.items():
        # 基于综合打分 (score) 降序排列，选拔最强个体
        sorted_designs = sorted(cluster_designs, key=lambda d: d.score, reverse=True)
        alpha_wolf = sorted_designs[0]
        champions.append(alpha_wolf)
    return champions

# ==========================================
# 步骤 3：基于 PAE 的分支演化 (Evolve Lineup by PAE)
# ==========================================
def step3_evolve_lineup_by_pae(champions: List[PeptideDesign], global_pae_pool: Set[int], pae_threshold: float = 15.0, distance_threshold: float = 10.0) -> List[Lineup]:
    """
    抛弃全局统一名单，为每一只“头狼”量身定制下一代的演化路线 (Lineup A, Lineup B...)。
    """
    new_lineups = []
    for i, champion in enumerate(champions):
        lineup_id = f"Lineup_{chr(65+i)}"
        
        # 3.1 剔除阶段 (Prune)
        # 踢除头狼当前接触面中，PAE 分数极差或表现不佳的废弃位点
        pruned_hotspots = set()
        for res_idx in champion.footprint:
            # 伪代码：从头狼的 pae_matrix 提取该残基的交互误差
            mock_pae_value = np.mean(champion.pae_matrix) 
            if mock_pae_value <= pae_threshold:
                pruned_hotspots.add(res_idx)
                
        # 3.2 增补阶段 (Add)
        # 结合全局潜能替补池，寻找靠近该头狼结合构象的新热点
        added_hotspots = set()
        for candidate_res in global_pae_pool:
            if candidate_res not in pruned_hotspots:
                # 伪代码：测算 candidate_res 距离头狼 3D 几何中心的距离及潜力
                mock_distance = np.random.uniform(2.0, 15.0) 
                mock_pae_potential = np.random.uniform(5.0, 20.0)
                
                # 挑选距离近且 PAE 潜力高的新热点补入
                if mock_distance <= distance_threshold and mock_pae_potential <= pae_threshold:
                    added_hotspots.add(candidate_res)
                    
        # 生成专属的独立演化名单
        custom_next_gen_hotspots = pruned_hotspots.union(added_hotspots)
        new_lineups.append(Lineup(lineup_id=lineup_id, champion=champion, active_hotspots=custom_next_gen_hotspots))
        
    return new_lineups

# ==========================================
# 步骤 4：多分支并行与末位淘汰 (Compare & Prune)
# ==========================================
def step4_compare_and_prune(active_lineups: List[Lineup], new_generation_designs: List[PeptideDesign]) -> List[Lineup]:
    """
    收集所有分支产生的新一代后代，基于分支后代的平均分进行资源再分配和末位淘汰。
    """
    # 统计各个分支(Lineup)的后代分数表现
    lineup_scores = {lineup.lineup_id: [] for lineup in active_lineups}
    for design in new_generation_designs:
        if design.parent_lineup in lineup_scores:
            lineup_scores[design.parent_lineup].append(design.score)
            
    surviving_lineups = []
    
    for lineup in active_lineups:
        scores = lineup_scores[lineup.lineup_id]
        if not scores:
            continue
            
        avg_score = sum(scores) / len(scores)
        lineup.performance_history.append(avg_score)
        
        # 末位淘汰机制：淘汰停滞不前且低分的分支
        if avg_score > 50.0:  # 设定及格线阈值
            surviving_lineups.append(lineup)
        else:
            # 分数远落后于及格线，直接淘汰该停滞分支
            print(f"✂️ 分支 {lineup.lineup_id} 后代平均分过低 ({avg_score:.2f})，被系统淘汰。")
            
    # Hint: 可以加入资源倾斜逻辑 (Resource Allocation)
    # 比如如果 Lineup B 分数远超 Lineup A，可以在下次生成时分配 80% 的批次给 B。
    return surviving_lineups

# ==========================================
# 完整进化闭环主流程 (Main Loop)
# ==========================================
def diversity_preserving_evolution_loop(current_designs: List[PeptideDesign], global_pae_pool: Set[int]):
    """
    执行一个完美的“Diversity-Preserving Beam Search”进化闭环
    """
    print(">>> 启动保持多样性的束搜索...")
    
    # 步骤 1：按结合构象聚类 (先聚类)
    clusters = step1_cluster_by_footprint(current_designs)
    print(f"✅ 成功将设计划分为 {len(clusters)} 个不同结合构象派系。")
    
    # 步骤 2：选出聚类冠军 (选头狼)
    champions = step2_select_cluster_champions(clusters)
    print(f"🐺 已从各大派系中选拔出 {len(champions)} 只头狼。")
    
    # 步骤 3：基于 PAE 的分支演化 (独立演化名单)
    lineups = step3_evolve_lineup_by_pae(champions, global_pae_pool)
    print(f"🧬 已为头狼们量身定制 {len(lineups)} 条相互独立的演化路线。")
    
    # --- [Mock] 将各自的 Lineup 喂给模型生成新后代 ---
    # mock_new_designs = generate_from_lineups(lineups)
    # mock_new_designs = [...] 
    
    # 步骤 4：再次决斗与淘汰 (末位淘汰)
    # surviving_lineups = step4_compare_and_prune(lineups, mock_new_designs)
    
    return lineups
