import os, re
from pathlib import Path

BASE_DIR = Path('/Users/ziqizhu/Code/Protein/Proteina-Complexa-dev')

def insert_sync_log(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Define the sync_log injection right after final_dir is defined
    sync_log_def = """
# --- Bidirectional Live Sync (Dual-Channel Logger) ---
LIVE_LOG_FILE = final_dir / f"Live_Sync_{run_id}.log"

def sync_log(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LIVE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\\n")
"""

    if "LIVE_LOG_FILE =" not in content:
        # Find where final_dir is defined
        if "final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name" in content:
            content = content.replace(
                "final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name",
                "final_dir = BASE_DIR / 'screening_results' / task_name / target_dir_name\n" + sync_log_def
            )

    return content

# --- Patch Cell 20 ---
f20 = BASE_DIR / "Cell_20_Deep_Greedy_Convergence_Loop.py"
if f20.exists():
    c20 = insert_sync_log(f20)
    c20 = c20.replace(
        'print(f"\\n🔄 [{island_name} - Iteration {iteration}] Active Hotspots: {\',\'.join(active_hotspots)}")',
        'msg = f"🔄 [{island_name} - Iteration {iteration}] Active Hotspots: {\',\'.join(active_hotspots)}"\n        print(f"\\n{msg}")\n        sync_log(msg)'
    )
    c20 = c20.replace(
        'print(f"📊 {island_name} Iter {iteration} Max ipSAE: {current_max_score:.4f}")',
        'msg = f"📊 {island_name} Iter {iteration} Max ipSAE: {current_max_score:.4f}"\n        print(msg)\n        sync_log(msg)'
    )
    c20 = c20.replace(
        'print(f"📉 Notice: Performance degraded from {highest_ipsae_state:.4f} to {current_max_score:.4f}.")',
        'msg = f"📉 Notice: Performance degraded from {highest_ipsae_state:.4f} to {current_max_score:.4f}."\n            print(msg)\n            sync_log(msg)'
    )
    c20 = c20.replace(
        'print(f"🛑 Rollback recovery failed. {island_name} is marked as CONVERGED (Local Minima).")',
        'msg = f"🛑 Rollback recovery failed. {island_name} is marked as CONVERGED (Local Minima)."\n                print(msg)\n                sync_log(msg)'
    )
    c20 = c20.replace(
        'print("🔙 Triggering Rollback...")',
        'msg = "🔙 Triggering Rollback..."\n            print(msg)\n            sync_log(msg)'
    )
    c20 = c20.replace(
        'print(f"➕ Absorbed highest contributing candidates: {\',\'.join(added)}")',
        'msg = f"➕ Absorbed highest contributing candidates: {\',\'.join(added)}"\n        print(msg)\n        sync_log(msg)'
    )
    with open(f20, 'w') as f: f.write(c20)

# --- Patch Cell 21 ---
f21 = BASE_DIR / "Cell_21_Spatial_Edge_Beam_Search.py"
if f21.exists():
    c21 = insert_sync_log(f21)
    c21 = c21.replace(
        'print(f"\\n📍 === Initiating Spatial Edge Expansion for Anchor {anchor_id} ===")',
        'msg = f"📍 === Initiating Spatial Edge Expansion for Anchor {anchor_id} ==="\n    print(f"\\n{msg}")\n    sync_log(msg)'
    )
    c21 = c21.replace(
        'print(f"   [Iter {iteration} | Branch {b_idx}] Max ipSAE Score: {current_max_score:.4f}")',
        'msg = f"   [Iter {iteration} | Branch {b_idx}] Max ipSAE Score: {current_max_score:.4f}"\n            print(msg)\n            sync_log(msg)'
    )
    c21 = c21.replace(
        'print(f"   🧬 Diversity-Preserving Phase: Grouped into {len(clusters)} unique binding conformations.")',
        'msg = f"   🧬 Diversity-Preserving Phase: Grouped into {len(clusters)} unique binding conformations."\n        print(msg)\n        sync_log(msg)'
    )
    c21 = c21.replace(
        'print(f"   📉 Degradation across all diverse branches. Stagnation Count: {stagnation_counter}/3")',
        'msg = f"   📉 Degradation across all diverse branches. Stagnation Count: {stagnation_counter}/3"\n            print(msg)\n            sync_log(msg)'
    )
    c21 = c21.replace(
        'print(f"💾 Anchor {anchor_id} Converged. Top Results Checkpointed in JSON.")',
        'msg = f"💾 Anchor {anchor_id} Converged. Top Results Checkpointed in JSON."\n        print(msg)\n        sync_log(msg)'
    )
    with open(f21, 'w') as f: f.write(c21)

# --- Patch Cell 22 ---
f22 = BASE_DIR / "Cell_22_Deep_Greedy_Convergence_Loop.py"
if f22.exists():
    c22 = insert_sync_log(f22)
    # Patch HTML displays or prints
    c22 = c22.replace(
        'print(f"♻️ Resumed Global Evolution from Iteration {iteration} (Historical Best ipSAE: {best_ipsae:.4f})")',
        'msg = f"♻️ Resumed Global Evolution from Iteration {iteration} (Historical Best ipSAE: {best_ipsae:.4f})"\n        print(msg)\n        sync_log(msg)'
    )
    c22 = c22.replace(
        'display(HTML(f"<hr><h4 style=\'color: #8B008B;\'>🔄 Iteration {iteration}</h4><p><b>Evaluating Active Hotspots:</b> {\',\'.join(active_hotspots)}</p>"))',
        'display(HTML(f"<hr><h4 style=\'color: #8B008B;\'>🔄 Iteration {iteration}</h4><p><b>Evaluating Active Hotspots:</b> {\',\'.join(active_hotspots)}</p>"))\n    sync_log(f"🔄 Iteration {iteration} | Active Hotspots: {\',\'.join(active_hotspots)}")'
    )
    c22 = c22.replace(
        'display(HTML(f"<p><b>Score achieved:</b> <span style=\'color:{color}; font-weight:bold; font-size:16px;\'>{current_ipsae:.4f}</span> (Historical Best: {best_ipsae:.4f})</p>"))',
        'display(HTML(f"<p><b>Score achieved:</b> <span style=\'color:{color}; font-weight:bold; font-size:16px;\'>{current_ipsae:.4f}</span> (Historical Best: {best_ipsae:.4f})</p>"))\n    sync_log(f"📊 Iteration {iteration} Max ipSAE: {current_ipsae:.4f}")'
    )
    c22 = c22.replace(
        'print("🛑 CONVERGED: Pool exhausted. Peak performance achieved.")',
        'msg = "🛑 CONVERGED: Pool exhausted. Peak performance achieved."\n            print(msg)\n            sync_log(msg)'
    )
    c22 = c22.replace(
        'print(f"➕ Added next best candidates from pool: {\',\'.join(added)}")',
        'msg = f"➕ Added next best candidates from pool: {\',\'.join(added)}"\n        print(msg)\n        sync_log(msg)'
    )
    c22 = c22.replace(
        'print("📉 Performance degraded. Discarding the last additions.")',
        'msg = "📉 Performance degraded. Discarding the last additions."\n        print(msg)\n        sync_log(msg)'
    )
    c22 = c22.replace(
        'print(f"🛑 CONVERGED: All combinations exhausted. Finalizing at ipSAE {best_ipsae:.4f}")',
        'msg = f"🛑 CONVERGED: All combinations exhausted. Finalizing at ipSAE {best_ipsae:.4f}"\n            print(msg)\n            sync_log(msg)'
    )
    c22 = c22.replace(
        'print(f"🔀 Retrying core with next alternative additions: {\',\'.join(added)}")',
        'msg = f"🔀 Retrying core with next alternative additions: {\',\'.join(added)}"\n        print(msg)\n        sync_log(msg)'
    )
    with open(f22, 'w') as f: f.write(c22)

print("Cells patched successfully.")
