#!/usr/bin/env python
"""Sprite animation pipeline for Deathblood Lazer.

Takes a canonical character sprite (PNG) and generates all animation sprite
sheets needed for the Godot beat-em-up game using the PixelLab API.

Two generation strategies:
  1. Skeleton-based (animate-with-skeleton) — combat/movement animations
  2. Text-based (animate-with-text-v3)      — idle/breathing animations

Usage:
    python sprite_pipeline.py --character wiley --canonical path/to/canonical.png --output path/to/output/
    python sprite_pipeline.py --character father_stu --canonical path/to/canonical.png --output path/to/output/
    python sprite_pipeline.py --character grunt --canonical path/to/canonical.png --output path/to/output/

    # Generate only specific animations:
    python sprite_pipeline.py --character wiley --canonical path/to/canonical.png --output path/to/output/ --only Idle Walk Attack_1

    # Skip expensive API calls and just assemble existing frames:
    python sprite_pipeline.py --assemble-only --frames-dir path/to/frames/ --output path/to/output/

    # Estimate skeleton keypoints for a new character:
    python sprite_pipeline.py --estimate-skeleton --canonical path/to/canonical.png

    # Dry run — show what would be generated without calling the API:
    python sprite_pipeline.py --character wiley --canonical path/to/canonical.png --output path/to/output/ --dry-run
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
from typing import Any

import requests
from PIL import Image

# ===========================================================================
# Constants
# ===========================================================================

FRAME_SIZE = 128  # PixelLab optimal generation size
SKELETON_API_URL = "https://api.pixellab.ai/v2/animate-with-skeleton"
TEXT_V3_API_URL = "https://api.pixellab.ai/v2/animate-with-text-v3"
ESTIMATE_SKELETON_URL = "https://api.pixellab.ai/v2/estimate-skeleton"
BACKGROUND_JOBS_URL = "https://api.pixellab.ai/v2/background-jobs"

# Async polling configuration
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
        raise RuntimeError(f"Could not load PixelLab config from ~/.claude.json: {e}")
    for arg in args:
        if arg.startswith("--secret="):
            return arg.split("=", 1)[1]
    raise RuntimeError("Could not find --secret= in pixellab MCP args")


# ===========================================================================
# Reference Image Loading
# ===========================================================================


def load_reference_image(path: str) -> str:
    """Load an image file and return its base64-encoded contents."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        raise RuntimeError(f"Canonical image not found: {path}")


# ===========================================================================
# Skeleton Keypoint System
# ===========================================================================

# Base keypoints tuned for Wiley's canonical pose (normalized 0-1 coords).
# For other characters, use --estimate-skeleton to get character-specific keypoints.
# fmt: off
WILEY_BASE_KEYPOINTS = [
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
# fmt: on


def make_frame(
    base_keypoints: list[dict[str, Any]],
    mods: dict[str, tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    """Return a frame (list of keypoint dicts) with optional delta modifications.

    Args:
        base_keypoints: The base skeleton keypoints to start from.
        mods: Dict of {label: (dx, dy)} offsets to apply on top of base keypoints.

    Returns:
        A list of keypoint dicts with modified positions, clamped to [0, 1].
    """
    if mods is None:
        mods = {}
    frame = []
    for kp in base_keypoints:
        new_kp = dict(kp)
        if kp["label"] in mods:
            dx, dy = mods[kp["label"]]
            new_kp["x"] = max(0.0, min(1.0, kp["x"] + dx))
            new_kp["y"] = max(0.0, min(1.0, kp["y"] + dy))
        frame.append(new_kp)
    return frame


def scale_mods(
    mods: dict[str, tuple[float, float]], factor: float
) -> dict[str, tuple[float, float]]:
    """Multiply all deltas in a mods dict by a scaling factor."""
    return {label: (dx * factor, dy * factor) for label, (dx, dy) in mods.items()}


# ===========================================================================
# Animation Definitions
# ===========================================================================

# Each animation is defined as a dict with:
#   "strategy": "skeleton" or "v3_text"
#   "direction": direction string (skeleton only)
#   "frames": list of frame mods dicts (skeleton only)
#   "action": text prompt (v3_text only)
#   "frame_count": number of frames (v3_text only)
#   "loop": whether to loop (v3_text only)


def _walk_frame_mods() -> list[dict[str, tuple[float, float]]]:
    """Return the 3-frame walk cycle modification dicts."""
    # fmt: off
    return [
        # Frame 0: Left leg forward, right back, arms swing opposite
        {
            "NOSE":          ( 0.005,  0.008),
            "NECK":          ( 0.003,  0.006),
            "LEFT EYE":      ( 0.003,  0.008),
            "RIGHT EYE":     ( 0.003,  0.008),
            "LEFT EAR":      ( 0.003,  0.008),
            "RIGHT EAR":     ( 0.003,  0.008),
            "LEFT HIP":      ( 0.02,   0.00),
            "LEFT KNEE":     ( 0.04,  -0.01),
            "LEFT LEG":      ( 0.06,   0.00),
            "RIGHT HIP":     (-0.02,   0.00),
            "RIGHT KNEE":    (-0.04,   0.01),
            "RIGHT LEG":     (-0.06,   0.00),
            "LEFT ELBOW":    (-0.02,   0.02),
            "LEFT ARM":      (-0.03,   0.03),
            "RIGHT ELBOW":   ( 0.02,  -0.02),
            "RIGHT ARM":     ( 0.03,  -0.03),
        },
        # Frame 1: Passing position, legs together
        {
            "NOSE":          ( 0.0,   -0.006),
            "NECK":          ( 0.0,   -0.004),
            "LEFT EYE":      ( 0.0,   -0.006),
            "RIGHT EYE":     ( 0.0,   -0.006),
            "LEFT EAR":      ( 0.0,   -0.006),
            "RIGHT EAR":     ( 0.0,   -0.006),
            "LEFT KNEE":     ( 0.00,  -0.005),
            "RIGHT KNEE":    ( 0.00,  -0.005),
        },
        # Frame 2: Right leg forward, left back, arms swing opposite
        {
            "NOSE":          ( 0.005,  0.008),
            "NECK":          ( 0.003,  0.006),
            "LEFT EYE":      ( 0.003,  0.008),
            "RIGHT EYE":     ( 0.003,  0.008),
            "LEFT EAR":      ( 0.003,  0.008),
            "RIGHT EAR":     ( 0.003,  0.008),
            "RIGHT HIP":     ( 0.02,   0.00),
            "RIGHT KNEE":    ( 0.04,  -0.01),
            "RIGHT LEG":     ( 0.06,   0.00),
            "LEFT HIP":      (-0.02,   0.00),
            "LEFT KNEE":     (-0.04,   0.01),
            "LEFT LEG":      (-0.06,   0.00),
            "RIGHT ELBOW":   (-0.02,   0.02),
            "RIGHT ARM":     (-0.03,   0.03),
            "LEFT ELBOW":    ( 0.02,  -0.02),
            "LEFT ARM":      ( 0.03,  -0.03),
        },
    ]
    # fmt: on


def build_animation_definitions(
    base_keypoints: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the full animation definitions dict using the given base keypoints.

    Returns a dict mapping output filename (without .png) to generation config.
    """
    walk_mods = _walk_frame_mods()

    # Run: same as walk but with 1.5x larger deltas for bigger strides
    run_mods = [scale_mods(m, 1.5) for m in walk_mods]

    animations: dict[str, dict[str, Any]] = {}

    # --- Idle: skeleton-based breathing ---
    # fmt: off
    idle_mods = [
        # Frame 0: neutral stance — weight centered, relaxed
        {},
        # Frame 1: inhale — chest expands, shoulders rise and widen, arms drift out, slight upward bob
        {
            "LEFT SHOULDER":  ( 0.02,  -0.03),
            "RIGHT SHOULDER": (-0.02,  -0.03),
            "LEFT ELBOW":     ( 0.03,  -0.02),
            "RIGHT ELBOW":    (-0.03,  -0.02),
            "LEFT ARM":       ( 0.03,  -0.015),
            "RIGHT ARM":      (-0.03,  -0.015),
            "NECK":           ( 0.0,   -0.015),
            "NOSE":           ( 0.0,   -0.02),
            "LEFT EYE":       ( 0.0,   -0.02),
            "RIGHT EYE":      ( 0.0,   -0.02),
            "LEFT EAR":       ( 0.0,   -0.015),
            "RIGHT EAR":      ( 0.0,   -0.015),
        },
        # Frame 2: exhale — shoulders drop below neutral, arms tuck in, slight downward settle
        {
            "LEFT SHOULDER":  (-0.01,   0.015),
            "RIGHT SHOULDER": ( 0.01,   0.015),
            "LEFT ELBOW":     (-0.015,  0.02),
            "RIGHT ELBOW":    ( 0.015,  0.02),
            "LEFT ARM":       (-0.015,  0.015),
            "RIGHT ARM":      ( 0.015,  0.015),
            "NECK":           ( 0.0,    0.008),
            "NOSE":           ( 0.0,    0.01),
            "LEFT EYE":       ( 0.0,    0.01),
            "RIGHT EYE":      ( 0.0,    0.01),
        },
    ]
    # fmt: on
    animations["Idle"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [make_frame(base_keypoints, m) for m in idle_mods],
    }

    # --- Walk: skeleton-based ---
    animations["Walk"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [make_frame(base_keypoints, m) for m in walk_mods],
    }

    # --- Run: skeleton-based (amplified walk) ---
    animations["Run"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [make_frame(base_keypoints, m) for m in run_mods],
    }

    # --- Jump: skeleton-based (crouch → wing leap) ---
    # fmt: off
    animations["Jump"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [
            # Frame 0: Deep crouch — coiled spring, knees wide, body compressed, arms/wings tucked tight
            make_frame(base_keypoints, {
                "NOSE":           ( 0.00,   0.07),
                "NECK":           ( 0.00,   0.06),
                "LEFT EYE":       ( 0.00,   0.07),
                "RIGHT EYE":      ( 0.00,   0.07),
                "LEFT EAR":       ( 0.00,   0.06),
                "RIGHT EAR":      ( 0.00,   0.06),
                "LEFT SHOULDER":  ( 0.01,   0.06),
                "RIGHT SHOULDER": (-0.01,   0.06),
                "LEFT ELBOW":     ( 0.02,   0.06),
                "LEFT ARM":       ( 0.02,   0.05),
                "RIGHT ELBOW":    (-0.02,   0.06),
                "RIGHT ARM":      (-0.02,   0.05),
                "LEFT HIP":       ( 0.01,   0.04),
                "RIGHT HIP":      (-0.01,   0.04),
                "LEFT KNEE":      ( 0.05,   0.05),
                "RIGHT KNEE":     (-0.05,   0.05),
                "LEFT LEG":       ( 0.06,   0.03),
                "RIGHT LEG":      (-0.06,   0.03),
            }),
            # Frame 1: Explosive launch — body shoots up, wings/arms spread WIDE and UP
            make_frame(base_keypoints, {
                "NOSE":           ( 0.00,  -0.10),
                "NECK":           ( 0.00,  -0.09),
                "LEFT EYE":       ( 0.00,  -0.10),
                "RIGHT EYE":      ( 0.00,  -0.10),
                "LEFT EAR":       ( 0.00,  -0.09),
                "RIGHT EAR":      ( 0.00,  -0.09),
                "LEFT SHOULDER":  ( 0.03,  -0.09),
                "RIGHT SHOULDER": (-0.03,  -0.09),
                "LEFT ELBOW":     ( 0.08,  -0.12),
                "LEFT ARM":       ( 0.12,  -0.10),
                "RIGHT ELBOW":    (-0.08,  -0.12),
                "RIGHT ARM":      (-0.12,  -0.10),
                "LEFT HIP":       ( 0.00,  -0.06),
                "RIGHT HIP":      ( 0.00,  -0.06),
                "LEFT KNEE":      ( 0.02,  -0.04),
                "RIGHT KNEE":     (-0.02,  -0.04),
                "LEFT LEG":       ( 0.03,  -0.02),
                "RIGHT LEG":      (-0.03,  -0.02),
            }),
            # Frame 2: Airborne — wings fully spread, legs tucked under, soaring
            make_frame(base_keypoints, {
                "NOSE":           ( 0.00,  -0.08),
                "NECK":           ( 0.00,  -0.07),
                "LEFT EYE":       ( 0.00,  -0.08),
                "RIGHT EYE":      ( 0.00,  -0.08),
                "LEFT EAR":       ( 0.00,  -0.07),
                "RIGHT EAR":      ( 0.00,  -0.07),
                "LEFT SHOULDER":  ( 0.04,  -0.07),
                "RIGHT SHOULDER": (-0.04,  -0.07),
                "LEFT ELBOW":     ( 0.10,  -0.06),
                "LEFT ARM":       ( 0.14,  -0.04),
                "RIGHT ELBOW":    (-0.10,  -0.06),
                "RIGHT ARM":      (-0.14,  -0.04),
                "LEFT HIP":       ( 0.00,  -0.05),
                "RIGHT HIP":      ( 0.00,  -0.05),
                "LEFT KNEE":      ( 0.03,  -0.02),
                "RIGHT KNEE":     (-0.03,  -0.02),
                "LEFT LEG":       ( 0.04,   0.00),
                "RIGHT LEG":      (-0.04,   0.00),
            }),
        ],
    }
    # fmt: on

    # --- Attack_1: light jab (punch_east) ---
    animations["Attack_1"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [
            # Frame 0: Wind up — pull right arm back, body coils
            make_frame(base_keypoints, {
                "RIGHT SHOULDER": (-0.02,   0.01),
                "RIGHT ELBOW":    (-0.06,   0.00),
                "RIGHT ARM":      (-0.08,  -0.02),
                "LEFT SHOULDER":  ( 0.01,   0.00),
                "LEFT ELBOW":     ( 0.02,   0.02),
                "LEFT ARM":       ( 0.02,   0.03),
                "NOSE":           (-0.01,   0.00),
                "NECK":           (-0.01,   0.00),
                "LEFT KNEE":      ( 0.01,   0.01),
                "RIGHT KNEE":     (-0.01,   0.01),
            }),
            # Frame 1: Strike — right fist extends far forward, body lunges
            make_frame(base_keypoints, {
                "RIGHT SHOULDER": ( 0.03,  -0.01),
                "RIGHT ELBOW":    ( 0.06,  -0.02),
                "RIGHT ARM":      ( 0.08,  -0.03),
                "LEFT SHOULDER":  (-0.01,   0.01),
                "LEFT ELBOW":     (-0.02,   0.02),
                "LEFT ARM":       (-0.03,   0.03),
                "NOSE":           ( 0.02,  -0.01),
                "NECK":           ( 0.02,   0.00),
                "LEFT HIP":       ( 0.02,   0.00),
                "RIGHT HIP":      ( 0.02,   0.00),
                "LEFT KNEE":      ( 0.02,   0.01),
                "RIGHT KNEE":     ( 0.01,   0.01),
            }),
            # Frame 2: Follow through — arm retracting
            make_frame(base_keypoints, {
                "RIGHT SHOULDER": ( 0.01,   0.00),
                "RIGHT ELBOW":    ( 0.03,  -0.01),
                "RIGHT ARM":      ( 0.04,  -0.01),
                "LEFT ELBOW":     (-0.01,   0.01),
                "LEFT ARM":       (-0.01,   0.01),
                "NOSE":           ( 0.01,   0.00),
            }),
        ],
    }

    # --- Attack_2: heavy cross (wide horizontal swing) ---
    animations["Attack_2"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [
            # Frame 0: Wind up — LEFT arm pulled back, torso rotates, weight shifts back
            make_frame(base_keypoints, {
                "LEFT SHOULDER":  (-0.04,  -0.01),
                "LEFT ELBOW":     (-0.08,   0.00),
                "LEFT ARM":       (-0.10,  -0.02),
                "RIGHT SHOULDER": ( 0.02,   0.01),
                "RIGHT ELBOW":    ( 0.03,   0.02),
                "RIGHT ARM":      ( 0.03,   0.03),
                "NOSE":           (-0.02,   0.00),
                "NECK":           (-0.02,   0.01),
                "LEFT HIP":       (-0.02,   0.00),
                "RIGHT HIP":      (-0.01,   0.01),
                "LEFT KNEE":      (-0.02,   0.01),
                "RIGHT KNEE":     (-0.03,   0.01),
                "LEFT LEG":       (-0.03,   0.00),
                "RIGHT LEG":      (-0.04,   0.00),
            }),
            # Frame 1: Strike — LEFT arm swings wide across body, torso follows, front foot steps
            make_frame(base_keypoints, {
                "LEFT SHOULDER":  ( 0.04,  -0.02),
                "LEFT ELBOW":     ( 0.08,  -0.03),
                "LEFT ARM":       ( 0.10,  -0.04),
                "RIGHT SHOULDER": (-0.02,   0.01),
                "RIGHT ELBOW":    (-0.03,   0.02),
                "RIGHT ARM":      (-0.04,   0.03),
                "NOSE":           ( 0.03,  -0.01),
                "NECK":           ( 0.03,   0.00),
                "LEFT HIP":       ( 0.03,   0.00),
                "RIGHT HIP":      ( 0.02,   0.00),
                "LEFT KNEE":      ( 0.04,   0.01),
                "RIGHT KNEE":     ( 0.02,   0.01),
                "LEFT LEG":       ( 0.05,   0.00),
                "RIGHT LEG":      ( 0.01,   0.00),
            }),
            # Frame 2: Follow through — arm extends past center, body recovers
            make_frame(base_keypoints, {
                "LEFT SHOULDER":  ( 0.02,   0.00),
                "LEFT ELBOW":     ( 0.05,  -0.01),
                "LEFT ARM":       ( 0.06,  -0.01),
                "RIGHT SHOULDER": (-0.01,   0.00),
                "RIGHT ELBOW":    (-0.01,   0.01),
                "RIGHT ARM":      (-0.01,   0.01),
                "NOSE":           ( 0.01,   0.00),
                "NECK":           ( 0.01,   0.00),
                "LEFT KNEE":      ( 0.01,   0.00),
                "RIGHT KNEE":     ( 0.01,   0.00),
            }),
        ],
    }

    # --- Attack_3: overhead slam (both arms up then down) ---
    animations["Attack_3"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [
            # Frame 0: Both arms raised high overhead
            make_frame(base_keypoints, {
                "LEFT SHOULDER":  ( 0.00,  -0.03),
                "RIGHT SHOULDER": ( 0.00,  -0.03),
                "LEFT ELBOW":     ( 0.02,  -0.10),
                "RIGHT ELBOW":    (-0.02,  -0.10),
                "LEFT ARM":       ( 0.01,  -0.14),
                "RIGHT ARM":      (-0.01,  -0.14),
                "NOSE":           ( 0.00,  -0.02),
                "NECK":           ( 0.00,  -0.02),
                "LEFT EYE":       ( 0.00,  -0.02),
                "RIGHT EYE":      ( 0.00,  -0.02),
                "LEFT HIP":       ( 0.00,  -0.01),
                "RIGHT HIP":      ( 0.00,  -0.01),
                "LEFT KNEE":      ( 0.01,   0.00),
                "RIGHT KNEE":     (-0.01,   0.00),
            }),
            # Frame 1: Arms slam down forcefully, body crouches
            make_frame(base_keypoints, {
                "LEFT SHOULDER":  ( 0.02,   0.03),
                "RIGHT SHOULDER": (-0.02,   0.03),
                "LEFT ELBOW":     ( 0.04,   0.06),
                "RIGHT ELBOW":    (-0.04,   0.06),
                "LEFT ARM":       ( 0.05,   0.08),
                "RIGHT ARM":      (-0.05,   0.08),
                "NOSE":           ( 0.01,   0.04),
                "NECK":           ( 0.01,   0.04),
                "LEFT EYE":       ( 0.01,   0.04),
                "RIGHT EYE":      ( 0.01,   0.04),
                "LEFT HIP":       ( 0.00,   0.03),
                "RIGHT HIP":      ( 0.00,   0.03),
                "LEFT KNEE":      ( 0.02,   0.04),
                "RIGHT KNEE":     (-0.02,   0.04),
                "LEFT LEG":       ( 0.02,   0.02),
                "RIGHT LEG":      (-0.02,   0.02),
            }),
            # Frame 2: Impact recovery — arms at sides, slight bounce
            make_frame(base_keypoints, {
                "LEFT SHOULDER":  ( 0.01,   0.01),
                "RIGHT SHOULDER": (-0.01,   0.01),
                "LEFT ELBOW":     ( 0.02,   0.02),
                "RIGHT ELBOW":    (-0.02,   0.02),
                "LEFT ARM":       ( 0.02,   0.02),
                "RIGHT ARM":      (-0.02,   0.02),
                "NOSE":           ( 0.00,   0.01),
                "NECK":           ( 0.00,   0.01),
                "LEFT HIP":       ( 0.00,   0.01),
                "RIGHT HIP":      ( 0.00,   0.01),
                "LEFT KNEE":      ( 0.01,   0.01),
                "RIGHT KNEE":     (-0.01,   0.01),
            }),
        ],
    }

    # --- Hurt: taking damage recoil ---
    animations["Hurt"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [
            # Frame 0: Impact — head snaps back, body recoils, arms flung back
            make_frame(base_keypoints, {
                "NOSE":           (-0.04,  -0.02),
                "NECK":           (-0.03,  -0.01),
                "LEFT EYE":       (-0.04,  -0.02),
                "RIGHT EYE":      (-0.04,  -0.02),
                "LEFT SHOULDER":  (-0.05,  -0.02),
                "RIGHT SHOULDER": (-0.05,  -0.02),
                "LEFT ELBOW":     (-0.07,  -0.01),
                "LEFT ARM":       (-0.08,   0.02),
                "RIGHT ELBOW":    (-0.07,  -0.01),
                "RIGHT ARM":      (-0.08,   0.02),
                "LEFT HIP":       (-0.02,   0.01),
                "RIGHT HIP":      (-0.02,   0.01),
                "LEFT KNEE":      (-0.01,   0.02),
                "RIGHT KNEE":     (-0.01,   0.02),
            }),
            # Frame 1: Staggering — leaning back
            make_frame(base_keypoints, {
                "NOSE":           (-0.03,  -0.01),
                "NECK":           (-0.02,   0.00),
                "LEFT SHOULDER":  (-0.03,  -0.01),
                "RIGHT SHOULDER": (-0.03,  -0.01),
                "LEFT ELBOW":     (-0.04,   0.01),
                "LEFT ARM":       (-0.05,   0.03),
                "RIGHT ELBOW":    (-0.04,   0.01),
                "RIGHT ARM":      (-0.05,   0.03),
                "LEFT KNEE":      ( 0.01,   0.01),
                "RIGHT KNEE":     ( 0.01,   0.01),
            }),
            # Frame 2: Recovering — straightening up
            make_frame(base_keypoints, {
                "NOSE":           (-0.01,   0.00),
                "NECK":           (-0.01,   0.00),
                "LEFT ELBOW":     (-0.01,   0.01),
                "LEFT ARM":       (-0.01,   0.01),
                "RIGHT ELBOW":    (-0.01,   0.01),
                "RIGHT ARM":      (-0.01,   0.01),
            }),
        ],
    }

    # --- Dead: dying/falling ---
    animations["Dead"] = {
        "strategy": "skeleton",
        "direction": "east",
        "frames": [
            # Frame 0: Clutching chest, leaning back
            make_frame(base_keypoints, {
                "NOSE":           (-0.02,  -0.01),
                "NECK":           (-0.02,   0.00),
                "LEFT SHOULDER":  (-0.02,  -0.01),
                "RIGHT SHOULDER": (-0.02,   0.01),
                "RIGHT ELBOW":    ( 0.04,  -0.04),
                "RIGHT ARM":      ( 0.06,  -0.06),
                "LEFT ELBOW":     ( 0.03,  -0.04),
                "LEFT ARM":       ( 0.05,  -0.05),
                "LEFT KNEE":      ( 0.01,   0.02),
                "RIGHT KNEE":     (-0.01,   0.02),
            }),
            # Frame 1: Falling backward, knees buckling
            make_frame(base_keypoints, {
                "NOSE":           (-0.06,   0.04),
                "NECK":           (-0.05,   0.04),
                "LEFT EYE":       (-0.06,   0.04),
                "RIGHT EYE":      (-0.06,   0.04),
                "LEFT SHOULDER":  (-0.06,   0.05),
                "RIGHT SHOULDER": (-0.06,   0.06),
                "LEFT ELBOW":     (-0.04,   0.06),
                "LEFT ARM":       (-0.02,   0.04),
                "RIGHT ELBOW":    (-0.04,   0.06),
                "RIGHT ARM":      (-0.02,   0.04),
                "LEFT HIP":       (-0.03,   0.04),
                "RIGHT HIP":      (-0.03,   0.04),
                "LEFT KNEE":      (-0.02,   0.06),
                "RIGHT KNEE":     (-0.04,   0.06),
                "LEFT LEG":       ( 0.00,   0.06),
                "RIGHT LEG":      (-0.02,   0.06),
            }),
            # Frame 2: On the ground, limbs spread
            make_frame(base_keypoints, {
                "NOSE":           (-0.08,   0.08),
                "NECK":           (-0.07,   0.08),
                "LEFT EYE":       (-0.08,   0.08),
                "RIGHT EYE":      (-0.08,   0.08),
                "LEFT EAR":       (-0.08,   0.08),
                "RIGHT EAR":      (-0.08,   0.08),
                "LEFT SHOULDER":  (-0.06,   0.08),
                "RIGHT SHOULDER": (-0.08,   0.08),
                "LEFT ELBOW":     (-0.04,   0.07),
                "LEFT ARM":       (-0.02,   0.05),
                "RIGHT ELBOW":    (-0.08,   0.07),
                "RIGHT ARM":      (-0.08,   0.05),
                "LEFT HIP":       (-0.04,   0.07),
                "RIGHT HIP":      (-0.06,   0.07),
                "LEFT KNEE":      (-0.02,   0.08),
                "RIGHT KNEE":     (-0.06,   0.08),
                "LEFT LEG":       ( 0.02,   0.07),
                "RIGHT LEG":      (-0.08,   0.07),
            }),
        ],
    }

    return animations


# ===========================================================================
# Image Decoding
# ===========================================================================


def decode_image(img_data: dict[str, Any]) -> Image.Image:
    """Decode an image dict from the PixelLab API response.

    Handles two formats:
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


def extract_images(response_json: dict[str, Any]) -> list[dict[str, Any]]:
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


# ===========================================================================
# Sprite Sheet Assembly
# ===========================================================================


def assemble_sprite_sheet(frames: list[Image.Image], output_path: str) -> None:
    """Concatenate frame images horizontally into a single sprite sheet PNG."""
    if not frames:
        print(f"  WARNING: No frames to assemble for {output_path}")
        return

    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        # Resize if needed (shouldn't happen, but safety check)
        if frame.size != (w, h):
            frame = frame.resize((w, h), Image.NEAREST)
        sheet.paste(frame, (i * w, 0))
    sheet.save(output_path)
    print(f"  Sheet saved: {output_path} ({len(frames)} frames, {w * len(frames)}x{h})")


# ===========================================================================
# API Generation Functions
# ===========================================================================


def generate_skeleton_anim(
    name: str,
    direction: str,
    frames: list[list[dict[str, Any]]],
    reference_b64: str,
    api_key: str,
    seed: int = 123,
) -> tuple[list[Image.Image] | None, float]:
    """Generate animation frames via the animate-with-skeleton endpoint.

    Args:
        name: Animation name (for logging).
        direction: Direction string ("east", "south", etc.).
        frames: List of frame keypoint lists.
        reference_b64: Base64-encoded reference image.
        api_key: PixelLab API key.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (list of PIL Images or None, USD cost as float).
    """
    print(f"\n{'='*60}")
    print(f"Generating: {name} (skeleton, direction={direction}, {len(frames)} frames, seed={seed})")
    print(f"{'='*60}")

    payload = {
        "image_size": {"width": FRAME_SIZE, "height": FRAME_SIZE},
        "skeleton_keypoints": frames,
        "direction": direction,
        "view": "side",
        "guidance_scale": 7.0,
        "isometric": False,
        "oblique_projection": False,
        "reference_image": {
            "type": "base64",
            "base64": reference_b64,
            "format": "png",
        },
        "init_image_strength": 300,
        "seed": seed,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(
            SKELETON_API_URL, json=payload, headers=headers, timeout=120
        )
        print(f"  Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"  Error: {resp.text[:500]}")
            return (None, 0.0)

        result = resp.json()
        images_data = result.get("images", [])
        if not images_data:
            print(f"  WARNING: No images in response. Keys: {list(result.keys())}")
            return (None, 0.0)

        decoded = []
        for img_obj in images_data:
            decoded.append(decode_image(img_obj))

        # Print cost
        usage = result.get("usage", {})
        cost = usage.get("usd", 0.0)
        if cost:
            print(f"  Cost: ${cost:.4f}")

        print(f"  Success: {len(decoded)} frames generated")
        return (decoded, cost)

    except requests.exceptions.Timeout:
        print("  Error: Request timed out (120s)")
        return (None, 0.0)
    except Exception as e:
        import traceback
        print(f"  Error: {e}")
        print(traceback.format_exc())
        return (None, 0.0)


def generate_v3_anim(
    name: str,
    action: str,
    frame_count: int,
    reference_b64: str,
    api_key: str,
    seed: int = 123,
    loop: bool = False,
) -> tuple[list[Image.Image] | None, float]:
    """Generate animation frames via the animate-with-text-v3 endpoint.

    This endpoint is ASYNC — returns a background_job_id that must be polled.

    Args:
        name: Animation name (for logging).
        action: Text description of the animation action.
        frame_count: Number of frames (must be even, 4-16).
        reference_b64: Base64-encoded reference image.
        api_key: PixelLab API key.
        seed: Random seed for reproducibility.
        loop: If True, set last_frame = first_frame for looping.

    Returns:
        Tuple of (list of PIL Images or None, USD cost as float).
    """
    print(f"\n{'='*60}")
    print(f"Generating: {name} (v3_text, action='{action}', {frame_count} frames, seed={seed})")
    print(f"{'='*60}")

    payload: dict[str, Any] = {
        "first_frame": {
            "type": "base64",
            "base64": reference_b64,
            "format": "png",
        },
        "action": action,
        "frame_count": frame_count,
        "no_background": True,
        "seed": seed,
    }

    if loop:
        payload["last_frame"] = payload["first_frame"]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(
            TEXT_V3_API_URL, json=payload, headers=headers, timeout=120
        )
        print(f"  Status: {resp.status_code}")

        if resp.status_code not in (200, 202):
            print(f"  Error: {resp.text[:500]}")
            return (None, 0.0)

        data = resp.json()

        # Check if this is an async job
        job_id = data.get("job_id") or data.get("background_job_id")
        if job_id and "images" not in data:
            print(f"  Async job: {job_id}")
            print(f"  Polling every {POLL_INTERVAL_SECONDS}s (timeout {POLL_TIMEOUT_SECONDS}s)...")
            poll_url = f"{BACKGROUND_JOBS_URL}/{job_id}"
            poll_headers = {"Authorization": f"Bearer {api_key}"}

            max_attempts = POLL_TIMEOUT_SECONDS // POLL_INTERVAL_SECONDS
            consecutive_404s = 0
            for attempt in range(1, max_attempts + 1):
                time.sleep(POLL_INTERVAL_SECONDS)
                try:
                    poll_resp = requests.get(
                        poll_url, headers=poll_headers, timeout=30
                    )
                except Exception as e:
                    print(f"  [{attempt}] Poll error: {e}")
                    continue

                if poll_resp.status_code == 404:
                    consecutive_404s += 1
                    print(f"  [{attempt}] Job not found (404) [{consecutive_404s}/3]")
                    if consecutive_404s >= 3:
                        print("  Error: 3 consecutive 404s — job likely invalid")
                        return (None, 0.0)
                    continue
                else:
                    consecutive_404s = 0
                if poll_resp.status_code != 200:
                    print(f"  [{attempt}] HTTP {poll_resp.status_code}")
                    continue

                data = poll_resp.json()
                status = data.get("status", "unknown")

                # Check for images in last_response
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
                    return (None, 0.0)
                if attempt % 10 == 0:
                    print(f"  [{attempt}] {status}...")
            else:
                print(f"  Error: Job did not complete after {POLL_TIMEOUT_SECONDS}s")
                return (None, 0.0)

        # Extract and decode images
        images_data = extract_images(data)
        print(f"  Received {len(images_data)} frames")

        decoded = []
        for img_obj in images_data:
            decoded.append(decode_image(img_obj))

        # Extract cost
        cost = 0.0
        for key in ["cost", "credits_used", "usage"]:
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    c = val.get("usd", 0.0)
                    if isinstance(c, (int, float)):
                        cost = float(c)
                        print(f"  Cost: ${cost:.4f}")
                    else:
                        print(f"  {key}: {val}")
                elif isinstance(val, (int, float)):
                    cost = float(val)
                    print(f"  {key}: {val}")
                break

        print(f"  Success: {len(decoded)} frames generated")
        return (decoded, cost)

    except requests.exceptions.Timeout:
        print("  Error: Request timed out (120s)")
        return (None, 0.0)
    except Exception as e:
        import traceback
        print(f"  Error: {e}")
        print(traceback.format_exc())
        return (None, 0.0)


# ===========================================================================
# Skeleton Estimation
# ===========================================================================


def estimate_skeleton_from_image(
    reference_b64: str, api_key: str
) -> list[dict[str, Any]] | None:
    """Estimate skeleton keypoints from a reference image.

    Uses the PixelLab estimate-skeleton endpoint to detect the character pose.

    Args:
        reference_b64: Base64-encoded reference image.
        api_key: PixelLab API key.

    Returns:
        List of keypoint dicts on success, None on failure.
    """
    print(f"\n{'='*60}")
    print("Estimating skeleton keypoints from reference image...")
    print(f"{'='*60}")

    payload = {
        "image": {
            "type": "base64",
            "base64": reference_b64,
            "format": "png",
        },
        "image_size": {"width": FRAME_SIZE, "height": FRAME_SIZE},
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(
            ESTIMATE_SKELETON_URL, json=payload, headers=headers, timeout=60
        )
        print(f"  Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"  Error: {resp.text[:500]}")
            return None

        result = resp.json()
        keypoints = result.get("keypoints", result.get("skeleton_keypoints", []))

        if not keypoints:
            print(f"  WARNING: No keypoints in response. Keys: {list(result.keys())}")
            print(f"  Response preview: {json.dumps(result, indent=2)[:500]}")
            return None

        usage = result.get("usage", {})
        if usage:
            print(f"  Cost: ${usage.get('usd', 0):.4f}")

        print(f"  Success: {len(keypoints)} keypoints detected")
        return keypoints

    except Exception as e:
        print(f"  Error: {e}")
        return None


# ===========================================================================
# CLI Argument Parsing
# ===========================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sprite animation pipeline for Deathblood Lazer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--character",
        type=str,
        default="wiley",
        help="Character name (wiley, father_stu, grunt, etc.). Default: wiley",
    )
    parser.add_argument(
        "--canonical",
        type=str,
        help="Path to the canonical character sprite PNG (required unless --assemble-only)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output directory for sprite sheets (required unless --estimate-skeleton)",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="ANIM",
        help="Generate only these animations (e.g. --only Idle Walk Attack_1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=123,
        help="Random seed for reproducibility. Default: 123",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling the API",
    )
    parser.add_argument(
        "--assemble-only",
        action="store_true",
        help="Skip API calls — just assemble existing frames into sheets",
    )
    parser.add_argument(
        "--frames-dir",
        type=str,
        help="Directory containing individual frame PNGs (used with --assemble-only)",
    )
    parser.add_argument(
        "--estimate-skeleton",
        action="store_true",
        help="Estimate skeleton keypoints from the canonical image and print them",
    )
    parser.add_argument(
        "--keypoints-json",
        type=str,
        help="Path to a JSON file with custom base keypoints (overrides built-in Wiley keypoints)",
    )

    return parser.parse_args()


# ===========================================================================
# Main Pipeline
# ===========================================================================


def run_assemble_only(frames_dir: str, output_dir: str, only: list[str] | None) -> None:
    """Assemble existing frame PNGs into sprite sheets without calling the API."""
    frames_path = Path(frames_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not frames_path.exists():
        print(f"Error: Frames directory does not exist: {frames_dir}")
        sys.exit(1)

    # Discover animations from frame files: {AnimName}_frame{N}.png
    anim_frames: dict[str, list[tuple[int, Image.Image]]] = {}
    for f in sorted(frames_path.glob("*_frame*.png")):
        # Parse: AnimName_frameN.png
        stem = f.stem  # e.g. "Walk_frame0"
        parts = stem.rsplit("_frame", 1)
        if len(parts) != 2:
            continue
        anim_name = parts[0]
        try:
            frame_idx = int(parts[1])
        except ValueError:
            continue

        if only and anim_name not in only:
            continue

        if anim_name not in anim_frames:
            anim_frames[anim_name] = []
        try:
            anim_frames[anim_name].append((frame_idx, Image.open(f).convert("RGBA")))
        except Exception as e:
            print(f"  WARNING: Skipping bad frame file {f.name}: {e}")
            continue

    if not anim_frames:
        print("No frame files found matching pattern {AnimName}_frame{N}.png")
        sys.exit(1)

    for anim_name, indexed_frames in sorted(anim_frames.items()):
        indexed_frames.sort(key=lambda x: x[0])
        frames = [img for _, img in indexed_frames]
        sheet_path = str(output_path / f"{anim_name}.png")
        assemble_sprite_sheet(frames, sheet_path)

    print(f"\nAssembly complete: {len(anim_frames)} sheets in {output_dir}")


def run_estimate_skeleton(canonical_path: str) -> None:
    """Estimate and print skeleton keypoints for a character image."""
    api_key = load_api_key()
    reference_b64 = load_reference_image(canonical_path)
    keypoints = estimate_skeleton_from_image(reference_b64, api_key)

    if keypoints is None:
        print("\nFailed to estimate skeleton.")
        sys.exit(1)

    print("\n# Estimated keypoints — copy into a JSON file or use directly:")
    print(json.dumps(keypoints, indent=2))
    print(f"\n# Total: {len(keypoints)} keypoints")
    print("# Save to a file and pass with --keypoints-json to use for animation generation.")


def run_pipeline(
    character: str,
    canonical_path: str,
    output_dir: str,
    only: list[str] | None,
    seed: int,
    dry_run: bool,
    custom_keypoints: list[dict[str, Any]] | None,
) -> None:
    """Run the full animation generation pipeline."""
    # Determine base keypoints
    if custom_keypoints:
        base_keypoints = custom_keypoints
        print(f"Using custom keypoints ({len(base_keypoints)} points)")
    elif character == "wiley":
        base_keypoints = WILEY_BASE_KEYPOINTS
        print(f"Using built-in Wiley keypoints ({len(base_keypoints)} points)")
    else:
        # For non-Wiley characters without custom keypoints, estimate from image
        print(f"Character '{character}' has no built-in keypoints. Estimating from image...")
        if dry_run:
            print("  (dry-run: would estimate skeleton from canonical image)")
            base_keypoints = WILEY_BASE_KEYPOINTS  # placeholder for dry-run
        else:
            api_key = load_api_key()
            reference_b64 = load_reference_image(canonical_path)
            estimated = estimate_skeleton_from_image(reference_b64, api_key)
            if estimated is None:
                print("Failed to estimate skeleton. Use --keypoints-json to provide custom keypoints.")
                sys.exit(1)
            base_keypoints = estimated
            # Save estimated keypoints for reuse
            kp_save_path = os.path.join(output_dir, f"{character}_keypoints.json")
            os.makedirs(output_dir, exist_ok=True)
            with open(kp_save_path, "w") as f:
                json.dump(base_keypoints, f, indent=2)
            print(f"  Saved estimated keypoints to: {kp_save_path}")

    # Build animation definitions
    animations = build_animation_definitions(base_keypoints)

    # Filter if --only specified
    if only:
        filtered = {}
        for name in only:
            if name in animations:
                filtered[name] = animations[name]
            else:
                print(f"WARNING: Unknown animation '{name}'. Available: {', '.join(animations.keys())}")
        animations = filtered

    if not animations:
        print("No animations to generate.")
        sys.exit(1)

    # Setup output directories
    output_path = Path(output_dir)
    frames_path = output_path / "frames"
    output_path.mkdir(parents=True, exist_ok=True)
    frames_path.mkdir(parents=True, exist_ok=True)

    print(f"\nCharacter:  {character}")
    print(f"Canonical:  {canonical_path}")
    print(f"Output:     {output_dir}")
    print(f"Seed:       {seed}")
    print(f"Animations: {len(animations)} ({', '.join(animations.keys())})")

    if dry_run:
        print("\n--- DRY RUN ---")
        for name, config in animations.items():
            strategy = config["strategy"]
            if strategy == "skeleton":
                n_frames = len(config["frames"])
                direction = config["direction"]
                print(f"  {name:12s}  skeleton  {n_frames} frames  direction={direction}")
            elif strategy == "v3_text":
                n_frames = config["frame_count"]
                action = config["action"]
                loop = config.get("loop", False)
                print(f"  {name:12s}  v3_text   {n_frames} frames  action='{action}'  loop={loop}")
        print("\nNo API calls made (dry run).")
        return

    # Load API resources
    api_key = load_api_key()
    reference_b64 = load_reference_image(canonical_path)

    print("\nAPI Key: loaded")

    # Generate each animation
    results: dict[str, str] = {}
    total_cost = 0.0
    total_frames = 0

    for name, config in animations.items():
        strategy = config["strategy"]
        frame_images: list[Image.Image] | None = None

        if strategy == "skeleton":
            frame_images, cost = generate_skeleton_anim(
                name=name,
                direction=config["direction"],
                frames=config["frames"],
                reference_b64=reference_b64,
                api_key=api_key,
                seed=seed,
            )
            total_cost += cost
        elif strategy == "v3_text":
            frame_images, cost = generate_v3_anim(
                name=name,
                action=config["action"],
                frame_count=config["frame_count"],
                reference_b64=reference_b64,
                api_key=api_key,
                seed=seed,
                loop=config.get("loop", False),
            )
            total_cost += cost

        if frame_images is None:
            results[name] = "FAILED"
            continue

        # Save individual frames for debugging
        for i, img in enumerate(frame_images):
            frame_path = str(frames_path / f"{name}_frame{i}.png")
            img.save(frame_path)

        # Assemble sprite sheet
        sheet_path = str(output_path / f"{name}.png")
        assemble_sprite_sheet(frame_images, sheet_path)

        total_frames += len(frame_images)
        results[name] = "OK"

    # Summary
    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print(f"{'='*60}")

    succeeded = sum(1 for v in results.values() if v == "OK")
    failed = sum(1 for v in results.values() if v == "FAILED")

    for name, status in results.items():
        marker = "+" if status == "OK" else "X"
        print(f"  [{marker}] {name}: {status}")

    print(f"\nAnimations: {succeeded} succeeded, {failed} failed out of {len(results)}")
    print(f"Total frames: {total_frames}")
    print(f"Output directory: {output_dir}")
    print(f"Individual frames: {frames_path}")
    if total_cost > 0:
        print(f"Total API cost: ${total_cost:.4f}")

    if failed > 0:
        print(f"\nWARNING: {failed} animation(s) failed. Check logs above for details.")
        sys.exit(1)


# ===========================================================================
# Entry Point
# ===========================================================================


def main() -> None:
    """Main entry point for the sprite pipeline."""
    args = parse_args()

    print("=" * 60)
    print("  Deathblood Lazer — Sprite Animation Pipeline")
    print("=" * 60)

    # Mode: estimate skeleton
    if args.estimate_skeleton:
        if not args.canonical:
            print("Error: --canonical is required with --estimate-skeleton")
            sys.exit(1)
        run_estimate_skeleton(args.canonical)
        return

    # Mode: assemble only
    if args.assemble_only:
        frames_dir = args.frames_dir
        if not frames_dir:
            if args.output:
                frames_dir = os.path.join(args.output, "frames")
            else:
                print("Error: --frames-dir or --output is required with --assemble-only")
                sys.exit(1)
        if not args.output:
            print("Error: --output is required with --assemble-only")
            sys.exit(1)
        run_assemble_only(frames_dir, args.output, args.only)
        return

    # Mode: full pipeline
    if not args.canonical:
        print("Error: --canonical is required (path to canonical character sprite)")
        sys.exit(1)
    if not args.output:
        print("Error: --output is required (output directory for sprite sheets)")
        sys.exit(1)

    # Load custom keypoints if provided
    custom_keypoints = None
    if args.keypoints_json:
        with open(args.keypoints_json, "r") as f:
            custom_keypoints = json.load(f)
        print(f"Loaded custom keypoints from: {args.keypoints_json}")

    run_pipeline(
        character=args.character,
        canonical_path=args.canonical,
        output_dir=args.output,
        only=args.only,
        seed=args.seed,
        dry_run=args.dry_run,
        custom_keypoints=custom_keypoints,
    )


if __name__ == "__main__":
    main()
