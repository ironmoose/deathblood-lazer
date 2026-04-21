#!/usr/bin/env python
"""Test the PixelLab /animate-with-text-v3 endpoint to generate idle animation frames for Wiley."""

import argparse
import base64
import json
import os
import sys
from io import BytesIO

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = "https://api.pixellab.ai/v2/animate-with-text-v3"


# ---------------------------------------------------------------------------
# 1. Load PixelLab API key from ~/.claude.json
# ---------------------------------------------------------------------------

def load_api_key():
    claude_json_path = os.path.expanduser("~/.claude.json")
    try:
        with open(claude_json_path, "r") as f:
            data = json.load(f)
        args = data["mcpServers"]["pixellab"]["args"]
    except (FileNotFoundError, KeyError) as e:
        raise RuntimeError(f"Could not load PixelLab config: {e}")
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    raise RuntimeError("Could not find --secret= in pixellab MCP args")


# ---------------------------------------------------------------------------
# 2. Load reference image as base64
# ---------------------------------------------------------------------------

def load_reference_image():
    ref_path = os.path.join(SCRIPT_DIR, "wiley_char_canonical.png")
    with open(ref_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# 3. Parse command line arguments
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Test PixelLab animate-with-text-v3 endpoint"
    )
    parser.add_argument(
        "--action", default="idle breathing",
        help="Animation action description (default: 'idle breathing')"
    )
    parser.add_argument(
        "--frames", type=int, default=4,
        help="Number of frames, 4-16, must be even (default: 4)"
    )
    parser.add_argument(
        "--seed", type=int, default=123,
        help="Random seed (default: 123)"
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Set last_frame = first_frame to create a looping animation"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print payload without calling the API"
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 4. Decode a single image from the API response
# ---------------------------------------------------------------------------

def decode_image(img_data):
    """Decode an image dict from the API response.

    Handles two formats:
    - rgba_bytes: {"type": "rgba_bytes", "width": N, "base64": "..."}
    - base64 PNG: {"type": "base64", "base64": "...", "format": "png"}
    """
    from PIL import Image

    img_type = img_data.get("type", "")

    if img_type == "rgba_bytes":
        width = img_data["width"]
        raw = base64.b64decode(img_data["base64"])
        height = len(raw) // (width * 4)
        return Image.frombytes("RGBA", (width, height), raw)
    else:
        raw = base64.b64decode(img_data["base64"])
        return Image.open(BytesIO(raw))


# ---------------------------------------------------------------------------
# 5. Extract images list from response (try multiple paths)
# ---------------------------------------------------------------------------

def extract_images(response_json):
    """Try several known response shapes to find the images list."""
    for path in ["images", "last_response.images", "result.images"]:
        obj = response_json
        try:
            for key in path.split("."):
                obj = obj[key]
            if isinstance(obj, list):
                return obj
        except (KeyError, TypeError):
            continue
    raise RuntimeError(
        f"Could not find images in response. Keys: {list(response_json.keys())}"
    )


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    reference_b64 = load_reference_image()

    payload = {
        "first_frame": {
            "type": "base64",
            "base64": reference_b64,
            "format": "png",
        },
        "action": args.action,
        "frame_count": args.frames,
        "no_background": True,
        "seed": args.seed,
    }

    if args.loop:
        payload["last_frame"] = payload["first_frame"]

    if args.dry_run:
        preview = dict(payload)
        b64_len = len(preview["first_frame"]["base64"])
        preview["first_frame"] = f"<base64 PNG, {b64_len} chars>"
        print("=== DRY RUN — would POST to", ENDPOINT)
        print(json.dumps(preview, indent=2))
        return

    api_key = load_api_key()

    print(f"Action: {args.action}")
    print(f"Frames: {args.frames}")
    print(f"Seed:   {args.seed}")
    print(f"POST {ENDPOINT} ...")

    resp = requests.post(
        ENDPOINT,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout=120,
    )

    print(f"Status: {resp.status_code}")

    if resp.status_code not in (200, 202):
        print(f"Error: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()

    # Check if this is an async job (can happen on both 200 and 202)
    job_id = data.get("job_id") or data.get("background_job_id")
    if job_id and "images" not in data:
        print(f"Async job: {job_id}")
        print("Polling...")
        import time
        poll_url = f"https://api.pixellab.ai/v2/background-jobs/{job_id}"
        poll_headers = {"Authorization": f"Bearer {api_key}"}
        for attempt in range(1, 121):
            time.sleep(3)
            try:
                poll_resp = requests.get(poll_url, headers=poll_headers, timeout=30)
            except Exception as e:
                print(f"  [{attempt}] Poll error: {e}")
                continue
            if poll_resp.status_code == 404:
                print(f"  [{attempt}] Job gone (404)")
                continue
            if poll_resp.status_code != 200:
                print(f"  [{attempt}] {poll_resp.status_code}")
                continue
            data = poll_resp.json()
            status = data.get("status", "unknown")
            lr = data.get("last_response", {})
            if isinstance(lr, dict) and "images" in lr:
                print(f"  [{attempt}] Got images!")
                data = lr
                break
            if status in ("completed", "done", "complete", "finished"):
                print(f"  [{attempt}] Completed")
                break
            if status in ("failed", "error"):
                print(f"  [{attempt}] FAILED: {data}")
                sys.exit(1)
            if attempt % 10 == 0:
                print(f"  [{attempt}] {status}...")
        else:
            print("Error: Job did not complete after 360s")
            sys.exit(1)

    # Print cost info if present
    for key in ["cost", "credits_used", "credits_remaining", "balance"]:
        if key in data:
            print(f"  {key}: {data[key]}")

    images = extract_images(data)
    print(f"Received {len(images)} frames")

    # Sanitize action for filenames
    action_slug = args.action.replace(" ", "_")

    for i, img_data in enumerate(images):
        img = decode_image(img_data)
        filename = f"wiley_v3_{action_slug}_{i}.png"
        filepath = os.path.join(SCRIPT_DIR, filename)
        img.save(filepath)
        print(f"  [{i}] {filename} — {img.size[0]}x{img.size[1]}")

    print("Done.")


if __name__ == "__main__":
    main()
