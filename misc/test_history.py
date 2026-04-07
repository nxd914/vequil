import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent / "src"))

from vequil.pipeline import run_pipeline

print("🚀 Testing Multi-Event Pipeline...")

# 1. Run for Game Alpha
print("Running Game Alpha...")
run_pipeline(event_id="game_alpha")

# 2. Run for Game Beta 
print("Running Game Beta...")
run_pipeline(event_id="game_beta")

# 3. Verify folders
output_dir = Path("data/output/events")
events = [d.name for d in output_dir.iterdir() if d.is_dir()]

print(f"\n✅ Verification complete! Found events: {events}")

if "game_alpha" in events and "game_beta" in events:
    print("✨ Multi-event history logic is working 100%!")
else:
    print("❌ Something went wrong with event folder creation.")
