"""
Generate a 3-part attack combo for Wiley using PixelLab API.
Each attack chains from the previous one's last frame.
"""

import json
import os
import sys
import time
import base64
import requests
import zipfile
import io
import re
from pathlib import Path
from PIL import Image
from io import BytesIO

# Config
CHARACTER_ID = "a1bed45e-85d3-476d-ada3-130b4dedcf09"
OUTPUT_DIR = Path("C:/Users/airet/workspaces/godot-game/assets/sprites/characters/wiley/frames")
API_BASE = "https://api.pixellab.ai/v2"
POLL_INTERVAL = 5
REQUEST_TIMEOUT = 30

# Load API key
key_data = json.load(open(os.path.expanduser("~/.claude.json")))
args = key_data["mcpServers"]["pixellab"]["args"]
api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}


def poll_job(job_id):
    """Poll a background job until completion."""
    print(f"  Polling job {job_id}...")
    while True:
        resp = requests.get(
            f"{API_BASE}/background-jobs/{job_id}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"  Job status: {status}")
        if status == "completed":
            return data
        elif status == "failed":
            print(f"  Job failed: {data}")
            sys.exit(1)
        time.sleep(POLL_INTERVAL)


def poll_job_for_images(job_id):
    """Poll a background job that returns images (animate-with-text-v3)."""
    print(f"  Polling job {job_id} for images...")
    while True:
        resp = requests.get(
            f"{API_BASE}/background-jobs/{job_id}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"  Job status: {status}")
        if status == "completed":
            last_resp = data.get("last_response", {})
            images = last_resp.get("images", [])
            if images:
                return images
            else:
                print(f"  Completed but no images found. Full response keys: {list(data.keys())}")
                print(f"  last_response keys: {list(last_resp.keys()) if last_resp else 'N/A'}")
                # Maybe images are at top level
                if "images" in data:
                    return data["images"]
                print(f"  Full data: {json.dumps(data, indent=2)[:2000]}")
                sys.exit(1)
        elif status == "failed":
            print(f"  Job failed: {data}")
            sys.exit(1)
        time.sleep(POLL_INTERVAL)


def decode_image(img_obj):
    """Decode an image object from the API response."""
    img_type = img_obj.get("type", "")
    raw_b64 = img_obj.get("base64", "")
    w = img_obj.get("width", 252)
    h = img_obj.get("height", 252)

    raw = base64.b64decode(raw_b64)

    if img_type == "rgba_bytes":
        expected = w * h * 4
        if len(raw) == expected:
            img = Image.frombytes("RGBA", (w, h), raw)
        else:
            print(f"  Warning: expected {expected} bytes for {w}x{h} RGBA, got {len(raw)}. Trying as PNG.")
            img = Image.open(BytesIO(raw))
    else:
        # Try as regular image (PNG/etc)
        img = Image.open(BytesIO(raw))

    return img


def save_frames(images, prefix):
    """Save a list of image objects as numbered frames."""
    sizes = set()
    for i, img_obj in enumerate(images):
        img = decode_image(img_obj)
        sizes.add(img.size)
        out_path = OUTPUT_DIR / f"{prefix}_frame{i}.png"
        img.save(out_path)
        print(f"  Saved {out_path.name} ({img.size[0]}x{img.size[1]})")
    return sizes


def get_last_frame_b64(prefix):
    """Read the highest-numbered frame for a prefix and return base64."""
    frames = sorted(OUTPUT_DIR.glob(f"{prefix}_frame*.png"))
    if not frames:
        print(f"  ERROR: No frames found for prefix {prefix}")
        sys.exit(1)
    last = frames[-1]
    print(f"  Using last frame: {last.name}")
    with open(last, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# STEP 1: Generate Attack 1 via Character Creator
# ============================================================
print("=" * 60)
print("STEP 1: Generate Attack 1 via Character Creator")
print("=" * 60)

payload = {
    "character_id": CHARACTER_ID,
    "mode": "v3",
    "action_description": "part 1 of 3 sword attack combo, powerful horizontal swinging motion from left to right with both arms extended, empty handed do not draw any weapon or sword, aggressive lunge forward",
    "frame_count": 6,
    "directions": ["east"],
}

print("  Sending animation request...")
resp = requests.post(
    f"{API_BASE}/characters/animations",
    headers=headers,
    json=payload,
    timeout=REQUEST_TIMEOUT,
)
resp.raise_for_status()
result = resp.json()
print(f"  Response: {json.dumps(result, indent=2)[:500]}")

job_ids = result.get("background_job_ids", [])
if not job_ids:
    print("  ERROR: No background_job_ids returned")
    sys.exit(1)

job_data = poll_job(job_ids[0])

# Download ZIP
print("  Downloading character ZIP...")
zip_resp = requests.get(
    f"{API_BASE}/characters/{CHARACTER_ID}/zip",
    headers=headers,
    timeout=120,
)
zip_resp.raise_for_status()

# Extract attack1 frames from ZIP
print("  Extracting frames from ZIP...")
zf = zipfile.ZipFile(BytesIO(zip_resp.content))
all_names = zf.namelist()
print(f"  ZIP contains {len(all_names)} files")

# Find the animation directory - look for recent animation files
# List all directories in the ZIP
dirs_in_zip = set()
for name in all_names:
    parts = name.split("/")
    if len(parts) > 1:
        dirs_in_zip.add(parts[0])

print(f"  Directories in ZIP: {sorted(dirs_in_zip)}")

# Find the directory matching our animation
# Look for directories containing keywords from our action description
attack1_dir = None
attack1_candidates = []
for d in sorted(dirs_in_zip):
    dl = d.lower()
    if any(kw in dl for kw in ["part_1", "horizontal", "swinging", "lunge", "combo"]):
        attack1_candidates.append(d)
    # Also consider it could be the most recent animation
    # Let's just list all and pick the right one

if attack1_candidates:
    attack1_dir = attack1_candidates[0]
    print(f"  Found matching directory: {attack1_dir}")
else:
    # Show all dirs with their files to find the right one
    print("  No obvious match found. Listing all directories:")
    for d in sorted(dirs_in_zip):
        files_in_dir = [n for n in all_names if n.startswith(d + "/")]
        print(f"    {d}/ ({len(files_in_dir)} files)")
        for f in sorted(files_in_dir)[:3]:
            print(f"      {f}")
    # Pick the last directory alphabetically (likely most recent)
    attack1_dir = sorted(dirs_in_zip)[-1]
    print(f"  Using last directory: {attack1_dir}")

# Extract PNG frames from the chosen directory
frame_files = sorted([
    n for n in all_names
    if n.startswith(attack1_dir + "/") and n.lower().endswith(".png")
])

print(f"  Found {len(frame_files)} PNG frames in {attack1_dir}/")

attack1_sizes = set()
for i, fname in enumerate(frame_files):
    img_data = zf.read(fname)
    img = Image.open(BytesIO(img_data))
    attack1_sizes.add(img.size)
    out_path = OUTPUT_DIR / f"v3_attack1_frame{i}.png"
    img.save(out_path)
    print(f"  Saved v3_attack1_frame{i}.png ({img.size[0]}x{img.size[1]})")

print(f"  Attack 1 sizes: {attack1_sizes}")

# ============================================================
# STEP 2: Get last frame of Attack 1
# ============================================================
print()
print("=" * 60)
print("STEP 2: Get last frame of Attack 1")
print("=" * 60)

last_attack1_b64 = get_last_frame_b64("v3_attack1")

# ============================================================
# STEP 3: Generate Attack 2 via animate-with-text-v3
# ============================================================
print()
print("=" * 60)
print("STEP 3: Generate Attack 2 via animate-with-text-v3")
print("=" * 60)

payload2 = {
    "first_frame": {"type": "base64", "base64": last_attack1_b64, "format": "png"},
    "action": "part 2 of 3 sword attack combo, spinning backhand swinging motion from right to left, empty handed no weapon drawn, reverse slash follow-through",
    "frame_count": 6,
    "no_background": True,
    "seed": 123,
}

print("  Sending animate-with-text-v3 request...")
resp2 = requests.post(
    f"{API_BASE}/animate-with-text-v3",
    headers=headers,
    json=payload2,
    timeout=REQUEST_TIMEOUT,
)
resp2.raise_for_status()
result2 = resp2.json()
print(f"  Response keys: {list(result2.keys())}")

# Check if it's async
if "background_job_id" in result2:
    images2 = poll_job_for_images(result2["background_job_id"])
elif "images" in result2:
    images2 = result2["images"]
else:
    print(f"  Full response: {json.dumps(result2, indent=2)[:2000]}")
    sys.exit(1)

print(f"  Got {len(images2)} frames for Attack 2")
attack2_sizes = save_frames(images2, "v3_attack2")
print(f"  Attack 2 sizes: {attack2_sizes}")

# ============================================================
# STEP 4: Get last frame of Attack 2, generate Attack 3
# ============================================================
print()
print("=" * 60)
print("STEP 4: Generate Attack 3 via animate-with-text-v3")
print("=" * 60)

last_attack2_b64 = get_last_frame_b64("v3_attack2")

payload3 = {
    "first_frame": {"type": "base64", "base64": last_attack2_b64, "format": "png"},
    "action": "part 3 of 3 sword attack combo, massive overhead slam with both fists raised high then crushing downward, devastating finishing blow, empty handed no weapon",
    "frame_count": 8,
    "no_background": True,
    "seed": 123,
}

print("  Sending animate-with-text-v3 request...")
resp3 = requests.post(
    f"{API_BASE}/animate-with-text-v3",
    headers=headers,
    json=payload3,
    timeout=REQUEST_TIMEOUT,
)
resp3.raise_for_status()
result3 = resp3.json()
print(f"  Response keys: {list(result3.keys())}")

if "background_job_id" in result3:
    images3 = poll_job_for_images(result3["background_job_id"])
elif "images" in result3:
    images3 = result3["images"]
else:
    print(f"  Full response: {json.dumps(result3, indent=2)[:2000]}")
    sys.exit(1)

print(f"  Got {len(images3)} frames for Attack 3")
attack3_sizes = save_frames(images3, "v3_attack3")
print(f"  Attack 3 sizes: {attack3_sizes}")

# ============================================================
# SUMMARY
# ============================================================
print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Attack 1: {len(frame_files)} frames, sizes: {attack1_sizes}")
print(f"  Attack 2: {len(images2)} frames, sizes: {attack2_sizes}")
print(f"  Attack 3: {len(images3)} frames, sizes: {attack3_sizes}")
print(f"  Output directory: {OUTPUT_DIR}")

all_output = sorted(OUTPUT_DIR.glob("v3_attack*_frame*.png"))
print(f"  Total output files: {len(all_output)}")
for f in all_output:
    img = Image.open(f)
    print(f"    {f.name}: {img.size[0]}x{img.size[1]}")

print("\nDone!")
