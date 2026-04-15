import json
import re

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        
        if "Cell_18_Automated_Hotspot_Evolution_Loop.py" in source:
            source = source.replace("evolution_round = 1", "evolution_iterate = 1\ngeneration_round = 1")
            source = source.replace("designs_in_current_round = 0", "designs_in_current_iterate = 0")
            source = source.replace("round_designs = []", "iterate_designs = []")
            
            source = source.replace(
                'current_run_name = f"{SESSION_NAME}_Round{evolution_round}_Batch{designs_in_current_round}"', 
                'current_run_name = f"{SESSION_NAME}_Iterate{evolution_iterate}_Round{generation_round}"'
            )
            
            old_print = 'print(f"\\n=======================================================")\n    print(f"\\U0001f9ec Evolution Generation [Round {evolution_round}]: {designs_in_current_round}/{evo_designs_per_loop} designs Commencing...")'
            new_print = 'print(f"\\n=======================================================")\n    print(f"\\U0001f9ec Evolution Generation [Iterate {evolution_iterate} - Round {generation_round}]: {designs_in_current_iterate}/{evo_designs_per_loop} designs Commencing...")'
            source = source.replace(old_print, new_print)
            
            source = source.replace("d_id = f\"Round{evolution_round}_{base_d_id}\"", "d_id = f\"Iterate{evolution_iterate}_Round{generation_round}_{base_d_id}\"")
            source = source.replace("row['session_loop'] = evolution_round", "row['session_loop'] = evolution_iterate")
            source = source.replace("'batch_num': evolution_round", "'batch_num': evolution_iterate")
            source = source.replace("'loop': evolution_round", "'loop': evolution_iterate")
            source = source.replace("re.sub(r'^Round\\\\d+_', '', d['id'])", "re.sub(r'^Iterate\\\\d+_Round\\\\d+_', '', d['id'])")
            
            old_extend = "    if batch_designs:\n        round_designs.extend(batch_designs)\n\n    designs_in_current_round += generation_batch_size\n\n    # Check if we have generated enough designs for one evolution round\n    if designs_in_current_round < evo_designs_per_loop:"
            new_extend = "    if batch_designs:\n        iterate_designs.extend(batch_designs)\n        designs_in_current_iterate += len(batch_designs)\n    else:\n        print(\"\\u26a0\\ufe0f Warning: No valid designs parsed in this batch. Incrementing loop counter to prevent infinite loop...\")\n        designs_in_current_iterate += generation_batch_size\n\n    generation_round += 1\n\n    # Check if we have generated enough designs for one evolution iterate\n    if designs_in_current_iterate < evo_designs_per_loop:"
            source = source.replace(old_extend, new_extend)
            
            source = source.replace("if round_designs:", "if iterate_designs:")
            source = source.replace("cycle_designs = round_designs", "cycle_designs = iterate_designs")
            
            old_success = "reached at Round {evolution_round} with highest"
            new_success = "reached at Iterate {evolution_iterate} with highest"
            source = source.replace(old_success, new_success)
            
            old_reset = "    print(\"\\U0001f9f9 Evolution round complete. Preparing next round...\")\n    designs_in_current_round = 0\n    evolution_round += 1\n    round_designs = []"
            new_reset = "    print(\"\\U0001f9f9 Evolution iterate complete. Preparing next iterate...\")\n    designs_in_current_iterate = 0\n    evolution_iterate += 1\n    generation_round = 1\n    iterate_designs = []"
            source = source.replace(old_reset, new_reset)
            
            source = source.replace("Halted after {evolution_round} rounds", "Halted after {evolution_iterate} iterates")
            
            cell['source'] = source.splitlines(True)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Names patching and iteration tracking successfully updated.")
