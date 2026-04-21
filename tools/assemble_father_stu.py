"""Assemble individual Father Stu PNG frames into horizontal sprite sheets.

Output folder: assets/sprites/characters/father_stu/
Frame size: 228x228 RGBA
"""

import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT / "assets" / "sprites" / "characters" / "father_stu" / "frames"
OUTPUT_DIR = ROOT / "assets" / "sprites" / "characters" / "father_stu"
FRAME_SIZE = 228


def assemble_strip(frame_paths: list[Path], output_name: str) -> Path:
    """Stitch frames left-to-right into a horizontal sprite sheet."""
    n = len(frame_paths)
    strip = Image.new("RGBA", (n * FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    for i, fp in enumerate(frame_paths):
        img = Image.open(fp).convert("RGBA")
        if img.size != (FRAME_SIZE, FRAME_SIZE):
            img = img.resize((FRAME_SIZE, FRAME_SIZE), Image.NEAREST)
        strip.paste(img, (i * FRAME_SIZE, 0))
    out = OUTPUT_DIR / output_name
    strip.save(out)
    print(f"  {output_name}: {strip.size[0]}x{strip.size[1]} ({n} frames)")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Walk.png — 9 frames (frame0..frame8)
    walk_frames = [FRAMES_DIR / f"v3_walk_se_frame{i}.png" for i in range(9)]
    for f in walk_frames:
        assert f.exists(), f"Missing walk frame: {f}"
    assemble_strip(walk_frames, "Walk.png")

    # 2. Idle.png — single canonical standing frame
    idle_frame = FRAMES_DIR / "cc_father_stu_south-east.png"
    assert idle_frame.exists(), f"Missing idle frame: {idle_frame}"
    assemble_strip([idle_frame], "Idle.png")

    # 3. Attack_1.png — 9 frames from inpaint folder (frame0..frame8)
    attack_frames = [FRAMES_DIR / "inpaint" / f"cc_attack_frame{i}.png" for i in range(9)]
    for f in attack_frames:
        assert f.exists(), f"Missing attack frame: {f}"
    attack1_path = assemble_strip(attack_frames, "Attack_1.png")

    # 4. Hurt.png — placeholder (canonical standing sprite)
    assemble_strip([idle_frame], "Hurt.png")

    # 5. Dead.png — placeholder (canonical standing sprite)
    assemble_strip([idle_frame], "Dead.png")

    # 6. Jump.png — placeholder (canonical standing sprite)
    assemble_strip([idle_frame], "Jump.png")

    # 7. Attack_2.png — copy of Attack_1.png
    attack2_path = OUTPUT_DIR / "Attack_2.png"
    shutil.copy2(attack1_path, attack2_path)
    print(f"  Attack_2.png: copied from Attack_1.png")

    # 8. Attack_3.png — copy of Attack_1.png
    attack3_path = OUTPUT_DIR / "Attack_3.png"
    shutil.copy2(attack1_path, attack3_path)
    print(f"  Attack_3.png: copied from Attack_1.png")

    print("\nDone! All sprite sheets written to:")
    print(f"  {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
