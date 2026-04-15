import json

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

patched = False

for cell in nb['cells']:
    if cell['cell_type'] != 'code':
        continue
    source = "".join(cell['source'])
    if "Cell_18_Automated_Hotspot_Evolution_Loop.py" not in source:
        continue

    # -----------------------------------------------------------------------
    # PATCH 1: Add prev_iterate_state tracker after active_hotspots init
    # -----------------------------------------------------------------------
    old_init = "# Start with base hotspots, converting to a python list of clean strings\nactive_hotspots = [x.strip() for x in base_hotspots.split(',') if x.strip()]"
    new_init = (
        "# Start with base hotspots, converting to a python list of clean strings\n"
        "active_hotspots = [x.strip() for x in base_hotspots.split(',') if x.strip()]\n"
        "# Regression detection: stores snapshot of the previous iterate before evolution\n"
        "prev_iterate_state = None  # {'active_hotspots', 'contact_scores', 'neo_sorted', 'best_score'}"
    )
    if "prev_iterate_state = None" not in source:
        source = source.replace(old_init, new_init)
        print("✅ PATCH 1: prev_iterate_state tracker added.")
    else:
        print("⏭ PATCH 1: Already applied, skipping.")

    # -----------------------------------------------------------------------
    # PATCH 2: Replace the Evolution Selection Algorithm block
    # -----------------------------------------------------------------------
    old_evo = """        # Evolution Selection Algorithm
        
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

    new_evo = """        # Evolution Selection Algorithm

        # --- Regression Detection & Rollback Check ---
        current_iterate_best = cycle_designs[0]['score'] if cycle_designs else 0.0
        use_rollback = (
            prev_iterate_state is not None and
            current_iterate_best < prev_iterate_state['best_score']
        )

        if use_rollback:
            print(f"\\n⚠️  [REGRESSION DETECTED] Iterate best ipSAE ({current_iterate_best:.4f}) < "
                  f"Previous best ({prev_iterate_state['best_score']:.4f})")
            print("   ↩️  Initiating Rollback: reverting to previous hotspot config, "
                  "trying alternative neo-hotspot candidates (rank 3 & 4)...")

            rb_hotspots = prev_iterate_state['active_hotspots']
            rb_scores   = prev_iterate_state['contact_scores']
            rb_neo      = prev_iterate_state['neo_sorted']

            # Score previous hotspots using previous iterate's contact map
            rb_cur_scores  = {r: rb_scores.get(r, 0.0) for r in rb_hotspots}
            rb_sorted_list = sorted(rb_cur_scores.keys(), key=lambda k: rb_cur_scores[k], reverse=True)

            drop_count        = min(evo_update_count, max(0, len(rb_hotspots) - 2))
            retained_hotspots = rb_sorted_list[:-drop_count] if drop_count > 0 else list(rb_sorted_list)
            eliminated        = rb_sorted_list[-drop_count:]  if drop_count > 0 else []

            # Use alternative neo-hotspots: skip the first drop_count (already tried),
            # take the next drop_count (i.e. rank 3 & 4 when drop_count=2)
            alt_start = drop_count
            top_neo   = rb_neo[alt_start : alt_start + drop_count]

            print(f"   [ROLLBACK] Base config : {','.join(rb_hotspots)}")
            if top_neo:
                print(f"   [ROLLBACK] Alt Neo-Hotspots (rank {alt_start+1}~{alt_start+drop_count}): {','.join(top_neo)}")
            else:
                print("   [ROLLBACK] No alternative neo-hotspot candidates available.")

            # Score reference for secondary cap uses previous iterate scores
            _score_ref = rb_scores

        else:
            # --- Normal Evolution Path ---

            # Pre-compute neo_hotspots list (needed for state save AND for top_neo selection)
            neo_hotspots = {k: v for k, v in contact_scores.items() if k not in active_hotspots}
            sorted_neo   = sorted(neo_hotspots.keys(), key=lambda k: neo_hotspots[k], reverse=True)

            # Save current state BEFORE evolving — for potential rollback next iterate
            prev_iterate_state = {
                'active_hotspots': list(active_hotspots),
                'contact_scores':  dict(contact_scores),
                'neo_sorted':      sorted_neo,
                'best_score':      current_iterate_best,
            }
            print(f"   📸 Snapshot saved (best={current_iterate_best:.4f}) for regression guard.")

            # 1. Score and rank original active hotspots
            current_scores = {r: contact_scores.get(r, 0.0) for r in active_hotspots}
            sorted_current = sorted(current_scores.keys(), key=lambda k: current_scores[k], reverse=True)

            # 2. Drop the lowest-scoring hotspots
            drop_count        = min(evo_update_count, max(0, len(active_hotspots) - 2))
            retained_hotspots = sorted_current[:-drop_count] if drop_count > 0 else list(sorted_current)
            eliminated        = sorted_current[-drop_count:]  if drop_count > 0 else []

            # 3. Add the top neo-hotspots (rank 1 & 2)
            top_neo = sorted_neo[:drop_count]

            # Score reference for secondary cap uses current iterate scores
            _score_ref = contact_scores

        # 4. Combine and apply max hotspot cap
        final_retained = list(retained_hotspots) + list(top_neo)
        if len(final_retained) > evo_max_hotspots:
            # Secondary check using the relevant iterate's scores
            all_scores = {r: _score_ref.get(r, 0.0) for r in final_retained}
            final_retained = sorted(final_retained, key=lambda k: all_scores[k], reverse=True)[:evo_max_hotspots]"""

    if "use_rollback" not in source:
        if old_evo in source:
            source = source.replace(old_evo, new_evo)
            print("✅ PATCH 2: Rollback evolution logic injected.")
        else:
            print("❌ PATCH 2: Could not find evolution algorithm target string. Aborting.")
    else:
        print("⏭ PATCH 2: Already applied, skipping.")

    cell['source'] = source.splitlines(True)
    patched = True
    break

if not patched:
    print("❌ Cell_18 not found in notebook.")
else:
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2)
    print("\n✅ Notebook saved successfully.")
