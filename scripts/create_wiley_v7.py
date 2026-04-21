"""Create Wiley v7 character via PixelLab Character Creator API - Blood Armor theme."""
import json
import os
import io
import time
import zipfile
import requests

# 1. Load API key from ~/.claude.json
key_data = json.load(open(os.path.expanduser("~/.claude.json")))
args = key_data["mcpServers"]["pixellab"]["args"]
api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]

BASE = "https://api.pixellab.ai/v2"
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

FRAMES_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/wiley/frames"
CHAR_ID_FILE = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/wiley/cc_character_id_v7.txt"

# 2. POST to create-character-with-8-directions
payload = {
    "description": (
        "medieval cyberpunk wolf-headed dragon-winged berserker beast warrior, "
        "WOLF HEAD with fangs and glowing eyes from every angle, "
        "wild flaming hair like fire burning from the top of head, "
        "massive muscular body, dark fur, "
        "blood red crimson plate armor with dark red and black color scheme, "
        "large glowing W letter emblem on center of chest plate, "
        "neon red and crimson glowing rune engravings, "
        "blood-colored spiked pauldrons with embedded dark crystals, "
        "crimson gauntlets crackling with dark energy, hooves, "
        "dragon wings with glowing red vein patterns, "
        "blood knight berserker beast, "
        "synthwave medieval cyberpunk dark red armor, "
        "gothic fantasy meets cyberpunk"
    ),
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

print("Creating Wiley v7 character (Blood Armor theme)...")
resp = requests.post(f"{BASE}/create-character-with-8-directions", headers=HEADERS, json=payload, timeout=30)
resp.raise_for_status()
data = resp.json()
print(f"Initial response keys: {list(data.keys())}")

# Extract job_id
job_id = data.get("background_job_id") or data.get("job_id")
if not job_id:
    print(f"Full response: {json.dumps(data, indent=2)}")
    raise RuntimeError("No job_id found in response")
character_id = data.get("character_id")
print(f"Job ID: {job_id}")
if character_id:
    print(f"Character ID (from creation): {character_id}")

# 3. Poll background-jobs endpoint every 5s, up to 10 min
print("Polling for completion...")
MAX_POLL = 120  # 10 minutes at 5s intervals
for i in range(MAX_POLL):
    time.sleep(5)
    poll_resp = requests.get(f"{BASE}/background-jobs/{job_id}", headers=HEADERS, timeout=30)
    poll_resp.raise_for_status()
    poll_data = poll_resp.json()
    status = poll_data.get("status", "unknown")
    print(f"  [{i+1}] Status: {status}")

    if status == "completed":
        print("Job completed!")
        break
    elif status in ("failed", "error"):
        print(f"Job failed: {json.dumps(poll_data, indent=2)}")
        raise RuntimeError(f"Job failed with status: {status}")
else:
    raise RuntimeError("Timed out waiting for job completion (10 minutes)")

# Extract character_id
if not character_id:
    character_id = poll_data.get("character_id")
if not character_id:
    result = poll_data.get("result", {})
    character_id = result.get("character_id") if isinstance(result, dict) else None
if not character_id:
    print(f"Poll response keys: {list(poll_data.keys())}")
    raise RuntimeError("No character_id found in completed job")

print(f"\n{'='*60}")
print(f"  WILEY v7 CHARACTER ID: {character_id}")
print(f"{'='*60}\n")

# 4. Download ZIP with retries
print("Downloading character ZIP...")
for attempt in range(5):
    try:
        zip_resp = requests.get(f"{BASE}/characters/{character_id}/zip", headers=HEADERS, timeout=120)
        if zip_resp.status_code == 423:
            print(f"  Attempt {attempt+1}: Character still generating (423), waiting 30s...")
            time.sleep(30)
            continue
        zip_resp.raise_for_status()
        zip_bytes = zip_resp.content
        if len(zip_bytes) < 100:
            print(f"  Attempt {attempt+1}: ZIP too small ({len(zip_bytes)} bytes), waiting 30s...")
            time.sleep(30)
            continue
        print(f"  ZIP downloaded: {len(zip_bytes)} bytes")
        break
    except requests.exceptions.RequestException as e:
        print(f"  Attempt {attempt+1}: Error {e}, waiting 30s...")
        time.sleep(30)
else:
    raise RuntimeError("Failed to download ZIP after 5 attempts")

# 5. Extract rotation PNGs with BOTH naming conventions for compound directions
os.makedirs(FRAMES_DIR, exist_ok=True)

directions = [
    "south", "south-west", "west", "north-west",
    "north", "north-east", "east", "south-east",
]

# Alternate names for compound directions (underscore instead of hyphen)
alt_names = {
    "south-west": "south_west",
    "north-west": "north_west",
    "north-east": "north_east",
    "south-east": "south_east",
}

with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    names = zf.namelist()
    print(f"ZIP contents ({len(names)} files):")
    for n in names:
        print(f"  {n}")

    extracted = 0
    for name in names:
        basename = os.path.basename(name)
        for direction in directions:
            if basename == f"{direction}.png":
                # Save with hyphenated name
                out_path = os.path.join(FRAMES_DIR, f"cc_wiley_v7_{direction}.png")
                img_data = zf.read(name)
                with open(out_path, "wb") as dst:
                    dst.write(img_data)
                print(f"  Extracted: {basename} -> cc_wiley_v7_{direction}.png")
                extracted += 1

                # Also save with underscore name for compound directions
                if direction in alt_names:
                    alt_path = os.path.join(FRAMES_DIR, f"cc_wiley_v7_{alt_names[direction]}.png")
                    with open(alt_path, "wb") as dst:
                        dst.write(img_data)
                    print(f"  Also saved: cc_wiley_v7_{alt_names[direction]}.png")
                break

    print(f"\nExtracted {extracted} rotation frames (+ {len([d for d in directions if d in alt_names])} alternate names)")

# 6. Save character_id
with open(CHAR_ID_FILE, "w") as f:
    f.write(character_id)
print(f"Character ID saved to: {CHAR_ID_FILE}")

# Save ZIP for reference
zip_path = os.path.join(os.path.dirname(CHAR_ID_FILE), "cc_v7_export.zip")
with open(zip_path, "wb") as f:
    f.write(zip_bytes)
print(f"ZIP saved to: {zip_path}")

# 7. Print character_id prominently
print(f"\n{'='*60}")
print(f"  WILEY v7 CHARACTER ID: {character_id}")
print(f"  Theme: Blood Armor / Medieval Cyberpunk")
print(f"{'='*60}")
print("Done!")
