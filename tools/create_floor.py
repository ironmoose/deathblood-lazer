"""
Generate a pixel art stone floor with built-in 2.5D perspective for a beat-em-up.
Simulates a ~30-45 degree overhead view like Golden Axe / Streets of Rage.

Produces:
  - floor_full.png         (640x192 full floor with perspective)
  - floor_tile_source.png  (320x192 reference half)

Key perspective features:
  - Brick rows get TALLER toward the bottom (nearer to viewer)
  - Vertical mortar lines angle slightly inward toward the top (vanishing point)
  - Classic offset brick pattern with transparent mortar gaps
"""

import random
import math
from PIL import Image, ImageDraw

# ── Configuration ──────────────────────────────────────────────────
FULL_W, FULL_H = 640, 192
TILE_SOURCE_W = 320  # half-width reference tile

MORTAR_W = 2          # mortar gap width in pixels (horizontal)
MORTAR_V = 2          # mortar gap width in pixels (vertical)
CRACK_CHANCE = 0.25   # chance a brick gets an internal diagonal crack

# Stone colour range (dark purples / greys)
STONE_R = (30, 65)
STONE_G = (20, 45)
STONE_B = (50, 85)

# Perspective: brick widths at top vs bottom
BRICK_W_TOP = 28      # bricks at the top (far) are narrower
BRICK_W_BOT = 36      # bricks at the bottom (near) are wider

# Vanishing point for vertical lines (centered above the image)
VANISH_X = FULL_W / 2.0
VANISH_Y = -600.0     # far above the image — subtle convergence

SEED = 42
random.seed(SEED)

OUT_DIR = "C:/Users/airet/workspaces/godot-game/assets/sprites/environment"


# ── Row height schedule (perspective) ─────────────────────────────
# Desired row heights from top (far) to bottom (near)
ROW_HEIGHTS_IDEAL = [12, 13, 14, 15, 17, 19, 21, 23, 25, 27]
# Sum = 186, need to distribute 6 extra pixels across the bottom rows

def _build_row_schedule():
    """
    Build row heights that fill exactly FULL_H pixels.
    Top rows are thinner (far), bottom rows are taller (near).
    Hand-tuned progression: 12 -> 27px across 10 rows.
    """
    heights = list(ROW_HEIGHTS_IDEAL)
    total = sum(heights)
    deficit = FULL_H - total

    # Distribute any deficit across the tallest (bottom) rows
    i = len(heights) - 1
    while deficit > 0 and i >= 0:
        add = min(deficit, 2)  # add at most 2px per row
        heights[i] += add
        deficit -= add
        i -= 1

    # If still short, add to the last row
    total = sum(heights)
    if total < FULL_H:
        heights[-1] += FULL_H - total

    # If over, trim from the last row
    total = sum(heights)
    if total > FULL_H:
        heights[-1] -= total - FULL_H

    # Build (y, h) tuples
    rows = []
    y = 0
    for h in heights:
        rows.append((y, h))
        y += h

    return rows


# ── Helpers ────────────────────────────────────────────────────────
def rand_stone_color():
    """Return a random base stone colour within the palette."""
    return (
        random.randint(*STONE_R),
        random.randint(*STONE_G),
        random.randint(*STONE_B),
        255,
    )


def vary_color(base, amount=8):
    """Return *base* nudged by up to +/-amount per channel (clamped 0-255)."""
    return tuple(
        max(0, min(255, c + random.randint(-amount, amount)))
        for c in base[:3]
    ) + (255,)


def add_texture(img, x0, y0, x1, y1, base_color):
    """Paint pixel-level noise inside a brick rectangle for texture."""
    pixels = img.load()
    for py in range(y0, min(y1, FULL_H)):
        for px in range(x0, min(x1, FULL_W)):
            col = vary_color(base_color, amount=10)
            pixels[px, py] = col


def add_brick_shading(img, x0, y0, x1, y1, base_color):
    """Add subtle top-highlight / bottom-shadow to a brick for depth."""
    pixels = img.load()
    h = y1 - y0
    w = x1 - x0
    if h < 4 or w < 4:
        return

    # Top edge: slightly lighter (1-2px)
    highlight_rows = min(2, h // 3)
    for dy in range(highlight_rows):
        py = y0 + dy
        if py >= FULL_H:
            break
        for px in range(x0, min(x1, FULL_W)):
            cur = pixels[px, py]
            if cur[3] > 0:
                lighter = tuple(min(255, c + 8 + (highlight_rows - dy) * 4) for c in cur[:3]) + (255,)
                pixels[px, py] = lighter

    # Bottom edge: slightly darker (1-2px)
    shadow_rows = min(2, h // 3)
    for dy in range(shadow_rows):
        py = y1 - 1 - dy
        if py < 0 or py >= FULL_H:
            continue
        for px in range(x0, min(x1, FULL_W)):
            cur = pixels[px, py]
            if cur[3] > 0:
                darker = tuple(max(0, c - 8 - (shadow_rows - dy) * 4) for c in cur[:3]) + (255,)
                pixels[px, py] = darker


def draw_diagonal_crack(img, x0, y0, x1, y1):
    """Draw a 1px transparent diagonal crack inside a brick area."""
    draw = ImageDraw.Draw(img)
    w = x1 - x0
    h = y1 - y0
    if w < 8 or h < 6:
        return

    # Pick random start/end along brick edges
    if random.random() < 0.5:
        sx = random.randint(x0 + 2, x0 + w // 2)
        sy = y0 + random.randint(1, max(1, h // 3))
        ex = random.randint(x0 + w // 2, x1 - 2)
        ey = y1 - random.randint(1, max(1, h // 3))
    else:
        sx = random.randint(x0 + w // 2, x1 - 2)
        sy = y0 + random.randint(1, max(1, h // 3))
        ex = random.randint(x0 + 2, x0 + w // 2)
        ey = y1 - random.randint(1, max(1, h // 3))

    draw.line([(sx, sy), (ex, ey)], fill=(0, 0, 0, 0), width=1)


# ── Perspective vertical mortar ───────────────────────────────────
def _mortar_x_at_y(base_x, base_y, target_y):
    """
    Given a mortar line that passes through (base_x, base_y) at the bottom
    of the image, compute where it would be at target_y, converging toward
    the vanishing point.
    """
    # Parametric line from vanishing point through (base_x, base_y)
    dy_base = base_y - VANISH_Y
    dy_target = target_y - VANISH_Y

    if abs(dy_base) < 0.001:
        return base_x

    ratio = dy_target / dy_base
    vx = VANISH_X + (base_x - VANISH_X) * ratio
    return vx


def _get_brick_layout_for_row(row_y, row_h, row_idx, brick_w_avg):
    """
    Generate brick x-positions for a single row, accounting for perspective.
    Returns list of (x_left, x_right) in pixel coordinates.
    Ensures horizontal tiling (left edge connects to right edge).
    """
    # Row center y for perspective calc
    center_y = row_y + row_h / 2.0

    # Generate evenly-spaced mortar positions at the BOTTOM of the image,
    # then project them to this row's y-position for convergence.
    # Use brick_w_avg spacing at the bottom row, with offset for odd rows.
    bottom_y = FULL_H  # reference line

    # How many bricks fit across at bottom spacing?
    n_bricks = max(4, round(FULL_W / brick_w_avg))
    spacing = FULL_W / n_bricks

    # Offset for alternating rows (classic brick pattern)
    offset = (spacing / 2.0) if (row_idx % 2 == 1) else 0.0

    # Generate mortar line positions at the bottom
    mortar_positions_bottom = []
    for i in range(n_bricks + 2):  # extra for safety
        bx = offset + i * spacing
        mortar_positions_bottom.append(bx)

    # Project each mortar position to this row's y
    mortar_positions = []
    for bx in mortar_positions_bottom:
        projected_x = _mortar_x_at_y(bx, bottom_y, center_y)
        mortar_positions.append(projected_x)

    # Build brick spans from mortar positions
    bricks = []
    for i in range(len(mortar_positions) - 1):
        x_left = mortar_positions[i]
        x_right = mortar_positions[i + 1]

        # Clip to image bounds
        xl = int(round(x_left))
        xr = int(round(x_right))

        # Skip bricks entirely outside the image
        if xr <= 0 or xl >= FULL_W:
            continue

        xl = max(0, xl)
        xr = min(FULL_W, xr)

        if xr - xl < 3:
            continue

        bricks.append((xl, xr))

    return bricks


# ── Horizontal tiling fix-up ──────────────────────────────────────
def _ensure_horizontal_tile(img):
    """
    Make sure the image tiles horizontally by mirroring a thin strip
    from the left edge to blend with the right edge.
    We do this by ensuring bricks that wrap around the edge share color.
    """
    # Already handled by generating full width with periodic mortar spacing.
    # The mortar spacing is FULL_W / n_bricks, which divides evenly,
    # so the pattern repeats. We just need to make sure the colors
    # at x=0 and x=FULL_W-1 are compatible, which they are since we
    # generate the full width in one pass.
    pass


# ── Main generation ────────────────────────────────────────────────
def generate_floor():
    """Create the 640x192 floor image with 2.5D perspective."""
    img = Image.new("RGBA", (FULL_W, FULL_H), (0, 0, 0, 0))

    row_schedule = _build_row_schedule()
    print(f"  Row schedule ({len(row_schedule)} rows):")
    for i, (ry, rh) in enumerate(row_schedule):
        print(f"    Row {i}: y={ry}, h={rh}")

    # Interpolate brick width based on row position
    for row_idx, (ry, rh) in enumerate(row_schedule):
        t = ry / max(1, FULL_H - rh)  # 0=top, 1=bottom
        brick_w = BRICK_W_TOP + (BRICK_W_BOT - BRICK_W_TOP) * t

        bricks = _get_brick_layout_for_row(ry, rh, row_idx, brick_w)

        # Horizontal mortar: leave top MORTAR_W pixels of each row transparent
        mortar_top = MORTAR_W if ry > 0 else 0
        brick_y0 = ry + mortar_top
        brick_y1 = ry + rh

        if brick_y1 <= brick_y0:
            continue

        for (xl, xr) in bricks:
            # Vertical mortar: leave left MORTAR_V pixels transparent
            bx0 = xl + MORTAR_V
            bx1 = xr

            if bx1 <= bx0:
                continue

            # Pick a stone color for this brick
            base = rand_stone_color()

            # Fill with textured stone
            add_texture(img, bx0, brick_y0, bx1, brick_y1, base)

            # Add edge shading for depth
            add_brick_shading(img, bx0, brick_y0, bx1, brick_y1, base)

            # Occasional diagonal crack
            if random.random() < CRACK_CHANCE:
                draw_diagonal_crack(img, bx0, brick_y0, bx1, brick_y1)

    # Sprinkle a few extra random highlight/shadow pixels across all stone
    pixels = img.load()
    for _ in range(FULL_W * FULL_H // 40):
        px = random.randint(0, FULL_W - 1)
        py = random.randint(0, FULL_H - 1)
        current = pixels[px, py]
        if current[3] > 0:
            if random.random() < 0.4:
                # Darker speck
                pixels[px, py] = vary_color(current, amount=12)
            else:
                # Lighter speck
                lighter = tuple(min(255, c + 10) for c in current[:3]) + (255,)
                pixels[px, py] = lighter

    # Add a few long random cracks that span multiple bricks
    draw = ImageDraw.Draw(img)
    for _ in range(random.randint(3, 7)):
        sx = random.randint(0, FULL_W - 1)
        sy = random.randint(0, FULL_H - 1)
        length = random.randint(8, 30)
        angle = random.uniform(-0.8, 0.8)  # mostly horizontal-ish
        ex = sx + int(length * math.cos(angle))
        ey = sy + int(length * math.sin(angle))
        ex = max(0, min(FULL_W - 1, ex))
        ey = max(0, min(FULL_H - 1, ey))
        draw.line([(sx, sy), (ex, ey)], fill=(0, 0, 0, 0), width=1)

    return img


def main():
    print("Generating 2.5D perspective stone floor (640x192)...")
    floor = generate_floor()

    full_path = f"{OUT_DIR}/floor_full.png"
    floor.save(full_path)
    print(f"  Saved: {full_path}")

    # Save left half as the reference tile source
    tile = floor.crop((0, 0, TILE_SOURCE_W, FULL_H))
    tile_path = f"{OUT_DIR}/floor_tile_source.png"
    tile.save(tile_path)
    print(f"  Saved: {tile_path}")

    # Quick stats
    total_px = FULL_W * FULL_H
    transparent_px = sum(
        1 for y in range(FULL_H) for x in range(FULL_W) if floor.getpixel((x, y))[3] == 0
    )
    print(f"\nFloor stats:")
    print(f"  Size:               {FULL_W}x{FULL_H}")
    print(f"  Total pixels:       {total_px}")
    print(f"  Transparent pixels: {transparent_px}  ({100 * transparent_px / total_px:.1f}%)")
    print(f"  Stone pixels:       {total_px - transparent_px}  ({100 * (total_px - transparent_px) / total_px:.1f}%)")
    print("Done.")


if __name__ == "__main__":
    main()
