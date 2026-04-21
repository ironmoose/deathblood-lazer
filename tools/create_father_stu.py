#!/usr/bin/env python
"""Create Father Stu character via PixelLab Character Creator API.

Father Stu is Player 1 (Dad) — a stout dwarf battle mage.
Uses create-character-with-8-directions, polls for completion,
downloads the character ZIP, and extracts rotation PNGs.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import requests

# ===========================================================================
# Constants
# ===========================================================================

BASE_URL = "https://api.pixellab.ai/v2"
POLL_INTERVAL = 5        # seconds between polls
POLL_TIMEOUT = 600       # 10 minutes max
REQUEST_TIMEOUT = 30     # seconds for normal requests
ZIP_TIMEOUT = 120        # seconds for ZIP download

OUTPUT_DIR = Path("C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames")
CHAR_ID_FILE = Path("C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/character_id.txt")

DESCRIPTION = (
    "medieval cyberpunk stout dwarf battle mage, DWARF with thick braided beard "
    "and glowing eyes from every angle, short stocky powerful build, heavy plate "
    "armor with large glowing S letter emblem on center of chest plate, neon orange "
    "and gold glowing rune engravings, ornate pauldrons with embedded fire crystals, "
    "gauntlets crackling with arcane energy, heavy boots, hooded cloak with glowing "
    "trim, battle staff with crystal tip, synthwave medieval dwarf knight mage, "
    "gothic fantasy meets cyberpunk"
)

# Map ZIP filenames (hyphenated) to our naming convention (no hyphens)
DIR_MAP = {
    "south": "south",
    "south-west": "southwest",
    "west": "west",
    "north-west": "northwest",
    "north": "north",
    "north-east": "northeast",
    "east": "east",
    "south-east": "southeast",
}


# ===========================================================================
# API Key
# ===========================================================================

def load_api_key() -> str:
    """Load the PixelLab API key from ~/.claude.json MCP server config."""
    key_data = json.load(open(os.path.expanduser("~/.claude.json")))
    args = key_data["mcpServers"]["pixellab"]["args"]
    api_key = [a.split("=", 1)[1] for a in args if a.startswith("--secret=")][0]
    return api_key


# ===========================================================================
# Job Polling
# ===========================================================================

def poll_job(job_id: str, headers: dict) -> dict:
    """Poll a background job until completion or timeout."""
    poll_url = f"{BASE_URL}/background-jobs/{job_id}"
    max_attempts = POLL_TIMEOUT // POLL_INTERVAL
    consecutive_404s = 0

    print(f"\n  Polling job {job_id}")
    print(f"  Every {POLL_INTERVAL}s, timeout {POLL_TIMEOUT}s ({POLL_TIMEOUT // 60} min)")

    for attempt in range(1, max_attempts + 1):
        time.sleep(POLL_INTERVAL)

        try:
            resp = requests.get(poll_url, headers=headers, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            print(f"  [{attempt:3d}] Network error: {e}")
            continue

        if resp.status_code == 404:
            consecutive_404s += 1
            print(f"  [{attempt:3d}] Job not found (404) [{consecutive_404s}/5]")
            if consecutive_404s >= 5:
                raise RuntimeError("5 consecutive 404s — job likely invalid")
            continue
        else:
            consecutive_404s = 0

        if resp.status_code != 200:
            print(f"  [{attempt:3d}] HTTP {resp.status_code}: {resp.text[:200]}")
            continue

        data = resp.json()
        status = data.get("status", "unknown")

        # Check for character_id in last_response
        lr = data.get("last_response", {})
        if isinstance(lr, dict) and "character_id" in lr:
            print(f"  [{attempt:3d}] Character created!")
            return data

        # Check for images
        if isinstance(lr, dict) and "images" in lr:
            print(f"  [{attempt:3d}] Got images!")
            return data

        # Terminal statuses
        if status in ("completed", "done", "complete", "finished"):
            print(f"  [{attempt:3d}] Job completed (status={status})")
            return data

        if status in ("failed", "error"):
            error_msg = data.get("error", data.get("message", str(data)))
            raise RuntimeError(f"Job failed: {error_msg}")

        # Progress
        elapsed = attempt * POLL_INTERVAL
        if attempt % 6 == 0:  # every 30s
            print(f"  [{attempt:3d}] Still {status}... ({elapsed}s elapsed)")

    raise RuntimeError(f"Job did not complete after {POLL_TIMEOUT}s")


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    print("=" * 60)
    print("  Father Stu — Character Creator")
    print("  Player 1 (Dad) — Stout Dwarf Battle Mage")
    print("=" * 60)

    # Load API key
    api_key = load_api_key()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    auth_headers = {"Authorization": f"Bearer {api_key}"}
    print("\n  API key loaded.")

    # -----------------------------------------------------------------------
    # Step 1: Create character with 8 directions
    # -----------------------------------------------------------------------
    payload = {
        "description": DESCRIPTION,
        "image_size": {"width": 128, "height": 128},
        "mode": "pro",
        "view": "side",
    }

    print(f"\n  POST {BASE_URL}/create-character-with-8-directions")
    print(f"  Description: {DESCRIPTION[:80]}...")

    resp = requests.post(
        f"{BASE_URL}/create-character-with-8-directions",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    print(f"  Status: {resp.status_code}")

    if resp.status_code not in (200, 202):
        print(f"  ERROR: {resp.text[:500]}")
        sys.exit(1)

    data = resp.json()

    # Check for async job
    job_id = data.get("background_job_id") or data.get("job_id")
    if job_id:
        print(f"  Async job started: {job_id}")
        data = poll_job(job_id, auth_headers)
    else:
        print("  Synchronous response received.")

    # -----------------------------------------------------------------------
    # Step 2: Extract character_id
    # -----------------------------------------------------------------------
    character_id = None

    # Try last_response
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
        print("\n  ERROR: Could not find character_id in response!")
        print(f"  Response keys: {list(data.keys())}")
        if isinstance(lr, dict):
            print(f"  last_response keys: {list(lr.keys())}")
        print(f"\n  Full response:\n{json.dumps(data, indent=2)[:2000]}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  CHARACTER ID: {character_id}")
    print(f"{'=' * 60}")

    # Save character_id
    CHAR_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHAR_ID_FILE, "w") as f:
        f.write(character_id)
    print(f"  Saved character_id to: {CHAR_ID_FILE}")

    # -----------------------------------------------------------------------
    # Step 3: Download character ZIP
    # -----------------------------------------------------------------------
    zip_url = f"{BASE_URL}/characters/{character_id}/zip"
    print(f"\n  Downloading ZIP from: {zip_url}")

    # The character may still be processing — retry on 423
    max_zip_retries = 60  # 5 minutes of retries
    for attempt in range(1, max_zip_retries + 1):
        zip_resp = requests.get(zip_url, headers=auth_headers, timeout=ZIP_TIMEOUT)

        if zip_resp.status_code == 200:
            print(f"  ZIP downloaded: {len(zip_resp.content)} bytes")
            break
        elif zip_resp.status_code == 423:
            print(f"  [{attempt}] Character still processing (423), retrying in 5s...")
            time.sleep(5)
        else:
            print(f"  ERROR downloading ZIP: HTTP {zip_resp.status_code}")
            print(f"  {zip_resp.text[:300]}")
            sys.exit(1)
    else:
        print("  ERROR: ZIP download timed out after retries.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 4: Extract rotation PNGs from ZIP
    # -----------------------------------------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        filenames = zf.namelist()
        print(f"\n  ZIP contents ({len(filenames)} files):")
        for name in filenames:
            print(f"    {name}")

        # Extract PNGs using direction names from filenames
        png_files = [f for f in filenames if f.lower().endswith(".png")]

        if not png_files:
            print("\n  ERROR: No PNG files found in ZIP!")
            sys.exit(1)

        print(f"\n  Found {len(png_files)} PNG files, extracting by direction name...")

        for png_path in png_files:
            stem = Path(png_path).stem.lower()  # e.g. "south-west"
            direction = DIR_MAP.get(stem)
            if not direction:
                print(f"    WARNING: Unknown direction '{stem}' in {png_path}, skipping")
                continue
            out_path = OUTPUT_DIR / f"cc_father_stu_{direction}.png"
            with zf.open(png_path) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            print(f"    {png_path} -> {out_path.name}")

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    print(f"\n{'=' * 60}")
    print(f"  DONE!")
    print(f"{'=' * 60}")
    print(f"  Character ID:  {character_id}")
    print(f"  ID saved to:   {CHAR_ID_FILE}")
    print(f"  Frames dir:    {OUTPUT_DIR}")
    print(f"  Frame files:")
    for f in sorted(OUTPUT_DIR.glob("cc_father_stu_*.png")):
        size = f.stat().st_size
        print(f"    {f.name}  ({size:,} bytes)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
