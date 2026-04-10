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
@export var move_speed: float = 200.0

## Top edge of the playable belt (Y coordinate).
@export var belt_min_y: float = 115.0

## Bottom edge of the playable belt (Y coordinate).
@export var belt_max_y: float = 235.0

## Vertical speed multiplier to give a depth / perspective feel.
const VERTICAL_SPEED_FACTOR: float = 0.7

## Frame size in the sprite sheets (all sheets use 96x96 frames).
const FRAME_SIZE: int = 96

## Sprite folder paths keyed by player_id.
const SPRITE_PATHS: Dictionary = {
	1: "res://assets/sprites/enemies/Craftpix_Orc/Orc_Berserk/",
	2: "res://assets/sprites/characters/Warrior_1/",
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
const ATTACK_ANIM_FPS: float = 12.0

## Light-attack combo window.
const COMBO_WINDOW: float = 0.5  # seconds to chain next hit

## Dodge constants.
const DODGE_SPEED: float = 300.0
const DODGE_DURATION: float = 0.2

## Jump arc constants.
const JUMP_FORCE: float = 200.0  # initial upward velocity
const GRAVITY: float = 600.0     # pulls back down

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

## Cached input prefix (set once in _ready).
var _input_prefix: String = ""

## Debug overlay.
var _debug_label: Label = null
var _debug_visible: bool = false

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
	animated_sprite.offset = Vector2(0, -FRAME_SIZE / 2.0)
	animated_sprite.animation_finished.connect(_on_animation_finished)
	_setup_shadow()
	_setup_debug_label()
	hitbox.owner_entity = self
	hurtbox.owner_entity = self
	hurtbox.damage_received.connect(_on_damage_received)
	_input_prefix = "p%d_" % player_id
	health.initialize()
	# Create and wire special meter.
	_special_meter = SpecialMeter.new()
	add_child(_special_meter)
	hitbox.damage_dealt.connect(_on_damage_dealt)
	_change_state(State.IDLE)


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
			if _state in [State.JUMP, State.ATTACK_1, State.ATTACK_2, State.ATTACK_3]:
				var input_dir := _get_input_direction()
				if input_dir.length() > 0.0:
					_change_state(State.MOVE)
				else:
					_change_state(State.IDLE)

		# Apply jump height as visual offset on the sprite (negative = up).
		animated_sprite.offset.y = (-FRAME_SIZE / 2.0) + _jump_height
	else:
		# On ground — restore normal offset.
		animated_sprite.offset.y = -FRAME_SIZE / 2.0

	# Run state-specific update.
	_update_state(delta)

	# Common post-update: clamp to belt, update z_index.
	position.y = clampf(position.y, belt_min_y, belt_max_y)
	z_index = int(position.y)

	# Debug overlay.
	if Input.is_action_just_pressed("ui_home"):  # F2 fallback — see _unhandled_input
		_toggle_debug()
	_update_debug()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_F2:
		_toggle_debug()


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
		State.ATTACK_3:
			_combo_count = 3
			_combo_timer = COMBO_WINDOW
			hitbox.damage = 25
			hitbox.activate()
			_play_anim("attack_3")
		State.DODGE:
			_is_dodging = true
			_dodge_timer = DODGE_DURATION
			_play_anim("run")
		State.SPECIAL:
			if not _special_meter.consume_segment():
				_change_state(State.IDLE)
				return
			_combo_count = 0
			_combo_timer = 0.0
			_buffered_input = &""
			_buffer_timer = 0.0
			hitbox.damage = SPECIAL_DAMAGE
			hitbox.activate()
			_play_anim("attack_3")
			ScreenFX.flash(0.15, Color.WHITE)
			ScreenFX.shake(0.3, 8.0)
		State.HURT:
			_state_timer = HURT_DURATION
			_play_anim("hurt")
		State.KNOCKDOWN:
			_state_timer = KNOCKDOWN_DURATION
			_play_anim("dead")
		State.GETUP:
			_state_timer = GETUP_DURATION
			_play_anim("idle")
		State.DEAD:
			_play_anim("dead")


func _exit_state(state: State, next_state: State = State.IDLE) -> void:
	match state:
		State.DODGE:
			_is_dodging = false
		State.JUMP:
			# Keep the jump arc alive when transitioning to an air attack.
			# The arc physics in _physics_process continues independently;
			# clearing here would snap the character to the ground.
			if next_state not in [State.ATTACK_1, State.ATTACK_2, State.ATTACK_3]:
				_jump_height = 0.0
				_is_jumping = false
				animated_sprite.offset.y = -FRAME_SIZE / 2.0
		State.ATTACK_1, State.ATTACK_2, State.ATTACK_3, State.SPECIAL:
			hitbox.deactivate()
			if _combo_timer <= 0.0:
				_combo_count = 0
			# If airborne and transitioning to a non-aerial state, land immediately.
			if _is_jumping and next_state not in [State.JUMP, State.ATTACK_1, State.ATTACK_2, State.ATTACK_3]:
				_is_jumping = false
				_jump_height = 0.0
				_jump_velocity = 0.0
				animated_sprite.offset.y = -FRAME_SIZE / 2.0


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
		if _special_meter.can_use_special():
			_change_state(State.SPECIAL)
			return

	# Check movement.
	var input_dir := _get_input_direction()
	if input_dir.length() > 0.0:
		_change_state(State.MOVE)
		return


func _update_move(_delta: float) -> void:
	var input_dir := _get_input_direction()

	# Check combat inputs.
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
		if _special_meter.can_use_special():
			_change_state(State.SPECIAL)
			return

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
	# Position hitbox in front of player.
	hitbox.position.x = 22.0 if not animated_sprite.flip_h else -22.0

	# No movement during special — player stands and delivers.
	velocity = Vector2.ZERO
	move_and_slide()


func _update_dodge(delta: float) -> void:
	_dodge_timer -= delta
	var dodge_dir := -1.0 if animated_sprite.flip_h else 1.0
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
		var dir: float = sign(global_position.x - (attacker as Node2D).global_position.x)
		velocity = Vector2(dir * knockback, 0)
	var _hit_entities: Array[Node] = [self]
	if attacker and is_instance_valid(attacker):
		_hit_entities.append(attacker)
	HitStop.freeze(0.05, _hit_entities)
	if health.is_dead():
		_change_state(State.DEAD)
	elif _state == State.KNOCKDOWN:
		pass  # already down, don't interrupt
	else:
		_change_state(State.HURT)


## Callback wired to [Hitbox.damage_dealt] — fills special meter when dealing damage.
func _on_damage_dealt(amount: int, _target: Node) -> void:
	if _special_meter:
		_special_meter.add_points_from_damage_dealt(amount)


func is_dead() -> bool:
	return _state == State.DEAD


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
	_debug_label.position = Vector2(-30, -FRAME_SIZE - 12)
	_debug_label.visible = _debug_visible
	add_child(_debug_label)


func _toggle_debug() -> void:
	_debug_visible = not _debug_visible
	if _debug_label:
		_debug_label.visible = _debug_visible


func _update_debug() -> void:
	if _debug_label and _debug_visible:
		var state_name: String = State.keys()[_state]
		var extra := ""
		if _is_jumping:
			extra = " (air)"
		if _buffered_input != &"":
			extra += " buf:" + str(_buffered_input)
		var meter_info: String = ""
		if _special_meter:
			meter_info = " M:%d" % _special_meter.get_segments()
		_debug_label.text = "P%d %s%s%s" % [player_id, state_name, extra, meter_info]


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
		var frame_count: int = int(texture.get_width() / float(FRAME_SIZE))

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
			atlas.region = Rect2(i * FRAME_SIZE, 0, FRAME_SIZE, FRAME_SIZE)
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
