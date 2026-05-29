import json
from pathlib import Path


NOTEBOOKS = [
    Path("coLab/Proteina_Complexa_coLab.ipynb"),
    Path("Proteina_Complexa_coLab.ipynb"),
]


def source_to_text(cell):
    return "".join(cell.get("source", []))


def text_to_source(text):
    return text.splitlines(keepends=True)


def patch_section_0(src):
    src = src.replace(
        "# UPDATE: Removed global force_restart. Added section-specific resume/restart toggles (Section 5, 6, 7) directly within their respective configuration blocks for granular session management.",
        "# UPDATE: Global force_restart creates a new run_id; stage-specific restart toggles only clear their own stage data.",
    )

    src = src.replace(
        'specific_resume_run_id = "" #@param {type:"string"}\n'
        "# @markdown Force start a brand new run? (Bypass history resume)\n"
        'force_restart_task = False #@param {type:"boolean"}',
        'specific_resume_run_id = "" #@param {type:"string"}\n'
        "\n"
        "# @markdown ### \U0001f504 Global Execution Restart\n"
        "# @markdown Force a complete restart of the entire pipeline? (Ignores all existing history and generates a new Run ID)\n"
        'force_restart = False #@param {type:"boolean"}',
    )

    src = src.replace(
        "# @markdown Force restart Section 7 completely? (Ignore existing history)\n"
        'force_restart_section_7 = False #@param {type:"boolean"}\n',
        "",
    )
    src = src.replace(
        '        "force_restart_task": force_restart_task,\n',
        '        "force_restart": force_restart,\n',
    )
    src = src.replace(
        '        "force_restart_section_7": force_restart_section_7,\n',
        "",
    )
    src = src.replace(
        '    print(f"Restart Sec 7: {\'YES\' if force_restart_section_7 else \'NO\'}")',
        '    print(f"Global Restart: {\'YES\' if force_restart else \'NO (Resume)\'}")',
    )
    src = src.replace(
        '    print(f"Restart Sec 7 (Evolution): {\'YES\' if force_restart_section_7 else \'NO (Resume)\'}")',
        '    print(f"Global Restart: {\'YES\' if force_restart else \'NO (Resume)\'}")',
    )
    return src


def patch_section_2(src):
    src = src.replace(
        'force_restart_task = cfg.get("force_restart_task", False)',
        'force_restart = cfg.get("force_restart", False)',
    )
    src = src.replace(
        'force_restart = cfg.get("force_restart", cfg.get("force_restart_task", False))',
        'force_restart = cfg.get("force_restart", False)',
    )
    src = src.replace("elif force_restart_task:", "elif force_restart:")
    return src


def patch_topological_seed_cell(src):
    src = src.replace(
        "# - Section 7 Smart Restart: Read force_restart_section_7 to wipe old geometric manifests if triggered.",
        "# - Uses the current run_id workspace; global force_restart is handled upstream in Section 2.",
    )
    src = src.replace(
        "# --- SMART RESTART LOGIC FOR SECTION 6 ---\n"
        "force_restart_section_7 = bool(root_cfg.get('force_restart_section_7', False))\n"
        "if force_restart_section_7:\n"
        '    print("\\n\U0001f5d1\ufe0f [COMMAND] Force Restart Section 6 is ENABLED.")\n'
        "    if geometric_manifest_path.exists():\n"
        "        geometric_manifest_path.unlink()\n"
        '        print("\U0001f9f9 Wiped old Geometric_Islands_Manifest.json to generate fresh geometric seeds.")\n'
        "else:\n"
        '    print(f"\\n\u23ed\ufe0f [RESUME] Smart Resume active. Regenerating topological surface arrays in memory...")',
        "# --- CURRENT RUN_ID WORKSPACE ---\n"
        'print("\\n[CURRENT RUN] Regenerating topological surface arrays in memory for the active run_id.")',
    )
    src = src.replace(
        "# --- SMART RESTART LOGIC FOR SECTION 6 ---\n"
        "force_restart = bool(root_cfg.get('force_restart_section_7', False))\n"
        "if force_restart:\n"
        '    print("\\n\U0001f5d1\ufe0f [COMMAND] Force Restart Section 6 is ENABLED.")\n'
        "    if geometric_manifest_path.exists():\n"
        "        geometric_manifest_path.unlink()\n"
        '        print("\U0001f9f9 Wiped old Geometric_Islands_Manifest.json to generate fresh geometric seeds.")\n'
        "else:\n"
        '    print(f"\\n\u23ed\ufe0f [RESUME] Smart Resume active. Regenerating topological surface arrays in memory...")',
        "# --- CURRENT RUN_ID WORKSPACE ---\n"
        'print("\\n[CURRENT RUN] Regenerating topological surface arrays in memory for the active run_id.")',
    )
    return src


def patch_core_hotspot_cell(src):
    if src.startswith("#Cell_20_Core Hotspot") and "force_restart_core_islands" not in src:
        src = src.replace(
            "#Cell_20_Core Hotspot Randomized Screening (Generation & Master Table Export)\n\n",
            "#Cell_20_Core Hotspot Randomized Screening (Generation & Master Table Export)\n\n"
            "# --- User Configuration ---\n"
            'force_restart_core_islands = False #@param {type:"boolean"}\n\n',
        )

    src = src.replace(
        "force_restart_section_7 = bool(root_cfg.get('force_restart_section_7', False))\n\n",
        "",
    )
    src = src.replace(
        "if not force_restart_section_7 and master_csv_path.exists():",
        "if not force_restart_core_islands and master_csv_path.exists():",
    )
    src = src.replace(
        "`force_restart_section_7` is set to False.",
        "`force_restart_core_islands` is set to False.",
    )
    src = src.replace(
        "'force_restart_section_7' is True.",
        "'force_restart_core_islands' is True.",
    )

    if "force_restart_core_islands" in src and "Core Hotspot data" not in src:
        src = src.replace(
            '    res_master_csv = final_dir / "Core_Residue_PAE_Master.csv"\n\n'
            "    core_res_pae_tracker = {}",
            '    res_master_csv = final_dir / "Core_Residue_PAE_Master.csv"\n\n'
            "    if force_restart_core_islands:\n"
            '        print("\u26a0\ufe0f [FORCE RESTART] Overwriting previous Core Hotspot data...")\n'
            "        for stale_path in [master_csv_path, path_csv_path, res_master_csv]:\n"
            "            if stale_path.exists(): stale_path.unlink()\n\n"
            "    core_res_pae_tracker = {}",
        )
    return src


def patch_stage_restart_cells(src):
    src = src.replace(
        "force_restart_section_7 = bool(root_cfg.get('force_restart_section_7', False))\n",
        "",
    )
    src = src.replace(
        "should_reset = force_restart_section_7 or force_restart_edge_islands",
        "should_reset = force_restart_edge_islands",
    )
    src = src.replace(
        "should_reset = force_restart_section_7 or force_restart_evo",
        "should_reset = force_restart_evo",
    )
    src = src.replace(
        "should_clear_evo = force_restart_section_7 or force_restart_evo",
        "should_clear_evo = force_restart_evo",
    )
    src = src.replace(
        "#force_restart_section_7 = False #@param {type:\"boolean\"}\n",
        "",
    )
    return src


def patch_plddt_thresholds(src):
    replacements = {
        "pLDDT >= 0.40": "pLDDT > 0.70",
        "pLDDT ≥ 0.40": "pLDDT > 0.70",
        "pLDDT≥0.40": "pLDDT>0.70",
        "pLDDT < 0.40": "pLDDT <= 0.70",
        "pLDDT {champ_plddt:.2f} < 0.40": "pLDDT {champ_plddt:.2f} <= 0.70",
        "df_scores['pLDDT'] >= 0.40": "df_scores['pLDDT'] > 0.70",
        "float(d['pLDDT']) >= 0.40": "float(d['pLDDT']) > 0.70",
        "df_upstream['pLDDT'] >= 0.40": "df_upstream['pLDDT'] > 0.70",
        "c_data['pLDDT'] >= 0.40": "c_data['pLDDT'] > 0.70",
        "float(c.get('pLDDT', 0)) >= 0.40": "float(c.get('pLDDT', 0)) > 0.70",
        "if pld < 0.40:": "if pld <= 0.70:",
        "elif pld < 0.55:": "elif pld < 0.85:",
        "if champ_plddt < 0.40:": "if champ_plddt <= 0.70:",
        "champ_plddt < 0.40": "champ_plddt <= 0.70",
        "plddt_threshold: float = 0.40": "plddt_threshold: float = 0.70",
        "pLDDT >= {plddt_threshold}": "pLDDT > {plddt_threshold}",
        "df_clean['pLDDT'] >= plddt_threshold": "df_clean['pLDDT'] > plddt_threshold",
        "Physical Threshold (0.4)": "Physical Threshold (0.7)",
    }
    for old, new in replacements.items():
        src = src.replace(old, new)
    return src


def scrub_stale_output_text(value):
    if isinstance(value, str):
        return (
            value.replace("force_restart_section_7", "stage-specific force_restart")
            .replace("Restart Sec 7 (Evolution)", "Global Restart")
            .replace("Restart Sec 7", "Global Restart")
        )
    if isinstance(value, list):
        return [scrub_stale_output_text(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_stale_output_text(item) for key, item in value.items()}
    return value


def patch_notebook(path):
    with path.open("r", encoding="utf-8") as f:
        nb = json.load(f)

    for cell in nb.get("cells", []):
        src = source_to_text(cell)
        if not src:
            continue

        src = src.replace("for line in reversed(lines):", "for line in lines:")

        if "Section_0_Global_Configuration_Dashboard.py" in src:
            src = patch_section_0(src)
        if "Cell_4b_PDB_Processing_and_YAML_Configuration_Generation.py" in src:
            src = patch_section_2(src)
        if "Cell_19_Topological_Seeding_and_Visualization.py" in src:
            src = patch_topological_seed_cell(src)
        if "Cell_20b_Core_Hotspot_Screening.py" in src or src.startswith("#Cell_20_Core Hotspot"):
            src = patch_core_hotspot_cell(src)
        if any(
            token in src
            for token in [
                "force_restart_section_7",
                "force_restart_edge_islands",
                "force_restart_evo",
            ]
        ):
            src = patch_stage_restart_cells(src)
        if "pLDDT" in src or "plddt_threshold" in src:
            src = patch_plddt_thresholds(src)

        cell["source"] = text_to_source(src)
        if "outputs" in cell:
            cell["outputs"] = scrub_stale_output_text(cell["outputs"])

    escape_non_ascii = len(path.parts) == 1
    with path.open("w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=escape_non_ascii)
        f.write("\n")


for notebook_path in NOTEBOOKS:
    patch_notebook(notebook_path)
    print(f"Patched {notebook_path}")
