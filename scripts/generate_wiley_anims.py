"""Generate idle and hurt animations for Wiley via PixelLab Character Creator API."""
import json
import os
import re
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
HEADERS = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
CHARACTER_ID = "a1bed45e-85d3-476d-ada3-130b4dedcf09"
OUTPUT_DIR = r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\wiley\frames"

ANIMATIONS = [
    {
        "name": "idle",
        "payload": {
            "character_id": CHARACTER_ID,
            "mode": "v3",
            "action_description": "combat ready fighting stance, weight on front foot, fists raised ready to strike, aggressive and alert, do not draw any weapon, empty hands",
            "frame_count": 6,
            "directions": ["east"],
        },
    },
    {
        "name": "hurt",
        "payload": {
            "character_id": CHARACTER_ID,
            "mode": "v3",
            "action_description": "getting hit hard and staggering backward in pain, head snapping back from impact, arms flung back, empty hands no weapons",
            "frame_count": 6,
            "directions": ["east"],
        },
    },
]

TIMEOUT_POLL = 300  # 5 minutes
POLL_INTERVAL = 5


def submit_animation(name, payload):
    print(f"[{name}] Submitting animation request...")
    resp = requests.post(f"{BASE}/characters/animations", headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data["background_job_ids"][0]
    print(f"[{name}] Job submitted: {job_id}")
    return job_id


def poll_job(name, job_id):
    print(f"[{name}] Polling job {job_id}...")
    start = time.time()
    while time.time() - start < TIMEOUT_POLL:
        resp = requests.get(f"{BASE}/background-jobs/{job_id}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"[{name}] Status: {status} ({int(time.time() - start)}s elapsed)")
        if status == "completed":
            return data
        if status in ("failed", "error"):
            raise RuntimeError(f"[{name}] Job failed: {data}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"[{name}] Job did not complete within {TIMEOUT_POLL}s")


def download_zip():
    print("Downloading character ZIP...")
    start = time.time()
    while time.time() - start < TIMEOUT_POLL:
        resp = requests.get(f"{BASE}/characters/{CHARACTER_ID}/zip", headers=HEADERS, timeout=120)
        if resp.status_code == 423:
            print(f"  ZIP locked (building), retrying in {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)
            continue
        resp.raise_for_status()
        return resp.content
    raise TimeoutError("ZIP download did not become available")


def extract_frames(zip_bytes):
    """Extract frames from ZIP and map to v3_idle / v3_hurt naming."""
    extracted = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # List all entries for debugging
        all_names = zf.namelist()
        print(f"\nZIP contains {len(all_names)} entries. Directories/files:")
        dirs_seen = set()
        for n in all_names:
            parts = n.split("/")
            if len(parts) > 1:
                dirs_seen.add(parts[-2] if parts[-1] else parts[-2])
        for d in sorted(dirs_seen):
            print(f"  {d}")

        # Define mapping: keyword patterns -> output prefix
        mapping = {
            "idle": {
                "keywords": ["combat_ready", "fists_raised_ready", "fighting_stance"],
                "prefix": "v3_idle",
            },
            "hurt": {
                "keywords": ["getting_hit", "staggering_backward"],
                "prefix": "v3_hurt",
            },
        }

        for entry in all_names:
            if not entry.lower().endswith(".png"):
                continue

            entry_lower = entry.lower().replace("-", "_")
            matched_prefix = None

            for anim_name, config in mapping.items():
                for kw in config["keywords"]:
                    if kw in entry_lower:
                        matched_prefix = config["prefix"]
                        break
                if matched_prefix:
                    break

            if not matched_prefix:
                continue

            # Extract frame number - handle frame_000, frame_00, frame_0, frame0 patterns
            frame_match = re.search(r'frame[_]?(\d+)', entry, re.IGNORECASE)
            if not frame_match:
                continue
            frame_num = int(frame_match.group(1))  # strips leading zeros

            # Check direction - only keep east
            if "east" not in entry_lower and "east" not in entry.lower():
                # If the ZIP doesn't have direction in filename, still keep it
                # (since we only requested east)
                pass

            out_name = f"{matched_prefix}_frame{frame_num}.png"
            out_path = os.path.join(OUTPUT_DIR, out_name)

            with zf.open(entry) as src, open(out_path, "wb") as dst:
                dst.write(src.read())

            extracted.append(out_name)
            print(f"  Extracted: {entry} -> {out_name}")

    return extracted


def main():
    # 2. Submit both animations sequentially
    jobs = {}
    for anim in ANIMATIONS:
        job_id = submit_animation(anim["name"], anim["payload"])
        jobs[anim["name"]] = job_id

    # 3. Poll both jobs
    for name, job_id in jobs.items():
        poll_job(name, job_id)

    # 4. Download ZIP
    zip_bytes = download_zip()
    print(f"ZIP downloaded: {len(zip_bytes)} bytes")

    # 5. Extract frames
    extracted = extract_frames(zip_bytes)

    # 7. Summary
    print(f"\n{'='*60}")
    print(f"Extracted {len(extracted)} frames to {OUTPUT_DIR}:")
    for f in sorted(extracted):
        print(f"  {f}")
    if not extracted:
        print("  WARNING: No frames matched the keyword patterns!")
        print("  Check the ZIP directory names above and adjust mapping keywords.")


if __name__ == "__main__":
    main()
