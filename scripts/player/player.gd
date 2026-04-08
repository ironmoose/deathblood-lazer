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
@export var move_speed: float = 60.0

## Top edge of the playable belt (Y coordinate).
@export var belt_min_y: float = 85.0

## Bottom edge of the playable belt (Y coordinate).
@export var belt_max_y: float = 175.0

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


func _ready() -> void:
	var folder: String = SPRITE_PATHS.get(player_id, SPRITE_PATHS[1])
	animated_sprite.sprite_frames = _load_sprite_frames(folder)
	# Offset the sprite so the feet (bottom of the frame) sit at the origin.
	# AnimatedSprite2D centers the texture by default, so -half moves bottom to origin.
	animated_sprite.offset = Vector2(0, -FRAME_SIZE / 2.0)
	animated_sprite.play("idle")
	_setup_shadow()


func _physics_process(_delta: float) -> void:
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

	# Switch between walk and idle animations.
	_update_animation(input_dir)

	# Z-index follows Y so lower characters render in front.
	z_index = int(position.y)


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
	if current in ["attack_1", "attack_2", "attack_3", "run_attack", "hurt", "dead"]:
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
