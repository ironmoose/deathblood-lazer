"""Generate idle and hurt animations for Wiley via PixelLab Character Creator API."""
import json
import os
import re
import time
import glob
import zipfile
import io
import requests

# Load API key
key_data = json.load(open(os.path.expanduser("~/.claude.json")))
args = key_data["mcpServers"]["pixellab"]["args"]
api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]

BASE = "https://api.pixellab.ai/v2"
HEADERS = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
CHARACTER_ID = "a1bed45e-85d3-476d-ada3-130b4dedcf09"
OUTPUT_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/characters/wiley/frames"

ANIMATIONS = [
    {
        "name": "idle",
        "payload": {
            "character_id": CHARACTER_ID,
            "mode": "v3",
            "action_description": (
                "combat idle stance bouncing up and down rhythmically, fists raised in guard position, "
                "bobbing on the balls of feet ready to fight, no stepping no walking, staying in place bouncing, "
                "empty hands no weapons"
            ),
            "frame_count": 8,
            "directions": ["east"],
        },
    },
    {
        "name": "hurt",
        "payload": {
            "character_id": CHARACTER_ID,
            "mode": "v3",
            "action_description": (
                "getting hit in the chest, body flinching and doubling over from a hard impact to the midsection, "
                "head lurching forward from the blow, pain reaction, no weapons no effects just the character reacting to being struck"
            ),
            "frame_count": 6,
            "directions": ["east"],
        },
    },
]

# Patterns for matching directories in the ZIP
DIR_PATTERNS = {
    "idle": [re.compile(r"bouncing", re.I), re.compile(r"combat_idle", re.I)],
    "hurt": [re.compile(r"getting_hit_in_the_chest", re.I), re.compile(r"flinching.*doubling_over", re.I)],
}


def submit_animation(anim):
    print(f"\n=== Submitting {anim['name']} animation ===")
    resp = requests.post(f"{BASE}/characters/animations", headers=HEADERS, json=anim["payload"], timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data["background_job_ids"][0]
    print(f"  Job ID: {job_id}")
    return job_id


def poll_job(job_id, label, timeout_sec=300):
    print(f"\nPolling {label} job {job_id}...")
    start = time.time()
    while time.time() - start < timeout_sec:
        resp = requests.get(f"{BASE}/background-jobs/{job_id}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "unknown")
        print(f"  [{label}] status={status} ({int(time.time()-start)}s elapsed)")
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(f"Job {job_id} failed: {data}")
        time.sleep(5)
    raise TimeoutError(f"Job {job_id} timed out after {timeout_sec}s")


def main():
    # Submit both animations sequentially
    jobs = {}
    for anim in ANIMATIONS:
        job_id = submit_animation(anim)
        jobs[anim["name"]] = job_id

    # Poll both to completion
    for name, job_id in jobs.items():
        poll_job(job_id, name)

    # Download ZIP
    print("\n=== Downloading character ZIP ===")
    resp = requests.get(
        f"{BASE}/characters/{CHARACTER_ID}/zip",
        headers=HEADERS,
        timeout=120,
    )
    resp.raise_for_status()
    print(f"  ZIP size: {len(resp.content)} bytes")

    # Parse ZIP
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    all_names = zf.namelist()

    # List all animation directories
    dirs = sorted(set(os.path.dirname(n) for n in all_names if "/" in n))
    print(f"\n=== All animation directories in ZIP ({len(dirs)}) ===")
    for d in dirs:
        print(f"  {d}")

    # Find matching directories (pick the LAST match = newest)
    matched = {}
    for anim_type, patterns in DIR_PATTERNS.items():
        candidates = []
        for d in dirs:
            if any(p.search(d) for p in patterns):
                candidates.append(d)
        if not candidates:
            print(f"\nWARNING: No directory matched for {anim_type}")
            continue
        chosen = candidates[-1]
        matched[anim_type] = chosen
        print(f"\n  {anim_type} => {chosen}")

    # Delete old files and extract new ones
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for anim_type, chosen_dir in matched.items():
        # Delete old files
        old_pattern = os.path.join(OUTPUT_DIR, f"v3_{anim_type}_frame*")
        old_files = glob.glob(old_pattern)
        if old_files:
            print(f"\nDeleting {len(old_files)} old v3_{anim_type} files...")
            for f in old_files:
                os.remove(f)

        # Find frames in chosen dir
        frames = sorted([n for n in all_names if n.startswith(chosen_dir + "/") and n.endswith(".png")])
        print(f"\nExtracting {len(frames)} frames for {anim_type} from {chosen_dir}")

        for f in frames:
            # Extract frame number, strip leading zeros
            basename = os.path.basename(f)
            m = re.search(r"frame[_]?(\d+)", basename)
            if m:
                frame_num = int(m.group(1))  # strips leading zeros
                out_name = f"v3_{anim_type}_frame{frame_num}.png"
            else:
                out_name = f"v3_{anim_type}_{basename}"

            out_path = os.path.join(OUTPUT_DIR, out_name)
            with open(out_path, "wb") as out_f:
                out_f.write(zf.read(f))
            print(f"  -> {out_name}")

    print("\n=== Done ===")
    for anim_type in matched:
        count = len(glob.glob(os.path.join(OUTPUT_DIR, f"v3_{anim_type}_frame*.png")))
        print(f"  {anim_type}: {count} frames")


if __name__ == "__main__":
    main()
