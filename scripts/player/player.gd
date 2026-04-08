## Player character controller for 2.5D beat 'em up movement.
##
## Supports two players via [member player_id]. Reads input actions prefixed
## with "p1_" or "p2_" and moves on an 8-directional grid clamped to the
## play belt (Y range). Vertical speed is reduced to ~70% for depth feel.
extends CharacterBody2D

## Which player this instance represents (1 or 2). Determines input prefix.
@export var player_id: int = 1

## Horizontal / vertical base movement speed in pixels per second.
@export var move_speed: float = 200.0

## Top edge of the playable belt (Y coordinate).
@export var belt_min_y: float = 400.0

## Bottom edge of the playable belt (Y coordinate).
@export var belt_max_y: float = 600.0

## Vertical speed multiplier to give a depth / perspective feel.
const VERTICAL_SPEED_FACTOR: float = 0.7

## Placeholder body size.
const BODY_WIDTH: int = 32
const BODY_HEIGHT: int = 48

@onready var sprite: Sprite2D = $Sprite2D
@onready var shadow: Sprite2D = $Shadow


func _ready() -> void:
	_setup_placeholder_visuals()


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
		sprite.flip_h = input_dir.x < 0.0

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


## Build coloured placeholder textures so the game is playable without art.
func _setup_placeholder_visuals() -> void:
	# Body colour: P1 = blue, P2 = green.
	var body_color: Color
	if player_id == 1:
		body_color = Color(0.2, 0.4, 0.9, 1.0)  # blue
	else:
		body_color = Color(0.2, 0.8, 0.3, 1.0)  # green

	# Create body texture.
	var body_image := Image.create(BODY_WIDTH, BODY_HEIGHT, false, Image.FORMAT_RGBA8)
	body_image.fill(body_color)
	sprite.texture = ImageTexture.create_from_image(body_image)
	# Offset so bottom of rectangle aligns with the character's feet (origin).
	sprite.offset = Vector2(0, -BODY_HEIGHT / 2.0)

	# Create shadow texture (dark semi-transparent ellipse).
	var shadow_size := Vector2i(BODY_WIDTH + 8, 12)
	var shadow_image := Image.create(shadow_size.x, shadow_size.y, false, Image.FORMAT_RGBA8)
	shadow_image.fill(Color(0, 0, 0, 0))  # transparent
	var center := Vector2(shadow_size.x / 2.0, shadow_size.y / 2.0)
	var rx := shadow_size.x / 2.0
	var ry := shadow_size.y / 2.0
	for y in range(shadow_size.y):
		for x in range(shadow_size.x):
			var dx := (x - center.x) / rx
			var dy := (y - center.y) / ry
			if dx * dx + dy * dy <= 1.0:
				shadow_image.set_pixel(x, y, Color(0, 0, 0, 0.35))
	shadow.texture = ImageTexture.create_from_image(shadow_image)
	shadow.offset = Vector2.ZERO
