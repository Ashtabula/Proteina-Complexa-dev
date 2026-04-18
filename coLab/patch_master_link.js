const fs = require('fs');
const path = 'Proteina_Complexa_coLab.ipynb';
const data = JSON.parse(fs.readFileSync(path, 'utf8'));

let cell_16 = data.cells[16];
let source_16 = cell_16.source;

let insert_idx = -1;
for (let i = 0; i < source_16.length; i++) {
    if (source_16[i].includes('master_log_path = final_dir / f"{run_id}_AutoPilot_master_log.csv"')) {
        insert_idx = i;
        break;
    }
}

if (insert_idx !== -1) {
    const update_logic = [
        "\n",
        "# --- UPDATE history_run.csv with Master Log Link ---\n",
        "HISTORY_CSV = BASE_DIR / 'screening_results' / 'history_run.csv'\n",
        "if HISTORY_CSV.exists():\n",
        "    try:\n",
        "        updated_rows = []\n",
        "        with open(HISTORY_CSV, 'r', encoding='utf-8') as f:\n",
        "            reader = csv.reader(f)\n",
        "            header = next(reader, None)\n",
        "            if header: updated_rows.append(header)\n",
        "            for row in reader:\n",
        "                if len(row) > 8 and row[3] == run_id:\n",
        "                    row[8] = f\"[{master_log_path.name}]({master_log_path.relative_to(BASE_DIR)})\"\n",
        "                updated_rows.append(row)\n",
        "        with open(HISTORY_CSV, 'w', newline='', encoding='utf-8') as f:\n",
        "            writer = csv.writer(f)\n",
        "            writer.writerows(updated_rows)\n",
        "        print(\"📊 GLOBAL HISTORY: Successfully linked master_log.csv to Overall_Data_Link.\")\n",
        "    except Exception as e:\n",
        "        print(f\"⚠️ Warning: Failed to update history_run.csv with masterlog link: {e}\")\n",
        "\n"
    ];
    source_16.splice(insert_idx + 1, 0, ...update_logic);
    cell_16.source = source_16;
    fs.writeFileSync(path, JSON.stringify(data, null, 1), 'utf8');
    console.log("Patch applied successfully.");
} else {
    console.log("Could not find insertion point.");
}
