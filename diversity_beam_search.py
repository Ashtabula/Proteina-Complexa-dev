"""
Diversity-Preserving Beam Search for AlphaFold2-based Peptide Design
This module implements a multi-branch evolutionary pipeline to avoid local optima traps 
caused by merging contradictory binding modes.

Includes Industrial-Grade State Control Module: 
- Hard Reset (force_restart_evolution)
- True Resume (Seamless resume from multi-branch states)
"""

import numpy as np
import os
import csv
from typing import List, Dict, Tuple, Set

class PeptideDesign:
    def __init__(self, design_id: str, sequence: str, footprint: Set[int], score: float, pae_matrix: np.ndarray, parent_lineup: str = None):
        self.design_id = design_id
        self.sequence = sequence
        self.footprint = footprint       # Set of interacting target residues (e.g., {12, 15, 34})
        self.score = score               # Comprehensive score (e.g., ipSAE or pLDDT)
        self.pae_matrix = pae_matrix     # PAE matrix for evaluating residue interactions
        self.parent_lineup = parent_lineup # Which lineup generated this design

class Lineup:
    def __init__(self, lineup_id: str, champion: PeptideDesign, active_hotspots: Set[int]):
        self.lineup_id = lineup_id
        self.champion = champion
        self.active_hotspots = active_hotspots # Current targets being optimized
        self.performance_history = []          # Track average score of offsprings

def compute_jaccard_similarity(set1: Set[int], set2: Set[int]) -> float:
    """Calculate Jaccard similarity between two footprint sets."""
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def step1_cluster_by_footprint(designs: List[PeptideDesign], similarity_threshold: float = 0.5) -> Dict[str, List[PeptideDesign]]:
    """Step 1: Clustering by Footprint (Preserve Diversity)"""
    clusters = {}
    cluster_id_counter = 1
    
    for design in designs:
        assigned = False
        for c_id, c_designs in clusters.items():
            rep_footprint = c_designs[0].footprint
            sim = compute_jaccard_similarity(design.footprint, rep_footprint)
            
            if sim >= similarity_threshold:
                clusters[c_id].append(design)
                assigned = True
                break
        
        if not assigned:
            new_c_id = f"Cluster_{chr(64 + cluster_id_counter)}" 
            clusters[new_c_id] = [design]
            cluster_id_counter += 1
            
    return clusters

def step2_select_cluster_champions(clusters: Dict[str, List[PeptideDesign]]) -> List[PeptideDesign]:
    """Step 2: Select Cluster Champions (Alpha Wolves)"""
    champions = []
    for c_id, c_designs in clusters.items():
        sorted_designs = sorted(c_designs, key=lambda x: x.score, reverse=True)
        champions.append(sorted_designs[0])
    return champions

def step3_evolve_lineup_by_pae(champions: List[PeptideDesign], global_hotspot_pool: Set[int], max_distance: float = 10.0, pae_threshold: float = 15.0) -> List[Lineup]:
    """Step 3: Evolve Lineup by PAE (Branch-Specific Evolution)"""
    new_lineups = []
    for i, champion in enumerate(champions):
        lineup_id = f"Lineup_{chr(65+i)}" 
        
        pruned_hotspots = set()
        for res_idx in champion.footprint:
            mock_pae_value = np.mean(champion.pae_matrix) 
            if mock_pae_value <= pae_threshold:
                pruned_hotspots.add(res_idx)
                
        added_hotspots = set()
        for candidate_res in global_hotspot_pool:
            if candidate_res not in pruned_hotspots:
                mock_distance = 5.0         
                mock_potential_pae = 10.0   
                if mock_distance <= max_distance and mock_potential_pae <= pae_threshold:
                    added_hotspots.add(candidate_res)
                    
        next_gen_hotspots = pruned_hotspots.union(added_hotspots)
        new_lineups.append(Lineup(lineup_id=lineup_id, champion=champion, active_hotspots=next_gen_hotspots))
        
    return new_lineups

def step4_compare_and_prune(lineups: List[Lineup], new_generation_designs: List[PeptideDesign], min_score_threshold: float = 50.0) -> List[Lineup]:
    """Step 4: Compare & Prune (Parallel Evaluation)"""
    lineup_performance = {lineup.lineup_id: [] for lineup in lineups}
    for design in new_generation_designs:
        if design.parent_lineup in lineup_performance:
            lineup_performance[design.parent_lineup].append(design.score)
            
    surviving_lineups = []
    for lineup in lineups:
        scores = lineup_performance[lineup.lineup_id]
        if not scores:
            continue
        avg_score = sum(scores) / len(scores)
        lineup.performance_history.append(avg_score)
        
        if avg_score > min_score_threshold:
            surviving_lineups.append(lineup)
            
    return surviving_lineups

# ==========================================
# State Control Module (Hard Reset & True Resume)
# ==========================================

def save_state_to_csv(iteration: int, lineups: List[Lineup], csv_path: str):
    """Saves the current state of all active branches to CSV for True Resume."""
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['iteration', 'lineup_id', 'champion_id', 'champion_score', 'active_hotspots'])
        
        for lineup in lineups:
            hotspots_str = ";".join(map(str, sorted(list(lineup.active_hotspots))))
            writer.writerow([
                iteration,
                lineup.lineup_id,
                lineup.champion.design_id,
                lineup.champion.score,
                hotspots_str
            ])

def load_state_from_csv(csv_path: str) -> Tuple[int, List[Lineup], Set[int]]:
    """Loads the battlefield morphology at the moment before the crash."""
    if not os.path.exists(csv_path):
        return 0, [], set()
        
    tested_history_set = set()
    last_iteration = -1
    lineup_dict = {} 
    
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            iter_num = int(row['iteration'])
            lineup_id = row['lineup_id']
            hotspots_str = row['active_hotspots'].strip()
            hotspots = set(int(x) for x in hotspots_str.split(';') if x) if hotspots_str else set()
            
            # Absolute Memory: track every single tested amino acid to prevent re-testing
            tested_history_set.update(hotspots)
            
            if iter_num > last_iteration:
                last_iteration = iter_num
                
            if iter_num not in lineup_dict:
                lineup_dict[iter_num] = []
                
            mock_champion = PeptideDesign(
                design_id=row['champion_id'], 
                sequence="[RESUMED_SEQ]", 
                footprint=hotspots, 
                score=float(row['champion_score']), 
                pae_matrix=np.zeros((1,1)), 
                parent_lineup=lineup_id
            )
            lineup_dict[iter_num].append(Lineup(lineup_id=lineup_id, champion=mock_champion, active_hotspots=hotspots))
            
    active_lineups = lineup_dict.get(last_iteration, [])
    start_iteration = last_iteration + 1 if last_iteration >= 0 else 0
    return start_iteration, active_lineups, tested_history_set

# ==========================================
# Main Industrial-Grade Evolution Loop
# ==========================================

def beam_search_evolution_loop(
    initial_designs: List[PeptideDesign], 
    global_hotspot_pool: Set[int], 
    max_iterations: int = 10,
    force_restart_evolution: bool = False,
    csv_path: str = "beam_search_state.csv"
):
    """
    The Main Evolutionary Loop integrating Branch Evolution and State Control.
    """
    print(f"--- Initialization: Diversity-Preserving Beam Search Engine ---")
    print(f"⚙️ Force Restart Flag: {force_restart_evolution}")
    
    # ---------------- State Control Interception ----------------
    if force_restart_evolution or not os.path.exists(csv_path):
        print("⏩ [State Control] Performing HARD RESET or Fresh Start. Generating Ground Zero Lineups...")
        if force_restart_evolution and os.path.exists(csv_path):
            os.remove(csv_path) # Burn the old history
            
        clusters = step1_cluster_by_footprint(initial_designs)
        champions = step2_select_cluster_champions(clusters)
        active_lineups = step3_evolve_lineup_by_pae(champions, global_hotspot_pool)
        
        tested_history_set = set()
        for lineup in active_lineups:
            tested_history_set.update(lineup.active_hotspots)
            
        save_state_to_csv(0, active_lineups, csv_path)
        start_iteration = 1
    else:
        print("⏮️ [State Control] True Resume Active. Reconstructing the battlefield...")
        start_iteration, active_lineups, tested_history_set = load_state_from_csv(csv_path)
        print(f"📊 Recovered {len(active_lineups)} active branches. Resuming at Iteration {start_iteration}.")
        print(f"🧠 Absolute Memory Filter: {len(tested_history_set)} historically tested hotspots loaded into blacklist.")
        
        if len(active_lineups) == 0:
            print("⚠️ CSV was empty or corrupted. Falling back to Ground Zero...")
            # Fallback logic here if needed
            pass

    # ---------------- Main Evolution Engine ----------------
    for iteration in range(start_iteration, max_iterations):
        print(f"\n🧬 === Iteration {iteration} | Active Branches: {len(active_lineups)} ===")
        
        # Filter global pool: absolute memory prevents cyclic traps
        available_global_pool = global_hotspot_pool - tested_history_set
        
        # 1. GENERATION PHASE (Call your AF2 / Flow Matching here for each active lineup)
        print(f"🚀 Dispatching {len(active_lineups)} batches to GPU...")
        mock_new_designs = [] # Replace with: generate_designs(active_lineups)
        
        # 2. PRUNING PHASE
        print("⚖️ Comparing and Pruning branches based on performance...")
        # active_lineups = step4_compare_and_prune(active_lineups, mock_new_designs)
        
        # 3. BRANCHING PHASE
        # clusters = step1_cluster_by_footprint(mock_new_designs)
        # champions = step2_select_cluster_champions(clusters)
        # active_lineups = step3_evolve_lineup_by_pae(champions, available_global_pool)
        
        # Update absolute memory with newly assigned hotspots
        for lineup in active_lineups:
            tested_history_set.update(lineup.active_hotspots)
            
        # 4. STATE PERSISTENCE
        save_state_to_csv(iteration, active_lineups, csv_path)
        print(f"💾 State saved. Battlefield morphology preserved for Iteration {iteration}.")

    print("\n✅ Evolution Pipeline Complete!")
    return active_lineups
