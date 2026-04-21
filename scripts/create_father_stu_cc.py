"""Create Father Stu character via PixelLab Character Creator API."""

import json
import os
import time
import zipfile
import io
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

FRAMES_DIR = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\father_stu\frames"
CHAR_ID_FILE = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\father_stu\character_id.txt"

# 2. POST to create character with Wiley-approved description
payload = {
    "description": (
        "medieval cyberpunk stout dwarf cleric, DWARF with thick braided beard "
        "and long flowing silver white hair and normal blue eyes from every angle, "
        "wearing a large hooded cloak with the hood pulled DOWN around shoulders "
        "showing flowing hair, cloak visible from all angles draped over armor, "
        "short stocky powerful build, dark purple plate armor underneath cloak, "
        "large glowing S letter emblem on a wide kidney belt like a viking belt buckle, "
        "neon magenta and hot pink glowing rune engravings, neon cyan glowing trim "
        "on all edges of armor boots gauntlets cloak and belt, ornate pauldrons with "
        "embedded purple crystals, gauntlets crackling with magenta energy, heavy "
        "armored boots with neon cyan glowing trim, empty hands no staff no weapon, "
        "synthwave medieval cyberpunk dark purple armor with magenta hot pink accents "
        "and consistent neon cyan trim, gothic fantasy meets cyberpunk"
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
    MAX_WAIT = 600
    while time.time() - start < MAX_WAIT:
        time.sleep(5)
        poll = requests.get(f"{BASE}/background-jobs/{job_id}", headers=HEADERS, timeout=30)
        poll.raise_for_status()
        job_data = poll.json()
        status = job_data.get("status", "unknown")
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] Job status: {status}")

        if status == "completed":
            if not character_id:
                character_id = job_data.get("character_id") or job_data.get("result", {}).get("character_id")
            break
        elif status in ("failed", "error"):
            print(f"Job failed: {json.dumps(job_data, indent=2)}")
            raise RuntimeError("Character creation job failed")
    else:
        raise TimeoutError("Job did not complete within 10 minutes")

if not character_id:
    character_id = data.get("character_id") or data.get("id")
    if not character_id:
        print(f"Full response: {json.dumps(data, indent=2)}")
        raise ValueError("Could not find character_id in response")

print(f"\n{'='*60}")
print(f"CHARACTER ID: {character_id}")
print(f"{'='*60}\n")

# 4. Download ZIP (retry up to 5x with 30s waits, timeout=120)
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
# Map ZIP basenames to hyphenated direction names
DIRECTION_MAP = {
    "south": "south",
    "south-west": "south-west",
    "west": "west",
    "north-west": "north-west",
    "north": "north",
    "north-east": "north-east",
    "east": "east",
    "south-east": "south-east",
}

os.makedirs(FRAMES_DIR, exist_ok=True)

with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
    print(f"\nZIP contents:")
    for name in zf.namelist():
        print(f"  {name}")

    for name in zf.namelist():
        if not name.lower().endswith(".png"):
            continue
        basename = os.path.splitext(os.path.basename(name))[0].lower()
        matched_dir = DIRECTION_MAP.get(basename)

        if matched_dir:
            png_data = zf.read(name)

            # Save hyphenated version (e.g., cc_father_stu_south-east.png)
            hyphenated_name = f"cc_father_stu_{matched_dir}.png"
            with open(os.path.join(FRAMES_DIR, hyphenated_name), "wb") as f:
                f.write(png_data)
            print(f"  Saved: {hyphenated_name}")

            # Save non-hyphenated version for compound directions
            # (e.g., cc_father_stu_southeast.png)
            if "-" in matched_dir:
                compact_name = f"cc_father_stu_{matched_dir.replace('-', '')}.png"
                with open(os.path.join(FRAMES_DIR, compact_name), "wb") as f:
                    f.write(png_data)
                print(f"  Saved: {compact_name}")
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
