import json

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        
        # 1. Patch Cell 0
        if "Section_0_Global_Configuration_Dashboard.py" in source:
            source = source.replace(
                'batch_size = 36 #@param {type:"integer"}\n',
                'generation_batch_size = 36 #@param {type:"integer"}\n'
                '# @markdown **[AF2 Evaluation Batch]** Safe limit: 1. Evaluator uses massive memory. Keep at 1 for 16GB GPUs, or max 2-3 for A100. Over 3 will OOM.\n'
                'evaluation_batch_size = 1 #@param {type:"integer"}\n'
            )
            source = source.replace(
                '"batch_size": batch_size,\n',
                '"generation_batch_size": generation_batch_size,\n        "evaluation_batch_size": evaluation_batch_size,\n'
            )
            source = source.replace(
                'batch_size,',
                'generation_batch_size, evaluation_batch_size,'
            )
            cell['source'] = source.splitlines(True)
            
        # 2. Patch Cell 6 (Section 3)
        elif "# Cell_6_Automated Pipeline for GFP Natural Substrate Benchmarking" in source:
            source = source.replace(
                "batch_size = int(root_cfg.get('batch_size', 12))",
                "evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))"
            )
            # Re-map batch_size variable inside string format
            source = source.replace(
                "++generation.dataloader.batch_size={batch_size}",
                "++generation.dataloader.batch_size={evaluation_batch_size}"
            )
            cell['source'] = source.splitlines(True)
            
        # 3. Patch Cell 7b (Section 4)
        elif "Auto-Pilot" in source and "batch_size = int(cfg['batch_size'])" in source:
            source = source.replace(
                "batch_size = int(cfg['batch_size'])\n",
                "generation_batch_size = int(cfg.get('generation_batch_size', 36))\n"
                "evaluation_batch_size = int(cfg.get('evaluation_batch_size', 1))\n"
            )
            source = source.replace("designs_per_loop / batch_size", "designs_per_loop / generation_batch_size")
            source = source.replace("num_batches * batch_size", "num_batches * generation_batch_size")
            
            old_str = "f\"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} \"\n"
            new_str = "f\"++generation.dataloader.batch_size={generation_batch_size} ++generation.search.max_batch_size={generation_batch_size} ++evaluation.dataloader.batch_size={evaluation_batch_size} \"\n"
            source = source.replace(old_str, new_str)
            cell['source'] = source.splitlines(True)

        # 4. Patch Cell 11 (Section 5)
        elif "scan_batch_size" in source and "complexa design" in source:
            source = source.replace(
                "batch_size = int(cfg['scan_batch_size'])\n",
                "batch_size = int(cfg['scan_batch_size'])\n"
                "evaluation_batch_size = int(cfg.get('evaluation_batch_size', 1))\n"
            )
            old_str = "f\"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} \"\n"
            new_str = "f\"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} ++evaluation.dataloader.batch_size={evaluation_batch_size} \"\n"
            source = source.replace(old_str, new_str)
            cell['source'] = source.splitlines(True)

        # 5. Patch Cell 18 (Section 6 Auto-Evolution)
        elif "# 3. Evolution Cycle Engine Loop" in source:
            source = source.replace(
                "batch_size = int(root_cfg.get('batch_size', 24))\n",
                "generation_batch_size = int(root_cfg.get('generation_batch_size', 36))\n"
                "evaluation_batch_size = int(root_cfg.get('evaluation_batch_size', 1))\n"
            )
            source = source.replace("evo_designs_per_loop / batch_size", "evo_designs_per_loop / generation_batch_size")
            source = source.replace("num_batches * batch_size", "num_batches * generation_batch_size")
            
            old_str = "f\"++generation.dataloader.batch_size={batch_size} ++generation.search.max_batch_size={batch_size} \"\n"
            new_str = "f\"++generation.dataloader.batch_size={generation_batch_size} ++generation.search.max_batch_size={generation_batch_size} ++evaluation.dataloader.batch_size={evaluation_batch_size} \"\n"
            source = source.replace(old_str, new_str)
            cell['source'] = source.splitlines(True)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Patching split complete!")
