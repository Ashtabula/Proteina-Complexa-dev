import json

notebook_path = "coLab/Proteina_Complexa_coLab.ipynb"
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

mod_count = 0
for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        new_source = []
        for line in cell.get("source", []):
            if "++run_evaluate=True" in line and "++evaluate.num_recycles=1" not in line:
                line = line.replace("++run_evaluate=True", "++run_evaluate=True ++evaluate.num_recycles=1 ++evaluate.pad_to_max_length=True ++evaluate.use_msa=False ++evaluate.msa_mode=single_sequence")
                mod_count += 1
            new_source.append(line)
        cell["source"] = new_source

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2)

print(f"Successfully patched {mod_count} occurrences of ++run_evaluate=True with acceleration flags.")
