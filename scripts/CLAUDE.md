# Scripts Directory

## player/player.gd (~1100 lines)
Player controller with 13-state enum machine: IDLE, MOVE, JUMP, ATTACK_1/2/3, DODGE, SPECIAL, HURT, KNOCKDOWN, GETUP, DEAD.

Key exports: `player_id` (1 or 2), `move_speed` (200), `belt_min_y`/`belt_max_y` (115/235).

Combo system: light chains 3 hits with 0.5s window, buffered input. Special: hold RB, tap X/Y for tier, release to fire. Jump: parabolic arc with visual Y offset.

Sprite loading: `_load_sprite_frames(folder)` reads PNGs, slices 96x96 AtlasTextures at runtime. Shadow: procedural ellipse at feet.

Weapon: `equip_weapon(WeaponData)` — auto-equips Frost Reaver on start.

Debug overlay: F1 shows state, HP, meter, hitbox status, input buffer.

## enemies/enemy_base.gd (~500 lines)
Enemy AI with 5 states: IDLE, APPROACH, ATTACK, STAGGER, DEATH.

Key exports: `max_hp` (30), `move_speed` (40), `attack_range` (55), `attack_damage` (10), `sprite_folder`.

AI: chase nearest player, separation force between enemies (40px), orbit when attack denied (70px), standoff at 55px. Attacks queue via EnemyGroupManager (max 3). Re-targets every 0.5s. Awards kill score to attacker.

## combat/

### hitbox.gd
Area2D attack hitbox. Multi-hit prevention via `_hit_targets` array per activation. `activate()`/`deactivate()` called by parent state machine. Emits `damage_dealt(amount, target)`. Y-axis depth tolerance check.

### hurtbox.gd
Area2D damage receiver. `take_damage(amount, knockback, hitstun, attacker)` emits `damage_received` signal. Parent entity connects to this signal.

### health_component.gd
Reusable HP tracker. `initialize(hp)`, `take_damage(amount)`, `heal(amount)`, `is_dead()`. Emits `health_changed(current, max)` and `died`.

### special_meter.gd
3-segment meter (10 pts/segment). Gains: 1x on deal damage, 1.5x on take damage. `can_use_tier(tier)` / `use_tier(tier)`. Emits `meter_changed`, `meter_full`, `meter_empty`.

### weapon_data.gd
Resource class. Fields: weapon_name, category (OFFENSE/SUPPORT), primary/secondary subcategory, per-tier stats (t1/t2/t3: name, damage, heal, duration, effect_scene).

### hitstop.gd (autoload)
Per-entity frame freeze. `freeze(duration, entities)` sets PROCESS_MODE_DISABLED on each entity, restores after duration. Safety timeout 0.5s prevents permanent freeze. Does NOT use Engine.time_scale (that was the old bug).

### screen_fx.gd (autoload)
`shake(duration, intensity)` — randomized canvas offset. `flash(duration, color)` — tween ColorRect overlay. Process mode ALWAYS so effects play during hitstop.

### special_vfx.gd
Procedural expanding circle. `setup(max_radius, color, duration)`. Self-destructs when done.

## managers/

### game_manager.gd (autoload)
Game state enum (MENU/PLAYING/PAUSED). Shared lives (3), per-player scores. `start_game()`, `pause_game()`, `resume_game()`, `add_score()`, `lose_life()`. Emits `game_state_changed`, `life_lost`, `game_over`, `score_changed`.

### input_manager.gd (autoload)
Controller hot-plug detection. Auto-assigns first pad=P1, second=P2. Remaps p1_*/p2_* input actions at runtime. Debug overlays: F1=entity state, F3=controller info.

### wave_manager.gd
Watches "enemies" group. When all dead: heal/revive players, wait 2s, spawn next wave (3 enemies). `enemies_per_wave`, `wave_delay`, `current_wave`.

### enemy_group_manager.gd (autoload)
`request_attack(enemy) -> bool` — returns true if <3 attackers. `release_attack(enemy)` — frees slot. MAX_ATTACKERS=3.

## ui/

### hud.gd (~330 lines)
Health bars, special meter, lives, scores — all built in code (no .tscn). P1 orange left, P2 blue right, lives center. Damage flash overlay on HP loss. Wires to HealthComponent, SpecialMeter, GameManager signals. PROCESS_MODE_ALWAYS.

### pause_overlay.gd (autoload)
ESC/Start toggles `get_tree().paused`. Dark overlay + "PAUSED!!!" text. PROCESS_MODE_ALWAYS.
