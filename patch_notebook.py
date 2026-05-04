import json
import os

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"
monitor_script = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/Cell_24_Live_Monitor.py"

with open(monitor_script, "r", encoding="utf-8") as f:
    monitor_code = f.readlines()

with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for cell in nb.get("cells", []):
    if cell.get("cell_type") == "code":
        source = cell.get("source", [])
        if any("Web Monitor for VS Code Process" in line for line in source):
            # Keep the @title line, replace the rest
            new_source = ["# @title 👁️‍🗨️ Web Monitor for VS Code Process\n"] + monitor_code
            cell["source"] = new_source
            break

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2, ensure_ascii=False)

print("Notebook updated successfully.")
