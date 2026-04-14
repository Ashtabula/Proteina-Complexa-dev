import json

notebook_path = "coLab/Latest_Proteina_Complexa_coLab.ipynb"
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        source = "".join(cell["source"])
        if "❌ Critical Warning: Underlying generation engine crashed" in source:
            # We found the AutoPilot loop cell!
            new_source = []
            for line in cell["source"]:
                new_source.append(line)
                if "print(f\"❌ Critical Warning: Underlying generation engine crashed (Error Code {ret_code})!\")" in line:
                    indent = line[:line.find("print")]
                    new_source.append(indent + "gc.collect()\n")
                    new_source.append(indent + "if torch.cuda.is_available():\n")
                    new_source.append(indent + "    torch.cuda.empty_cache()\n")
                    new_source.append(indent + "    torch.cuda.ipc_collect()\n")
                    new_source.append(indent + "print(\"🧹 Crash Recovery: Buffer and IPC memory forcibly cleared.\")\n")
            
            cell["source"] = new_source
            print("Successfully patched the AutoPilot loop memory leak bug in the notebook.")

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2)

