#!/usr/bin/env python3
"""
修复 Section 6 中的两个 Bug：
Bug 1: f-string 里用了未定义变量 evolution_round / designs_in_current_round
       → 应为 evolution_iterate / designs_in_current_iterate
Bug 2: while 循环末尾有多余的 generation_round += 1（循环顶部已经 +1 过了）
       → 删除末尾多余的 generation_round += 1
"""

import json

NOTEBOOK_PATH = "/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev/coLab/Proteina_Complexa_coLab.ipynb"

with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

fixes = [
    # Bug 1a: wrong variable names in progress print
    (
        '    print(f"\\n=======================================================")\\n',
        '    print(f"\\n=======================================================")\\n',
        None  # no-op, just to mark where the next fix is
    ),
]

# We need to do string-level replacement in the raw JSON string
# Serialize → fix → deserialize

raw = json.dumps(nb, ensure_ascii=False)

# Bug 1: wrong variable names in the progress banner print
old1 = (
    r'Evolution Generation [Round {evolution_round}]: '
    r'{designs_in_current_round}/{evo_designs_per_loop} designs Commencing...'
)
new1 = (
    r'Evolution Generation [Iterate {evolution_iterate} - Round {generation_round}]: '
    r'{designs_in_current_iterate}/{evo_designs_per_loop} designs Commencing...'
)

if old1 in raw:
    raw = raw.replace(old1, new1, 1)
    print(f"[FIXED] Bug 1: progress banner variable names corrected")
else:
    print(f"[WARN] Bug 1 pattern not found — checking JSON-escaped version...")
    # Try JSON-escaped version
    old1_esc = (
        'Evolution Generation [Round {evolution_round}]: '
        '{designs_in_current_round}/{evo_designs_per_loop} designs Commencing...'
    )
    new1_esc = (
        'Evolution Generation [Iterate {evolution_iterate} - Round {generation_round}]: '
        '{designs_in_current_iterate}/{evo_designs_per_loop} designs Commencing...'
    )
    if old1_esc in raw:
        raw = raw.replace(old1_esc, new1_esc, 1)
        print(f"[FIXED] Bug 1 (escaped): progress banner variable names corrected")
    else:
        print(f"[ERROR] Bug 1 pattern not found at all!")

# Bug 2: duplicate generation_round += 1 at end of loop
# The loop end has: "generation_round += 1\n",  "iterate_designs = []\n",  "time.sleep(3)\n"
# We need to remove the extra generation_round += 1 there.
# The correct location: after "designs_in_current_iterate = 0" at loop reset
old2 = (
    '"    designs_in_current_iterate = 0\\\\n",'
    ' "    generation_round += 1\\\\n",'
    ' "    iterate_designs = []\\\\n"'
)
new2 = (
    '"    designs_in_current_iterate = 0\\\\n",'
    ' "    iterate_designs = []\\\\n"'
)

if old2 in raw:
    raw = raw.replace(old2, new2, 1)
    print(f"[FIXED] Bug 2: removed duplicate generation_round += 1 at loop end")
else:
    # Try without spaces
    old2b = '"    designs_in_current_iterate = 0\\\\n","    generation_round += 1\\\\n","    iterate_designs = []\\\\n"'
    new2b = '"    designs_in_current_iterate = 0\\\\n","    iterate_designs = []\\\\n"'
    if old2b in raw:
        raw = raw.replace(old2b, new2b, 1)
        print(f"[FIXED] Bug 2 (compact): removed duplicate generation_round += 1 at loop end")
    else:
        # More flexible: find the section in raw
        # The pattern in the JSON will be:
        # "    designs_in_current_iterate = 0\n",\n    "    generation_round += 1\n",\n    "    iterate_designs = []\n",
        import re
        pattern = r'("    designs_in_current_iterate = 0\\\\n",\s*\n\s*)"    generation_round \+= 1\\\\n",\s*\n\s*("    iterate_designs = \[\]\\\\n")'
        replacement = r'\1\2'
        new_raw, count = re.subn(pattern, replacement, raw, count=1)
        if count:
            raw = new_raw
            print(f"[FIXED] Bug 2 (regex): removed duplicate generation_round += 1 at loop end")
        else:
            print(f"[WARN] Bug 2 pattern not found — may already be fixed or needs manual check")

nb_fixed = json.loads(raw)
with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
    json.dump(nb_fixed, f, ensure_ascii=False, indent=1)

print("\n✅ 修复完成，notebook 已保存。")
