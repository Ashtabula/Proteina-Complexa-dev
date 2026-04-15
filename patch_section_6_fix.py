import json

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        if "Section_0_Global_Configuration_Dashboard.py" in source:
            # Patch cell 0
            new_source = source.replace(
                '"evo_update_count": evo_update_count,\n',
                '"evo_update_count": evo_update_count,\n        "evo_target_threshold": evo_target_threshold,\n'
            )
            new_source = new_source.replace(
                'evo_update_count = 2 #@param {type:"integer"}\n',
                'evo_update_count = 2 #@param {type:"integer"}\nevo_target_threshold = 0.85 #@param {type:"number"}\n'
            )
            cell['source'] = new_source.splitlines(True)
            
        elif "# 3. Evolution Cycle Engine Loop" in source:
            # Patch cell 18
            new_source = source.replace(
                "evo_designs_per_loop = int(cfg.get('evo_designs_per_loop', 48))",
                "evo_designs_per_loop = int(root_cfg.get('evo_designs_per_loop', 48))"
            )
            new_source = new_source.replace(
                "evo_max_iterations = int(cfg.get('evo_max_iterations', 10))",
                "evo_max_iterations = int(root_cfg.get('evo_max_iterations', 10))"
            )
            new_source = new_source.replace(
                "evo_max_hotspots = int(cfg.get('evo_max_hotspots', 8))",
                "evo_max_hotspots = int(root_cfg.get('evo_max_hotspots', 8))"
            )
            new_source = new_source.replace(
                "evo_update_count = int(cfg.get('evo_update_count', 2))",
                "evo_update_count = int(root_cfg.get('evo_update_count', 2))\n        evo_target_threshold = float(root_cfg.get('evo_target_threshold', 0.85))"
            )
            
            old_code = '    print("-" * 85)\n\n    gc.collect()\n    if torch.cuda.is_available(): torch.cuda.empty_cache(); torch.cuda.ipc_collect()\n\n    if current_iteration < evo_max_iterations:\n'
            early_stop_code = '    print("-" * 85)\n\n    gc.collect()\n    if torch.cuda.is_available(): torch.cuda.empty_cache(); torch.cuda.ipc_collect()\n\n    best_score_so_far = ALL_DESIGNS_POOL[0][\'score\'] if ALL_DESIGNS_POOL else 0\n    if best_score_so_far >= evo_target_threshold:\n        print(f"\\n🎉 SUCCESS! Evolution Target Threshold ({evo_target_threshold}) reached at Cycle {current_iteration} with highest ipSAE score: {best_score_so_far:.4f}")\n        break\n\n    if current_iteration < evo_max_iterations:\n'
            
            new_source = new_source.replace(old_code, early_stop_code)
            cell['source'] = new_source.splitlines(True)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Patching complete!")
