# Deathblood Lazer

A Golden Axe-style fantasy beat 'em up with local 2-player co-op. Side-scrolling, belt-scroll combat, pixel art. Built in Godot 4.6 with GDScript.

The art direction is synthwave fantasy. Think neon-lit dungeons, skull motifs, the vibe of Huntdown meets Golden Axe.

**Status: work in progress / prototype**

## Characters

- **Player 1** - Father Stu, a stout dwarf cleric (orange theme)
- **Player 2** - Wiley, a towering wolf-dragon berserker (blue theme)

Shared lives, separate health bars and special meters. No friendly fire.

## What's Working

- 3-hit light combo with input buffering
- Heavy attacks, dodge with i-frames, jump with parabolic arc
- Tiered special attacks (hold + select tier 1/2/3, costs meter)
- Hit stop, screen shake, damage flash
- Enemy AI with group attack coordination (max 3 attackers at once)
- Wave-based spawning with heal/revive between waves
- Weapon system (resource-based, one weapon so far: Frost Reaver)
- HUD with health bars, 3-segment special meter, score, shared lives
- Gamepad support with hot-plug detection and per-player remapping
- Pause overlay

## Enemies

Orc grunts with chase/attack/stagger states. Boss sprites exist (Fire Spirit, Skeleton, Plent) but aren't wired up yet.

## Art Pipeline

Character sprites are generated with [PixelLab](https://www.pixellab.ai/) and loaded at runtime as atlas textures (96x96 frames). There are Python tools in `tools/` for the sprite pipeline and a visual skeleton editor.

## Running It

Open the project in Godot 4.6+, hit F5. Player 1 uses WASD + J/K/Space. Player 2 uses arrow keys + numpad or a second gamepad.

## Project Structure

```
scenes/         .tscn scene files
scripts/        GDScript (player, enemies, combat, managers, ui)
assets/sprites/ pixel art (characters, enemies, bosses, effects)
data/weapons/   .tres weapon resources
shaders/        hit flash shader
tools/          sprite generation and editing tools
```
