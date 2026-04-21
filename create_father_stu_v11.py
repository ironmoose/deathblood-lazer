"""Create Father Stu v11 character via PixelLab Character Creator API (pro mode)."""

import json
import os
import time
import zipfile
import io
import shutil
import requests

# Load API key from ~/.claude.json
claude_json_path = os.path.expanduser("~/.claude.json")
with open(claude_json_path, "r") as f:
    claude_config = json.load(f)

# Extract API key from pixellab MCP server args
api_key = None
pixellab_config = claude_config.get("mcpServers", {}).get("pixellab", {})
for arg in pixellab_config.get("args", []):
    if arg.startswith("--secret="):
        api_key = arg.split("=", 1)[1]
        break

if not api_key:
    raise RuntimeError("Could not find PixelLab API key in ~/.claude.json")

print(f"API Key loaded: {api_key[:8]}...")

BASE_URL = "https://api.pixellab.ai/v2"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
}

OUTPUT_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Step 1: Create character
print("\n=== Creating Father Stu v11 character (pro mode) ===")
payload = {
    "description": "medieval cyberpunk stout dwarf cleric, DWARF with thick braided beard and long flowing silver white hair and normal blue eyes from every angle, short stocky powerful build, dark purple plate armor, large glowing S letter emblem on a wide kidney belt like a viking belt buckle, neon magenta and hot pink glowing rune engravings, consistent neon cyan glowing trim on ALL edges of armor gauntlets boots belt and pauldrons, ornate pauldrons with embedded purple crystals, gauntlets with neon cyan trim crackling with magenta energy, heavy armored boots with neon cyan glowing trim, empty hands no staff no weapon, synthwave medieval cyberpunk dark purple armor with magenta hot pink accents and consistent neon cyan glowing trim everywhere, gothic fantasy meets cyberpunk",
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

resp = requests.post(
    f"{BASE_URL}/create-character-with-8-directions",
    headers=HEADERS,
    json=payload,
    timeout=30,
)
resp.raise_for_status()
result = resp.json()
print(f"Response: {json.dumps(result, indent=2)}")

# Extract job_id and character_id
job_id = result.get("background_job_id") or result.get("job_id")
character_id = result.get("character_id")

if character_id:
    print(f"Character ID: {character_id}")

if job_id:
    print(f"Background Job ID: {job_id}")
    # Step 2: Poll for job completion
    print("\n=== Polling for job completion (up to 10 min) ===")
    max_polls = 120  # 10 min at 5s intervals
    for i in range(max_polls):
        time.sleep(5)
        poll_resp = requests.get(
            f"{BASE_URL}/background-jobs/{job_id}",
            headers=HEADERS,
            timeout=30,
        )
        poll_resp.raise_for_status()
        job_status = poll_resp.json()
        status = job_status.get("status", "unknown")
        print(f"  Poll {i+1}: status={status}")

        if status == "completed":
            # Get character_id from result if not already set
            if not character_id:
                character_id = (
                    job_status.get("result", {}).get("character_id")
                    or job_status.get("character_id")
                )
            print(f"  Job completed! Character ID: {character_id}")
            break
        elif status == "failed":
            raise RuntimeError(f"Job failed: {job_status}")
    else:
        raise RuntimeError("Job polling timed out after 10 minutes")
elif not character_id:
    raise RuntimeError(f"Unexpected response: {result}")

# Step 3: Download ZIP
print(f"\n=== Downloading character ZIP (character_id={character_id}) ===")
zip_downloaded = False
for attempt in range(5):
    try:
        zip_resp = requests.get(
            f"{BASE_URL}/characters/{character_id}/zip",
            headers=HEADERS,
            timeout=120,
        )
        zip_resp.raise_for_status()
        zip_downloaded = True
        print(f"  ZIP downloaded ({len(zip_resp.content)} bytes)")
        break
    except Exception as e:
        print(f"  Attempt {attempt+1}/5 failed: {e}")
        if attempt < 4:
            print(f"  Waiting 30s before retry...")
            time.sleep(30)

if not zip_downloaded:
    raise RuntimeError("Failed to download ZIP after 5 attempts")

# Step 4: Extract PNGs
print("\n=== Extracting rotation PNGs ===")
zip_buffer = io.BytesIO(zip_resp.content)
with zipfile.ZipFile(zip_buffer, "r") as zf:
    print(f"  Files in ZIP: {zf.namelist()}")
    for name in zf.namelist():
        if name.endswith(".png"):
            # Extract direction from filename
            # PixelLab typically names them like: south.png, south-east.png, etc.
            basename = os.path.splitext(os.path.basename(name))[0].lower()
            direction = basename  # e.g. "south", "south-east", etc.

            # Save with hyphenated name
            hyphenated = direction
            out_path_hyphen = os.path.join(OUTPUT_DIR, f"cc_father_stu_{hyphenated}.png")

            # Save with non-hyphenated name
            non_hyphenated = direction.replace("-", "")
            out_path_no_hyphen = os.path.join(OUTPUT_DIR, f"cc_father_stu_{non_hyphenated}.png")

            data = zf.read(name)

            with open(out_path_hyphen, "wb") as f:
                f.write(data)
            print(f"  Saved: {out_path_hyphen}")

            if hyphenated != non_hyphenated:
                with open(out_path_no_hyphen, "wb") as f:
                    f.write(data)
                print(f"  Saved: {out_path_no_hyphen}")

# Step 5: Save character_id
id_path = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/character_id.txt"
with open(id_path, "w") as f:
    f.write(character_id)
print(f"\nCharacter ID saved to: {id_path}")

print("\n" + "=" * 60)
print(f"  CHARACTER ID: {character_id}")
print("=" * 60)
print("\nDone!")
