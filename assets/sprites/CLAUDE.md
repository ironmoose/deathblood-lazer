# Sprites Directory

## Format
- Frame size: 96x96 (current game sprites), 228-256px (PixelLab Character Creator output)
- Horizontal sprite sheets (frames side-by-side in single PNG)
- Transparent PNG with pixelated rendering
- Animation names: Idle, Walk, Run, Jump, Attack_1, Attack_2, Attack_3, Hurt, Dead

## characters/
Custom playable characters generated via PixelLab.

### wiley/
Player 2 (blue). Wolf-headed dragon-winged berserker. Blood red/black/silver armor.
- `frames/cc_wiley_v8_*.png` — 8 rotation frames (256x256), APPROVED
- Character ID: `d1babc2c-390f-4620-96af-899a95a227ba`
- Old files (v1-v7, v3_* animations) are from previous iterations — DO NOT USE

### father_stu/
Player 1 (orange). Stout dwarf cleric. Dark purple armor, cyan trim, magenta runes.
- `frames/cc_father_stu_*.png` — 8 rotation frames (228x228), APPROVED (v11)
- Character ID: `9a05b9af-fa16-4a7a-b603-c55d5249774e`
- Old `v3_*` animation frames are from previous iterations — DO NOT USE

### Warrior_1/, Warrior_2/, Warrior_3/
Placeholder sprite sheets (Craftpix assets). Standard 96x96 format.

## enemies/
### Craftpix_Orc/
- `Orc_Warrior/` — default enemy grunt sprites (used in enemy_base.gd)
- `Orc_Berserk/` — currently used as P1 sprite (placeholder)

## bosses/
Boss sprite sheets. Fire_Spirit/, Plent/ — multi-frame sheets, not yet wired in.

## player/
- `preview.html` — character preview page (both Wiley + Father Stu tabs, static rotations only)

## Art Pipeline
1. PixelLab Character Creator: text description → character with 8 rotations
2. Movement animations: PixelLab web editor (Pixelorama integration) 
3. Combat animations: skeleton API via tools/sprite_pipeline.py
4. Export: ZIP from Character Creator, individual PNGs from skeleton API
5. Cleanup: Aseprite if needed
6. Import: Godot reads PNGs from folder, slices at runtime via player.gd `_load_sprite_frames()`

## Important
- DO NOT call PixelLab API without user approval — credits are limited (2000/cycle)
- Current sprites on disk for Wiley/Father Stu are the APPROVED versions
- Old animation frames (v3_*) exist on disk but are INVALID (wrong character versions)
