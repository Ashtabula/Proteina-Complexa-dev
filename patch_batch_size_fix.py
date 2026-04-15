import json

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        
        # 1. Patch Cell 0: Move batch_size to the top
        if "Section_0_Global_Configuration_Dashboard.py" in source:
            # First, check if we already moved it to prevent duplication
            if "Hardware Memory VRAM Limits" not in source:
                # Add the new section after Cache Settings
                cache_settings = 'enable_cache_backup = True # @param {type:"boolean"}\n'
                global_batch_settings = (
                    '\n# ==========================================\n'
                    '# --- Hardware Memory VRAM Limits ---\n'
                    '# ==========================================\n'
                    '# @markdown ### 💻 Hardware Memory Limits (VRAM Limit)\n'
                    '# @markdown Set this lower if you encounter OOM (Out Of Memory). This is shared across evaluating and generating sections (Section 3, 4, 6).\n'
                    'batch_size = 36 #@param {type:"integer"}\n'
                )
                source = source.replace(cache_settings, cache_settings + global_batch_settings)
                
                # Remove batch_size from Section 4 configuration where it originally was
                old_batch_def = 'batch_size = 36 #@param {type:"integer"}\n'
                # But wait, it might have been replaced. Let's just remove the one under Auto-Pilot
                # It is located between max_iterations and designs_per_loop
                source = source.replace(
                    'max_iterations = 30 #@param {type:"integer"}\n\nbatch_size = 36 #@param {type:"integer"}\ndesigns_per_loop = 36 #@param {type:"integer"}\n',
                    'max_iterations = 30 #@param {type:"integer"}\n\ndesigns_per_loop = 36 #@param {type:"integer"}\n'
                )
                cell['source'] = source.splitlines(True)
                
        # 2. Patch Cell 6 (Section 3 GFP Tutorial)
        elif "# Cell_6_Automated Pipeline for GFP Natural Substrate Benchmarking" in source:
            if "batch_size = int(root_cfg.get('batch_size" not in source:
                import_stmt = 'import os, sys, subprocess, shutil, gc, torch, time\n'
                new_import = 'import os, sys, subprocess, shutil, gc, torch, time, json\n'
                source = source.replace(import_stmt, new_import)
                
                job_id_stmt = 'JOB_ID = 0\n'
                config_load = (
                    'JOB_ID = 0\n\n'
                    '# --- [Global Settings Import] ---\n'
                    'ROOT_SETTING = BASE_DIR / \'internal_settings.json\'\n'
                    'if ROOT_SETTING.exists():\n'
                    '    with open(ROOT_SETTING, \'r\') as f: root_cfg = json.load(f)\n'
                    'else:\n'
                    '    root_cfg = {}\n'
                    'batch_size = int(root_cfg.get(\'batch_size\', 12))\n'
                )
                source = source.replace(job_id_stmt, config_load)
                
                base_args_old = '++generation.dataloader.batch_size=1 ++hydra.job.chdir=False ++eval_nmodels=1'
                base_args_new = '++generation.dataloader.batch_size={batch_size} ++hydra.job.chdir=False ++eval_nmodels=1'
                source = source.replace(base_args_old, base_args_new)
                
                cell['source'] = source.splitlines(True)

        # 3. Patch Cell 18 (Section 6 Auto-Evolution)
        elif "# 3. Evolution Cycle Engine Loop" in source:
            # Fix Indentation Error in cell 18
            source = source.replace(
                "        evo_target_threshold = float(root_cfg.get('evo_target_threshold', 0.85))\n",
                "evo_target_threshold = float(root_cfg.get('evo_target_threshold', 0.85))\n"
            )
            # Update batch_name mapping to use root_cfg
            source = source.replace(
                "batch_size = int(cfg.get('batch_size', 24))\n",
                "batch_size = int(root_cfg.get('batch_size', 24))\n"
            )
            cell['source'] = source.splitlines(True)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Patching complete!")
