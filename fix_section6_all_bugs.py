#!/usr/bin/env python3
"""
综合修复 Section 6 的所有 Bug（JSON 对象级别操作，避免格式问题）：
Bug 1: f-string 里 evolution_round → evolution_iterate, designs_in_current_round → designs_in_current_iterate
Bug 2a: generation_round += 1 → generation_round = 1  (循环末尾 reset)
Bug 2b: 添加 evolution_iterate += 1 (Iterate 计数器从不递增)
"""

import json

NOTEBOOK_PATH = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

total_fixes = 0

for cell in nb["cells"]:
    if cell.get("cell_type") != "code":
        continue
    src = cell["source"]
    full = "".join(src)
    if "Automated Hotspot Evolution Engine" not in full:
        continue

    print("Found Section 6 cell.")

    new_src = []
    for line in src:
        original = line

        # Bug 1: wrong variable names in progress banner
        if "evolution_round" in line and "evolution_round +=" not in line:
            line = line.replace("{evolution_round}", "{evolution_iterate}")
            print(f"  [FIX Bug1a] evolution_round → evolution_iterate")
            total_fixes += 1

        if "designs_in_current_round" in line:
            line = line.replace("designs_in_current_round", "designs_in_current_iterate")
            print(f"  [FIX Bug1b] designs_in_current_round → designs_in_current_iterate")
            total_fixes += 1

        new_src.append(line)

    # Bug 2a+2b: Fix loop reset block
    # Find: ["    designs_in_current_iterate = 0\n", "    generation_round += 1\n", ...]
    TARGET = [
        "    designs_in_current_iterate = 0\n",
        "    generation_round += 1\n",
        "    iterate_designs = []\n",
        "    time.sleep(3)\n",
    ]
    REPLACEMENT = [
        "    evolution_iterate += 1\n",
        "    generation_round = 1\n",
        "    designs_in_current_iterate = 0\n",
        "    iterate_designs = []\n",
        "    time.sleep(3)\n",
    ]
    for i in range(len(new_src) - len(TARGET) + 1):
        if new_src[i:i+len(TARGET)] == TARGET:
            print(f"  [FIX Bug2a] generation_round += 1 → generation_round = 1")
            print(f"  [FIX Bug2b] evolution_iterate += 1 added")
            new_src = new_src[:i] + REPLACEMENT + new_src[i+len(TARGET):]
            total_fixes += 2
            break

    cell["source"] = new_src
    break

print(f"\nTotal fixes applied: {total_fixes}")

with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("✅ Notebook saved.")

# Verify
nb2 = json.load(open(NOTEBOOK_PATH))
for cell in nb2["cells"]:
    if cell.get("cell_type") != "code": continue
    full = "".join(cell["source"])
    if "Automated Hotspot Evolution Engine" not in full: continue
    
    errors = []
    # Bug 1 check
    import re
    # evolution_round should only appear as "evolution_iterate" now in fstrings
    bad_uses = re.findall(r'\{evolution_round\}', full)
    if bad_uses:
        errors.append(f"Bug1a still present: {bad_uses}")
    bad_uses2 = re.findall(r'designs_in_current_round', full)
    if bad_uses2:
        errors.append(f"Bug1b still present")
    if "generation_round = 1" not in full:
        errors.append("Bug2a: generation_round reset missing")
    if "evolution_iterate += 1" not in full:
        errors.append("Bug2b: evolution_iterate increment missing")
    
    if errors:
        print("\n❌ VERIFICATION FAILED:")
        for e in errors: print(f"  - {e}")
    else:
        print("\n✅ VERIFICATION PASSED: All 3 bugs fixed!")
    break
