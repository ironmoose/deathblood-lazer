"""Create Father Stu character via PixelLab Character Creator API."""
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

FRAMES_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames"
CHAR_ID_FILE = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/character_id.txt"

# 2. POST to create-character-with-8-directions
payload = {
    "description": (
        "medieval cyberpunk stout dwarf cleric, DWARF with thick braided beard "
        "and long flowing silver white hair and glowing orange eyes from every angle, "
        "hooded cloak with hood DOWN around shoulders showing hair, short stocky powerful build, "
        "dark chainmail and leather armor under cloak, neon orange and cyan synthwave glowing "
        "rune engravings on cloak and armor, orange glowing bracers with embedded crystals, "
        "shoulder guards with orange crystal inlays, heavy boots with neon orange trim, "
        "glowing S rune emblem on chest, empty hands no staff no weapon, "
        "synthwave medieval cyberpunk dwarf cleric, gothic fantasy cyberpunk with vibrant "
        "neon orange as primary color and cyan accents"
    ),
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

print("Creating Father Stu character...")
resp = requests.post(f"{BASE}/create-character-with-8-directions", headers=HEADERS, json=payload, timeout=30)
resp.raise_for_status()
data = resp.json()
print(f"Initial response keys: {list(data.keys())}")

# Extract job_id - try both field names
job_id = data.get("background_job_id") or data.get("job_id")
if not job_id:
    print(f"Full response: {json.dumps(data, indent=2)}")
    raise RuntimeError("No job_id found in response")
# Also grab character_id from creation response if available
character_id = data.get("character_id")
print(f"Job ID: {job_id}")
if character_id:
    print(f"Character ID (from creation): {character_id}")

# 3. Poll background-jobs endpoint
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

# Extract character_id (prefer from creation response, fallback to poll)
if not character_id:
    character_id = poll_data.get("character_id")
if not character_id:
    result = poll_data.get("result", {})
    character_id = result.get("character_id") if isinstance(result, dict) else None
if not character_id:
    # Print keys only, not the full response (contains huge base64 data)
    print(f"Poll response keys: {list(poll_data.keys())}")
    raise RuntimeError("No character_id found in completed job")

print(f"\n{'='*60}")
print(f"  CHARACTER ID: {character_id}")
print(f"{'='*60}\n")

# 4. Download ZIP
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

# 5. Extract rotation PNGs
os.makedirs(FRAMES_DIR, exist_ok=True)

directions = [
    "south", "south-west", "west", "north-west",
    "north", "north-east", "east", "south-east",
]

with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    names = zf.namelist()
    print(f"ZIP contents ({len(names)} files):")
    for n in names:
        print(f"  {n}")

    extracted = 0
    for name in names:
        basename = os.path.basename(name)
        # Match exact direction basenames like "south-east.png"
        for direction in directions:
            if basename == f"{direction}.png":
                out_path = os.path.join(FRAMES_DIR, f"cc_father_stu_{direction}.png")
                with zf.open(name) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                print(f"  Extracted: {basename} -> cc_father_stu_{direction}.png")
                extracted += 1
                break

    print(f"\nExtracted {extracted} rotation frames")

# 6. Save character_id
with open(CHAR_ID_FILE, "w") as f:
    f.write(character_id)
print(f"Character ID saved to: {CHAR_ID_FILE}")

# 7. Print character_id prominently
print(f"\n{'='*60}")
print(f"  FATHER STU CHARACTER ID: {character_id}")
print(f"{'='*60}")
print("Done!")
