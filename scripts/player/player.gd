## Player character controller for 2.5D beat 'em up movement.
##
## Supports two players via [member player_id]. Reads input actions prefixed
## with "p1_" or "p2_" and moves on an 8-directional grid clamped to the
## play belt (Y range). Vertical speed is reduced to ~70% for depth feel.
##
## Loads sprite sheets from disk based on player_id and builds SpriteFrames
## at runtime so each player has unique art.
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

@onready var animated_sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var shadow: Sprite2D = $Shadow

## Light-attack combo state.
var _combo_count: int = 0
var _combo_timer: float = 0.0
const COMBO_WINDOW: float = 0.5  # seconds to chain next hit

## Dodge state.
var _is_dodging: bool = false
var _dodge_timer: float = 0.0
const DODGE_SPEED: float = 300.0
const DODGE_DURATION: float = 0.2

## Jump arc state.
var _is_jumping: bool = false
var _jump_velocity: float = 0.0
var _jump_height: float = 0.0  # current visual offset (0 = on ground)

const JUMP_FORCE: float = 200.0  # initial upward velocity
const GRAVITY: float = 600.0     # pulls back down


func _ready() -> void:
	var folder: String = SPRITE_PATHS.get(player_id, SPRITE_PATHS[1])
	animated_sprite.sprite_frames = _load_sprite_frames(folder)
	# Offset the sprite so the feet (bottom of the frame) sit at the origin.
	# AnimatedSprite2D centers the texture by default, so -half moves bottom to origin.
	animated_sprite.offset = Vector2(0, -FRAME_SIZE / 2.0)
	animated_sprite.play("idle")
	_setup_shadow()


func _physics_process(delta: float) -> void:
	# Jump arc physics — update visual offset independent of other movement.
	if _is_jumping:
		_jump_velocity += GRAVITY * delta
		_jump_height += _jump_velocity * delta

		if _jump_height >= 0.0:
			# Landed
			_jump_height = 0.0
			_is_jumping = false
			_jump_velocity = 0.0

		# Apply jump height as visual offset on the sprite (negative = up).
		animated_sprite.offset.y = (-FRAME_SIZE / 2.0) + _jump_height
	else:
		# On ground — restore normal offset.
		animated_sprite.offset.y = -FRAME_SIZE / 2.0

	# Handle dodge movement — skip normal movement while dodging.
	if _is_dodging:
		_dodge_timer -= delta
		var dodge_dir := -1.0 if animated_sprite.flip_h else 1.0
		velocity = Vector2(dodge_dir * DODGE_SPEED, 0)
		move_and_slide()
		position.y = clampf(position.y, belt_min_y, belt_max_y)
		if _dodge_timer <= 0.0:
			_is_dodging = false
		return  # skip normal movement during dodge

	# Combo timer countdown.
	if _combo_timer > 0.0:
		_combo_timer -= delta
		if _combo_timer <= 0.0:
			_combo_count = 0

	var input_dir := _get_input_direction()

	# Build velocity vector with reduced vertical speed.
	velocity = Vector2(
		input_dir.x * move_speed,
		input_dir.y * move_speed * VERTICAL_SPEED_FACTOR
	)

	move_and_slide()

	# Clamp position to play belt.
	position.y = clampf(position.y, belt_min_y, belt_max_y)

	# Flip sprite based on horizontal direction.
	if input_dir.x != 0.0:
		animated_sprite.flip_h = input_dir.x < 0.0

	# Check for combat inputs before updating locomotion animation.
	_handle_combat_input()

	# Switch between walk and idle animations.
	_update_animation(input_dir)

	# Z-index follows Y so lower characters render in front.
	z_index = int(position.y)


## Check for combat-related input (attacks, jump, dodge) and play the
## appropriate one-shot animation.
func _handle_combat_input() -> void:
	var prefix := "p%d_" % player_id

	# Don't accept new combat input during one-shot animations.
	var current := animated_sprite.animation
	if current in ["attack_1", "attack_2", "attack_3", "run_attack", "hurt", "dead", "jump"]:
		if animated_sprite.is_playing():
			return

	# Jump
	if Input.is_action_just_pressed(prefix + "jump"):
		if not _is_jumping:
			_is_jumping = true
			_jump_velocity = -JUMP_FORCE  # negative = up in screen coords
			if animated_sprite.sprite_frames.has_animation("jump"):
				animated_sprite.play("jump")
		return

	# Light attack — cycles through attack_1, attack_2, attack_3 for basic combo.
	if Input.is_action_just_pressed(prefix + "light"):
		_do_light_attack()
		return

	# Heavy attack
	if Input.is_action_just_pressed(prefix + "heavy"):
		if animated_sprite.sprite_frames.has_animation("attack_2"):
			animated_sprite.play("attack_2")
		return

	# Dodge — quick dash in facing direction.
	if Input.is_action_just_pressed(prefix + "dodge"):
		_do_dodge()
		return


## Execute the next hit in the 3-hit light-attack combo chain.
func _do_light_attack() -> void:
	_combo_count += 1
	_combo_timer = COMBO_WINDOW

	match _combo_count:
		1:
			if animated_sprite.sprite_frames.has_animation("attack_1"):
				animated_sprite.play("attack_1")
		2:
			if animated_sprite.sprite_frames.has_animation("attack_2"):
				animated_sprite.play("attack_2")
		_:
			if animated_sprite.sprite_frames.has_animation("attack_3"):
				animated_sprite.play("attack_3")
			else:
				if animated_sprite.sprite_frames.has_animation("attack_1"):
					animated_sprite.play("attack_1")
			_combo_count = 0  # reset after 3rd hit


## Start a dodge: short burst of speed in the current facing direction.
func _do_dodge() -> void:
	_is_dodging = true
	_dodge_timer = DODGE_DURATION
	if animated_sprite.sprite_frames.has_animation("run"):
		animated_sprite.play("run")


## Read the four directional actions for this player and return a normalised
## direction vector.
func _get_input_direction() -> Vector2:
	var prefix := "p%d_" % player_id
	var dir := Vector2.ZERO
	dir.x = Input.get_axis(prefix + "move_left", prefix + "move_right")
	dir.y = Input.get_axis(prefix + "move_up", prefix + "move_down")
	if dir.length() > 1.0:
		dir = dir.normalized()
	return dir


## Select the correct animation based on movement state.
# TODO: Wire up run animation when sprint/run input is added.
func _update_animation(input_dir: Vector2) -> void:
	var current := animated_sprite.animation
	# Don't interrupt one-shot animations (attacks, hurt, dead).
	if current in ["attack_1", "attack_2", "attack_3", "run_attack", "hurt", "dead", "jump"]:
		if animated_sprite.is_playing():
			return

	if input_dir.length() > 0.0:
		if animated_sprite.sprite_frames.has_animation("walk"):
			if current != "walk":
				animated_sprite.play("walk")
	else:
		if current != "idle":
			animated_sprite.play("idle")


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
