"""
Create Father Stu synthwave character via PixelLab Character Creator API.
Full synthwave neon colorway, cleric not heavy warrior.
"""
import json
import os
import time
import zipfile
import io
import shutil
import requests

# ── Config ──────────────────────────────────────────────────────────────
API_BASE = "https://api.pixellab.ai/v2"
FRAMES_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames"
CHAR_ID_FILE = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/character_id.txt"

# Direction order from PixelLab: S, SW, W, NW, N, NE, E, SE (indices 0-7)
DIRECTION_ORDER = ["south", "south-west", "west", "north-west", "north", "north-east", "east", "south-east"]

# ── Load API key from ~/.claude.json ────────────────────────────────────
claude_json_path = os.path.expanduser("~/.claude.json")
with open(claude_json_path, "r") as f:
    claude_config = json.load(f)

# Find the pixellab API key in mcpServers config
api_key = None
for server_name, server_cfg in claude_config.get("mcpServers", {}).items():
    if "pixellab" in server_name.lower():
        args = server_cfg.get("args", [])
        for arg in args:
            if arg.startswith("--secret="):
                api_key = arg.split("=", 1)[1]
                break
        break

if not api_key:
    raise RuntimeError("Could not find PixelLab API key in ~/.claude.json")

print(f"[OK] API key loaded ({api_key[:8]}...)")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ── Step 1: Create character ────────────────────────────────────────────
payload = {
    "description": (
        "medieval cyberpunk stout dwarf cleric, DWARF with thick braided beard "
        "and long flowing silver white hair and glowing orange eyes from every angle, "
        "hooded cloak with hood DOWN draped over shoulders showing hair, short stocky "
        "powerful build, full synthwave neon orange and hot pink glowing cleric robes "
        "and light armor, bright neon orange and magenta rune engravings covering robes "
        "and bracers, glowing S letter emblem on chest, ornate shoulder guards with "
        "bright neon crystal inlays, arcane bracers pulsing with orange energy, heavy "
        "boots with neon trim, empty hands no staff no weapon, vibrant synthwave neon "
        "colorway, medieval cyberpunk dwarf cleric knight, gothic fantasy meets cyberpunk"
    ),
    "image_size": {"width": 128, "height": 128},
    "mode": "pro",
    "view": "side",
}

print("\n[POST] Creating character with 8 directions...")
resp = requests.post(f"{API_BASE}/create-character-with-8-directions", headers=headers, json=payload, timeout=30)
resp.raise_for_status()
result = resp.json()
print(f"  Response: {json.dumps(result, indent=2)}")

# Extract IDs
data = result.get("data", result)
character_id = data.get("character_id")
job_id = data.get("background_job_id")

if not character_id or not job_id:
    raise RuntimeError(f"Missing character_id or background_job_id in response: {result}")

print(f"\n  character_id:      {character_id}")
print(f"  background_job_id: {job_id}")

# ── Step 2: Poll background job ─────────────────────────────────────────
print("\n[POLL] Waiting for job to complete...")
max_poll_time = 600  # 10 minutes
poll_interval = 5
start = time.time()

while True:
    elapsed = time.time() - start
    if elapsed > max_poll_time:
        raise TimeoutError(f"Job did not complete within {max_poll_time}s")

    resp = requests.get(f"{API_BASE}/background-jobs/{job_id}", headers=headers, timeout=30)
    resp.raise_for_status()
    job = resp.json()
    status = job.get("status", "unknown")
    print(f"  [{elapsed:.0f}s] Status: {status}")

    if status in ("completed", "complete", "done", "succeeded"):
        print("  Job complete!")
        break
    elif status in ("failed", "error"):
        raise RuntimeError(f"Job failed: {json.dumps(job, indent=2)}")

    time.sleep(poll_interval)

# ── Step 3: Download ZIP ────────────────────────────────────────────────
print("\n[GET] Downloading character ZIP...")
zip_data = None
for attempt in range(1, 6):
    try:
        resp = requests.get(
            f"{API_BASE}/characters/{character_id}/zip",
            headers={**headers, "Accept": "application/zip, application/octet-stream, */*"},
            timeout=120,
        )
        if resp.status_code == 423:
            print(f"  Attempt {attempt}: character still generating (423), waiting 30s...")
            time.sleep(30)
            continue
        resp.raise_for_status()
        zip_data = resp.content
        print(f"  Downloaded {len(zip_data)} bytes")
        break
    except requests.exceptions.RequestException as e:
        print(f"  Attempt {attempt} failed: {e}")
        if attempt < 5:
            print(f"  Retrying in 30s...")
            time.sleep(30)
        else:
            raise

if not zip_data:
    raise RuntimeError("Failed to download ZIP after 5 attempts")

# ── Step 4: Extract rotation PNGs ───────────────────────────────────────
print(f"\n[EXTRACT] Extracting to {FRAMES_DIR}")
os.makedirs(FRAMES_DIR, exist_ok=True)

with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
    names = zf.namelist()
    print(f"  ZIP contents ({len(names)} files):")
    for n in names:
        print(f"    {n}")

    # Find PNG files - they should be the rotation frames
    png_files = sorted([n for n in names if n.lower().endswith(".png")])
    print(f"\n  Found {len(png_files)} PNG files")

    if len(png_files) == 8:
        # Standard case: 8 PNGs matching the 8 directions
        for i, png_name in enumerate(png_files):
            direction = DIRECTION_ORDER[i]
            # Hyphenated name
            out_hyphen = os.path.join(FRAMES_DIR, f"cc_father_stu_{direction}.png")
            # Non-hyphenated name (for compound directions)
            out_nohyphen = os.path.join(FRAMES_DIR, f"cc_father_stu_{direction.replace('-', '')}.png")

            data = zf.read(png_name)
            with open(out_hyphen, "wb") as f:
                f.write(data)
            print(f"  Saved: {os.path.basename(out_hyphen)}")

            if out_hyphen != out_nohyphen:
                shutil.copy2(out_hyphen, out_nohyphen)
                print(f"  Saved: {os.path.basename(out_nohyphen)}")
    else:
        # If not exactly 8, try to match by filename or just extract all
        print(f"  WARNING: Expected 8 PNGs, got {len(png_files)}. Extracting all...")
        for png_name in png_files:
            data = zf.read(png_name)
            base = os.path.basename(png_name)
            out_path = os.path.join(FRAMES_DIR, base)
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  Saved: {base}")

# ── Step 5: Save character_id ───────────────────────────────────────────
with open(CHAR_ID_FILE, "w") as f:
    f.write(character_id)
print(f"\n[OK] Saved character_id to {CHAR_ID_FILE}")

# ── Done ────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"  CHARACTER ID: {character_id}")
print("=" * 60)
print("\nSynthwave Father Stu created successfully!")
