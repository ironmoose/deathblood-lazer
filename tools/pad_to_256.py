"""Pad 228x228 sprite and mask images to 256x256, centered."""

from pathlib import Path
from PIL import Image

FRAMES_DIR = Path(r"C:/Users/airet/workspaces/godot-game/assets/sprites/characters/father_stu/frames")
INPAINT_DIR = FRAMES_DIR / "inpaint"

TARGET = 256


def pad_image(src: Path, dst: Path, bg_color: tuple) -> None:
    img = Image.open(src)
    w, h = img.size
    canvas = Image.new(img.mode, (TARGET, TARGET), bg_color)
    offset_x = (TARGET - w) // 2
    offset_y = (TARGET - h) // 2
    canvas.paste(img, (offset_x, offset_y))
    canvas.save(dst)
    print(f"  {dst.name}: {canvas.size} {canvas.mode}")


def main() -> None:
    INPAINT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Pad the RGBA sprite
    sprite_src = FRAMES_DIR / "cc_father_stu_south-east.png"
    sprite_dst = INPAINT_DIR / "base_256.png"
    print("Padding sprite (transparent background):")
    pad_image(sprite_src, sprite_dst, (0, 0, 0, 0))

    # 2. Pad the grayscale masks (black background = keep)
    mask_names = [
        "attack_mask_windup",
        "attack_mask_midswing",
        "attack_mask_followthrough",
    ]
    print("\nPadding masks (black background):")
    for name in mask_names:
        src = INPAINT_DIR / f"{name}.png"
        dst = INPAINT_DIR / f"{name}_256.png"
        pad_image(src, dst, 0)

    print("\nDone.")


if __name__ == "__main__":
    main()
