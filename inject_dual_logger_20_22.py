import json
import os

notebook_path = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

insert_lines = [
    "\n",
    "# ----------------------------------------------------\n",
    "# 📡 内部双向流同步探针 (Dual-Channel Logger)\n",
    "# ----------------------------------------------------\n",
    "LIVE_LOG_FILE = final_dir / f\"Live_Sync_{run_id}.log\"\n",
    "\n",
    "class DualLogger:\n",
    "    def __init__(self, filepath):\n",
    "        self.terminal = sys.stdout\n",
    "        # buffering=1 启用行级强缓冲，确保 minimum invasive 的实时性\n",
    "        self.log = open(filepath, \"a\", buffering=1, encoding=\"utf-8\") \n",
    "\n",
    "    def write(self, message):\n",
    "        self.terminal.write(message)\n",
    "        self.log.write(message)\n",
    "        self.flush()\n",
    "\n",
    "    def flush(self):\n",
    "        self.terminal.flush()\n",
    "        self.log.flush()\n",
    "\n",
    "# 全局接管标准输出与标准错误\n",
    "sys.stdout = DualLogger(LIVE_LOG_FILE)\n",
    "sys.stderr = sys.stdout\n",
    "print(f\"📡 笔记本模式双向同步日志流已接管: {LIVE_LOG_FILE}\")\n",
    "# ----------------------------------------------------\n",
    "\n"
]

for cell in nb.get("cells", []):
    if cell.get("cell_type") == "code":
        source = cell.get("source", [])
        
        # Inject into Cell 20b
        if any("Cell_20b_Core_Hotspot_Screening.py" in line for line in source):
            # Check if DualLogger is already there
            if not any("DualLogger" in line for line in source):
                insert_idx = -1
                for i, line in enumerate(source):
                    if 'resolve_workspace' in line and 'specific_resume_run_id_core' in line:
                        insert_idx = i + 1
                        break
                if insert_idx != -1:
                    new_source = source[:insert_idx] + insert_lines + source[insert_idx:]
                    cell["source"] = new_source
                    print("Injected DualLogger into Cell 20b.")

        # Inject into Cell 22
        if any("Cell_22_Island_Constrained_Single_Point_Scanning.py" in line for line in source):
            # Check if DualLogger is already there
            if not any("DualLogger" in line for line in source):
                insert_idx = -1
                for i, line in enumerate(source):
                    if 'resolve_workspace' in line and 'specific_resume_run_id_edge' in line:
                        insert_idx = i + 1
                        break
                if insert_idx != -1:
                    new_source = source[:insert_idx] + insert_lines + source[insert_idx:]
                    cell["source"] = new_source
                    print("Injected DualLogger into Cell 22.")

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2, ensure_ascii=False)
