#!/usr/bin/env python
"""Inpaint attack animation frames for Father Stu using PixelLab inpaint API.

Loads the canonical south-east sprite + hand-drawn masks, calls the inpaint
endpoint 3 times (windup, midswing, followthrough), and saves the results.

Usage:
    python tools/inpaint_attack.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

# ===========================================================================
# Constants
# ===========================================================================

INPAINT_API_URL = "https://api.pixellab.ai/v2/inpaint"
FRAME_SIZE = 128

BASE_DIR = Path("C:/Users/airet/workspaces/godot-game")
SPRITE_PATH = BASE_DIR / "assets/sprites/characters/father_stu/frames/cc_father_stu_south-east.png"
MASK_DIR = BASE_DIR / "assets/sprites/characters/father_stu/frames/inpaint"
OUTPUT_DIR = MASK_DIR  # save results alongside masks

# Frame definitions: (mask_filename, output_filename, description)
FRAMES = [
    (
        "attack_mask_windup.png",
        "attack_frame1_windup.png",
        "arms raised high overhead, both hands together above head, winding up for powerful overhead swing, empty hands",
    ),
    (
        "attack_mask_midswing.png",
        "attack_frame2_midswing.png",
        "arms swinging down at 45 degrees to the right, both hands together, mid-swing powerful attack motion, empty hands",
    ),
    (
        "attack_mask_followthrough.png",
        "attack_frame3_followthrough.png",
        "arms extended forward and down to the right, completing a powerful overhead swing, follow-through pose, empty hands",
    ),
]


# ===========================================================================
# API Key Loading (same pattern as sprite_pipeline.py)
# ===========================================================================


def load_api_key() -> str:
    """Load the PixelLab API key from ~/.claude.json MCP server config."""
    claude_json_path = os.path.expanduser("~/.claude.json")
    try:
        with open(claude_json_path, "r") as f:
            data = json.load(f)
        args = data["mcpServers"]["pixellab"]["args"]
    except (FileNotFoundError, KeyError) as e:
        raise RuntimeError(f"Could not load PixelLab config from ~/.claude.json: {e}")
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    raise RuntimeError("Could not find --secret= in pixellab MCP args")


# ===========================================================================
# Image Helpers
# ===========================================================================


def load_and_resize(path: Path, size: int = FRAME_SIZE) -> Image.Image:
    """Load an image and resize to size x size using NEAREST neighbor."""
    img = Image.open(path)
    if img.size != (size, size):
        img = img.resize((size, size), Image.NEAREST)
    return img


def image_to_base64(img: Image.Image) -> str:
    """Convert a PIL Image to base64-encoded PNG string."""
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def decode_response_image(img_data: dict) -> Image.Image:
    """Decode an image from the PixelLab API response.

    Handles:
    - rgba_bytes: {"type": "rgba_bytes", "width": N, "base64": "..."}
    - base64 PNG: {"type": "base64", "base64": "...", "format": "png"}
    """
    img_type = img_data.get("type", "")

    if img_type == "rgba_bytes":
        width = img_data["width"]
        raw = base64.b64decode(img_data["base64"])
        if width == 0 or len(raw) % (width * 4) != 0:
            raise ValueError(f"rgba_bytes data is corrupt: {len(raw)} bytes, width={width}")
        height = len(raw) // (width * 4)
        return Image.frombytes("RGBA", (width, height), raw)
    else:
        # Assume base64-encoded PNG
        raw = base64.b64decode(img_data["base64"])
        return Image.open(BytesIO(raw)).convert("RGBA")


# ===========================================================================
# Main
# ===========================================================================


def main() -> None:
    print("=" * 60)
    print("  Father Stu — Inpaint Attack Frames")
    print("=" * 60)

    # Load API key
    api_key = load_api_key()
    print(f"API key: loaded ({len(api_key)} chars)")

    # Load and resize base sprite
    print(f"\nLoading base sprite: {SPRITE_PATH}")
    base_img = load_and_resize(SPRITE_PATH)
    base_b64 = image_to_base64(base_img)
    print(f"  Resized to {base_img.size[0]}x{base_img.size[1]}")

    # Save resized base for reference
    base_128_path = OUTPUT_DIR / "base_128.png"
    base_img.save(str(base_128_path))
    print(f"  Saved reference: {base_128_path}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    for i, (mask_file, output_file, description) in enumerate(FRAMES, 1):
        print(f"\n{'='*60}")
        print(f"Frame {i}/3: {output_file}")
        print(f"  Description: {description}")
        print(f"{'='*60}")

        # Load and resize mask
        mask_path = MASK_DIR / mask_file
        print(f"  Loading mask: {mask_path}")
        mask_img = load_and_resize(mask_path)

        # Convert mask to grayscale then back to RGB PNG for the API
        # (masks should be white=inpaint, black=keep)
        if mask_img.mode != "L":
            mask_img = mask_img.convert("L")
        # Convert back to RGB for API compatibility
        mask_img_rgb = mask_img.convert("RGB")
        mask_b64 = image_to_base64(mask_img_rgb)
        print(f"  Mask size: {mask_img.size[0]}x{mask_img.size[1]}")

        # Build payload
        payload = {
            "description": description,
            "image_size": {"width": FRAME_SIZE, "height": FRAME_SIZE},
            "inpainting_image": {"type": "base64", "base64": base_b64, "format": "png"},
            "mask_image": {"type": "base64", "base64": mask_b64, "format": "png"},
            "view": "side",
            "direction": "south-east",
            "seed": 42,
        }

        # Call API
        print(f"  Calling inpaint API...")
        try:
            resp = requests.post(INPAINT_API_URL, json=payload, headers=headers, timeout=120)
            print(f"  Status: {resp.status_code}")

            if resp.status_code != 200:
                print(f"  ERROR: {resp.text[:1000]}")
                continue

            result = resp.json()

            # Print full response structure for first call
            if i == 1:
                print(f"\n  === RESPONSE STRUCTURE (frame 1) ===")
                # Print keys and types, but truncate base64 data
                def summarize(obj, depth=0):
                    indent = "    " + "  " * depth
                    if isinstance(obj, dict):
                        print(f"{indent}{{")
                        for k, v in obj.items():
                            if isinstance(v, str) and len(v) > 100:
                                print(f"{indent}  \"{k}\": \"<string, {len(v)} chars>\"")
                            elif isinstance(v, (dict, list)):
                                print(f"{indent}  \"{k}\":")
                                summarize(v, depth + 1)
                            else:
                                print(f"{indent}  \"{k}\": {json.dumps(v)}")
                        print(f"{indent}}}")
                    elif isinstance(obj, list):
                        print(f"{indent}[ ({len(obj)} items)")
                        if obj:
                            summarize(obj[0], depth + 1)
                            if len(obj) > 1:
                                print(f"{indent}  ... ({len(obj)-1} more)")
                        print(f"{indent}]")
                    else:
                        print(f"{indent}{json.dumps(obj)}")

                summarize(result)
                print(f"  === END RESPONSE STRUCTURE ===\n")

            # Extract image from response
            # Try common response shapes
            images = None
            for key_path in [["images"], ["image"], ["result", "images"]]:
                obj = result
                try:
                    for key in key_path:
                        obj = obj[key]
                    if isinstance(obj, list):
                        images = obj
                        break
                    elif isinstance(obj, dict):
                        images = [obj]
                        break
                except (KeyError, TypeError):
                    continue

            if images is None:
                print(f"  ERROR: Could not find images in response. Keys: {list(result.keys())}")
                print(f"  Full response (truncated): {json.dumps(result, default=str)[:500]}")
                continue

            # Decode and save the first image
            img = decode_response_image(images[0])
            output_path = OUTPUT_DIR / output_file
            img.save(str(output_path))
            print(f"  Saved: {output_path} ({img.size[0]}x{img.size[1]})")

            # Print cost if available
            usage = result.get("usage", {})
            if usage:
                cost = usage.get("usd", 0)
                print(f"  Cost: ${cost:.4f}")

        except requests.exceptions.Timeout:
            print("  ERROR: Request timed out (120s)")
            continue
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            continue

    print(f"\n{'='*60}")
    print("Done! Check output files in:")
    print(f"  {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
