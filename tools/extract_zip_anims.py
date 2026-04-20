#!/usr/bin/env python
"""Download Wiley v8 Character Creator ZIP and extract all animation frames.

Downloads from PixelLab /v2/characters/{id}/zip endpoint and extracts each
animation folder into properly named frame files.

Animation mapping:
  walking_forward-*  -> walk_frame0.png, walk_frame1.png, ...
  Walking-*          -> walk_short_frame0.png, ...
  Fight_Stance_Idle-* -> fight_idle_frame0.png, ...
  Falling_Back_Death-* -> death_frame0.png, ...
"""

import glob
import io
import os
import sys
import zipfile

# Import load_api_key from sprite_pipeline
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from sprite_pipeline import load_api_key

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHARACTER_ID = "d1babc2c-390f-4620-96af-899a95a227ba"
ZIP_URL = f"https://api.pixellab.ai/v2/characters/{CHARACTER_ID}/zip"
OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "assets",
    "sprites",
    "characters",
    "wiley",
    "frames",
)

# Map animation folder name prefixes to output file prefixes
# Keys are lowercase for matching; the ZIP folders have mixed case + hash suffixes
ANIMATION_MAP = {
    "walking_forward": "walk",
    "walking": "walk_short",
    "fight_stance_idle": "fight_idle",
    "falling_back_death": "death",
}


def download_zip(api_key: str) -> zipfile.ZipFile:
    """Download the character ZIP from PixelLab."""
    print(f"Downloading ZIP from {ZIP_URL} ...")
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    resp = requests.get(ZIP_URL, headers=headers, timeout=120)
    resp.raise_for_status()
    print(f"  Downloaded {len(resp.content)} bytes")
    return zipfile.ZipFile(io.BytesIO(resp.content))


def match_animation(folder_name: str) -> str | None:
    """Match a ZIP folder name (e.g. 'Walking-03870efb') to our output prefix.

    We strip the hash suffix and match case-insensitively.
    Longer prefixes are checked first so 'walking_forward' matches before 'walking'.
    """
    # Strip hash suffix: "Walking-03870efb" -> "Walking"
    base = folder_name.rsplit("-", 1)[0] if "-" in folder_name else folder_name
    base_lower = base.lower()

    # Sort by length descending so "walking_forward" matches before "walking"
    for prefix in sorted(ANIMATION_MAP.keys(), key=len, reverse=True):
        if base_lower == prefix:
            return ANIMATION_MAP[prefix]
    return None


def cleanup_old_walk_frames(output_dir: str) -> None:
    """Remove old mixed walk_frame*.png files that were incorrectly extracted."""
    pattern = os.path.join(output_dir, "walk_frame*.png")
    old_files = glob.glob(pattern)
    if old_files:
        print(f"\nCleaning up {len(old_files)} old walk_frame*.png files:")
        for f in sorted(old_files):
            os.remove(f)
            print(f"  Removed {os.path.basename(f)}")


def extract_animations(zf: zipfile.ZipFile, output_dir: str) -> None:
    """Extract animation frames from the ZIP into named files."""
    os.makedirs(output_dir, exist_ok=True)

    # Group files by animation folder
    # ZIP structure: animations/<AnimName-hash>/<direction>/frame_NNN.png
    anim_files: dict[str, list[str]] = {}
    for name in zf.namelist():
        parts = name.split("/")
        if len(parts) >= 4 and parts[0] == "animations" and name.endswith(".png"):
            anim_folder = parts[1]
            direction = parts[2]
            # We only want south-east direction
            if direction == "south-east":
                if anim_folder not in anim_files:
                    anim_files[anim_folder] = []
                anim_files[anim_folder].append(name)

    if not anim_files:
        print("WARNING: No animation folders found in ZIP!")
        print("ZIP contents:")
        for name in sorted(zf.namelist()):
            print(f"  {name}")
        return

    print(f"\nFound {len(anim_files)} animation folders in ZIP:")
    for folder in sorted(anim_files.keys()):
        print(f"  {folder} ({len(anim_files[folder])} frames)")

    # Extract each animation
    total_extracted = 0
    for anim_folder, files in sorted(anim_files.items()):
        output_prefix = match_animation(anim_folder)
        if output_prefix is None:
            print(f"\n  SKIPPING unknown animation: {anim_folder}")
            continue

        # Sort files by frame number
        files.sort()

        print(f"\n  {anim_folder} -> {output_prefix}_frame*.png ({len(files)} frames)")
        for i, zip_path in enumerate(files):
            out_name = f"{output_prefix}_frame{i}.png"
            out_path = os.path.join(output_dir, out_name)
            with zf.open(zip_path) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            print(f"    {out_name}")
            total_extracted += 1

    print(f"\nDone! Extracted {total_extracted} frames to {os.path.abspath(output_dir)}")


def main():
    api_key = load_api_key()
    zf = download_zip(api_key)
    output_dir = os.path.normpath(OUTPUT_DIR)
    cleanup_old_walk_frames(output_dir)
    extract_animations(zf, output_dir)


if __name__ == "__main__":
    main()
