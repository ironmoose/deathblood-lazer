# Deathblood Lazer — Godot Beat 'em Up

Golden Axe-style 2P co-op side-scrolling brawler. Godot 4.6, GDScript, painterly 2D.

## Project Structure

```
scenes/          — .tscn scene files (main, player, enemies)
scripts/         — GDScript (player/, enemies/, combat/, managers/, ui/)
assets/sprites/  — character sprites, enemies, effects, environment
data/weapons/    — .tres weapon resources
tools/           — sprite_pipeline.py, skeleton_editor.html
docs/            — research notes
shaders/         — custom shaders (hit_flash.gdshader)
```

## Licensing

- Source code (GDScript, Python, shell, config): MIT License, see `LICENSE`
- Art, audio, character designs, and other creative content: All Rights Reserved
- Character sprites are AI-generated via PixelLab under an active subscription
- See `NOTICE.md` for full asset licensing, AI-content disclosure, and fan inspiration disclaimer

## Engine Settings

- Viewport: 2560x1440 native painterly render (no pixelization)
- Stretch mode: canvas_items, keep aspect
- Main scene: res://scenes/main.tscn

## Autoloads (Singletons)

- `GameManager` — game state (MENU/PLAYING/PAUSED), shared lives, scores
- `InputManager` — controller hot-plug, per-player input remapping, debug overlays (F1/F3)
- `HitStop` — per-entity frame-freeze on hit (not global Engine.time_scale)
- `EnemyGroupManager` — limits concurrent enemy attacks to 3
- `PauseOverlay` — ESC/Start pause with overlay
- `ScreenFX` — screen shake + color flash

## Collision Layers

1. World | 2. Player | 3. Enemy | 4. PlayerHurtbox | 5. EnemyHurtbox | 6. PlayerHitbox | 7. EnemyHitbox | 8. Pickup

## Input Mapping

All inputs are prefixed `p1_` / `p2_`. Movement: WASD or joypad analog. Combat: light (J/X), heavy (K/Y), jump (Space/A), special (L/RB), block (U/LB), dodge (I/B). Pause: ESC or joypad select.

## Architecture Patterns

- **State machines**: Player has 13 enum states, Enemy has 5. Both use `_change_state()` with timer-based transitions.
- **Component pattern**: HealthComponent, SpecialMeter, Hitbox, Hurtbox are child nodes attached to entities.
- **Signal-driven**: HealthComponent emits `health_changed`/`died`, Hurtbox emits `damage_received`, Hitbox emits `damage_dealt`.
- **Dynamic sprite loading**: `_load_sprite_frames()` reads PNGs from a folder at runtime, slices into AtlasTextures (96x96 frames). (pixel-art pipeline pattern; will be replaced when bone-rig pipeline lands)

## Combat System

- 3-hit light combo with 0.5s window, input buffering (0.15s)
- Dodge: 0.2s i-frame dash
- Jump: parabolic arc (GRAVITY=600), visual Y offset on sprite
- Specials: hold RB, tap X/Y to select tier (1/2/3), release RB to fire. Costs 1/2/3 meter segments. T1=30dmg cyan, T2=60dmg purple, T3=100dmg gold.
- Meter: 3 segments, 10pts each. Gains on deal damage (1x) and take damage (1.5x).

## Weapon System

WeaponData .tres resources define per-tier stats (damage, heal, duration, effect scene). Currently one weapon: Frost Reaver (auto-equipped). Planned: 150 weapons across 5-6 classes with combo overrides.

## Enemy AI

- Chase nearest player, maintain separation from allies
- Attack when in range (55px) + Y-aligned (25px tolerance)
- Queue attacks via EnemyGroupManager (max 3 simultaneous)
- Re-target every 0.5s

## Art Pipeline

- Render target: 2560x1440 native, characters ~400-800 px tall painterly assets
- Generation: local ComfyUI (4070 Ti Super) with dbstyle_v4 / dbpainterly Style LoRAs + per-character LoRAs (wiley_character_v1, stu_character_v1)
- Rigging: Spine or DragonBones bone-rigged 2D (NOT frame-by-frame sprite sheets)
- Style refs: Hollow Knight, Cuphead, Cult of the Lamb, Darkest Dungeon, Skul: The Hero Slayer
- Painterly canonicals locked at `~/workspaces/deathblood-lazer-training/canonical/locked/`
- PixelLab pipeline (96x96 frames, PixelLab character IDs, skeleton API): SUPERSEDED 2026-05-19

## Co-op

- 2 players: P1=Father Stu (orange), P2=Wiley (blue)
- Per-player health/special meter, shared lives (3)
- Friendly fire OFF
- Wave clear heals + revives dead players

## HUD

Built in code (hud.gd), not .tscn. P1 status left, P2 right, lives center. Health bars with damage flash, 3-segment meter (gold=filled), 6-digit scores.

## Key Conventions

- GDScript with static typing where possible
- Node references via @onready or get_node
- Signals for cross-component communication, never direct method calls between unrelated nodes
- Y-sort for 2.5D depth ordering
- Belt bounds: Y 115-235 (playable area)
- Vertical speed factor: 0.7x for depth perspective
