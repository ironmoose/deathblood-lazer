#!/usr/bin/env python
"""Test the PixelLab Character Creator pipeline.

Subcommands:
    create     — Create a character from a canonical sprite (async)
    templates  — List available animation templates
    animate    — Generate an animation for an existing character (async)
    list       — List animations for an existing character

Usage:
    python test_character_creator.py create
    python test_character_creator.py templates
    python test_character_creator.py animate --character-id CHAR_ID --template cross-punch
    python test_character_creator.py list --character-id CHAR_ID
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import requests

# ===========================================================================
# Constants
# ===========================================================================

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
CANONICAL_PATH = SCRIPT_DIR / ".." / "assets" / "sprites" / "player" / "wiley_char_canonical.png"
FRAMES_OUTPUT_DIR = SCRIPT_DIR / ".." / "assets" / "sprites" / "characters" / "wiley" / "frames"

BASE_URL = "https://api.pixellab.ai/v2"

POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300  # 5 minutes


# ===========================================================================
# API Key Loading
# ===========================================================================


def load_api_key() -> str:
    """Load the PixelLab API key from ~/.claude.json MCP server config."""
    claude_json_path = os.path.expanduser("~/.claude.json")
    try:
        with open(claude_json_path, "r") as f:
            data = json.load(f)
        args = data["mcpServers"]["pixellab"]["args"]
    except (FileNotFoundError, KeyError) as e:
        print(f"ERROR: Could not load PixelLab config from ~/.claude.json: {e}")
        sys.exit(1)
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    print("ERROR: Could not find --secret= in pixellab MCP args")
    sys.exit(1)


def get_headers(api_key: str) -> dict[str, str]:
    """Return standard request headers."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }


# ===========================================================================
# Reference Image Loading
# ===========================================================================


def load_canonical_b64() -> str:
    """Load Wiley's canonical sprite as base64."""
    path = CANONICAL_PATH.resolve()
    if not path.exists():
        print(f"ERROR: Canonical sprite not found: {path}")
        sys.exit(1)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    print(f"Loaded canonical sprite: {path} ({len(b64)} chars base64)")
    return b64


# ===========================================================================
# Image Decoding
# ===========================================================================


def decode_image(img_data: dict) -> bytes:
    """Decode an image dict from the PixelLab API response into PNG bytes.

    Handles two formats:
    - base64 PNG: {"type": "base64", "base64": "...", "format": "png"}
    - rgba_bytes: {"type": "rgba_bytes", "width": N, "base64": "..."}
    """
    img_type = img_data.get("type", "")

    if img_type == "rgba_bytes":
        # Raw RGBA pixel data — convert to PNG via PIL
        try:
            from PIL import Image
        except ImportError:
            print("ERROR: PIL/Pillow is required to decode rgba_bytes images.")
            print("       Install with: pip install Pillow")
            sys.exit(1)

        width = img_data["width"]
        raw = base64.b64decode(img_data["base64"])
        if width == 0 or len(raw) % (width * 4) != 0:
            raise ValueError(f"rgba_bytes data is corrupt: {len(raw)} bytes, width={width}")
        height = len(raw) // (width * 4)
        img = Image.frombytes("RGBA", (width, height), raw)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    else:
        # Assume base64-encoded PNG
        return base64.b64decode(img_data["base64"])


# ===========================================================================
# Async Job Polling
# ===========================================================================


def poll_background_job(job_id: str, api_key: str) -> dict:
    """Poll a background job until it completes or times out.

    Args:
        job_id: The background job ID to poll.
        api_key: PixelLab API key.

    Returns:
        The final job response dict.

    Raises:
        RuntimeError: If the job fails or times out.
    """
    poll_url = f"{BASE_URL}/background-jobs/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    max_attempts = POLL_TIMEOUT_SECONDS // POLL_INTERVAL_SECONDS
    consecutive_404s = 0

    print(f"  Polling job {job_id} every {POLL_INTERVAL_SECONDS}s (timeout {POLL_TIMEOUT_SECONDS}s)...")

    for attempt in range(1, max_attempts + 1):
        time.sleep(POLL_INTERVAL_SECONDS)

        try:
            resp = requests.get(poll_url, headers=headers, timeout=30)
        except Exception as e:
            print(f"  [{attempt:3d}] Poll network error: {e}")
            continue

        if resp.status_code == 404:
            consecutive_404s += 1
            print(f"  [{attempt:3d}] Job not found (404) [{consecutive_404s}/3]")
            if consecutive_404s >= 3:
                raise RuntimeError("3 consecutive 404s — job likely invalid or expired")
            continue
        else:
            consecutive_404s = 0

        if resp.status_code != 200:
            print(f"  [{attempt:3d}] HTTP {resp.status_code}: {resp.text[:200]}")
            continue

        data = resp.json()
        status = data.get("status", "unknown")

        # Check for images in last_response
        lr = data.get("last_response", {})
        if isinstance(lr, dict) and "images" in lr:
            print(f"  [{attempt:3d}] Got images in last_response!")
            return data

        # Check for character_id in last_response (create-character result)
        if isinstance(lr, dict) and "character_id" in lr:
            print(f"  [{attempt:3d}] Got character_id in last_response!")
            return data

        # Check top-level completion
        if status in ("completed", "done", "complete", "finished"):
            print(f"  [{attempt:3d}] Job completed (status={status})")
            return data

        if status in ("failed", "error"):
            error_msg = data.get("error", data.get("message", str(data)))
            raise RuntimeError(f"Job failed: {error_msg}")

        # Progress report
        if attempt % 6 == 0:  # Every 30s
            print(f"  [{attempt:3d}] Still {status}...")

    raise RuntimeError(f"Job did not complete after {POLL_TIMEOUT_SECONDS}s")


def submit_and_poll(url: str, payload: dict, api_key: str) -> dict:
    """Submit a request and poll if async.

    Returns the final response data (either immediate or polled).
    """
    headers = get_headers(api_key)

    print(f"  POST {url}")
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    print(f"  Status: {resp.status_code}")

    if resp.status_code not in (200, 202):
        print(f"  Error response: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()

    # Check if this is an async job
    job_id = data.get("background_job_id") or data.get("job_id")
    if job_id:
        print(f"  Async job started: {job_id}")
        return poll_background_job(job_id, api_key)

    # Synchronous response
    return data


# ===========================================================================
# Subcommand: create
# ===========================================================================


def cmd_create(args: argparse.Namespace) -> None:
    """Create a character from the canonical sprite."""
    api_key = load_api_key()
    b64 = load_canonical_b64()

    description = (
        "wolf-headed dragon-winged berserker with hooves, "
        "ripped muscles, spiked pauldrons, bloody fists"
    )

    payload = {
        "description": description,
        "image_size": {"width": 128, "height": 128},
        "mode": "pro",
        "view": "side",
        "reference_image": {
            "type": "base64",
            "base64": b64,
            "format": "png",
        },
    }

    print(f"\n{'='*60}")
    print("Creating character with 8 directions")
    print(f"{'='*60}")
    print(f"  Description: {description}")

    data = submit_and_poll(f"{BASE_URL}/create-character-with-8-directions", payload, api_key)

    # Extract character_id from response
    character_id = None

    # Try last_response first
    lr = data.get("last_response", {})
    if isinstance(lr, dict):
        character_id = lr.get("character_id")

    # Try top-level
    if not character_id:
        character_id = data.get("character_id")

    # Try result
    if not character_id:
        result = data.get("result", {})
        if isinstance(result, dict):
            character_id = result.get("character_id")

    if not character_id:
        print("\nWARNING: Could not find character_id in response.")
        print(f"Response keys: {list(data.keys())}")
        if isinstance(lr, dict):
            print(f"last_response keys: {list(lr.keys())}")
        print(f"\nFull response (truncated):\n{json.dumps(data, indent=2)[:2000]}")
        sys.exit(1)

    # Save character_id to file
    output_dir = FRAMES_OUTPUT_DIR.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    id_file = output_dir / "character_id.txt"
    with open(id_file, "w") as f:
        f.write(character_id)

    print(f"\n{'='*60}")
    print(f"  CHARACTER ID: {character_id}")
    print(f"{'='*60}")
    print(f"  Saved to: {id_file}")
    print()
    print("  Next steps:")
    print(f"    python {sys.argv[0]} templates")
    print(f"    python {sys.argv[0]} animate --character-id {character_id} --template cross-punch")
    print(f"    python {sys.argv[0]} list --character-id {character_id}")


# ===========================================================================
# Subcommand: templates
# ===========================================================================


def cmd_templates(args: argparse.Namespace) -> None:
    """List available animation templates."""
    api_key = load_api_key()
    headers = get_headers(api_key)

    url = f"{BASE_URL}/characters/animation-templates"
    print(f"GET {url}")

    resp = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()

    # Handle different response shapes
    templates = data if isinstance(data, list) else data.get("templates", data.get("animation_templates", []))

    if not templates:
        print("No templates found.")
        print(f"Response: {json.dumps(data, indent=2)[:1000]}")
        return

    print(f"\n{'='*60}")
    print(f"Available Animation Templates ({len(templates)})")
    print(f"{'='*60}")

    for t in templates:
        if isinstance(t, dict):
            tid = t.get("id", t.get("template_id", t.get("name", "?")))
            desc = t.get("description", t.get("label", ""))
            directions = t.get("directions", [])
            frame_count = t.get("frame_count", t.get("num_frames", "?"))
            print(f"  {tid:<30s}  frames={frame_count}  dirs={directions}")
            if desc:
                print(f"    {desc}")
        else:
            print(f"  {t}")


# ===========================================================================
# Subcommand: animate
# ===========================================================================


def cmd_animate(args: argparse.Namespace) -> None:
    """Generate an animation for an existing character."""
    api_key = load_api_key()
    character_id = args.character_id
    template = args.template
    directions = args.directions.split(",") if args.directions else ["east"]

    payload = {
        "character_id": character_id,
        "mode": "template",
        "template_animation_id": template,
        "directions": directions,
    }

    print(f"\n{'='*60}")
    print(f"Generating animation: {template}")
    print(f"{'='*60}")
    print(f"  Character ID: {character_id}")
    print(f"  Template:     {template}")
    print(f"  Directions:   {directions}")

    data = submit_and_poll(f"{BASE_URL}/characters/animations", payload, api_key)

    # Extract images from response
    images = None

    # Try last_response.images
    lr = data.get("last_response", {})
    if isinstance(lr, dict) and "images" in lr:
        images = lr["images"]

    # Try top-level images
    if not images:
        images = data.get("images")

    # Try result.images
    if not images:
        result = data.get("result", {})
        if isinstance(result, dict):
            images = result.get("images")

    if not images:
        print("\nWARNING: No images found in response.")
        print(f"Response keys: {list(data.keys())}")
        if isinstance(lr, dict):
            print(f"last_response keys: {list(lr.keys())}")
        print(f"\nFull response (truncated):\n{json.dumps(data, indent=2)[:2000]}")
        sys.exit(1)

    # Save frames
    output_dir = FRAMES_OUTPUT_DIR.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Received {len(images)} frames")
    print(f"  Saving to: {output_dir}")

    for i, img_data in enumerate(images):
        try:
            png_bytes = decode_image(img_data)
            filename = f"{template}_frame{i}.png"
            filepath = output_dir / filename
            with open(filepath, "wb") as f:
                f.write(png_bytes)
            print(f"    [{i}] {filename} ({len(png_bytes)} bytes)")
        except Exception as e:
            print(f"    [{i}] ERROR decoding frame: {e}")

    print(f"\n  Done. {len(images)} frames saved to {output_dir}")


# ===========================================================================
# Subcommand: list
# ===========================================================================


def cmd_list(args: argparse.Namespace) -> None:
    """List animations for an existing character."""
    api_key = load_api_key()
    character_id = args.character_id
    headers = get_headers(api_key)

    url = f"{BASE_URL}/characters/{character_id}/animations"
    print(f"GET {url}")

    resp = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()

    # Handle different response shapes
    animations = data if isinstance(data, list) else data.get("animations", [])

    print(f"\n{'='*60}")
    print(f"Animations for character {character_id}")
    print(f"{'='*60}")

    if not animations:
        print("  No animations found.")
        print(f"  Response: {json.dumps(data, indent=2)[:1000]}")
        return

    for anim in animations:
        if isinstance(anim, dict):
            anim_id = anim.get("id", anim.get("animation_id", "?"))
            template = anim.get("template_animation_id", anim.get("template", "?"))
            status = anim.get("status", "?")
            directions = anim.get("directions", [])
            created = anim.get("created_at", "")
            print(f"  {anim_id}")
            print(f"    template={template}  status={status}  directions={directions}")
            if created:
                print(f"    created={created}")
        else:
            print(f"  {anim}")

    print(f"\n  Total: {len(animations)} animation(s)")


# ===========================================================================
# CLI Argument Parsing
# ===========================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Test the PixelLab Character Creator pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # create
    create_parser = subparsers.add_parser(
        "create",
        help="Create a character from the canonical sprite (async)",
    )

    # templates
    templates_parser = subparsers.add_parser(
        "templates",
        help="List available animation templates",
    )

    # animate
    animate_parser = subparsers.add_parser(
        "animate",
        help="Generate an animation for an existing character (async)",
    )
    animate_parser.add_argument(
        "--character-id",
        required=True,
        help="Character ID (from the create step)",
    )
    animate_parser.add_argument(
        "--template",
        required=True,
        help="Animation template ID (e.g. cross-punch, walk, idle)",
    )
    animate_parser.add_argument(
        "--directions",
        default="east",
        help="Comma-separated directions (default: east). E.g. east,west,north,south",
    )

    # list
    list_parser = subparsers.add_parser(
        "list",
        help="List animations for an existing character",
    )
    list_parser.add_argument(
        "--character-id",
        required=True,
        help="Character ID to list animations for",
    )

    return parser


# ===========================================================================
# Entry Point
# ===========================================================================


def main() -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    print("=" * 60)
    print("  PixelLab Character Creator Pipeline Test")
    print("=" * 60)

    dispatch = {
        "create": cmd_create,
        "templates": cmd_templates,
        "animate": cmd_animate,
        "list": cmd_list,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
