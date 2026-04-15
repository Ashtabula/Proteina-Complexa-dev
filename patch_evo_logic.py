import json
import re

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        
        # Patch Section 0
        if "Section_0_Global_Configuration_Dashboard" in source:
            old_evo_config = """evo_target_threshold = 0.85 #@param {type:"number"}\n"""
            new_evo_config = """evo_target_threshold = 0.85 #@param {type:"number"}
# @markdown Strict Geometric Confinement (Filter High RMSD before Evolution Selection)
evo_strict_rmsd_filter = True #@param {type:"boolean"}\n"""
            if "evo_strict_rmsd_filter = True" not in source:
                source = source.replace(old_evo_config, new_evo_config)
            
            old_json_config = """        "evo_target_threshold": evo_target_threshold,\n    }"""
            new_json_config = """        "evo_target_threshold": evo_target_threshold,
        "evo_strict_rmsd_filter": evo_strict_rmsd_filter,
    }"""
            if '"evo_strict_rmsd_filter": evo_strict_rmsd_filter' not in source:
                source = source.replace(old_json_config, new_json_config)
            cell['source'] = source.splitlines(True)
            
        # Patch Section 6
        if "Cell_18_Automated_Hotspot_Evolution_Loop.py" in source:
            # 1. Add variable reading
            if "evo_strict_rmsd_filter =" not in source:
                old_var = "evo_target_threshold = float(root_cfg.get('evo_target_threshold', 0.85))\n"
                new_var = "evo_target_threshold = float(root_cfg.get('evo_target_threshold', 0.85))\nevo_strict_rmsd_filter = root_cfg.get('evo_strict_rmsd_filter', True)\n"
                source = source.replace(old_var, new_var)

            # 2. Add RMSD Filtering
            old_sort = """        # Sort current cycle designs by score
        cycle_designs.sort(key=lambda x: x['score'], reverse=True)"""
            new_sort = """        if evo_strict_rmsd_filter:
            cycle_designs = [d for d in cycle_designs if d.get('rmsd', -999.0) != -999.0 and d.get('rmsd', 999.0) < 10.0]
        # Sort current cycle designs by score
        cycle_designs.sort(key=lambda x: x['score'], reverse=True)"""
            if "if evo_strict_rmsd_filter:" not in source:
                source = source.replace(old_sort, new_sort)

            # 3. Patch the elimination logic
            old_elim_logic = """        # Evolution Selection Algorithm
        new_hotspots_pool = {}
        
        # 1. Eliminate weak/dead original hotspots
        eliminated = []
        for res_id in active_hotspots:
            if contact_scores.get(res_id, 0) > 0:
                new_hotspots_pool[res_id] = contact_scores[res_id]
            else:
                eliminated.append(res_id)
                
        # 2. Integrate highly potent Neo-Hotspots based on the quota (evo_update_count)
        neo_hotspots = {k: v for k, v in contact_scores.items() if k not in active_hotspots}
        sorted_neo = sorted(neo_hotspots.keys(), key=lambda k: neo_hotspots[k], reverse=True)
        top_neo = sorted_neo[:evo_update_count]
        
        for neo_k in top_neo:
            new_hotspots_pool[neo_k] = contact_scores[neo_k]
            
        # 3. Cap Total Hotspots up to evo_max_hotspots based on ultimate combined scoring
        sorted_combined = sorted(new_hotspots_pool.keys(), key=lambda k: new_hotspots_pool[k], reverse=True)
        final_retained = sorted_combined[:evo_max_hotspots]"""
        
            new_elim_logic = """        # Evolution Selection Algorithm
        
        # 1. Score and rank original active hotspots
        current_scores = {res_id: contact_scores.get(res_id, 0.0) for res_id in active_hotspots}
        sorted_current = sorted(current_scores.keys(), key=lambda k: current_scores[k], reverse=True)
        
        # 2. Drop only the lowest-scoring hotspots based on evo_update_count quota
        drop_count = min(evo_update_count, max(0, len(active_hotspots) - 2)) # Ensure we don't drop everything
        retained_hotspots = sorted_current[:-drop_count] if drop_count > 0 else sorted_current
        eliminated = sorted_current[-drop_count:] if drop_count > 0 else []
                
        # 3. Integrate highly potent Neo-Hotspots based on the quota (evo_update_count)
        neo_hotspots = {k: v for k, v in contact_scores.items() if k not in active_hotspots}
        sorted_neo = sorted(neo_hotspots.keys(), key=lambda k: neo_hotspots[k], reverse=True)
        top_neo = sorted_neo[:drop_count] # Add as many as we dropped
        
        # 4. Combine and apply max limit
        final_retained = retained_hotspots + top_neo
        if len(final_retained) > evo_max_hotspots:
            # Secondary check to ensure we don't exceed max hotspots
            all_scores = {res_id: contact_scores.get(res_id, 0.0) for res_id in final_retained}
            final_retained = sorted(final_retained, key=lambda k: all_scores[k], reverse=True)[:evo_max_hotspots]"""
            
            source = source.replace(old_elim_logic, new_elim_logic)
            cell['source'] = source.splitlines(True)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Patching complete!")
