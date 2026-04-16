import json
import os

NOTEBOOK_PATH = '/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/Proteina_Complexa_coLab.ipynb'
CELL_19_PATH = '/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/Cell_19_Topological_Seeding_and_Hybridization.py'
CELL_20_PATH = '/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/Cell_20_Deep_Greedy_Convergence_Loop.py'

def read_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def main():
    print(f"Loading notebook: {NOTEBOOK_PATH}")
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    cell19_source = read_file(CELL_19_PATH)
    cell20_source = read_file(CELL_20_PATH)

    markdown_cell = {
        "cell_type": "markdown",
        "metadata": {"id": "section7_markdown"},
        "source": [
            "## Section 7: Topological Seeding and Deep Greedy Convergence\n",
            "This section introduces a two-stage automated hotspot evolution architecture:\n",
            "- **Cell 19: Topological Seeding and Hybridization**: Generates non-overlapping satellite islands and forms hybrid hotspots.\n",
            "- **Cell 20: Deep Greedy Convergence Loop**: Sifts through high priority hybrid islands and iteratively drops weak spots in favor of neo-hotspots until convergence."
        ]
    }

    code_cell_19 = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"id": "cell_19_code"},
        "outputs": [],
        "source": [line + ('\n' if not line.endswith('\n') else '') for line in cell19_source.split('\n')]
    }

    code_cell_20 = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"id": "cell_20_code"},
        "outputs": [],
        "source": [line + ('\n' if not line.endswith('\n') else '') for line in cell20_source.split('\n')]
    }
    
    # We strip trailing newline in the source list for the last element sometimes, but Jupyter handles it.

    nb['cells'].extend([markdown_cell, code_cell_19, code_cell_20])
    
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2)
        
    print("Successfully appended Section 7 to the notebook.")

if __name__ == "__main__":
    main()
