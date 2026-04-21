"""Create Father Stu character via PixelLab Character Creator API."""
import json
import os
import sys
import time
import zipfile
import io
import requests

# Load API key
key_data = json.load(open(os.path.expanduser("~/.claude.json")))
args = key_data["mcpServers"]["pixellab"]["args"]
api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]

BASE_URL = "https://api.pixellab.ai/v2"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
}

OUTPUT_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames"
CHAR_ID_FILE = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/character_id.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Use the character_id from the previous creation call (already created)
character_id = "8af64444-b615-4cb1-a44f-b30da2ae808d"
job_id = "6bb5a279-1ce0-436f-acb7-30bc5a3e4771"

print(f"Using existing job: {job_id}")
print(f"Character ID: {character_id}")

# Step 2: Poll for completion
print("\nPolling for job completion...")
start = time.time()
MAX_WAIT = 600  # 10 minutes

while True:
    elapsed = time.time() - start
    if elapsed > MAX_WAIT:
        print(f"ERROR: Timed out after {MAX_WAIT}s")
        sys.exit(1)

    time.sleep(5)
    poll_resp = requests.get(
        f"{BASE_URL}/background-jobs/{job_id}",
        headers=HEADERS,
        timeout=30,
    )
    poll_resp.raise_for_status()
    poll_data = poll_resp.json()
    status = poll_data.get("status", "unknown")
    print(f"  [{elapsed:.0f}s] Status: {status}")

    if status == "completed":
        print(f"Job completed!")
        break
    elif status in ("failed", "error"):
        print(f"ERROR: Job failed: {json.dumps(poll_data, indent=2)}")
        sys.exit(1)

# Step 3: Download ZIP
print(f"\nDownloading character ZIP for {character_id}...")
for attempt in range(5):
    try:
        zip_resp = requests.get(
            f"{BASE_URL}/characters/{character_id}/zip",
            headers=HEADERS,
            timeout=120,
        )
        zip_resp.raise_for_status()

        if len(zip_resp.content) < 100:
            print(f"  Attempt {attempt+1}: ZIP too small ({len(zip_resp.content)} bytes), retrying in 30s...")
            time.sleep(30)
            continue

        print(f"  ZIP downloaded: {len(zip_resp.content)} bytes")
        break
    except Exception as e:
        print(f"  Attempt {attempt+1} failed: {e}")
        if attempt < 4:
            print("  Retrying in 30s...")
            time.sleep(30)
        else:
            print("ERROR: All download attempts failed")
            sys.exit(1)

# Step 4: Extract rotation PNGs
print("\nExtracting rotation PNGs...")
zf = zipfile.ZipFile(io.BytesIO(zip_resp.content))
print(f"  ZIP contents: {zf.namelist()}")

extracted = 0
for name in zf.namelist():
    if "rotations/" in name and name.endswith(".png"):
        direction = name.split("rotations/")[-1].replace(".png", "").replace("-", "")
        out_path = os.path.join(OUTPUT_DIR, f"cc_father_stu_{direction}.png")
        with open(out_path, "wb") as f:
            f.write(zf.read(name))
        print(f"  Saved: {out_path}")
        extracted += 1

if extracted == 0:
    print("WARNING: No rotation PNGs found in rotations/ folder. Extracting all PNGs...")
    for name in zf.namelist():
        if name.endswith(".png"):
            basename = os.path.basename(name).replace(".png", "").replace("-", "")
            out_path = os.path.join(OUTPUT_DIR, f"cc_father_stu_{basename}.png")
            with open(out_path, "wb") as f:
                f.write(zf.read(name))
            print(f"  Saved: {out_path}")
            extracted += 1

# Step 5: Save character_id
with open(CHAR_ID_FILE, "w") as f:
    f.write(character_id)
print(f"\nCharacter ID saved to: {CHAR_ID_FILE}")

print(f"\n{'='*60}")
print(f"  CHARACTER ID: {character_id}")
print(f"{'='*60}")
print(f"\nExtracted {extracted} rotation frames to {OUTPUT_DIR}")
print("Done!")
