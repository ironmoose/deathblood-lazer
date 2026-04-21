"""Create Father Stu character via PixelLab Character Creator API (v2 - synthwave cyberpunk)."""

import json
import os
import time
import zipfile
import io
import shutil
import requests

# 1. Load API key
key_data = json.load(open(os.path.expanduser("~/.claude.json")))
args = key_data["mcpServers"]["pixellab"]["args"]
api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]

BASE = "https://api.pixellab.ai/v2"
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

FRAMES_DIR = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\father_stu\frames"
CHAR_ID_FILE = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\father_stu\character_id.txt"

# 2. POST to create character
payload = {
    "description": (
        "medieval cyberpunk stout dwarf cleric warrior, DWARF with thick braided beard "
        "and long flowing silver white hair and glowing orange eyes from every angle, "
        "short stocky powerful build, plate armor with large glowing S letter emblem on "
        "center of chest plate, neon orange and cyan glowing rune engravings, ornate "
        "pauldrons with embedded fire crystals, gauntlets crackling with arcane orange "
        "energy, heavy armored boots, hooded cloak with hood DOWN draped over shoulders "
        "and back showing hair, empty hands no staff no weapon, synthwave medieval dwarf "
        "cleric knight, gothic fantasy meets cyberpunk"
    ),
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

print("Creating character...")
resp = requests.post(f"{BASE}/create-character-with-8-directions", headers=HEADERS, json=payload, timeout=30)
resp.raise_for_status()
data = resp.json()
print(f"Response keys: {list(data.keys())}")

# Check for async job
job_id = data.get("background_job_id")
character_id = data.get("character_id")

if job_id:
    print(f"Background job: {job_id}")
    # 3. Poll for completion (every 5s, up to 10 min)
    start = time.time()
    MAX_WAIT = 600  # 10 minutes
    while time.time() - start < MAX_WAIT:
        time.sleep(5)
        poll = requests.get(f"{BASE}/background-jobs/{job_id}", headers=HEADERS, timeout=30)
        poll.raise_for_status()
        job_data = poll.json()
        status = job_data.get("status", "unknown")
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] Job status: {status}")

        if status == "completed":
            # Extract character_id from job result
            if not character_id:
                lr = job_data.get("last_response", {})
                if isinstance(lr, dict):
                    character_id = lr.get("character_id")
                if not character_id:
                    character_id = job_data.get("character_id") or job_data.get("result", {}).get("character_id")
            break
        elif status in ("failed", "error"):
            print(f"Job failed: {json.dumps(job_data, indent=2)}")
            raise RuntimeError("Character creation job failed")
    else:
        raise TimeoutError("Job did not complete within 10 minutes")

if not character_id:
    # Try to find it in the response
    character_id = data.get("character_id") or data.get("id")
    lr = data.get("last_response", {})
    if isinstance(lr, dict) and not character_id:
        character_id = lr.get("character_id")
    if not character_id:
        print(f"Full response: {json.dumps(data, indent=2)}")
        raise ValueError("Could not find character_id in response")

print(f"\n{'='*60}")
print(f"CHARACTER ID: {character_id}")
print(f"{'='*60}\n")

# 4. Download ZIP (timeout=120, retry up to 5x with 30s waits)
for attempt in range(5):
    print(f"Downloading ZIP (attempt {attempt + 1}/5)...")
    try:
        zip_resp = requests.get(f"{BASE}/characters/{character_id}/zip", headers=HEADERS, timeout=120)
        zip_resp.raise_for_status()
        zip_bytes = zip_resp.content
        print(f"  ZIP size: {len(zip_bytes)} bytes")

        if len(zip_bytes) < 100:
            print("  ZIP too small, retrying...")
            if attempt < 4:
                time.sleep(30)
                continue
            else:
                raise ValueError("ZIP file consistently too small")

        break
    except requests.exceptions.RequestException as e:
        print(f"  Download error: {e}")
        if attempt < 4:
            time.sleep(30)
            continue
        raise

# 5. Extract rotation PNGs with BOTH naming conventions
# ZIP contains files named like: south.png, south-east.png, north-west.png, etc.
# We save both hyphenated and non-hyphenated versions for compound directions.
DIRECTION_MAP = {
    "south":      ["south"],
    "south-west": ["south-west", "southwest"],
    "west":       ["west"],
    "north-west": ["north-west", "northwest"],
    "north":      ["north"],
    "north-east": ["north-east", "northeast"],
    "east":       ["east"],
    "south-east": ["south-east", "southeast"],
}

os.makedirs(FRAMES_DIR, exist_ok=True)

# Clear old cc_father_stu_* files
for old_file in os.listdir(FRAMES_DIR):
    if old_file.startswith("cc_father_stu_") and old_file.endswith(".png"):
        os.remove(os.path.join(FRAMES_DIR, old_file))
        print(f"  Removed old: {old_file}")

with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    print(f"\nZIP contents:")
    for name in zf.namelist():
        print(f"  {name}")

    for name in zf.namelist():
        if not name.lower().endswith(".png"):
            continue
        # Use exact basename match (no extension)
        basename = os.path.splitext(os.path.basename(name))[0].lower()
        output_names = DIRECTION_MAP.get(basename)

        if output_names:
            img_data = zf.read(name)
            for out_dir_name in output_names:
                out_name = f"cc_father_stu_{out_dir_name}.png"
                out_path = os.path.join(FRAMES_DIR, out_name)
                with open(out_path, "wb") as dst:
                    dst.write(img_data)
                print(f"  Extracted: {out_name}")
        else:
            print(f"  Skipped (no direction match): {name}")

# 6. Save character_id
with open(CHAR_ID_FILE, "w") as f:
    f.write(character_id)
print(f"\nSaved character_id to {CHAR_ID_FILE}")

# 7. Final summary
print(f"\n{'='*60}")
print(f"DONE! CHARACTER ID: {character_id}")
print(f"{'='*60}")
print(f"\nFrames saved to: {FRAMES_DIR}")
for fn in sorted(os.listdir(FRAMES_DIR)):
    if fn.startswith("cc_father_stu_"):
        print(f"  {fn}")
