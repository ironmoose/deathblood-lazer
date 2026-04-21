"""Create Father Stu cleric character via PixelLab Character Creator API."""
import json
import os
import time
import zipfile
import io
import requests

# Load API key
key_data = json.load(open(os.path.expanduser("~/.claude.json")))
args = key_data["mcpServers"]["pixellab"]["args"]
api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]

BASE = "https://api.pixellab.ai/v2"
HEADERS = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
OUTPUT_DIR = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\father_stu\frames"
CHAR_ID_FILE = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\father_stu\character_id.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Create character
payload = {
    "description": (
        "medieval cyberpunk stout dwarf cleric healer, DWARF with thick braided beard "
        "and long flowing silver white hair and glowing orange eyes from every angle, "
        "hooded dark cloak with hood DOWN around shoulders showing hair, short stocky "
        "powerful build, dark leather and chainmail armor underneath cloak not heavy plate, "
        "subtle orange neon rune engravings on cloak edges and bracers, worn leather mage "
        "bracers with small embedded crystals, simple shoulder guards, heavy boots, glowing "
        "S rune on chest visible through open cloak, empty hands no staff no weapon, "
        "cyberpunk medieval dwarf cleric mystic healer, dark tones with orange synthwave "
        "accents not golden"
    ),
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

print("Creating character...")
resp = requests.post(f"{BASE}/create-character-with-8-directions", headers=HEADERS, json=payload, timeout=30)
resp.raise_for_status()
data = resp.json()
print(f"API response: {json.dumps(data, indent=2)}")
job_id = data.get("background_job_id") or data.get("job_id") or data.get("id")
character_id_initial = data.get("character_id")
print(f"Job ID: {job_id}")
print(f"Character ID (from create): {character_id_initial}")

# 2. Poll for completion
MAX_POLL = 120  # 10 minutes at 5s intervals
for i in range(MAX_POLL):
    time.sleep(5)
    r = requests.get(f"{BASE}/background-jobs/{job_id}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    status = r.json()
    state = status.get("status", "unknown")
    print(f"  Poll {i+1}: {state}")
    if state == "completed":
        result = status.get("result", {})
        if isinstance(result, dict):
            character_id = result.get("character_id")
        else:
            character_id = None
        if not character_id:
            character_id = status.get("character_id") or character_id_initial
        print(f"Character ID: {character_id}")
        break
    elif state == "failed":
        print(f"Job failed: {status}")
        raise SystemExit(1)
else:
    print("Timed out waiting for job")
    raise SystemExit(1)

# 3. Download ZIP with retries
print(f"\nDownloading character ZIP for {character_id}...")
for attempt in range(5):
    r = requests.get(f"{BASE}/characters/{character_id}/zip", headers=HEADERS, timeout=120)
    r.raise_for_status()
    if len(r.content) > 500:
        print(f"  ZIP downloaded: {len(r.content)} bytes")
        break
    print(f"  Attempt {attempt+1}: ZIP too small ({len(r.content)} bytes), retrying in 30s...")
    time.sleep(30)
else:
    print("Failed to download valid ZIP after 5 attempts")
    raise SystemExit(1)

# 4. Extract rotation PNGs
zf = zipfile.ZipFile(io.BytesIO(r.content))
print("\nZIP contents:")
for name in zf.namelist():
    print(f"  {name}")

extracted = 0
for name in zf.namelist():
    if not name.endswith(".png"):
        continue
    basename = os.path.basename(name)
    # Match rotation files like south-east.png
    parent = os.path.basename(os.path.dirname(name))
    if parent == "rotations" or "rotation" in os.path.dirname(name).lower():
        direction = os.path.splitext(basename)[0]
        out_name = f"cc_father_stu_{direction}.png"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        with open(out_path, "wb") as f:
            f.write(zf.read(name))
        print(f"  Saved: {out_name}")
        extracted += 1

if extracted == 0:
    # Fallback: extract all PNGs with direction-like names
    directions = {"north", "south", "east", "west", "north-east", "north-west", "south-east", "south-west",
                  "northeast", "northwest", "southeast", "southwest"}
    for name in zf.namelist():
        if not name.endswith(".png"):
            continue
        basename = os.path.splitext(os.path.basename(name))[0]
        if basename.lower() in directions:
            out_name = f"cc_father_stu_{basename}.png"
            out_path = os.path.join(OUTPUT_DIR, out_name)
            with open(out_path, "wb") as f:
                f.write(zf.read(name))
            print(f"  Saved (fallback): {out_name}")
            extracted += 1

print(f"\nExtracted {extracted} rotation frames")

# 5. Save character_id
with open(CHAR_ID_FILE, "w") as f:
    f.write(str(character_id))
print(f"Character ID saved to {CHAR_ID_FILE}")

print(f"\n{'='*60}")
print(f"  CHARACTER ID: {character_id}")
print(f"{'='*60}")
