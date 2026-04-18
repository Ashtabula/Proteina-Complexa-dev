const fs = require('fs');

const path = 'Proteina_Complexa_coLab.ipynb';
const data = JSON.parse(fs.readFileSync(path, 'utf8'));

// Modify Cell 3 (Section 0)
let cell_3 = data.cells[3];
let source_3 = cell_3.source;

// 1. Insert UI element at the top
let insert_idx_ui = -1;
for (let i = 0; i < source_3.length; i++) {
    if (source_3[i].includes('# @markdown ### 📁 Target File Selection')) {
        insert_idx_ui = i;
        break;
    }
}

if (insert_idx_ui !== -1) {
    const ui_lines = [
        "# ==========================================\n",
        "# --- Time Machine / Global Resume ---\n",
        "# ==========================================\n",
        "# @markdown ---\n",
        "# @markdown ---\n",
        "# @markdown ### 🔮 Time Machine / Global Resume\n",
        "# @markdown Fill in a Specific Run ID (e.g. `AR_LBD_20260418_043148`) to travel back and resume from it. Leave blank for normal operation.\n",
        "specific_resume_run_id = \"\" #@param {type:\"string\"}\n",
        "\n"
    ];
    source_3.splice(insert_idx_ui, 0, ...ui_lines);
}

// 2. Add to write_settings_to_disk
let insert_idx_dict = -1;
for (let i = 0; i < source_3.length; i++) {
    if (source_3[i].includes('"enable_cache_backup": enable_cache_backup,')) {
        insert_idx_dict = i;
        break;
    }
}

if (insert_idx_dict !== -1) {
    source_3.splice(insert_idx_dict, 0, '        "specific_resume_run_id": specific_resume_run_id,\n');
}

// Modify Cell 10 (Section 2 Backend Router)
let cell_10 = data.cells[10];
let source_10 = cell_10.source;

let start_idx = -1;
for (let i = 0; i < source_10.length; i++) {
    if (source_10[i].includes('# 2. Run ID Resolution & Smart Directory Targeting')) {
        start_idx = i;
        break;
    }
}

let end_idx = -1;
for (let i = 0; i < source_10.length; i++) {
    if (source_10[i].includes('# 3. History Tracker')) {
        end_idx = i;
        break;
    }
}

if (start_idx !== -1 && end_idx !== -1) {
    const new_routing_logic = [
        "# 2. Run ID Resolution & Smart Directory Targeting\n",
        "# ---------------------------------------------------------\n",
        "last_run_file = BASE_DIR / 'screening_results' / 'last_runs.txt'\n",
        "active_run_id = None\n",
        "active_final_dir = None\n",
        "is_resuming = False\n",
        "last_recorded_time = \"N/A\"\n",
        "\n",
        "specific_resume_run_id = cfg.get(\"specific_resume_run_id\", \"\").strip()\n",
        "force_restart_task = cfg.get(\"force_restart_task\", False)\n",
        "\n",
        "if specific_resume_run_id:\n",
        "    # --- Time Machine Mode ---\n",
        "    try:\n",
        "        hist_timestamp = specific_resume_run_id.split('_')[-2] + \"_\" + specific_resume_run_id.split('_')[-1]\n",
        "    except:\n",
        "        hist_timestamp = specific_resume_run_id.replace(task_name + \"_\", \"\")\n",
        "    \n",
        "    candidate_dir = BASE_DIR / 'screening_results' / task_name / f\"final_{hist_timestamp}\"\n",
        "    hist_setting_path = candidate_dir / 'internal_settings.json'\n",
        "    \n",
        "    if hist_setting_path.exists():\n",
        "        with open(hist_setting_path, 'r') as hf:\n",
        "            hist_cfg = json.load(hf)\n",
        "        \n",
        "        # OVERWRITE CURRENT CONFIG with history config!\n",
        "        cfg.update(hist_cfg)\n",
        "        task_name = cfg.get('task_name', task_name)  # update if needed\n",
        "        \n",
        "        active_run_id = specific_resume_run_id\n",
        "        active_final_dir = candidate_dir\n",
        "        is_resuming = True\n",
        "        print(f\"\\n🚀 Time Machine Active: Resuming from specific historical session [{specific_resume_run_id}]\")\n",
        "        print(f\"✅ All physical parameters reverted to historical state.\")\n",
        "        \n",
        "        # Force rewrite last_runs.txt\n",
        "        last_run_file.parent.mkdir(parents=True, exist_ok=True)\n",
        "        with open(last_run_file, 'a', encoding='utf-8') as f:\n",
        "            f.write(f\"Section2_TargetPreprocess_TimeMachine | Run_ID: {active_run_id} | Dir: {active_final_dir.name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\")\n",
        "    else:\n",
        "        print(f\"❌ Time Machine Error: Historical folder not found at {candidate_dir.relative_to(BASE_DIR)}. Aborting.\")\n",
        "        sys.exit(1)\n",
        "\n",
        "elif force_restart_task:\n",
        "    print(\"⚡ Force Restart is ON. Bypassing history checks and generating new session.\")\n",
        "    is_resuming = False\n",
        "else:\n",
        "    # --- Normal Resume Mode ---\n",
        "    if last_run_file.exists():\n",
        "        with open(last_run_file, 'r', encoding='utf-8') as f:\n",
        "            lines = f.readlines()\n",
        "            pattern = rf\"Section2_TargetPreprocess \| Run_ID: ({re.escape(task_name)}_\\d+_\\d+)\"\n",
        "            for line in reversed(lines):\n",
        "                match = re.search(pattern, line)\n",
        "                if match:\n",
        "                    candidate_run_id = match.group(1)\n",
        "                    hist_timestamp = candidate_run_id.split('_')[-2] + \"_\" + candidate_run_id.split('_')[-1] if len(candidate_run_id.split('_')) >= 3 else candidate_run_id.split('_')[-1]\n",
        "                    candidate_dir = BASE_DIR / 'screening_results' / task_name / f\"final_{hist_timestamp}\"\n",
        "                    hist_setting_path = candidate_dir / 'internal_settings.json'\n",
        "                    \n",
        "                    time_match = re.search(r\"Date:\\s*(.*?)(?:$|\\|)\", line)\n",
        "                    if time_match: last_recorded_time = time_match.group(1).strip()\n",
        "\n",
        "                    if hist_setting_path.exists():\n",
        "                        with open(hist_setting_path, 'r') as hf:\n",
        "                            hist_cfg = json.load(hf)\n",
        "                        print(f\"🔄 ARCHIVE FOUND: Validating historical session [{candidate_run_id}]...\")\n",
        "                        \n",
        "                        mismatches = []\n",
        "                        for key in CORE_PHYSICAL_KEYS:\n",
        "                            val_curr = str(cfg.get(key, '')).strip()\n",
        "                            val_hist = str(hist_cfg.get(key, '')).strip()\n",
        "                            if val_curr != val_hist:\n",
        "                                mismatches.append(f\"{key}: Current='{val_curr}' | Archive='{val_hist}'\")\n",
        "\n",
        "                        if mismatches:\n",
        "                            print(f\"⚠️ Notice: Core physical parameters changed. Generating a NEW session instead of resuming.\")\n",
        "                            for m in mismatches: print(f\"   -> {m}\")\n",
        "                            break\n",
        "\n",
        "                        active_run_id = candidate_run_id\n",
        "                        active_final_dir = candidate_dir\n",
        "                        is_resuming = True\n",
        "                        print(f\"✅ VALIDATION PASSED: Re-activating existing workspace for in-place continuation.\")\n",
        "                    break\n",
        "\n",
        "# If not resuming, generate new\n",
        "if not is_resuming:\n",
        "    SESSION_TIMESTAMP = datetime.datetime.now().strftime(\"%Y%m%d_%H%M%S\")\n",
        "    active_run_id = f\"{task_name}_{SESSION_TIMESTAMP}\"\n",
        "    active_final_dir = BASE_DIR / 'screening_results' / task_name / f\"final_{SESSION_TIMESTAMP}\"\n",
        "    active_final_dir.mkdir(parents=True, exist_ok=True)\n",
        "\n",
        "    last_run_file.parent.mkdir(parents=True, exist_ok=True)\n",
        "    with open(last_run_file, 'a', encoding='utf-8') as f:\n",
        "        f.write(f\"Section2_TargetPreprocess | Run_ID: {active_run_id} | Dir: {active_final_dir.name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\")\n",
        "    print(f\"🆕 NEW SESSION ACTIVE: Global Run ID registered: {active_run_id}\")\n",
        "\n",
        "# ---------------------------------------------------------\n"
    ];

    source_10.splice(start_idx, end_idx - start_idx, ...new_routing_logic);
}

fs.writeFileSync(path, JSON.stringify(data, null, 1), 'utf8');
console.log("Patch applied successfully.");
