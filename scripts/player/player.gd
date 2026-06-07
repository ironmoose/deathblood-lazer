## Player character controller for 2.5D beat 'em up movement.
##
## Supports two players via [member player_id]. Reads input actions prefixed
## with "p1_" or "p2_" and moves on an 8-directional grid clamped to the
## play belt (Y range). Vertical speed is reduced to ~70% for depth feel.
##
## Loads sprite sheets from disk based on player_id and builds SpriteFrames
## at runtime so each player has unique art.
##
## Uses an enum-based finite state machine for clean state management.
extends CharacterBody2D

## Which player this instance represents (1 or 2). Determines input prefix.
@export var player_id: int = 1

## Horizontal / vertical base movement speed in pixels per second.
@export var move_speed: float = 800.0

## Top edge of the playable belt (Y coordinate).
@export var belt_min_y: float = 900.0

## Bottom edge of the playable belt (Y coordinate).
@export var belt_max_y: float = 1380.0

## Vertical speed multiplier to give a depth / perspective feel.
const VERTICAL_SPEED_FACTOR: float = 0.7

## Frame size in the sprite sheets (all sheets use 96x96 frames).
var _frame_size: int = 96
var _feet_padding: float = 0.0

## Sprite folder paths keyed by player_id.
const SPRITE_PATHS: Dictionary = {
	1: "res://assets/sprites/characters/father_stu/",
	2: "res://assets/sprites/characters/wiley/",
}

## Target visual height in pixels per player. Stu is a stout dwarf (smaller),
## Wiley is a towering wolf-dragon berserker (bigger than standard enemies).
const SPRITE_TARGET_SIZE: Dictionary = {
	1: 320.0,   # Father Stu, dwarf, shorter than orcs (384px)
	2: 480.0,   # Wiley, berserker, taller than orcs
}

## Transparent padding below feet in the source sprite (pixels, unscaled).
## Used to adjust offset so feet sit on the ground instead of floating.
const SPRITE_FEET_PADDING: Dictionary = {
	1: 57.0,   # Father Stu
	2: 67.0,   # Wiley
}

## Mapping from sprite-sheet file base name to animation name.
const ANIM_MAP: Dictionary = {
	"Idle": "idle",
	"Walk": "walk",
	"Run": "run",
	"Jump": "jump",
	"Attack_1": "attack_1",
	"Attack_2": "attack_2",
	"Attack_3": "attack_3",
	"Run+Attack": "run_attack",
	"Hurt": "hurt",
	"Dead": "dead",
}

## Animations that should loop.
const LOOPING_ANIMS: Array[String] = ["idle", "walk", "run"]

## Default FPS for animations.
const DEFAULT_ANIM_FPS: float = 10.0

## FPS for attack animations (slightly faster).
const ATTACK_ANIM_FPS: float = 20.0

## Light-attack combo window.
const COMBO_WINDOW: float = 0.5  # seconds to chain next hit

## Dodge constants.
const DODGE_SPEED: float = 1200.0
const DODGE_DURATION: float = 0.2

## Jump arc constants.
const JUMP_FORCE: float = 800.0  # initial upward velocity
const GRAVITY: float = 2400.0    # pulls back down

## Input buffer window.
const INPUT_BUFFER_TIME: float = 0.15  # 150ms buffer window

## Hurt stagger duration.
const HURT_DURATION: float = 0.4

## Knockdown duration (time on ground before getup).
const KNOCKDOWN_DURATION: float = 0.8

## Getup duration (recovery before returning to idle).
const GETUP_DURATION: float = 0.5

## Special move damage (matches a heavy hit).
const SPECIAL_DAMAGE: int = 50

## Special meter component — created in _ready.
var _special_meter: SpecialMeter = null

## Currently equipped weapon — null means bare-fists (basic special only).
var _weapon: WeaponData = null

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

enum State {
	IDLE,
	MOVE,
	JUMP,
	ATTACK_1,
	ATTACK_2,
	ATTACK_3,
	DODGE,
	SPECIAL,
	HURT,
	KNOCKDOWN,
	GETUP,
	DEAD,
}

var _state: State = State.IDLE
var _previous_state: State = State.IDLE

# ---------------------------------------------------------------------------
# State timers / variables
# ---------------------------------------------------------------------------

## Combo state.
var _combo_count: int = 0
var _combo_timer: float = 0.0

## Dodge state.
var _is_dodging: bool = false
var _dodge_timer: float = 0.0

## Jump arc state.
var _is_jumping: bool = false
var _jump_velocity: float = 0.0
var _jump_height: float = 0.0  # current visual offset (0 = on ground)

## Input buffer.
var _buffered_input: StringName = &""
var _buffer_timer: float = 0.0

## Generic state timer (used by HURT, KNOCKDOWN, GETUP).
var _state_timer: float = 0.0

## Which special tier was selected (1 = T1, 2 = T2, 3 = T3).
var _special_tier: int = 1

## Whether RB (special) is currently held for tier selection.
var _special_held: bool = false

## Latched tier during special charge (highest tier selected wins).
var _latched_tier: int = 1

## Cached input prefix (set once in _ready).
var _input_prefix: String = ""

## Debug overlay.
var _debug_label: Label = null

## Tier indicator label shown while charging special.
var _tier_label: Label = null

## Cached default hitbox collision shape size and position for restoration after specials.
var _default_hitbox_size: Vector2 = Vector2(72.0, 80.0)
var _default_hitbox_pos: Vector2 = Vector2(88.0, -104.0)

@onready var animated_sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var shadow: Sprite2D = $Shadow
@onready var hitbox: Hitbox = $Hitbox
@onready var hurtbox: Hurtbox = $Hurtbox
@onready var health: HealthComponent = $HealthComponent


func _ready() -> void:
	add_to_group("players")
	var folder: String = SPRITE_PATHS.get(player_id, SPRITE_PATHS[1])
	animated_sprite.sprite_frames = _load_sprite_frames(folder)
	# Offset the sprite so the feet (bottom of the frame) sit at the origin.
	# AnimatedSprite2D centers the texture by default, so -half moves bottom to origin.
	_feet_padding = SPRITE_FEET_PADDING.get(player_id, 0.0)
	animated_sprite.offset = Vector2(0, -_frame_size / 2.0 + _feet_padding)
	# Scale sprite to per-character target size.
	var target_size: float = SPRITE_TARGET_SIZE.get(player_id, 96.0)
	var sprite_scale: float = target_size / float(_frame_size)
	animated_sprite.scale = Vector2(sprite_scale, sprite_scale)
	animated_sprite.animation_finished.connect(_on_animation_finished)
	_setup_shadow()
	_setup_debug_label()
	_setup_tier_label()
	hitbox.owner_entity = self
	hurtbox.owner_entity = self
	hurtbox.damage_received.connect(_on_damage_received)
	_input_prefix = "p%d_" % player_id
	health.initialize()
	# Create and wire special meter.
	_special_meter = SpecialMeter.new()
	_special_meter.name = "SpecialMeter"
	add_child(_special_meter)
	hitbox.damage_dealt.connect(_on_damage_dealt)
	_change_state(State.IDLE)

	# Duplicate the hitbox shape so each player instance has its own — shared
	# sub-resources would otherwise affect both players simultaneously.
	var hitbox_shape_init: CollisionShape2D = hitbox.get_node("CollisionShape2D") as CollisionShape2D
	if hitbox_shape_init and hitbox_shape_init.shape:
		hitbox_shape_init.shape = hitbox_shape_init.shape.duplicate()
		if hitbox_shape_init.shape is RectangleShape2D:
			_default_hitbox_size = (hitbox_shape_init.shape as RectangleShape2D).size
			_default_hitbox_pos = hitbox_shape_init.position

	# Auto-equip Frost Reaver for testing.
	var frost_reaver: WeaponData = load("res://data/weapons/frost_reaver.tres") as WeaponData
	if frost_reaver:
		equip_weapon(frost_reaver)

	# Apply hit flash shader material.
	var shader_mat := ShaderMaterial.new()
	shader_mat.shader = load("res://shaders/hit_flash.gdshader")
	animated_sprite.material = shader_mat

	# Player glow light for synthwave atmosphere.
	var glow := PointLight2D.new()
	glow.energy = 0.8
	glow.texture = _create_light_texture()
	glow.texture_scale = 3.0
	glow.position = Vector2(0.0, -160.0)  # center on body
	# P1 = warm orange/pink, P2 = cool cyan/blue.
	if player_id == 1:
		glow.color = Color(1.0, 0.5, 0.3, 1.0)  # warm orange
	else:
		glow.color = Color(0.3, 0.7, 1.0, 1.0)  # cool cyan
	add_child(glow)


func _physics_process(delta: float) -> void:
	# Input buffer countdown.
	if _buffer_timer > 0.0:
		_buffer_timer -= delta
		if _buffer_timer <= 0.0:
			_buffered_input = &""

	# Jump arc physics — runs regardless of state so aerial attacks keep the arc.
	if _is_jumping:
		_jump_velocity += GRAVITY * delta
		_jump_height += _jump_velocity * delta

		if _jump_height >= 0.0:
			# Landed.
			_jump_height = 0.0
			_is_jumping = false
			_jump_velocity = 0.0
			_combo_count = 0  # reset combo so ground combos start fresh
			# Transition out of aerial state on landing.
			match _state:
				State.JUMP, State.ATTACK_1, State.ATTACK_2, State.ATTACK_3:
					var input_dir := _get_input_direction()
					if input_dir.length() > 0.0:
						_change_state(State.MOVE)
					else:
						_change_state(State.IDLE)
				State.HURT, State.KNOCKDOWN, State.DEAD:
					# Already in a damage state — don't interrupt.
					# Jump vars are cleared above; sprite lands naturally.
					pass

		# Apply jump height as visual offset on the sprite (negative = up).
		animated_sprite.offset.y = (-_frame_size / 2.0 + _feet_padding) + _jump_height
	else:
		# On ground — restore normal offset.
		animated_sprite.offset.y = -_frame_size / 2.0 + _feet_padding

	# Run state-specific update.
	_update_state(delta)

	# Common post-update: clamp to belt, update z_index.
	position.y = clampf(position.y, belt_min_y, belt_max_y)
	z_index = int(position.y)

	# Debug overlay.
	_update_tier_indicator()
	_update_debug()


func _unhandled_input(_event: InputEvent) -> void:
	pass


# ===========================================================================
# State machine core
# ===========================================================================

func _change_state(new_state: State) -> void:
	if new_state == _state:
		# Allow HURT to re-enter to refresh the stagger timer.
		if new_state == State.HURT:
			_state_timer = HURT_DURATION
		return
	_exit_state(_state, new_state)
	_previous_state = _state
	_state = new_state
	_enter_state(new_state)


func _enter_state(state: State) -> void:
	match state:
		State.IDLE:
			_play_anim("idle")
		State.MOVE:
			_play_anim("walk")
		State.JUMP:
			if not _is_jumping:
				_jump_velocity = -JUMP_FORCE
				_jump_height = 0.0
				_is_jumping = true
			_play_anim("jump")
		State.ATTACK_1:
			_combo_count = 1
			_combo_timer = COMBO_WINDOW
			hitbox.damage = 10
			hitbox.activate()
			_play_anim("attack_1")
		State.ATTACK_2:
			_combo_count = 2
			_combo_timer = COMBO_WINDOW
			hitbox.damage = 15
			hitbox.activate()
			_play_anim("attack_2")
			_show_combo_indicator()
		State.ATTACK_3:
			_combo_count = 3
			_combo_timer = COMBO_WINDOW
			hitbox.damage = 25
			hitbox.activate()
			_play_anim("attack_3")
			_show_combo_indicator()
	# Combo color glow — tint the sprite to show combo progress.
	if state in [State.ATTACK_1, State.ATTACK_2, State.ATTACK_3]:
		match _combo_count:
			1:
				animated_sprite.modulate = Color.WHITE
			2:
				animated_sprite.modulate = Color(0.7, 0.9, 1.0, 1.0)  # slight cyan tint
				ScreenFX.shake(0.08, 2.0)  # small shake on combo 2
			3:
				animated_sprite.modulate = Color(1.0, 0.9, 0.4, 1.0)  # gold tint
				ScreenFX.shake(0.12, 4.0)  # bigger shake on combo 3
	match state:
		State.DODGE:
			_is_dodging = true
			_dodge_timer = DODGE_DURATION
			_play_anim("run")
		State.SPECIAL:
			_special_held = false
			if _tier_label:
				_tier_label.visible = false
			if not _special_meter.use_tier(_special_tier):
				_change_state(State.IDLE)
				return
			_combo_count = 0
			_combo_timer = 0.0
			_buffered_input = &""
			_buffer_timer = 0.0
			if _weapon:
				hitbox.damage = _weapon.get_tier_damage(_special_tier)
			else:
				hitbox.damage = SPECIAL_DAMAGE * _special_tier
			hitbox.activate()
			match _special_tier:
				1:
					_play_anim("attack_1")
				2:
					_play_anim("attack_2")
				3:
					_play_anim("attack_3")
			# Flash player sprite the tier color.
			var tier_color: Color
			match _special_tier:
				1: tier_color = Color.CYAN
				2: tier_color = Color.MEDIUM_PURPLE
				3: tier_color = Color.GOLD
				_: tier_color = Color.WHITE
			var sprite_tween: Tween = create_tween()
			animated_sprite.modulate = tier_color
			sprite_tween.tween_property(animated_sprite, "modulate", Color.WHITE, 0.3 + 0.1 * float(_special_tier))
			# Scale hitbox collision shape by tier.
			var hitbox_shape: CollisionShape2D = hitbox.get_node("CollisionShape2D") as CollisionShape2D
			if hitbox_shape and hitbox_shape.shape is RectangleShape2D:
				var rect: RectangleShape2D = hitbox_shape.shape as RectangleShape2D
				match _special_tier:
					1:
						rect.size = _default_hitbox_size
						hitbox_shape.position = _default_hitbox_pos
					2:
						rect.size = Vector2(240.0, 200.0)
						hitbox_shape.position = Vector2(0.0, -104.0)
					3:
						rect.size = Vector2(800.0, 320.0)
						hitbox_shape.position = Vector2(0.0, -104.0)
			# Spawn VFX.
			var vfx: SpecialVFX = SpecialVFX.new()
			match _special_tier:
				1:
					vfx.setup(30.0, Color.CYAN, 0.3)
					vfx.position = Vector2(88.0 if not animated_sprite.flip_h else -88.0, -120.0)
				2:
					vfx.setup(60.0, Color.MEDIUM_PURPLE, 0.4)
					vfx.position = Vector2(0.0, -120.0)
				3:
					vfx.setup(120.0, Color.GOLD, 0.5)
					vfx.position = Vector2(0.0, -120.0)
			add_child(vfx)
			var flash_color: Color = Color.WHITE if _special_tier < 3 else Color.GOLD
			ScreenFX.flash(0.1 + 0.05 * float(_special_tier), flash_color)
			ScreenFX.shake(0.2 + 0.1 * float(_special_tier), 6.0 + 2.0 * float(_special_tier))
			# Tier-scaled hitstop on all enemies in range.
			var hitstop_duration: float = 0.03 * float(_special_tier)
			var hit_targets: Array[Node] = [self]
			for enemy: Node in get_tree().get_nodes_in_group("enemies"):
				if is_instance_valid(enemy):
					hit_targets.append(enemy)
			HitStop.freeze(hitstop_duration, hit_targets)
		State.HURT:
			_special_held = false
			_state_timer = HURT_DURATION
			_play_anim("hurt")
		State.KNOCKDOWN:
			_special_held = false
			_state_timer = KNOCKDOWN_DURATION
			_play_anim("dead")
		State.GETUP:
			_state_timer = GETUP_DURATION
			_play_anim("idle")
		State.DEAD:
			_special_held = false
			_play_anim("dead")


func _exit_state(state: State, next_state: State = State.IDLE) -> void:
	match state:
		State.DODGE:
			_is_dodging = false
		State.JUMP:
			# Keep the jump arc alive when transitioning to an air attack or a
			# damage state — the arc physics in _physics_process continues
			# independently; clearing here would snap the sprite to the ground.
			if next_state not in [State.ATTACK_1, State.ATTACK_2, State.ATTACK_3, State.HURT, State.KNOCKDOWN, State.DEAD]:
				_jump_height = 0.0
				_is_jumping = false
				animated_sprite.offset.y = -_frame_size / 2.0 + _feet_padding
		State.ATTACK_1, State.ATTACK_2, State.ATTACK_3, State.SPECIAL:
			hitbox.deactivate()
			# Restore default hitbox size after any attack or special.
			var hitbox_shape_exit: CollisionShape2D = hitbox.get_node("CollisionShape2D") as CollisionShape2D
			if hitbox_shape_exit and hitbox_shape_exit.shape is RectangleShape2D:
				(hitbox_shape_exit.shape as RectangleShape2D).size = _default_hitbox_size
				hitbox_shape_exit.position = _default_hitbox_pos
			if _combo_timer <= 0.0:
				_combo_count = 0
			# Clear combo tint when leaving an attack state.
			animated_sprite.modulate = Color.WHITE
			# If airborne and transitioning to a non-aerial, non-damage state,
			# land immediately.  Damage states let the arc continue so the hit
			# reaction plays at height before the player falls to the ground.
			if _is_jumping and next_state not in [State.JUMP, State.ATTACK_1, State.ATTACK_2, State.ATTACK_3, State.HURT, State.KNOCKDOWN, State.DEAD]:
				_is_jumping = false
				_jump_height = 0.0
				_jump_velocity = 0.0
				animated_sprite.offset.y = -_frame_size / 2.0 + _feet_padding


func _update_state(delta: float) -> void:
	match _state:
		State.IDLE:
			_update_idle(delta)
		State.MOVE:
			_update_move(delta)
		State.JUMP:
			_update_jump(delta)
		State.ATTACK_1:
			_update_attack(delta)
		State.ATTACK_2:
			_update_attack(delta)
		State.ATTACK_3:
			_update_attack(delta)
		State.DODGE:
			_update_dodge(delta)
		State.SPECIAL:
			_update_special(delta)
		State.HURT:
			_update_hurt(delta)
		State.KNOCKDOWN:
			_update_knockdown(delta)
		State.GETUP:
			_update_getup(delta)
		State.DEAD:
			_update_dead(delta)


# ===========================================================================
# Per-state update functions
# ===========================================================================

func _update_idle(_delta: float) -> void:
	# Check combat inputs.
	if not _special_held:
		if Input.is_action_just_pressed(_input_prefix + "light"):
			_change_state(State.ATTACK_1)
			return
		if Input.is_action_just_pressed(_input_prefix + "heavy"):
			_change_state(State.ATTACK_2)
			return
	if Input.is_action_just_pressed(_input_prefix + "jump"):
		_change_state(State.JUMP)
		return
	if Input.is_action_just_pressed(_input_prefix + "dodge"):
		_change_state(State.DODGE)
		return
	if Input.is_action_just_pressed(_input_prefix + "special"):
		if _special_meter.can_use_tier(1):
			_special_held = true
			_latched_tier = 1
		else:
			ScreenFX.flash(0.1, Color.RED)
	if _special_held and Input.is_action_just_released(_input_prefix + "special"):
		_special_held = false
		if _special_meter.can_use_tier(_latched_tier):
			_special_tier = _latched_tier
			_change_state(State.SPECIAL)
			return
		else:
			ScreenFX.flash(0.1, Color.RED)

	# Check movement.
	var input_dir := _get_input_direction()
	if input_dir.length() > 0.0:
		_change_state(State.MOVE)
		return


func _update_move(_delta: float) -> void:
	var input_dir := _get_input_direction()

	# Check combat inputs.
	if not _special_held:
		if Input.is_action_just_pressed(_input_prefix + "light"):
			_change_state(State.ATTACK_1)
			return
		if Input.is_action_just_pressed(_input_prefix + "heavy"):
			_change_state(State.ATTACK_2)
			return
	if Input.is_action_just_pressed(_input_prefix + "jump"):
		_change_state(State.JUMP)
		return
	if Input.is_action_just_pressed(_input_prefix + "dodge"):
		_change_state(State.DODGE)
		return
	if Input.is_action_just_pressed(_input_prefix + "special"):
		if _special_meter.can_use_tier(1):
			_special_held = true
			_latched_tier = 1
		else:
			ScreenFX.flash(0.1, Color.RED)
	if _special_held and Input.is_action_just_released(_input_prefix + "special"):
		_special_held = false
		if _special_meter.can_use_tier(_latched_tier):
			_special_tier = _latched_tier
			_change_state(State.SPECIAL)
			return
		else:
			ScreenFX.flash(0.1, Color.RED)

	# No movement → idle.
	if input_dir.length() < 0.001:
		_change_state(State.IDLE)
		return

	# Apply movement.
	_apply_movement(input_dir)

	# Flip sprite based on horizontal direction.
	if input_dir.x != 0.0:
		animated_sprite.flip_h = input_dir.x < 0.0


func _update_jump(_delta: float) -> void:
	# Allow attacking mid-air.
	if Input.is_action_just_pressed(_input_prefix + "light"):
		_change_state(State.ATTACK_1)
		return
	if Input.is_action_just_pressed(_input_prefix + "heavy"):
		_change_state(State.ATTACK_2)
		return

	# Horizontal movement during jump.
	var input_dir := _get_input_direction()
	if input_dir.length() > 0.0:
		_apply_movement(input_dir)
		if input_dir.x != 0.0:
			animated_sprite.flip_h = input_dir.x < 0.0
	else:
		velocity = Vector2.ZERO
		move_and_slide()


func _update_attack(delta: float) -> void:
	# Position hitbox in front of player based on facing direction.
	hitbox.position.x = 22.0 if not animated_sprite.flip_h else -22.0

	# Combo timer countdown.
	if _combo_timer > 0.0:
		_combo_timer -= delta
		if _combo_timer <= 0.0:
			_combo_count = 0
			_buffered_input = &""
			_buffer_timer = 0.0

	# Buffer attack input during animation.
	if Input.is_action_just_pressed(_input_prefix + "light"):
		_buffered_input = &"light"
		_buffer_timer = INPUT_BUFFER_TIME
	if Input.is_action_just_pressed(_input_prefix + "heavy"):
		_buffered_input = &"heavy"
		_buffer_timer = INPUT_BUFFER_TIME

	# Allow dodge cancel at any point during a ground attack.
	if not _is_jumping and Input.is_action_just_pressed(_input_prefix + "dodge"):
		_change_state(State.DODGE)
		return

	# Allow movement cancel once we are in recovery frames (>= 60% through
	# the animation).  Only applies on the ground — air attacks finish normally.
	if not _is_jumping and animated_sprite.sprite_frames:
		var anim: StringName = animated_sprite.animation
		var frame_count: int = animated_sprite.sprite_frames.get_frame_count(anim)
		if frame_count > 1:
			var progress: float = float(animated_sprite.frame) / float(frame_count - 1)
			if progress >= 0.6:
				var input_dir: Vector2 = _get_input_direction()
				var attacking: bool = Input.is_action_pressed(_input_prefix + "light") or Input.is_action_pressed(_input_prefix + "heavy")
				if input_dir.length() > 0.001 and not attacking:
					_change_state(State.MOVE)
					return

	# If jumping, keep the jump arc movement going.
	if _is_jumping:
		var input_dir: Vector2 = _get_input_direction()
		if input_dir.length() > 0.0:
			_apply_movement(input_dir)
			if input_dir.x != 0.0:
				animated_sprite.flip_h = input_dir.x < 0.0
		else:
			velocity = Vector2.ZERO
			move_and_slide()
	else:
		# Ground attacks: stop movement.
		velocity = Vector2.ZERO
		move_and_slide()


func _update_special(_delta: float) -> void:
	# Position hitbox in front of player for T1; centered for T2/T3.
	if _special_tier == 1:
		hitbox.position.x = 22.0 if not animated_sprite.flip_h else -22.0
	else:
		hitbox.position.x = 0.0

	# No movement during special — player stands and delivers.
	velocity = Vector2.ZERO
	move_and_slide()


func _update_dodge(delta: float) -> void:
	_dodge_timer -= delta
	var dodge_dir: float = -1.0 if animated_sprite.flip_h else 1.0
	velocity = Vector2(dodge_dir * DODGE_SPEED, 0)
	move_and_slide()

	if _dodge_timer <= 0.0:
		var input_dir := _get_input_direction()
		if input_dir.length() > 0.0:
			_change_state(State.MOVE)
		else:
			_change_state(State.IDLE)


func _update_hurt(delta: float) -> void:
	_state_timer -= delta
	velocity = Vector2.ZERO
	move_and_slide()
	if _state_timer <= 0.0:
		_change_state(State.IDLE)


func _update_knockdown(delta: float) -> void:
	_state_timer -= delta
	velocity = Vector2.ZERO
	move_and_slide()
	if _state_timer <= 0.0:
		_change_state(State.GETUP)


func _update_getup(delta: float) -> void:
	_state_timer -= delta
	velocity = Vector2.ZERO
	move_and_slide()
	if _state_timer <= 0.0:
		_change_state(State.IDLE)


func _update_dead(_delta: float) -> void:
	# No transitions — game over for this player.
	velocity = Vector2.ZERO
	move_and_slide()


# ===========================================================================
# Animation finished callback
# ===========================================================================

func _on_animation_finished() -> void:
	match _state:
		State.ATTACK_1:
			_on_attack_finished(State.ATTACK_2)
		State.ATTACK_2:
			_on_attack_finished(State.ATTACK_3)
		State.ATTACK_3:
			# Combo ends after third hit.
			_combo_count = 0
			_on_attack_chain_end()
		State.SPECIAL:
			_on_attack_chain_end()
		State.HURT:
			_change_state(State.IDLE)
		State.KNOCKDOWN:
			# Animation finished but stay in knockdown until timer expires.
			pass
		State.GETUP:
			_change_state(State.IDLE)


## Handle the end of an attack animation — check buffer/combo for chaining.
func _on_attack_finished(next_combo_state: State) -> void:
	# Check buffered input for combo continuation.
	if _buffered_input == &"light" and _combo_timer > 0.0:
		_buffered_input = &""
		_buffer_timer = 0.0
		_change_state(next_combo_state)
		return
	if _buffered_input == &"heavy":
		_buffered_input = &""
		_buffer_timer = 0.0
		_change_state(next_combo_state)
		return

	# No combo continuation — return to movement or idle.
	_on_attack_chain_end()


## Transition out of attack when the combo chain ends or breaks.
func _on_attack_chain_end() -> void:
	_buffered_input = &""
	_buffer_timer = 0.0
	# Clear combo tint.
	animated_sprite.modulate = Color.WHITE

	# If still in the air, go back to jump state.
	if _is_jumping:
		_change_state(State.JUMP)
		return

	var input_dir := _get_input_direction()
	if input_dir.length() > 0.0:
		_change_state(State.MOVE)
	else:
		_change_state(State.IDLE)


# ===========================================================================
# Public API for external systems (hitbox, health, etc.)
# ===========================================================================

## Call this from a hitbox/damage system to put the player into hurt state.
func take_damage() -> void:
	if _state == State.DEAD or _state == State.GETUP:
		return
	_change_state(State.HURT)


## Call this for heavy hits that knock the player down.
func knockdown() -> void:
	if _state == State.DEAD:
		return
	_change_state(State.KNOCKDOWN)


## Call this when HP reaches zero.
func die() -> void:
	_change_state(State.DEAD)


## Callback wired to [Hurtbox.damage_received] — applies damage, knockback,
## hitstop, and transitions to the appropriate state.
func _on_damage_received(amount: int, knockback: float, hitstun: float, attacker: Node) -> void:
	if _state == State.DEAD or _state == State.GETUP:
		return
	health.take_damage(amount)
	if _special_meter:
		_special_meter.add_points_from_damage_taken(amount)
	# Apply knockback direction.
	if attacker and is_instance_valid(attacker):
		var attacker_2d := attacker as Node2D
		if attacker_2d:
			var dir: float = signf(global_position.x - attacker_2d.global_position.x)
			velocity = Vector2(dir * knockback, 0)
	var _hit_entities: Array[Node] = [self]
	if attacker and is_instance_valid(attacker):
		_hit_entities.append(attacker)
	HitStop.freeze(0.05, _hit_entities)
	# Screen shake on player hit.
	ScreenFX.shake(0.15, 4.0)
	# Hit flash.
	if animated_sprite.material is ShaderMaterial:
		var mat: ShaderMaterial = animated_sprite.material as ShaderMaterial
		mat.set_shader_parameter("flash_amount", 1.0)
		var flash_tween: Tween = create_tween()
		flash_tween.tween_method(func(val: float) -> void:
			mat.set_shader_parameter("flash_amount", val)
		, 1.0, 0.0, 0.1)
	# Hit spark.
	if attacker and is_instance_valid(attacker):
		var attacker_2d := attacker as Node2D
		_spawn_hit_spark(attacker_2d.global_position if attacker_2d else global_position)
	if health.is_dead():
		_change_state(State.DEAD)
	elif _state == State.KNOCKDOWN:
		pass  # already down, don't interrupt
	else:
		_change_state(State.HURT)


## Callback wired to [Hitbox.damage_dealt] — fills special meter when dealing damage.
func _on_damage_dealt(amount: int, _target: Node) -> void:
	if _special_meter and _state != State.SPECIAL:
		_special_meter.add_points_from_damage_dealt(amount)


## Spawn a procedural hit spark at the impact point between self and the attacker.
func _spawn_hit_spark(attacker_pos: Vector2) -> void:
	var spark := GPUParticles2D.new()
	spark.emitting = true
	spark.one_shot = true
	spark.amount = 12
	spark.lifetime = 0.25
	spark.explosiveness = 1.0
	spark.z_index = 10
	spark.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

	# Position at hit point (between self and attacker, offset up to body center).
	var dir_to_attacker: Vector2 = (attacker_pos - global_position).normalized()
	spark.global_position = global_position + dir_to_attacker * 15.0
	spark.position.y -= 30.0

	# Glow blend mode.
	var canvas_mat := CanvasItemMaterial.new()
	canvas_mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	spark.material = canvas_mat

	# Crisp 2x2 pixel dot for pixel-art style sparks.
	var img := Image.create(2, 2, false, Image.FORMAT_RGBA8)
	img.fill(Color.WHITE)
	var tex := ImageTexture.create_from_image(img)
	spark.texture = tex

	# Particle behavior.
	var mat := ParticleProcessMaterial.new()
	mat.direction = Vector3((global_position.x - attacker_pos.x), -0.5, 0.0).normalized()
	mat.spread = 50.0
	mat.initial_velocity_min = 400.0
	mat.initial_velocity_max = 800.0
	mat.gravity = Vector3(0, 1200, 0)
	mat.damping_min = 3.0
	mat.damping_max = 6.0
	mat.scale_min = 1.0
	mat.scale_max = 3.0

	# Color: bright yellow/white → orange → fade out.
	var color_ramp := Gradient.new()
	color_ramp.set_color(0, Color(1.0, 1.0, 0.8, 1.0))  # bright white-yellow
	color_ramp.add_point(0.3, Color(1.0, 0.7, 0.2, 1.0))  # orange
	color_ramp.add_point(0.7, Color(1.0, 0.3, 0.1, 0.6))  # dark orange, fading
	color_ramp.set_color(1, Color(0.8, 0.1, 0.0, 0.0))   # red, transparent
	var color_tex := GradientTexture1D.new()
	color_tex.gradient = color_ramp
	mat.color_ramp = color_tex

	spark.process_material = mat

	# Add to scene root so it survives potential entity removal.
	get_tree().current_scene.add_child(spark)
	var timer: SceneTreeTimer = get_tree().create_timer(0.5)
	timer.timeout.connect(spark.queue_free)


func _show_combo_indicator() -> void:
	if _combo_count < 2:
		return
	var label := Label.new()
	label.text = "x%d!" % _combo_count
	label.add_theme_font_size_override("font_size", 16)
	label.add_theme_color_override("font_color", Color.GOLD if _combo_count >= 3 else Color.WHITE)
	label.add_theme_color_override("font_shadow_color", Color.BLACK)
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.z_index = 20
	label.position = Vector2(-10, -_frame_size * 0.6)
	add_child(label)
	# Float up and fade out.
	var tween: Tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(label, "position:y", label.position.y - 30.0, 0.6)
	tween.tween_property(label, "modulate:a", 0.0, 0.6)
	tween.chain().tween_callback(label.queue_free)


func is_dead() -> bool:
	return _state == State.DEAD


## Equip a weapon for this player. Pass null to revert to bare-fists.
## Call this from the camp / merchant screen before a wave starts.
func equip_weapon(weapon: WeaponData) -> void:
	_weapon = weapon


## Revive this player from DEAD state — resets HP to max, restores
## visibility, and returns to IDLE. Called by WaveManager on wave clear.
func revive() -> void:
	if _state != State.DEAD:
		return
	health.initialize()  # resets HP to max
	if _special_meter:
		_special_meter.reset()
	_change_state(State.IDLE)
	modulate.a = 1.0
	visible = true


# ===========================================================================
# Helpers
# ===========================================================================

## Return the special tier based on which modifier buttons are held at activation.
## Heavy (Y) takes priority over light (X) so both-held -> T3.
func _determine_special_tier() -> int:
	if Input.is_action_pressed(_input_prefix + "heavy"):
		return 3
	if Input.is_action_pressed(_input_prefix + "light"):
		return 2
	return 1


## Build a procedural radial gradient ImageTexture for use as a PointLight2D
## texture. Produces a soft circular falloff with quadratic rolloff.
func _create_light_texture() -> ImageTexture:
	var size: int = 64
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var center := Vector2(float(size) / 2.0, float(size) / 2.0)
	for y_px: int in range(size):
		for x_px: int in range(size):
			var dist: float = Vector2(float(x_px), float(y_px)).distance_to(center) / (float(size) / 2.0)
			var intensity: float = clampf(1.0 - dist, 0.0, 1.0)
			intensity = intensity * intensity  # quadratic falloff
			img.set_pixel(x_px, y_px, Color(intensity, intensity, intensity, 1.0))
	return ImageTexture.create_from_image(img)


## Play an animation with a has_animation guard.
func _play_anim(anim_name: String) -> void:
	if animated_sprite.sprite_frames and animated_sprite.sprite_frames.has_animation(anim_name):
		animated_sprite.play(anim_name)


## Apply standard movement from an input direction vector.
func _apply_movement(input_dir: Vector2) -> void:
	velocity = Vector2(
		input_dir.x * move_speed,
		input_dir.y * move_speed * VERTICAL_SPEED_FACTOR
	)
	move_and_slide()


## Read the four directional actions for this player and return a normalised
## direction vector.
func _get_input_direction() -> Vector2:
	var dir := Vector2.ZERO
	dir.x = Input.get_axis(_input_prefix + "move_left", _input_prefix + "move_right")
	dir.y = Input.get_axis(_input_prefix + "move_up", _input_prefix + "move_down")
	if dir.length() > 1.0:
		dir = dir.normalized()
	return dir


# ===========================================================================
# Debug overlay
# ===========================================================================

func _setup_debug_label() -> void:
	_debug_label = Label.new()
	_debug_label.add_theme_font_size_override("font_size", 10)
	_debug_label.add_theme_color_override("font_color", Color.YELLOW)
	_debug_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_debug_label.add_theme_constant_override("outline_size", 2)
	_debug_label.position = Vector2(-30, -_frame_size - 12)
	_debug_label.visible = false
	add_child(_debug_label)


func _setup_tier_label() -> void:
	_tier_label = Label.new()
	_tier_label.add_theme_font_size_override("font_size", 12)
	_tier_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_tier_label.add_theme_constant_override("outline_size", 2)
	_tier_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_tier_label.position = Vector2(-16, -_frame_size - 24)
	_tier_label.visible = false
	add_child(_tier_label)


func _update_tier_indicator() -> void:
	if not _tier_label:
		return
	if not _special_held:
		_tier_label.visible = false
		return

	# Latch tier upward when X/Y pressed during hold
	if Input.is_action_just_pressed(_input_prefix + "heavy") and _latched_tier < 3:
		_latched_tier = 3
	elif Input.is_action_just_pressed(_input_prefix + "light") and _latched_tier < 2:
		_latched_tier = 2

	_tier_label.visible = true
	match _latched_tier:
		1:
			_tier_label.text = "T1"
			_tier_label.add_theme_color_override("font_color", Color.CYAN)
		2:
			_tier_label.text = "T2"
			_tier_label.add_theme_color_override("font_color", Color.MEDIUM_PURPLE)
		3:
			_tier_label.text = "T3"
			_tier_label.add_theme_color_override("font_color", Color.GOLD)


func _update_debug() -> void:
	if not _debug_label:
		return
	var debug_on: bool = InputManager.entity_debug_visible
	_debug_label.visible = debug_on
	if not debug_on:
		return

	var state_name: String = State.keys()[_state] as String
	var hp_current: int = health.current_hp
	var hp_max: int = health.max_hp
	var meter_segs: int = 0
	if _special_meter:
		meter_segs = _special_meter.get_segments()
	var hitbox_on: bool = hitbox.monitoring
	var hurtbox_mode: String = _process_mode_name(hurtbox.process_mode)
	var entity_mode: String = _process_mode_name(process_mode)

	var extra: String = ""
	if _is_jumping:
		extra = " air"
	if _buffered_input != &"":
		extra += " buf:" + str(_buffered_input)

	_debug_label.text = (
		"P%d %s%s\nHP:%d/%d M:%d\nhit:%s hurt:%s\nproc:%s"
		% [player_id, state_name, extra,
		   hp_current, hp_max, meter_segs,
		   "ON" if hitbox_on else "off",
		   hurtbox_mode, entity_mode]
	)


## Convert ProcessMode enum to string for debug display.
static func _process_mode_name(mode: int) -> String:
	match mode:
		0: return "INHERIT"
		1: return "PAUSABLE"
		2: return "WHEN_PAUSED"
		3: return "ALWAYS"
		4: return "DISABLED"
	return "UNKNOWN"


# ===========================================================================
# Sprite loading (unchanged)
# ===========================================================================

## Build a SpriteFrames resource by loading every sprite sheet found in the
## given folder and slicing it into 96x96 AtlasTexture frames.
func _load_sprite_frames(folder_path: String) -> SpriteFrames:
	var frames := SpriteFrames.new()
	# Remove the default animation that SpriteFrames ships with.
	if frames.has_animation("default"):
		frames.remove_animation("default")

	for file_name: String in ANIM_MAP:
		var anim_name: String = ANIM_MAP[file_name]
		var path: String = folder_path + file_name + ".png"
		if not ResourceLoader.exists(path):
			continue

		var texture: Texture2D = load(path)
		_frame_size = texture.get_height()
		var frame_count: int = int(texture.get_width() / float(_frame_size))

		frames.add_animation(anim_name)

		# Determine FPS — attacks get a slightly faster rate.
		var fps: float = DEFAULT_ANIM_FPS
		if anim_name.begins_with("attack") or anim_name == "run_attack":
			fps = ATTACK_ANIM_FPS
		frames.set_animation_speed(anim_name, fps)
		frames.set_animation_loop(anim_name, anim_name in LOOPING_ANIMS)

		for i in range(frame_count):
			var atlas := AtlasTexture.new()
			atlas.atlas = texture
			atlas.region = Rect2(i * _frame_size, 0, _frame_size, _frame_size)
			frames.add_frame(anim_name, atlas)

	return frames


## Generate a procedural shadow ellipse positioned at the character's feet.
func _setup_shadow() -> void:
	var shadow_width: int = 48
	var shadow_height: int = 14
	var shadow_image := Image.create(shadow_width, shadow_height, false, Image.FORMAT_RGBA8)
	shadow_image.fill(Color(0, 0, 0, 0))  # transparent
	var center := Vector2(shadow_width / 2.0, shadow_height / 2.0)
	var rx := shadow_width / 2.0
	var ry := shadow_height / 2.0
	for y in range(shadow_height):
		for x in range(shadow_width):
			var dx := (x - center.x) / rx
			var dy := (y - center.y) / ry
			if dx * dx + dy * dy <= 1.0:
				shadow_image.set_pixel(x, y, Color(0, 0, 0, 0.35))
	shadow.texture = ImageTexture.create_from_image(shadow_image)
	shadow.offset = Vector2.ZERO
