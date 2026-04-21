"""Create Father Stu v9 character via PixelLab Character Creator API."""
import json
import os
import time
import zipfile
import io
import shutil
import requests

# Load API key from ~/.claude.json
claude_config_path = os.path.expanduser("~/.claude.json")
with open(claude_config_path, "r") as f:
    config = json.load(f)

api_key = None
pixellab_cfg = config.get("mcpServers", {}).get("pixellab", {})
for arg in pixellab_cfg.get("args", []):
    if isinstance(arg, str) and arg.startswith("--secret="):
        api_key = arg.split("=", 1)[1]
        break

if not api_key:
    raise RuntimeError("Could not find PixelLab API key in ~/.claude.json")

print(f"Using API key: {api_key[:8]}...")

BASE_URL = "https://api.pixellab.ai/v2"
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

OUTPUT_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Step 1: Create character
payload = {
    "description": "medieval cyberpunk stout dwarf cleric, DWARF with thick braided beard and long flowing silver white hair and normal blue eyes from every angle, hooded cloak with hood DOWN draped over shoulders showing hair, short stocky powerful build, dark purple plate armor, large glowing S letter emblem on a wide kidney belt like a viking belt buckle, neon cyan and magenta and hot pink glowing rune engravings, ornate pauldrons with embedded purple crystals, gauntlets crackling with magenta energy, heavy armored boots with cyan trim, empty hands no staff no weapon, synthwave medieval cyberpunk dark purple armor with cyan magenta hot pink accents, gothic fantasy meets cyberpunk",
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

print("\n=== Creating character (8 directions) ===")
resp = requests.post(
    f"{BASE_URL}/create-character-with-8-directions",
    headers=HEADERS,
    json=payload,
    timeout=30,
)
resp.raise_for_status()
job_data = resp.json()
print(f"Response: {json.dumps(job_data, indent=2)}")

job_id = job_data.get("background_job_id") or job_data.get("job_id")
character_id_early = job_data.get("character_id")
if not job_id:
    raise RuntimeError(f"No job_id/background_job_id in response: {job_data}")
print(f"Job ID: {job_id}")
if character_id_early:
    print(f"Character ID (early): {character_id_early}")

# Step 2: Poll for completion
print("\n=== Polling for job completion ===")
max_poll = 120  # 10 minutes at 5s intervals
character_id = None
for i in range(max_poll):
    time.sleep(5)
    poll_resp = requests.get(
        f"{BASE_URL}/background-jobs/{job_id}",
        headers=HEADERS,
        timeout=30,
    )
    poll_resp.raise_for_status()
    status_data = poll_resp.json()
    status = status_data.get("status", "unknown")
    print(f"  [{i+1}] Status: {status}")

    if status == "completed":
        character_id = status_data.get("character_id") or status_data.get("result", {}).get("character_id")
        print(f"  Job completed! character_id = {character_id}")
        if not character_id:
            print(f"  Full response: {json.dumps(status_data, indent=2)}")
        break
    elif status == "failed":
        print(f"  Job FAILED: {json.dumps(status_data, indent=2)}")
        raise RuntimeError("Job failed")
else:
    # for loop exhausted without break = timeout
    raise RuntimeError("Timed out waiting for job completion (10 min)")

if not character_id:
    character_id = character_id_early
if not character_id:
    # Try extracting from full status
    print(f"Full final status: {json.dumps(status_data, indent=2)}")
    raise RuntimeError("Could not extract character_id from completed job")

# Step 3: Download ZIP
print(f"\n=== Downloading character ZIP ===")
zip_data = None
for attempt in range(5):
    try:
        print(f"  Download attempt {attempt+1}/5...")
        zip_resp = requests.get(
            f"{BASE_URL}/characters/{character_id}/zip",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/zip",
            },
            timeout=120,
        )
        zip_resp.raise_for_status()
        zip_data = zip_resp.content
        print(f"  Downloaded {len(zip_data)} bytes")
        break
    except Exception as e:
        print(f"  Attempt {attempt+1} failed: {e}")
        if attempt < 4:
            print(f"  Waiting 30s before retry...")
            time.sleep(30)
        else:
            raise RuntimeError("Failed to download ZIP after 5 attempts")

# Step 4: Extract rotation PNGs
print(f"\n=== Extracting rotation PNGs ===")
with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
    print(f"  ZIP contents: {zf.namelist()}")
    for name in zf.namelist():
        if name.endswith(".png"):
            # Extract direction from filename
            # Typical names: north.png, south.png, north-east.png, etc.
            basename = os.path.splitext(os.path.basename(name))[0].lower()
            direction = basename  # e.g., "north-east", "south", etc.

            # Save with standard naming
            out_name = f"cc_father_stu_{direction}.png"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            with open(out_path, "wb") as f:
                f.write(zf.read(name))
            print(f"  Saved: {out_name}")

            # For compound directions, also save with alternate naming
            if "-" in direction:
                # Save non-hyphenated version
                alt_direction = direction.replace("-", "")
                alt_name = f"cc_father_stu_{alt_direction}.png"
                alt_path = os.path.join(OUTPUT_DIR, alt_name)
                shutil.copy2(out_path, alt_path)
                print(f"  Saved: {alt_name} (alias)")
            elif any(d in direction for d in ["northeast", "northwest", "southeast", "southwest"]):
                # Save hyphenated version
                for compound in ["northeast", "northwest", "southeast", "southwest"]:
                    if compound in direction:
                        hyphenated = compound[:5] + "-" + compound[5:]
                        hyp_name = f"cc_father_stu_{direction.replace(compound, hyphenated)}.png"
                        hyp_path = os.path.join(OUTPUT_DIR, hyp_name)
                        shutil.copy2(out_path, hyp_path)
                        print(f"  Saved: {hyp_name} (alias)")

# Step 5: Save character_id
id_path = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/character_id.txt"
with open(id_path, "w") as f:
    f.write(character_id)
print(f"\nSaved character_id to: {id_path}")

print(f"\n{'='*60}")
print(f"  FATHER STU v9 CHARACTER ID: {character_id}")
print(f"{'='*60}")
print(f"\nAll rotation frames saved to: {OUTPUT_DIR}")
print("Done!")
