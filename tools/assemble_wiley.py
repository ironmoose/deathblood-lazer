"""Assemble Wiley sprite sheets from individual frames."""

from pathlib import Path
from PIL import Image

FRAME_SIZE = 256
FRAMES_DIR = Path(r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\wiley\frames")
INPAINT_DIR = FRAMES_DIR / "inpaint"
OUTPUT_DIR = Path(r"C:\Users\airet\workspaces\godot-game\assets\sprites\characters\wiley")
CANONICAL = FRAMES_DIR / "cc_wiley_v8_south-east.png"


def assemble_strip(frame_paths: list[Path], output_path: Path) -> None:
    """Assemble frames into a horizontal strip."""
    count = len(frame_paths)
    strip = Image.new("RGBA", (FRAME_SIZE * count, FRAME_SIZE), (0, 0, 0, 0))
    for i, path in enumerate(frame_paths):
        frame = Image.open(path).convert("RGBA")
        if frame.size != (FRAME_SIZE, FRAME_SIZE):
            frame = frame.resize((FRAME_SIZE, FRAME_SIZE), Image.NEAREST)
        strip.paste(frame, (i * FRAME_SIZE, 0))
    strip.save(output_path)
    print(f"  Saved: {output_path} ({strip.width}x{strip.height})")


def single_frame(source: Path, output_path: Path) -> None:
    """Save a single frame sprite sheet."""
    img = Image.open(source).convert("RGBA")
    if img.size != (FRAME_SIZE, FRAME_SIZE):
        img = img.resize((FRAME_SIZE, FRAME_SIZE), Image.NEAREST)
    img.save(output_path)
    print(f"  Saved: {output_path} ({img.width}x{img.height})")


def main() -> None:
    print("Assembling Wiley sprite sheets...")

    # Multi-frame animations
    animations = {
        "Walk": [INPAINT_DIR / f"cc_walk_frame{i}.png" for i in range(9)],
        "Attack_1": [INPAINT_DIR / f"cc_attack_frame{i}.png" for i in range(9)],
        "Attack_2": [INPAINT_DIR / f"cc_attack2_frame{i}.png" for i in range(9)],
        "Attack_3": [INPAINT_DIR / f"cc_attack3_frame{i}.png" for i in range(9)],
        "Hurt": [INPAINT_DIR / f"cc_hurt_frame{i}.png" for i in range(9)],
    }

    for name, frames in animations.items():
        # Verify all frames exist
        missing = [f for f in frames if not f.exists()]
        if missing:
            print(f"  WARNING: Missing frames for {name}: {missing}")
            continue
        assemble_strip(frames, OUTPUT_DIR / f"{name}.png")

    # Single-frame placeholders from canonical sprite
    single_frame(CANONICAL, OUTPUT_DIR / "Idle.png")
    single_frame(CANONICAL, OUTPUT_DIR / "Dead.png")
    single_frame(CANONICAL, OUTPUT_DIR / "Jump.png")

    print("Done!")


if __name__ == "__main__":
    main()
