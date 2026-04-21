#!/usr/bin/env python
"""Generate Wiley character animations via PixelLab animate-with-skeleton API."""

import base64
import json
import os
import sys
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 1. Load PixelLab API key from ~/.claude.json
# ---------------------------------------------------------------------------

def load_api_key():
    claude_json_path = os.path.expanduser("~/.claude.json")
    with open(claude_json_path, "r") as f:
        data = json.load(f)
    args = data["mcpServers"]["pixellab"]["args"]
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    raise RuntimeError("Could not find --secret= in pixellab MCP args")


API_KEY = load_api_key()

# ---------------------------------------------------------------------------
# 2. Load reference image
# ---------------------------------------------------------------------------

def load_reference_image():
    ref_path = os.path.join(SCRIPT_DIR, "wiley_char_canonical.png")
    with open(ref_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


REFERENCE_B64 = load_reference_image()

# ---------------------------------------------------------------------------
# 3. Base skeleton keypoints (normalized 0-1 coords)
# ---------------------------------------------------------------------------

BASE_KEYPOINTS = [
    {"label": "NOSE",            "x": 0.353, "y": 0.271, "z_index": 0},
    {"label": "LEFT EYE",        "x": 0.394, "y": 0.241, "z_index": -1},
    {"label": "RIGHT EYE",       "x": 0.356, "y": 0.246, "z_index": -1},
    {"label": "LEFT EAR",        "x": 0.461, "y": 0.192, "z_index": -2},
    {"label": "RIGHT EAR",       "x": 0.394, "y": 0.208, "z_index": -2},
    {"label": "LEFT SHOULDER",   "x": 0.632, "y": 0.349, "z_index": -1},
    {"label": "RIGHT SHOULDER",  "x": 0.304, "y": 0.376, "z_index": -1},
    {"label": "LEFT ELBOW",      "x": 0.732, "y": 0.509, "z_index": 0},
    {"label": "RIGHT ELBOW",     "x": 0.253, "y": 0.520, "z_index": 0},
    {"label": "LEFT ARM",        "x": 0.757, "y": 0.658, "z_index": 0},
    {"label": "RIGHT ARM",       "x": 0.172, "y": 0.672, "z_index": 0},
    {"label": "LEFT HIP",        "x": 0.529, "y": 0.596, "z_index": -1},
    {"label": "RIGHT HIP",       "x": 0.404, "y": 0.604, "z_index": -1},
    {"label": "LEFT KNEE",       "x": 0.591, "y": 0.747, "z_index": 0},
    {"label": "RIGHT KNEE",      "x": 0.320, "y": 0.742, "z_index": 0},
    {"label": "LEFT LEG",        "x": 0.646, "y": 0.872, "z_index": -1},
    {"label": "RIGHT LEG",       "x": 0.358, "y": 0.853, "z_index": -1},
    {"label": "NECK",            "x": 0.468, "y": 0.363, "z_index": -1},
]

# ---------------------------------------------------------------------------
# 4. Helper: make_frame(mods)
# ---------------------------------------------------------------------------

def make_frame(mods=None):
    """Return a frame (list of keypoint dicts) with optional delta modifications.

    mods: dict of {label: (dx, dy)} offsets to apply on top of base keypoints.
    """
    if mods is None:
        mods = {}
    frame = []
    for kp in BASE_KEYPOINTS:
        new_kp = dict(kp)
        if kp["label"] in mods:
            dx, dy = mods[kp["label"]]
            new_kp["x"] = max(0.0, min(1.0, kp["x"] + dx))
            new_kp["y"] = max(0.0, min(1.0, kp["y"] + dy))
        frame.append(new_kp)
    return frame

# ---------------------------------------------------------------------------
# 5. Helper: generate(name, direction, frames, seed)
# ---------------------------------------------------------------------------

API_URL = "https://api.pixellab.ai/v2/animate-with-skeleton"


def generate(name, direction, frames, seed=123):
    """POST to PixelLab animate-with-skeleton and save each frame.

    Returns True on success, False on failure.
    """
    print(f"\n{'='*60}")
    print(f"Generating: {name} (direction={direction}, {len(frames)} frames, seed={seed})")
    print(f"{'='*60}")

    # API expects list of frames, each frame is a list of keypoint dicts
    skeleton_keypoints = frames

    payload = {
        "image_size": {"width": 128, "height": 128},
        "skeleton_keypoints": skeleton_keypoints,
        "direction": direction,
        "view": "side",
        "guidance_scale": 7.0,
        "isometric": False,
        "oblique_projection": False,
        "reference_image": {
            "type": "base64",
            "base64": REFERENCE_B64,
            "format": "png",
        },
        "init_image_strength": 300,
        "seed": seed,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        print(f"  Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"  Error: {resp.text[:500]}")
            return False

        result = resp.json()

        # The API returns images as list of {"type":"base64","base64":"...","format":"png"}
        images = result.get("images", [])
        if not images:
            print(f"  Warning: No images in response. Keys: {list(result.keys())}")
            print(f"  Response preview: {str(result)[:300]}")
            return False

        for i, img_obj in enumerate(images):
            out_path = os.path.join(SCRIPT_DIR, f"wiley_{name}_{i}.png")
            # img_obj is a dict with "base64" key
            img_b64 = img_obj["base64"] if isinstance(img_obj, dict) else img_obj
            img_data = base64.b64decode(img_b64)
            with open(out_path, "wb") as f:
                f.write(img_data)
            print(f"  Saved: wiley_{name}_{i}.png")

        # Print cost if available
        usage = result.get("usage", {})
        if usage:
            print(f"  Cost: ${usage.get('usd', 0):.4f}")

        print(f"  Success: {len(images)} frames saved")
        return True

    except requests.exceptions.Timeout:
        print("  Error: Request timed out (120s)")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False

# ---------------------------------------------------------------------------
# 6. Animation definitions
# ---------------------------------------------------------------------------

ANIMATIONS = {}

# --- walk_east: 3-frame walk cycle (side view) ---
ANIMATIONS["walk_east"] = {
    "direction": "east",
    "frames": [
        # Frame 0: Left leg forward, right back, arms swing opposite
        make_frame({
            "NOSE":          ( 0.005, 0.008),
            "NECK":          ( 0.003, 0.006),
            "LEFT EYE":      ( 0.003, 0.008),
            "RIGHT EYE":     ( 0.003, 0.008),
            "LEFT EAR":      ( 0.003, 0.008),
            "RIGHT EAR":     ( 0.003, 0.008),
            "LEFT HIP":      ( 0.02,  0.00),
            "LEFT KNEE":     ( 0.04, -0.01),
            "LEFT LEG":      ( 0.06,  0.00),
            "RIGHT HIP":     (-0.02,  0.00),
            "RIGHT KNEE":    (-0.04,  0.01),
            "RIGHT LEG":     (-0.06,  0.00),
            "LEFT ELBOW":    (-0.02,  0.02),
            "LEFT ARM":      (-0.03,  0.03),
            "RIGHT ELBOW":   ( 0.02, -0.02),
            "RIGHT ARM":     ( 0.03, -0.03),
        }),
        # Frame 1: Passing position, legs together
        make_frame({
            "NOSE":          ( 0.0,  -0.006),
            "NECK":          ( 0.0,  -0.004),
            "LEFT EYE":      ( 0.0,  -0.006),
            "RIGHT EYE":     ( 0.0,  -0.006),
            "LEFT EAR":      ( 0.0,  -0.006),
            "RIGHT EAR":     ( 0.0,  -0.006),
            "LEFT KNEE":     ( 0.00, -0.005),
            "RIGHT KNEE":    ( 0.00, -0.005),
        }),
        # Frame 2: Right leg forward, left back, arms swing opposite
        make_frame({
            "NOSE":          ( 0.005, 0.008),
            "NECK":          ( 0.003, 0.006),
            "LEFT EYE":      ( 0.003, 0.008),
            "RIGHT EYE":     ( 0.003, 0.008),
            "LEFT EAR":      ( 0.003, 0.008),
            "RIGHT EAR":     ( 0.003, 0.008),
            "RIGHT HIP":     ( 0.02,  0.00),
            "RIGHT KNEE":    ( 0.04, -0.01),
            "RIGHT LEG":     ( 0.06,  0.00),
            "LEFT HIP":      (-0.02,  0.00),
            "LEFT KNEE":     (-0.04,  0.01),
            "LEFT LEG":      (-0.06,  0.00),
            "RIGHT ELBOW":   (-0.02,  0.02),
            "RIGHT ARM":     (-0.03,  0.03),
            "LEFT ELBOW":    ( 0.02, -0.02),
            "LEFT ARM":      ( 0.03, -0.03),
        }),
    ],
}

# --- walk_south: walking toward camera ---
ANIMATIONS["walk_south"] = {
    "direction": "south",
    "frames": [
        # Frame 0: Left step forward
        make_frame({
            "NOSE":          ( 0.005, 0.008),
            "NECK":          ( 0.003, 0.006),
            "LEFT EYE":      ( 0.003, 0.008),
            "RIGHT EYE":     ( 0.003, 0.008),
            "LEFT EAR":      ( 0.003, 0.008),
            "RIGHT EAR":     ( 0.003, 0.008),
            "LEFT HIP":      (-0.02,  0.01),
            "LEFT KNEE":     (-0.03,  0.03),
            "LEFT LEG":      (-0.04,  0.04),
            "RIGHT HIP":     ( 0.02, -0.01),
            "RIGHT KNEE":    ( 0.03, -0.02),
            "RIGHT LEG":     ( 0.04, -0.03),
            "LEFT ELBOW":    ( 0.02,  0.02),
            "LEFT ARM":      ( 0.03,  0.03),
            "RIGHT ELBOW":   (-0.02, -0.02),
            "RIGHT ARM":     (-0.03, -0.03),
        }),
        # Frame 1: Passing
        make_frame({
            "NOSE":          ( 0.0,  -0.006),
            "NECK":          ( 0.0,  -0.004),
            "LEFT EYE":      ( 0.0,  -0.006),
            "RIGHT EYE":     ( 0.0,  -0.006),
            "LEFT EAR":      ( 0.0,  -0.006),
            "RIGHT EAR":     ( 0.0,  -0.006),
            "LEFT KNEE":     ( 0.00, -0.005),
            "RIGHT KNEE":    ( 0.00, -0.005),
        }),
        # Frame 2: Right step forward
        make_frame({
            "NOSE":          ( 0.005, 0.008),
            "NECK":          ( 0.003, 0.006),
            "LEFT EYE":      ( 0.003, 0.008),
            "RIGHT EYE":     ( 0.003, 0.008),
            "LEFT EAR":      ( 0.003, 0.008),
            "RIGHT EAR":     ( 0.003, 0.008),
            "RIGHT HIP":     (-0.02,  0.01),
            "RIGHT KNEE":    (-0.03,  0.03),
            "RIGHT LEG":     (-0.04,  0.04),
            "LEFT HIP":      ( 0.02, -0.01),
            "LEFT KNEE":     ( 0.03, -0.02),
            "LEFT LEG":      ( 0.04, -0.03),
            "RIGHT ELBOW":   ( 0.02,  0.02),
            "RIGHT ARM":     ( 0.03,  0.03),
            "LEFT ELBOW":    (-0.02, -0.02),
            "LEFT ARM":      (-0.03, -0.03),
        }),
    ],
}

# --- walk_north: walking away from camera ---
ANIMATIONS["walk_north"] = {
    "direction": "north",
    "frames": [
        # Frame 0: Left step forward (mirrored perspective)
        make_frame({
            "NOSE":          ( 0.005, 0.008),
            "NECK":          ( 0.003, 0.006),
            "LEFT EYE":      ( 0.003, 0.008),
            "RIGHT EYE":     ( 0.003, 0.008),
            "LEFT EAR":      ( 0.003, 0.008),
            "RIGHT EAR":     ( 0.003, 0.008),
            "LEFT HIP":      ( 0.02, -0.01),
            "LEFT KNEE":     ( 0.03, -0.03),
            "LEFT LEG":      ( 0.04, -0.04),
            "RIGHT HIP":     (-0.02,  0.01),
            "RIGHT KNEE":    (-0.03,  0.02),
            "RIGHT LEG":     (-0.04,  0.03),
            "LEFT ELBOW":    (-0.02, -0.02),
            "LEFT ARM":      (-0.03, -0.03),
            "RIGHT ELBOW":   ( 0.02,  0.02),
            "RIGHT ARM":     ( 0.03,  0.03),
        }),
        # Frame 1: Passing
        make_frame({
            "NOSE":          ( 0.0,  -0.006),
            "NECK":          ( 0.0,  -0.004),
            "LEFT EYE":      ( 0.0,  -0.006),
            "RIGHT EYE":     ( 0.0,  -0.006),
            "LEFT EAR":      ( 0.0,  -0.006),
            "RIGHT EAR":     ( 0.0,  -0.006),
            "LEFT KNEE":     ( 0.00, -0.005),
            "RIGHT KNEE":    ( 0.00, -0.005),
        }),
        # Frame 2: Right step forward
        make_frame({
            "NOSE":          ( 0.005, 0.008),
            "NECK":          ( 0.003, 0.006),
            "LEFT EYE":      ( 0.003, 0.008),
            "RIGHT EYE":     ( 0.003, 0.008),
            "LEFT EAR":      ( 0.003, 0.008),
            "RIGHT EAR":     ( 0.003, 0.008),
            "RIGHT HIP":     ( 0.02, -0.01),
            "RIGHT KNEE":    ( 0.03, -0.03),
            "RIGHT LEG":     ( 0.04, -0.04),
            "LEFT HIP":      (-0.02,  0.01),
            "LEFT KNEE":     (-0.03,  0.02),
            "LEFT LEG":      (-0.04,  0.03),
            "RIGHT ELBOW":   (-0.02, -0.02),
            "RIGHT ARM":     (-0.03, -0.03),
            "LEFT ELBOW":    ( 0.02,  0.02),
            "LEFT ARM":      ( 0.03,  0.03),
        }),
    ],
}

# --- hurt_east: taking damage recoil ---
ANIMATIONS["hurt_east"] = {
    "direction": "east",
    "frames": [
        # Frame 0: Impact - head snaps back, body recoils, arms flung back
        make_frame({
            "NOSE":          (-0.04, -0.02),
            "NECK":          (-0.03, -0.01),
            "LEFT EYE":      (-0.04, -0.02),
            "RIGHT EYE":     (-0.04, -0.02),
            "LEFT SHOULDER":  (-0.05, -0.02),
            "RIGHT SHOULDER": (-0.05, -0.02),
            "LEFT ELBOW":    (-0.07, -0.01),
            "LEFT ARM":      (-0.08,  0.02),
            "RIGHT ELBOW":   (-0.07, -0.01),
            "RIGHT ARM":     (-0.08,  0.02),
            "LEFT HIP":      (-0.02,  0.01),
            "RIGHT HIP":     (-0.02,  0.01),
            "LEFT KNEE":     (-0.01,  0.02),
            "RIGHT KNEE":    (-0.01,  0.02),
        }),
        # Frame 1: Staggering - leaning back
        make_frame({
            "NOSE":          (-0.03, -0.01),
            "NECK":          (-0.02,  0.00),
            "LEFT SHOULDER":  (-0.03, -0.01),
            "RIGHT SHOULDER": (-0.03, -0.01),
            "LEFT ELBOW":    (-0.04,  0.01),
            "LEFT ARM":      (-0.05,  0.03),
            "RIGHT ELBOW":   (-0.04,  0.01),
            "RIGHT ARM":     (-0.05,  0.03),
            "LEFT KNEE":     ( 0.01,  0.01),
            "RIGHT KNEE":    ( 0.01,  0.01),
        }),
        # Frame 2: Recovering - straightening up
        make_frame({
            "NOSE":          (-0.01,  0.00),
            "NECK":          (-0.01,  0.00),
            "LEFT ELBOW":    (-0.01,  0.01),
            "LEFT ARM":      (-0.01,  0.01),
            "RIGHT ELBOW":   (-0.01,  0.01),
            "RIGHT ARM":     (-0.01,  0.01),
        }),
    ],
}

# --- punch_east: unarmed forward punch ---
ANIMATIONS["punch_east"] = {
    "direction": "east",
    "frames": [
        # Frame 0: Wind up - pull right arm way back, body coils
        make_frame({
            "RIGHT SHOULDER": (-0.02,  0.01),
            "RIGHT ELBOW":   (-0.06,  0.00),
            "RIGHT ARM":     (-0.08, -0.02),
            "LEFT SHOULDER":  ( 0.01,  0.00),
            "LEFT ELBOW":    ( 0.02,  0.02),
            "LEFT ARM":      ( 0.02,  0.03),
            "NOSE":          (-0.01,  0.00),
            "NECK":          (-0.01,  0.00),
            "LEFT KNEE":     ( 0.01,  0.01),
            "RIGHT KNEE":    (-0.01,  0.01),
        }),
        # Frame 1: Strike - right fist extends far forward, body lunges
        make_frame({
            "RIGHT SHOULDER": ( 0.03, -0.01),
            "RIGHT ELBOW":   ( 0.06, -0.02),
            "RIGHT ARM":     ( 0.08, -0.03),
            "LEFT SHOULDER":  (-0.01,  0.01),
            "LEFT ELBOW":    (-0.02,  0.02),
            "LEFT ARM":      (-0.03,  0.03),
            "NOSE":          ( 0.02, -0.01),
            "NECK":          ( 0.02,  0.00),
            "LEFT HIP":      ( 0.02,  0.00),
            "RIGHT HIP":     ( 0.02,  0.00),
            "LEFT KNEE":     ( 0.02,  0.01),
            "RIGHT KNEE":    ( 0.01,  0.01),
        }),
        # Frame 2: Follow through - arm retracting
        make_frame({
            "RIGHT SHOULDER": ( 0.01,  0.00),
            "RIGHT ELBOW":   ( 0.03, -0.01),
            "RIGHT ARM":     ( 0.04, -0.01),
            "LEFT ELBOW":    (-0.01,  0.01),
            "LEFT ARM":      (-0.01,  0.01),
            "NOSE":          ( 0.01,  0.00),
        }),
    ],
}

# --- death_east: dying/falling ---
ANIMATIONS["death_east"] = {
    "direction": "east",
    "frames": [
        # Frame 0: Clutching chest, leaning back
        make_frame({
            "NOSE":          (-0.02, -0.01),
            "NECK":          (-0.02,  0.00),
            "LEFT SHOULDER":  (-0.02, -0.01),
            "RIGHT SHOULDER": (-0.02,  0.01),
            "RIGHT ELBOW":   ( 0.04, -0.04),
            "RIGHT ARM":     ( 0.06, -0.06),
            "LEFT ELBOW":    ( 0.03, -0.04),
            "LEFT ARM":      ( 0.05, -0.05),
            "LEFT KNEE":     ( 0.01,  0.02),
            "RIGHT KNEE":    (-0.01,  0.02),
        }),
        # Frame 1: Falling backward, knees buckling
        make_frame({
            "NOSE":          (-0.06,  0.04),
            "NECK":          (-0.05,  0.04),
            "LEFT EYE":      (-0.06,  0.04),
            "RIGHT EYE":     (-0.06,  0.04),
            "LEFT SHOULDER":  (-0.06,  0.05),
            "RIGHT SHOULDER": (-0.06,  0.06),
            "LEFT ELBOW":    (-0.04,  0.06),
            "LEFT ARM":      (-0.02,  0.04),
            "RIGHT ELBOW":   (-0.04,  0.06),
            "RIGHT ARM":     (-0.02,  0.04),
            "LEFT HIP":      (-0.03,  0.04),
            "RIGHT HIP":     (-0.03,  0.04),
            "LEFT KNEE":     (-0.02,  0.06),
            "RIGHT KNEE":    (-0.04,  0.06),
            "LEFT LEG":      ( 0.00,  0.06),
            "RIGHT LEG":     (-0.02,  0.06),
        }),
        # Frame 2: On the ground, limbs spread
        make_frame({
            "NOSE":          (-0.08,  0.08),
            "NECK":          (-0.07,  0.08),
            "LEFT EYE":      (-0.08,  0.08),
            "RIGHT EYE":     (-0.08,  0.08),
            "LEFT EAR":      (-0.08,  0.08),
            "RIGHT EAR":     (-0.08,  0.08),
            "LEFT SHOULDER":  (-0.06,  0.08),
            "RIGHT SHOULDER": (-0.08,  0.08),
            "LEFT ELBOW":    (-0.04,  0.07),
            "LEFT ARM":      (-0.02,  0.05),
            "RIGHT ELBOW":   (-0.08,  0.07),
            "RIGHT ARM":     (-0.08,  0.05),
            "LEFT HIP":      (-0.04,  0.07),
            "RIGHT HIP":     (-0.06,  0.07),
            "LEFT KNEE":     (-0.02,  0.08),
            "RIGHT KNEE":    (-0.06,  0.08),
            "LEFT LEG":      ( 0.02,  0.07),
            "RIGHT LEG":     (-0.08,  0.07),
        }),
    ],
}

# --- jump_east: jumping ---
ANIMATIONS["jump_east"] = {
    "direction": "east",
    "frames": [
        # Frame 0: Crouch before jump - deep knee bend, arms down
        make_frame({
            "NOSE":          ( 0.00,  0.04),
            "NECK":          ( 0.00,  0.04),
            "LEFT EYE":      ( 0.00,  0.04),
            "RIGHT EYE":     ( 0.00,  0.04),
            "LEFT SHOULDER":  ( 0.00,  0.04),
            "RIGHT SHOULDER": ( 0.00,  0.04),
            "LEFT ELBOW":    ( 0.01,  0.04),
            "LEFT ARM":      ( 0.02,  0.04),
            "RIGHT ELBOW":   (-0.01,  0.04),
            "RIGHT ARM":     (-0.02,  0.04),
            "LEFT HIP":      ( 0.00,  0.03),
            "RIGHT HIP":     ( 0.00,  0.03),
            "LEFT KNEE":     ( 0.03,  0.04),
            "RIGHT KNEE":    (-0.03,  0.04),
            "LEFT LEG":      ( 0.04,  0.03),
            "RIGHT LEG":     (-0.04,  0.03),
        }),
        # Frame 1: Peak of jump - body compressed upward, knees tucked, arms up
        make_frame({
            "NOSE":          ( 0.00, -0.06),
            "NECK":          ( 0.00, -0.06),
            "LEFT EYE":      ( 0.00, -0.06),
            "RIGHT EYE":     ( 0.00, -0.06),
            "LEFT EAR":      ( 0.00, -0.06),
            "RIGHT EAR":     ( 0.00, -0.06),
            "LEFT SHOULDER":  ( 0.00, -0.06),
            "RIGHT SHOULDER": ( 0.00, -0.06),
            "LEFT ELBOW":    ( 0.02, -0.08),
            "LEFT ARM":      ( 0.03, -0.08),
            "RIGHT ELBOW":   (-0.02, -0.08),
            "RIGHT ARM":     (-0.03, -0.08),
            "LEFT HIP":      ( 0.00, -0.04),
            "RIGHT HIP":     ( 0.00, -0.04),
            "LEFT KNEE":     ( 0.02, -0.03),
            "RIGHT KNEE":    (-0.02, -0.03),
            "LEFT LEG":      ( 0.03, -0.02),
            "RIGHT LEG":     (-0.03, -0.02),
        }),
        # Frame 2: Landing - legs extending down, arms spreading for balance
        make_frame({
            "NOSE":          ( 0.00,  0.01),
            "NECK":          ( 0.00,  0.01),
            "LEFT SHOULDER":  ( 0.01,  0.01),
            "RIGHT SHOULDER": (-0.01,  0.01),
            "LEFT ELBOW":    ( 0.04,  0.00),
            "LEFT ARM":      ( 0.06,  0.01),
            "RIGHT ELBOW":   (-0.04,  0.00),
            "RIGHT ARM":     (-0.06,  0.01),
            "LEFT HIP":      ( 0.00,  0.01),
            "RIGHT HIP":     ( 0.00,  0.01),
            "LEFT KNEE":     ( 0.02,  0.03),
            "RIGHT KNEE":    (-0.02,  0.03),
            "LEFT LEG":      ( 0.02,  0.02),
            "RIGHT LEG":     (-0.02,  0.02),
        }),
    ],
}

# ---------------------------------------------------------------------------
# 7. Run all generations
# ---------------------------------------------------------------------------

def main():
    print("PixelLab Animation Generator for Wiley")
    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"Reference image: wiley_char_canonical.png")
    print(f"Animations to generate: {len(ANIMATIONS)}")

    results = {}
    for name, config in ANIMATIONS.items():
        ok = generate(
            name=name,
            direction=config["direction"],
            frames=config["frames"],
            seed=123,
        )
        results[name] = "OK" if ok else "FAILED"

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    succeeded = sum(1 for v in results.values() if v == "OK")
    failed = sum(1 for v in results.values() if v == "FAILED")
    for name, status in results.items():
        marker = "+" if status == "OK" else "X"
        print(f"  [{marker}] {name}: {status}")
    print(f"\nTotal: {succeeded} succeeded, {failed} failed out of {len(results)}")


if __name__ == "__main__":
    main()
