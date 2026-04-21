"""
Generate inpainting masks for Father Stu attack animation frames.

Creates 3 masks (228x228) for different attack swing phases:
  1. windup    — arms raised overhead
  2. midswing  — mid-swing at ~45 degrees to the right
  3. followthrough — follow-through completion, arms low-right

White = areas to repaint (arms, weapon sweep space)
Black = areas to keep  (face, chest core, legs)

Character analysis (from alpha channel):
  Bounding box:  y=59..170, x=71..150  (80x112 px)
  Center:        (110, 114)
  Head zone:     y=59..92   (top 30%)
  Torso zone:    y=92..126  (mid 30%)
  Legs zone:     y=126..170 (bottom 40%)
  Widest row:    y≈126, x=72..149  (78 px)
"""

from pathlib import Path
from PIL import Image, ImageDraw

SIZE = 228
OUT_DIR = Path(__file__).resolve().parent.parent / "assets/sprites/characters/father_stu/frames/inpaint"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Character landmark coordinates (from alpha-channel analysis)
# ---------------------------------------------------------------------------
# Bounding box
CHAR_TOP = 59
CHAR_BOT = 170
CHAR_LEFT = 71
CHAR_RIGHT = 150
CHAR_CX = 110   # horizontal center
CHAR_CY = 114   # vertical center

# Zones (vertical)
HEAD_TOP = CHAR_TOP
HEAD_BOT = 92
TORSO_TOP = 92
TORSO_BOT = 126
LEGS_TOP = 126
LEGS_BOT = CHAR_BOT

# Face/head center box — always keep this protected
FACE_LEFT = 88
FACE_RIGHT = 132
FACE_TOP = HEAD_TOP
FACE_BOT = HEAD_BOT + 4  # small padding below head zone

# Chest core — narrow vertical strip we want to keep
CHEST_LEFT = 92
CHEST_RIGHT = 128
CHEST_TOP = TORSO_TOP
CHEST_BOT = TORSO_BOT

# Legs — keep everything below torso
LEGS_KEEP_TOP = LEGS_TOP
LEGS_KEEP_BOT = LEGS_BOT + 5  # slight padding


def make_base_mask() -> Image.Image:
    """Start with all-black (keep everything)."""
    return Image.new("L", (SIZE, SIZE), 0)


def draw_arm_regions(draw: ImageDraw.ImageDraw):
    """
    Mask both arm regions on the base idle pose.
    Arms hang at roughly shoulder level down to hip level,
    on the left and right sides of the torso.
    """
    # Left arm region (character's right arm, viewer's left)
    # Extends from left edge of character to the chest core
    draw.rectangle([CHAR_LEFT - 10, TORSO_TOP - 8, CHEST_LEFT + 2, LEGS_TOP + 10], fill=255)

    # Right arm region (character's left arm, viewer's right)
    # Extends from chest core to right edge of character
    draw.rectangle([CHEST_RIGHT - 2, TORSO_TOP - 8, CHAR_RIGHT + 10, LEGS_TOP + 10], fill=255)


def protect_face(draw: ImageDraw.ImageDraw):
    """Black-out the face region so it's always kept."""
    draw.rectangle([FACE_LEFT, FACE_TOP, FACE_RIGHT, FACE_BOT], fill=0)


def protect_legs(draw: ImageDraw.ImageDraw):
    """Black-out the legs region so it's always kept."""
    draw.rectangle([CHAR_LEFT - 5, LEGS_KEEP_TOP, CHAR_RIGHT + 5, LEGS_KEEP_BOT], fill=0)


def protect_chest_core(draw: ImageDraw.ImageDraw):
    """Black-out the narrow chest center so it's always kept."""
    draw.rectangle([CHEST_LEFT + 4, CHEST_TOP, CHEST_RIGHT - 4, CHEST_BOT], fill=0)


# =========================================================================
# Mask 1: WINDUP — arms raised overhead
# =========================================================================
def create_windup_mask() -> Image.Image:
    mask = make_base_mask()
    draw = ImageDraw.Draw(mask)

    # Arm regions at sides (where arms currently are — need to erase them)
    draw_arm_regions(draw)

    # Large region ABOVE the head for raised arms + weapon
    # Generous: from top of frame down to mid-head, full character width + extra
    draw.rectangle([CHAR_LEFT - 20, 0, CHAR_RIGHT + 20, HEAD_BOT - 5], fill=255)

    # Also mask the shoulder area generously (arms transition zone)
    draw.rectangle([CHAR_LEFT - 15, HEAD_BOT - 5, CHAR_RIGHT + 15, TORSO_TOP + 15], fill=255)

    # Protect: face center (smaller protected zone — just the core face)
    # For windup, arms go above, so we keep a tighter face region
    draw.ellipse([FACE_LEFT + 5, FACE_TOP + 3, FACE_RIGHT - 5, FACE_BOT - 2], fill=0)

    # Protect chest core
    protect_chest_core(draw)

    # Protect legs
    protect_legs(draw)

    return mask


# =========================================================================
# Mask 2: MIDSWING — swinging at ~45 degrees to the right
# =========================================================================
def create_midswing_mask() -> Image.Image:
    mask = make_base_mask()
    draw = ImageDraw.Draw(mask)

    # Arm regions at sides
    draw_arm_regions(draw)

    # Large region to the RIGHT of the character for the swing arc
    # Covers from above shoulder level to below waist, extending well past character
    draw.rectangle([CHAR_CX - 5, HEAD_BOT - 15, SIZE, TORSO_BOT + 20], fill=255)

    # Also add a diagonal sweep area (upper-right to mid-right)
    # Using a polygon for the swing arc
    draw.polygon([
        (CHAR_CX, HEAD_TOP),           # start near head center
        (SIZE, HEAD_TOP - 10),          # upper right corner area
        (SIZE, TORSO_BOT + 15),         # lower right
        (CHAR_CX + 10, TORSO_BOT + 15), # back near center-bottom
        (CHAR_CX - 5, TORSO_TOP),       # center torso
    ], fill=255)

    # Mask left arm region too (arm pulling back)
    draw.rectangle([CHAR_LEFT - 15, TORSO_TOP - 15, CHEST_LEFT + 5, TORSO_BOT + 5], fill=255)

    # Protect face
    draw.ellipse([FACE_LEFT + 2, FACE_TOP, FACE_RIGHT - 2, FACE_BOT], fill=0)

    # Protect legs
    protect_legs(draw)

    return mask


# =========================================================================
# Mask 3: FOLLOW-THROUGH — arms swept down to lower-right
# =========================================================================
def create_followthrough_mask() -> Image.Image:
    mask = make_base_mask()
    draw = ImageDraw.Draw(mask)

    # Arm regions at sides
    draw_arm_regions(draw)

    # Large region to the LOWER-RIGHT for follow-through
    # Arms have swept down past the target
    draw.polygon([
        (CHAR_CX - 10, TORSO_TOP),       # start at mid-torso
        (CHAR_RIGHT + 5, TORSO_TOP - 5),  # right shoulder area
        (SIZE, TORSO_TOP + 10),            # far right, shoulder level
        (SIZE, LEGS_BOT + 20),             # far right, below feet
        (CHAR_CX + 20, LEGS_BOT + 20),    # below character center
        (CHAR_CX - 10, TORSO_BOT + 10),   # back to center
    ], fill=255)

    # Also mask left side for the pulling-back arm
    draw.rectangle([CHAR_LEFT - 15, TORSO_TOP - 10, CHEST_LEFT + 5, TORSO_BOT + 10], fill=255)

    # Shoulder/upper-arm transition zone
    draw.rectangle([CHAR_LEFT - 10, HEAD_BOT - 5, CHAR_RIGHT + 10, TORSO_TOP + 10], fill=255)

    # Protect face
    draw.ellipse([FACE_LEFT + 2, FACE_TOP, FACE_RIGHT - 2, FACE_BOT], fill=0)

    # Protect chest core (tighter for follow-through)
    protect_chest_core(draw)

    # Protect legs
    protect_legs(draw)

    return mask


# =========================================================================
# Main
# =========================================================================
def main():
    masks = {
        "attack_mask_windup.png": create_windup_mask,
        "attack_mask_midswing.png": create_midswing_mask,
        "attack_mask_followthrough.png": create_followthrough_mask,
    }

    for filename, creator in masks.items():
        mask = creator()
        out_path = OUT_DIR / filename
        mask.save(out_path)
        print(f"Created: {out_path}")

    print(f"\nAll {len(masks)} masks saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
