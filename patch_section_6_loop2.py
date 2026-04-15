import json
import re

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = "".join(cell['source'])
        
        # Remove evo_max_iterations from Cell 0
        if "Section_0_Global_Configuration_Dashboard.py" in source:
            source = source.replace('evo_max_iterations = 10 #@param {type:"integer"}\n', '')
            source = source.replace('"evo_max_iterations": evo_max_iterations,\n', '')
            source = source.replace('evo_max_iterations,', '')
            cell['source'] = source.splitlines(True)
            
        # Refactor Cell 18 (Section 6)
        elif "# 3. Evolution Cycle Engine Loop" in source:
            # Change initialization
            source = source.replace(
                "evo_max_iterations = int(root_cfg.get('evo_max_iterations', 10))\n",
                ""
            )
            
            # The big refactor of the loop structure
            old_loop_start = """global_start_time = time.time()
current_iteration = max_loop_found

# The contact distance threshold for defining a "hit" between binder and target
CONTACT_THRESHOLD = 4.5  

while current_iteration < evo_max_iterations:
    current_iteration += 1
    loop_start_time = time.time()
    batch_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_seed = random.randint(1, 1000000)
    current_run_name = f"{SESSION_NAME}_Cycle{current_iteration}"
    
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / current_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)
    
    print(f"\\n=======================================================")
    print(f"🧬 Evolution Cycle [{current_iteration}/{evo_max_iterations}] Commencing...")
    print(f"🎯 Current Active Hotspots: {','.join(active_hotspots)}")
    print(f"=======================================================")

    # Force inject dynamic hotspots into complexa yaml right before runtime
    yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
            
    num_batches = math.ceil(evo_designs_per_loop / generation_batch_size)
    total_designs = num_batches * generation_batch_size

    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={current_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={total_designs} "
        f"++generation.dataloader.batch_size={generation_batch_size} ++generation.search.max_batch_size={generation_batch_size} ++evaluation.dataloader.batch_size={evaluation_batch_size} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=True ++run_analyze=True ++seed={current_seed}"
    )"""

            new_loop_start = """global_start_time = time.time()

# The contact distance threshold for defining a "hit" between binder and target
CONTACT_THRESHOLD = 4.5  

evolution_round = 1
designs_in_current_round = 0
round_designs = []

while True:
    loop_start_time = time.time()
    batch_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_seed = random.randint(1, 1000000)
    current_run_name = f"{SESSION_NAME}_Round{evolution_round}_Batch{designs_in_current_round}"
    
    RUN_ISOLATED_DIR = SESSION_MASTER_DIR / current_run_name
    RUN_ISOLATED_DIR.mkdir(parents=True, exist_ok=True)

    ISOLATED_PDB_PATH = RUN_ISOLATED_DIR / f"{task_name}_fixed.pdb"
    shutil.copy(SOURCE_PDB_PATH, ISOLATED_PDB_PATH)
    
    print(f"\\n=======================================================")
    print(f"🧬 Evolution Generation [Round {evolution_round}]: {designs_in_current_round}/{evo_designs_per_loop} designs Commencing...")
    print(f"🎯 Current Active Hotspots: {','.join(active_hotspots)}")
    print(f"=======================================================")

    # Force inject dynamic hotspots into complexa yaml right before runtime
    yaml_path = BASE_DIR / 'configs/targets/targets_dict.yaml'
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        yaml_data['target_dict_cfg'][task_name]['hotspot_residues'] = [f"{target_chains}{r}" for r in active_hotspots]
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    cmd_str = (
        f"complexa design configs/search_binder_local_pipeline.yaml ++run_name={current_run_name} "
        f"++generation.task_name={task_name} ++generation.num_designs={generation_batch_size} "
        f"++generation.dataloader.batch_size={generation_batch_size} ++generation.search.max_batch_size={generation_batch_size} ++evaluation.dataloader.batch_size={evaluation_batch_size} "
        f"++generation.dataloader.dataset.conditional_features.0.pdb_path={ISOLATED_PDB_PATH} "
        f"++run_filter=True ++run_evaluate=True ++run_analyze=True ++seed={current_seed}"
    )"""

            source = source.replace(old_loop_start, new_loop_start)
            
            # Now patch the cycle_designs accumulation
            # Find the parsing block
            old_csv_parse = """    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{current_run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]
    cycle_designs = []

    if valid_csvs:"""
            new_csv_parse = """    inference_dir = BASE_DIR / 'inference' / f'search_binder_local_pipeline_{task_name}_{current_run_name}'
    valid_csvs = [f for f in inference_dir.rglob('*.csv') if 'timing' not in f.name.lower()]
    batch_designs = []

    if valid_csvs:"""
            source = source.replace(old_csv_parse, new_csv_parse)
            
            source = source.replace("cycle_designs.append(design_entry)", "batch_designs.append(design_entry)")
            
            # After writer.writerows(rows_to_write), we add to round_designs and check if we hit 48!
            # The code is:
            old_hotspot_eval = """    # ---------------------------------------------------------
    # 5. Iterative Hotspot Evolution Mechanism (ipSAE-Weighted)
    # ---------------------------------------------------------
    if cycle_designs:"""
            
            new_hotspot_eval = """    if batch_designs:
        round_designs.extend(batch_designs)

    designs_in_current_round += generation_batch_size

    # Check if we have generated enough designs for one evolution round
    if designs_in_current_round < evo_designs_per_loop:
        continue  # Proceed to generate the next batch for this round

    # ---------------------------------------------------------
    # 5. Iterative Hotspot Evolution Mechanism (ipSAE-Weighted)
    # ---------------------------------------------------------
    if round_designs:
        print(f"\\n🧬 Evolution Target {evo_designs_per_loop}/{evo_designs_per_loop} Reached! Selecting highest models to evolve hotspots...")
        cycle_designs = round_designs"""
            source = source.replace(old_hotspot_eval, new_hotspot_eval)
            
            # Now logic to handle end of loop and break condition
            old_end_loop_logic = """    if best_score_so_far >= evo_target_threshold:
        print(f"\\n🎉 SUCCESS! Evolution Target Threshold ({evo_target_threshold}) reached at Cycle {current_iteration} with highest ipSAE score: {best_score_so_far:.4f}")
        break

    if current_iteration < evo_max_iterations:
        print("🧹 Cycle wrap-up complete. Preparing next generation iteration...")
        time.sleep(3)

print(f"\\n✅ Evolutionary Protocol Halted after {current_iteration} cycles.")"""

            new_end_loop_logic = """    if best_score_so_far >= evo_target_threshold:
        print(f"\\n🎉 SUCCESS! Evolution Target Threshold ({evo_target_threshold}) reached at Round {evolution_round} with highest ipSAE score: {best_score_so_far:.4f}")
        break

    print("🧹 Evolution round complete. Preparing next round...")
    designs_in_current_round = 0
    evolution_round += 1
    round_designs = []
    time.sleep(3)

print(f"\\n✅ Evolutionary Protocol Halted after {evolution_round} rounds.")"""
            
            source = source.replace(old_end_loop_logic, new_end_loop_logic)
            
            # Replace occurrences of current_iteration in the CSV parsing / logging
            source = source.replace("d_id = f\"Cycle{current_iteration}_", "d_id = f\"Round{evolution_round}_")
            source = source.replace("row['session_loop'] = current_iteration", "row['session_loop'] = evolution_round")
            source = source.replace("'batch_num': current_iteration", "'batch_num': evolution_round")
            source = source.replace("'loop': current_iteration", "'loop': evolution_round")
            source = source.replace("base_d_id = re.sub(r'^Cycle\\\\d+_', '', d['id'])", "base_d_id = re.sub(r'^Round\\\\d+_', '', d['id'])")

            cell['source'] = source.splitlines(True)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Patching of Section 6 loop complete!")
