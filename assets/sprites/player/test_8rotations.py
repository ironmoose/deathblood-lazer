#!/usr/bin/env python
"""Test PixelLab /generate-8-rotations-v2 endpoint with Wiley's canonical sprite.

Generates all 8 directional views from a single reference image, saves individual
direction PNGs and a combined 3x3 grid image.

Usage:
    python test_8rotations.py           # Run the generation
    python test_8rotations.py --dry-run # Print payload without calling API
"""

import argparse
import base64
import json
import os
import sys
import time

import requests
from PIL import Image
from io import BytesIO

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 8 directions in standard order. NOTE: The positional mapping of the API's
# "images" array to these direction names is assumed based on the standard
# PixelLab 3x3 grid layout (S, SW, W, NW, N, NE, E, SE). If the output
# looks wrong (e.g. directions are mislabeled), check the actual API response
# by inspecting the saved JSON dump.
DIRECTIONS = [
    "south", "south-west", "west", "north-west",
    "north", "north-east", "east", "south-east",
]

# Grid layout: 3x3 with center = reference
# Row 0: NW, N, NE
# Row 1: W, [ref], E
# Row 2: SW, S, SE
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


# ---------------------------------------------------------------------------
# API key loading (same pattern as generate_anims.py)
# ---------------------------------------------------------------------------

def load_api_key():
    claude_json_path = os.path.expanduser("~/.claude.json")
    try:
        with open(claude_json_path, "r") as f:
            data = json.load(f)
        args = data["mcpServers"]["pixellab"]["args"]
    except FileNotFoundError:
        raise RuntimeError(f"Config file not found: {claude_json_path}")
    except KeyError:
        raise RuntimeError(
            f"PixelLab MCP server not configured in {claude_json_path}. "
            "Expected: mcpServers.pixellab.args with --secret=<key>"
        )
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    raise RuntimeError("Could not find --secret= in pixellab MCP args")


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def load_reference_image():
    """Load wiley_char_canonical.png as base64 string."""
    ref_path = os.path.join(SCRIPT_DIR, "wiley_char_canonical.png")
    if not os.path.exists(ref_path):
        print(f"ERROR: Reference image not found: {ref_path}")
        sys.exit(1)
    with open(ref_path, "rb") as f:
        data = f.read()
    print(f"Loaded reference image: {ref_path} ({len(data)} bytes)")
    return base64.b64encode(data).decode("utf-8")


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

def submit_rotation_job(api_key, reference_b64, dry_run=False):
    """Submit the 8-rotations generation job.

    Returns a dict with either:
      {"synchronous": True, "data": <response>}  for 200 responses
      {"synchronous": False, "job_id": <id>}      for 202 responses
    """
    url = "https://api.pixellab.ai/v2/generate-8-rotations-v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "method": "rotate_character",
        "reference_image": {
            "image": {
                "type": "base64",
                "base64": reference_b64,
            },
            "width": 128,
            "height": 128,
        },
        "image_size": {"width": 128, "height": 128},
        "view": "side",
        "no_background": True,
        "seed": 123,
    }

    if dry_run:
        # Print payload without the huge base64 blob
        display_payload = dict(payload)
        display_payload["reference_image"] = {
            "image": {
                "type": "base64",
                "base64": f"<{len(reference_b64)} chars>",
            },
            "width": 128,
            "height": 128,
        }
        print("\n--- DRY RUN ---")
        print(f"POST {url}")
        print("Headers: Authorization: Bearer <key>, Content-Type: application/json")
        print(f"Payload:\n{json.dumps(display_payload, indent=2)}")
        print("--- END DRY RUN ---")
        return None

    print(f"\nSubmitting 8-rotations job to {url}...")
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed: {e}")
        sys.exit(1)

    print(f"Response status: {resp.status_code}")

    if resp.status_code == 200:
        # Synchronous response -- images returned directly
        result = resp.json()
        print("Got synchronous response (no polling needed)")
        return {"synchronous": True, "data": result}

    if resp.status_code == 202:
        result = resp.json()
        job_id = result.get("job_id") or result.get("background_job_id")
        if not job_id:
            print(f"ERROR: 202 response but no job_id or background_job_id. Response:\n{json.dumps(result, indent=2)[:500]}")
            sys.exit(1)
        print(f"Job submitted successfully. job_id: {job_id}")
        return {"synchronous": False, "job_id": job_id}

    # Unexpected status
    print(f"ERROR: Unexpected status {resp.status_code}")
    print(f"Response body:\n{resp.text[:1000]}")
    sys.exit(1)


def poll_job(api_key, job_id, poll_interval=5, max_attempts=60):
    """Poll background job until completion. Returns the completed job response."""
    url = f"https://api.pixellab.ai/v2/background-jobs/{job_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    print(f"\nPolling job {job_id} every {poll_interval}s (max {max_attempts} attempts)...")

    last_good_response = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"  [{attempt}/{max_attempts}] Poll request failed: {e}")
            time.sleep(poll_interval)
            continue

        if resp.status_code == 404:
            print(f"  [{attempt}/{max_attempts}] Job not found (404) - job may have completed and been cleaned up")
            # If we previously got a result with images, return it
            if last_good_response and ("images" in last_good_response or "result" in last_good_response):
                print("  Returning last good response that had data")
                return last_good_response
            # Otherwise keep polling briefly in case it's a transient issue
            time.sleep(poll_interval)
            continue
        if resp.status_code != 200:
            print(f"  [{attempt}/{max_attempts}] Poll returned {resp.status_code}: {resp.text[:300]}")
            time.sleep(poll_interval)
            continue

        result = resp.json()
        last_good_response = result
        status = result.get("status", "unknown")
        # Show status and all response keys (excluding large data)
        keys_info = [k for k in result.keys() if k != "result"]
        print(f"  [{attempt}/{max_attempts}] Status: {status} | Keys: {keys_info}")

        # Inspect last_response for progress info
        last_resp = result.get("last_response")
        if last_resp and attempt % 10 == 0:  # Print every 10th poll to avoid spam
            if isinstance(last_resp, dict):
                lr_keys = list(last_resp.keys())
                print(f"    last_response keys: {lr_keys}")
                # Check for images in last_response
                if "images" in last_resp:
                    print(f"    FOUND IMAGES IN last_response! Count: {len(last_resp['images'])}")
            elif isinstance(last_resp, str):
                print(f"    last_response: {last_resp[:200]}")

        if status in ("completed", "done", "complete", "finished"):
            print("Job completed!")
            # Dump response structure for debugging
            result_keys = list(result.keys())
            print(f"  Response keys: {result_keys}")
            if "result" in result and isinstance(result["result"], dict):
                print(f"  result sub-keys: {list(result['result'].keys())}")
            return result
        elif status in ("failed", "error"):
            error_msg = result.get("error", result.get("message", "Unknown error"))
            print(f"ERROR: Job failed: {error_msg}")
            print(f"Full response:\n{json.dumps(result, indent=2)[:1000]}")
            sys.exit(1)
        elif status in ("pending", "processing", "in_progress", "queued"):
            time.sleep(poll_interval)
        else:
            # Unknown status -- keep polling but warn
            print(f"  Warning: Unknown status '{status}', continuing to poll...")
            time.sleep(poll_interval)

    print(f"ERROR: Job did not complete after {max_attempts} attempts "
          f"({max_attempts * poll_interval}s)")

    # Save last response for debugging
    if last_good_response:
        debug_path = os.path.join(SCRIPT_DIR, "debug_last_poll_response.json")
        # Strip large base64 blobs for readability
        debug_data = json.dumps(last_good_response, default=str)
        if len(debug_data) > 50000:
            debug_data = debug_data[:50000] + "\n... (truncated)"
        with open(debug_path, "w") as f:
            f.write(debug_data)
        print(f"  Saved last poll response to: {debug_path}")

        # Also check if last_response has our images
        last_resp = last_good_response.get("last_response")
        if last_resp and isinstance(last_resp, dict):
            print(f"  last_response keys: {list(last_resp.keys())}")
            if "images" in last_resp:
                print(f"  FOUND IMAGES! Returning last_good_response")
                return last_good_response

    sys.exit(1)


# ---------------------------------------------------------------------------
# Image saving
# ---------------------------------------------------------------------------

def decode_image(img_obj):
    """Decode a PixelLab image object to PIL Image.

    Handles:
    - {"type": "rgba_bytes", "width": N, "base64": "..."} -- raw RGBA pixel data
    - {"type": "base64", "base64": "...", "format": "png"} -- standard PNG/JPEG
    - Raw base64 string (assumed PNG)
    """
    if isinstance(img_obj, str):
        b64_data = img_obj
        if b64_data.startswith("data:"):
            b64_data = b64_data.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_data)
        return Image.open(BytesIO(img_bytes))

    if not isinstance(img_obj, dict):
        raise ValueError(f"Unexpected image object type: {type(img_obj)}")

    img_type = img_obj.get("type", "base64")
    b64_data = img_obj.get("base64", "")

    if b64_data.startswith("data:"):
        b64_data = b64_data.split(",", 1)[1]

    raw_bytes = base64.b64decode(b64_data)

    if img_type == "rgba_bytes":
        # Raw RGBA pixel data — width * height * 4 bytes
        width = img_obj.get("width", 128)
        height = len(raw_bytes) // (width * 4) if width else 128
        return Image.frombytes("RGBA", (width, height), raw_bytes)
    else:
        # Standard image file (PNG, JPEG, etc.)
        return Image.open(BytesIO(raw_bytes))


def save_direction_images(result):
    """Extract and save individual direction images from the API result.

    Returns a dict of {direction: PIL.Image} for grid assembly.

    Tries three extraction strategies in priority order:
    1. "images" list at top level or under "result" key (index-mapped to DIRECTIONS)
    2. Direction-keyed dicts at top level or under "result" key
    3. Dump response for debugging
    """
    direction_images = {}

    # --- Strategy 0: images inside last_response (generate-8-rotations-v2 format) ---
    images = None
    last_resp = result.get("last_response")
    if last_resp and isinstance(last_resp, dict):
        if "images" in last_resp:
            images = last_resp["images"]
            print(f"  Found {len(images)} images in last_response")
        # Also capture character_id for reference
        char_id = last_resp.get("character_id")
        if char_id:
            print(f"  Character ID: {char_id}")

    # --- Strategy 1: images list at top level or under "result" key ---
    if images is None and "images" in result:
        images = result["images"]
    elif images is None and "result" in result and isinstance(result["result"], dict):
        inner = result["result"]
        if "images" in inner:
            images = inner["images"]

    if images is not None:
        if len(images) != 8:
            print(f"  Warning: Expected 8 images, got {len(images)}")
        for i, img_obj in enumerate(images):
            direction = DIRECTIONS[i] if i < len(DIRECTIONS) else f"extra_{i}"
            img = decode_image(img_obj)
            direction_images[direction] = img
            print(f"  Extracted: {direction} (from images[{i}])")
    else:
        # --- Strategy 2: direction-keyed dicts (fallback) ---
        search_dicts = [result]
        if "result" in result and isinstance(result["result"], dict):
            search_dicts.append(result["result"])

        for search_dict in search_dicts:
            for direction in DIRECTIONS:
                if direction in direction_images:
                    continue
                for key in [direction, direction.replace("-", "_")]:
                    if key in search_dict:
                        img = decode_image(search_dict[key])
                        direction_images[direction] = img
                        print(f"  Extracted: {direction} (from key '{key}')")
                        break

    if not direction_images:
        print("ERROR: Could not extract any images from the response")
        print(f"Response keys: {list(result.keys())}")
        if "result" in result:
            inner = result["result"]
            if isinstance(inner, dict):
                print(f"Result keys: {list(inner.keys())}")
            else:
                print(f"Result type: {type(inner)}")
        result_str = json.dumps(result, default=str)
        if len(result_str) > 2000:
            result_str = result_str[:2000] + "... (truncated)"
        print(f"Full response:\n{result_str}")
        sys.exit(1)

    # Save individual files
    saved_count = 0
    for direction, img in direction_images.items():
        filename = f"wiley_rot_{direction}.png"
        filepath = os.path.join(SCRIPT_DIR, filename)
        img.save(filepath)
        print(f"  Saved: {filename} ({img.size[0]}x{img.size[1]})")
        saved_count += 1

    # Also save quantized versions if available
    if last_resp and isinstance(last_resp, dict) and "quantized_images" in last_resp:
        q_images = last_resp["quantized_images"]
        print(f"\n  Also found {len(q_images)} quantized images (palette-reduced)")
        for i, img_obj in enumerate(q_images):
            if i < len(DIRECTIONS):
                direction = DIRECTIONS[i]
                img = decode_image(img_obj)
                filename = f"wiley_rot_{direction}_quantized.png"
                filepath = os.path.join(SCRIPT_DIR, filename)
                img.save(filepath)
                print(f"  Saved: {filename} ({img.size[0]}x{img.size[1]})")

    print(f"\nSaved {saved_count} direction images")

    if saved_count < 8:
        missing = [d for d in DIRECTIONS if d not in direction_images]
        print(f"WARNING: Missing directions: {missing}")

    return direction_images


def create_grid_image(direction_images):
    """Create a 3x3 grid image with all 8 directions + reference in center.

    Grid layout:
        NW    N    NE
        W   [ref]   E
        SW    S    SE
    """
    cell_size = 128
    grid_size = cell_size * 3
    grid = Image.new("RGBA", (grid_size, grid_size), (0, 0, 0, 0))

    # Load reference image for center cell
    ref_path = os.path.join(SCRIPT_DIR, "wiley_char_canonical.png")
    ref_img = Image.open(ref_path).convert("RGBA")
    if ref_img.size != (cell_size, cell_size):
        ref_img = ref_img.resize((cell_size, cell_size), Image.NEAREST)

    # Place reference in center (row=1, col=1)
    grid.paste(ref_img, (1 * cell_size, 1 * cell_size))

    # Place direction images
    placed = 0
    for direction, (row, col) in GRID_POSITIONS.items():
        if direction in direction_images:
            img = direction_images[direction].convert("RGBA")
            if img.size != (cell_size, cell_size):
                img = img.resize((cell_size, cell_size), Image.NEAREST)
            grid.paste(img, (col * cell_size, row * cell_size))
            placed += 1
        else:
            print(f"  Warning: No image for direction '{direction}', grid cell left empty")

    grid_path = os.path.join(SCRIPT_DIR, "wiley_8rotations_grid.png")
    grid.save(grid_path)
    print(f"\nSaved grid image: wiley_8rotations_grid.png ({grid_size}x{grid_size}, "
          f"{placed}/8 directions placed)")
    return grid_path


# ---------------------------------------------------------------------------
# Cost / usage reporting
# ---------------------------------------------------------------------------

def print_usage(result):
    """Print cost and usage information from the response."""
    print("\n--- Usage / Cost ---")

    # Collect usage info from top level and nested result
    found_info = False
    search_dicts = [result]
    if "result" in result and isinstance(result["result"], dict):
        search_dicts.append(result["result"])

    for search_dict in search_dicts:
        for key in ("usage", "cost", "credits_used", "credits_remaining"):
            if key in search_dict:
                value = search_dict[key]
                if isinstance(value, dict):
                    for k, v in value.items():
                        print(f"  {k}: {v}")
                else:
                    print(f"  {key}: {value}")
                found_info = True

    if not found_info:
        print("  No usage/cost info in response")

    print("--------------------")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Test PixelLab /generate-8-rotations-v2 with Wiley's canonical sprite"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request payload without making the API call",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PixelLab 8-Rotations Test -- Wiley Character")
    print("=" * 60)

    # 1. Load API key
    print("\nLoading API key...")
    api_key = load_api_key()
    print(f"API key: {api_key[:8]}...{api_key[-4:]}")

    # 2. Load reference image
    print("\nLoading reference image...")
    reference_b64 = load_reference_image()

    # 3. Submit job
    job_result = submit_rotation_job(api_key, reference_b64, dry_run=args.dry_run)

    if args.dry_run:
        print("\nDry run complete. No API call was made.")
        return

    # 4. Get the final result (poll if async)
    if job_result["synchronous"]:
        result = job_result["data"]
    else:
        result = poll_job(api_key, job_result["job_id"])

    # 5. Save individual direction images
    print("\nExtracting and saving direction images...")
    direction_images = save_direction_images(result)

    # 6. Create grid image
    print("\nCreating 3x3 grid image...")
    create_grid_image(direction_images)

    # 7. Print usage info
    print_usage(result)

    print("\n" + "=" * 60)
    print("Done! Check the output files in:")
    print(f"  {SCRIPT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
