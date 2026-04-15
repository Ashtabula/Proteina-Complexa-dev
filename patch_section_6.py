import json

notebook_path = "coLab/Proteina_Complexa_coLab.ipynb"
with open(notebook_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

# The new cell source
with open("scratch/cell_18_source.py", "r", encoding="utf-8") as f:
    code_source_lines = f.readlines()

new_markdown_cell = {
    "cell_type": "markdown",
    "metadata": {},
    "source": [
        "# Section 6: Automated Hotspot Evolution / Iterative Target Mapped Design\n",
        "**Evolution-Driven High-Throughput Generative Target Optimization:** \n",
        "This section inherits the asynchronous sandbox characteristics from Section 4, but actively mutates your `hotspots_input` iteratively. \n",
        "After every cycle, it spatially calculates target receptor contact distributions within < 4.5A. Invalid hotspots are eliminated, and dynamically discovered highly potent neo-hotspots will overwrite your global settings map, resulting in higher affinity with each generation cycle."
    ]
}

new_code_cell = {
    "cell_type": "code",
    "execution_count": None,
    "metadata": {},
    "outputs": [],
    "source": code_source_lines
}

nb["cells"].append(new_markdown_cell)
nb["cells"].append(new_code_cell)

with open(notebook_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=2)

print("✅ Patched notebook with Section 6!")
