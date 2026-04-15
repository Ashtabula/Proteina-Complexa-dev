#!/usr/bin/env python3
"""
直接 JSON 对象级别修复 Section 6 source 数组里的计数器 Bug，
不依赖原始字符串匹配，避免格式问题。
"""

import json

NOTEBOOK_PATH = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

TARGET_STRINGS = [
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

fixed = False
for cell in nb["cells"]:
    if cell.get("cell_type") != "code":
        continue
    src = cell["source"]
    # Find the target sequence in this cell's source lines
    for i in range(len(src) - len(TARGET_STRINGS) + 1):
        if src[i:i+len(TARGET_STRINGS)] == TARGET_STRINGS:
            print(f"[FOUND] Target sequence at source line {i}")
            print(f"  Context before: {repr(src[max(0,i-2):i])}")
            cell["source"] = src[:i] + REPLACEMENT + src[i+len(TARGET_STRINGS):]
            fixed = True
            print(f"[FIXED] Replaced {len(TARGET_STRINGS)} lines with {len(REPLACEMENT)} lines")
            break
    if fixed:
        break

if not fixed:
    print("[ERROR] Target sequence not found in any code cell!")
    # Debug: search for similar lines
    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        for i, line in enumerate(cell["source"]):
            if "generation_round += 1" in line:
                src = cell["source"]
                print(f"Found 'generation_round += 1' at line {i}:")
                print(repr(src[max(0,i-3):i+4]))
else:
    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("\n✅ Notebook 已保存。")
