#!/usr/bin/env python
"""Test PixelLab /generate-8-rotations-v2 with 'low top-down' view for Wiley.

Simplified version of test_8rotations.py using view: "low top-down" instead of "side".
Saves individual direction PNGs as wiley_rot2_{direction}.png and a 3x3 grid.
"""

import base64
import json
import os
import sys
import time

import requests
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DIRECTIONS = [
    "south", "south-west", "west", "north-west",
    "north", "north-east", "east", "south-east",
]

GRID_POSITIONS = {
    "north-west":  (0, 0),
    "north":       (0, 1),
    "north-east":  (0, 2),
    "west":        (1, 0),
    "east":        (1, 2),
    "south-west":  (2, 0),
    "south":       (2, 1),
    "south-east":  (2, 2),
}


def load_api_key():
    claude_json_path = os.path.expanduser("~/.claude.json")
    with open(claude_json_path, "r") as f:
        data = json.load(f)
    args = data["mcpServers"]["pixellab"]["args"]
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    raise RuntimeError("Could not find --secret= in pixellab MCP args")


def load_reference_image():
    ref_path = os.path.join(SCRIPT_DIR, "wiley_char_canonical.png")
    with open(ref_path, "rb") as f:
        data = f.read()
    print(f"Loaded reference image: {ref_path} ({len(data)} bytes)")
    return base64.b64encode(data).decode("utf-8")


def submit_job(api_key, reference_b64):
    url = "https://api.pixellab.ai/v2/generate-8-rotations-v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "method": "rotate_character",
        "reference_image": {
            "image": {"type": "base64", "base64": reference_b64},
            "width": 128,
            "height": 128,
        },
        "image_size": {"width": 128, "height": 128},
        "view": "low top-down",
        "no_background": True,
        "seed": 123,
    }

    print(f"Submitting 8-rotations job (low top-down) to {url}...")
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    print(f"Response status: {resp.status_code}")

    if resp.status_code == 200:
        return {"synchronous": True, "data": resp.json()}

    if resp.status_code == 202:
        result = resp.json()
        job_id = result.get("job_id") or result.get("background_job_id")
        if not job_id:
            print(f"ERROR: 202 but no job_id. Response: {json.dumps(result, indent=2)[:500]}")
            sys.exit(1)
        print(f"Job submitted. job_id: {job_id}")
        return {"synchronous": False, "job_id": job_id}

    print(f"ERROR: Unexpected status {resp.status_code}\n{resp.text[:1000]}")
    sys.exit(1)


def poll_job(api_key, job_id, poll_interval=5, max_attempts=80):
    url = f"https://api.pixellab.ai/v2/background-jobs/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    print(f"Polling job {job_id} every {poll_interval}s (max {max_attempts} attempts)...")

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"  [{attempt}/{max_attempts}] Poll failed: {e}")
            time.sleep(poll_interval)
            continue

        if resp.status_code != 200:
            print(f"  [{attempt}/{max_attempts}] Status {resp.status_code}: {resp.text[:200]}")
            time.sleep(poll_interval)
            continue

        result = resp.json()
        status = result.get("status", "unknown")

        # Check last_response for images (job stays "processing" even when done)
        last_resp = result.get("last_response")
        has_images = (
            last_resp
            and isinstance(last_resp, dict)
            and "images" in last_resp
        )

        print(f"  [{attempt}/{max_attempts}] Status: {status} | has_images: {has_images}")

        if has_images:
            print("Job done! Found images in last_response.")
            return result

        if status in ("completed", "done", "complete", "finished"):
            print("Job completed!")
            return result

        if status in ("failed", "error"):
            error_msg = result.get("error", result.get("message", "Unknown"))
            print(f"ERROR: Job failed: {error_msg}")
            sys.exit(1)

        time.sleep(poll_interval)

    print(f"ERROR: Job did not complete after {max_attempts} attempts")
    sys.exit(1)


def decode_image(img_obj):
    if isinstance(img_obj, str):
        return Image.open(__import__("io").BytesIO(base64.b64decode(img_obj)))

    img_type = img_obj.get("type", "base64")
    b64_data = img_obj.get("base64", "")
    raw_bytes = base64.b64decode(b64_data)

    if img_type == "rgba_bytes":
        width = img_obj.get("width", 128)
        height = len(raw_bytes) // (width * 4)
        return Image.frombytes("RGBA", (width, height), raw_bytes)
    else:
        return Image.open(__import__("io").BytesIO(raw_bytes))


def save_direction_images(result):
    images = None
    last_resp = result.get("last_response")
    if last_resp and isinstance(last_resp, dict) and "images" in last_resp:
        images = last_resp["images"]
        print(f"Found {len(images)} images in last_response")

    if images is None and "images" in result:
        images = result["images"]
    if images is None and "result" in result and isinstance(result["result"], dict):
        if "images" in result["result"]:
            images = result["result"]["images"]

    if not images:
        print("ERROR: No images found in response")
        print(f"Keys: {list(result.keys())}")
        sys.exit(1)

    direction_images = {}
    for i, img_obj in enumerate(images):
        direction = DIRECTIONS[i] if i < len(DIRECTIONS) else f"extra_{i}"
        img = decode_image(img_obj)
        direction_images[direction] = img
        filename = f"wiley_rot2_{direction}.png"
        filepath = os.path.join(SCRIPT_DIR, filename)
        img.save(filepath)
        print(f"  Saved: {filename} ({img.size[0]}x{img.size[1]})")

    return direction_images


def create_grid(direction_images):
    cell = 128
    grid = Image.new("RGBA", (cell * 3, cell * 3), (0, 0, 0, 0))

    # Center: canonical reference
    ref_path = os.path.join(SCRIPT_DIR, "wiley_char_canonical.png")
    ref_img = Image.open(ref_path).convert("RGBA")
    if ref_img.size != (cell, cell):
        ref_img = ref_img.resize((cell, cell), Image.NEAREST)
    grid.paste(ref_img, (cell, cell))

    for direction, (row, col) in GRID_POSITIONS.items():
        if direction in direction_images:
            img = direction_images[direction].convert("RGBA")
            if img.size != (cell, cell):
                img = img.resize((cell, cell), Image.NEAREST)
            grid.paste(img, (col * cell, row * cell))

    grid_path = os.path.join(SCRIPT_DIR, "wiley_8rot_topdown_grid.png")
    grid.save(grid_path)
    print(f"Saved grid: {grid_path}")


def main():
    print("=" * 60)
    print("PixelLab 8-Rotations Test -- Low Top-Down View")
    print("=" * 60)

    api_key = load_api_key()
    print(f"API key: {api_key[:8]}...{api_key[-4:]}")

    reference_b64 = load_reference_image()

    job_result = submit_job(api_key, reference_b64)

    if job_result["synchronous"]:
        result = job_result["data"]
    else:
        result = poll_job(api_key, job_result["job_id"])

    print("\nExtracting images...")
    direction_images = save_direction_images(result)

    print("\nCreating grid...")
    create_grid(direction_images)

    print("\nDone!")


if __name__ == "__main__":
    main()
