## Base enemy controller for 2.5D beat 'em up AI.
##
## Uses an enum-based finite state machine (IDLE, APPROACH, ATTACK, STAGGER, DEATH).
## Loads sprite sheets at runtime from [member sprite_folder] using the same
## AtlasTexture-slicing pattern as the player.
##
## Subclass or instance directly for different enemy types by changing exports.
class_name EnemyBase
extends CharacterBody2D

enum State { IDLE, APPROACH, ATTACK, STAGGER, DEATH }

@export var max_hp: int = 30
@export var move_speed: float = 40.0
@export var attack_range: float = 35.0
@export var attack_damage: int = 10
@export var knockback_force: float = 80.0
@export var stagger_duration: float = 0.3
@export var attack_cooldown: float = 1.0

## Sprite folder path — override per-enemy type.
@export var sprite_folder: String = "res://assets/sprites/enemies/Craftpix_Orc/Orc_Warrior/"

const FRAME_SIZE: int = 96
const BELT_MIN_Y: float = 115.0
const BELT_MAX_Y: float = 235.0

## Vertical speed multiplier for depth feel (same as player).
const VERTICAL_SPEED_FACTOR: float = 0.7

## Y-axis tolerance for lining up to attack.
const Y_ATTACK_TOLERANCE: float = 15.0

## Brief pause in IDLE before re-acquiring a target.
const IDLE_THINK_TIME: float = 0.4

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

const DEFAULT_ANIM_FPS: float = 10.0
const ATTACK_ANIM_FPS: float = 12.0

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

var _state: State = State.IDLE
var _state_timer: float = 0.0
var _cooldown_timer: float = 0.0
var _target: Node = null

@onready var animated_sprite: AnimatedSprite2D = $AnimatedSprite2D
@onready var shadow: Sprite2D = $Shadow
@onready var hitbox: Hitbox = $Hitbox
@onready var hurtbox: Hurtbox = $Hurtbox
@onready var health: HealthComponent = $HealthComponent


func _ready() -> void:
	add_to_group("enemies")
	animated_sprite.sprite_frames = _load_sprite_frames(sprite_folder)
	animated_sprite.offset = Vector2(0, -FRAME_SIZE / 2.0)
	animated_sprite.animation_finished.connect(_on_animation_finished)
	_setup_shadow()
	hitbox.owner_entity = self
	hitbox.damage = attack_damage
	hitbox.knockback_force = knockback_force
	hurtbox.owner_entity = self
	hurtbox.damage_received.connect(_on_damage_received)
	health.initialize(max_hp)
	_change_state(State.IDLE)


func _physics_process(delta: float) -> void:
	# Cooldown countdown.
	if _cooldown_timer > 0.0:
		_cooldown_timer -= delta

	_update_state(delta)

	# Belt clamp and depth sort.
	position.y = clampf(position.y, BELT_MIN_Y, BELT_MAX_Y)
	z_index = int(position.y)


# ===========================================================================
# State machine core
# ===========================================================================

func _change_state(new_state: State) -> void:
	if new_state == _state:
		if new_state == State.STAGGER:
			_state_timer = stagger_duration
		return
	_exit_state(_state)
	_state = new_state
	_enter_state(new_state)


func _enter_state(state: State) -> void:
	match state:
		State.IDLE:
			_state_timer = IDLE_THINK_TIME
			_play_anim("idle")
		State.APPROACH:
			_play_anim("walk")
		State.ATTACK:
			hitbox.damage = attack_damage
			hitbox.activate()
			_play_anim("attack_1")
		State.STAGGER:
			_state_timer = stagger_duration
			_play_anim("hurt")
		State.DEATH:
			_play_anim("dead")


func _exit_state(state: State) -> void:
	match state:
		State.ATTACK:
			hitbox.deactivate()
			EnemyGroupManager.release_attack(self)
			_cooldown_timer = attack_cooldown


func _update_state(delta: float) -> void:
	match _state:
		State.IDLE:
			_update_idle(delta)
		State.APPROACH:
			_update_approach(delta)
		State.ATTACK:
			_update_attack(delta)
		State.STAGGER:
			_update_stagger(delta)
		State.DEATH:
			_update_death(delta)


# ===========================================================================
# Per-state updates
# ===========================================================================

func _update_idle(delta: float) -> void:
	_state_timer -= delta
	velocity = Vector2.ZERO
	move_and_slide()

	if _state_timer <= 0.0:
		_target = _find_nearest_player()
		if _target:
			_change_state(State.APPROACH)
		else:
			# No player found, reset think timer.
			_state_timer = IDLE_THINK_TIME


func _update_approach(_delta: float) -> void:
	if not _target or not is_instance_valid(_target):
		_target = _find_nearest_player()
		if not _target:
			_change_state(State.IDLE)
			return

	# Check if in attack range and cooldown is done.
	if _is_in_attack_range(_target) and _cooldown_timer <= 0.0:
		if EnemyGroupManager.request_attack(self):
			_change_state(State.ATTACK)
			return
		else:
			# Denied by group manager, wait briefly.
			velocity = Vector2.ZERO
			move_and_slide()
			return

	# Move toward target.
	var dir := _get_direction_to_target(_target)

	# Flip sprite to face the target.
	if dir.x != 0.0:
		animated_sprite.flip_h = dir.x < 0.0

	velocity = Vector2(
		dir.x * move_speed,
		dir.y * move_speed * VERTICAL_SPEED_FACTOR
	)
	move_and_slide()


func _update_attack(_delta: float) -> void:
	# Position hitbox in front of enemy based on facing direction.
	hitbox.position.x = 25.0 if not animated_sprite.flip_h else -25.0

	velocity = Vector2.ZERO
	move_and_slide()


func _update_stagger(delta: float) -> void:
	_state_timer -= delta
	# Apply knockback decay.
	velocity = velocity.lerp(Vector2.ZERO, 0.15)
	move_and_slide()

	if _state_timer <= 0.0:
		if health.is_dead():
			_change_state(State.DEATH)
		else:
			_change_state(State.APPROACH)


func _update_death(_delta: float) -> void:
	velocity = Vector2.ZERO
	move_and_slide()


# ===========================================================================
# Animation finished callback
# ===========================================================================

func _on_animation_finished() -> void:
	match _state:
		State.ATTACK:
			_change_state(State.IDLE)
		State.DEATH:
			# Brief delay then remove.
			var tween := create_tween()
			tween.tween_property(self, "modulate:a", 0.0, 0.5)
			tween.tween_callback(queue_free)


# ===========================================================================
# Combat callbacks
# ===========================================================================

func _on_damage_received(amount: int, knockback: float, hitstun: float, attacker: Node) -> void:
	if _state == State.DEATH:
		return
	health.take_damage(amount)
	# Apply knockback direction.
	if attacker and is_instance_valid(attacker):
		var dir := sign(global_position.x - attacker.global_position.x)
		velocity = Vector2(dir * knockback, 0)
	HitStop.freeze(0.05)
	if health.is_dead():
		_change_state(State.DEATH)
	else:
		_change_state(State.STAGGER)


# ===========================================================================
# AI helpers
# ===========================================================================

func _find_nearest_player() -> Node:
	var players := get_tree().get_nodes_in_group("players")
	var closest: Node = null
	var closest_dist: float = INF
	for p in players:
		if not is_instance_valid(p):
			continue
		# Skip dead players.
		if p.has_method("is_dead") and p.is_dead():
			continue
		var dist: float = global_position.distance_to(p.global_position)
		if dist < closest_dist:
			closest_dist = dist
			closest = p
	return closest


func _get_direction_to_target(target: Node) -> Vector2:
	return (target.global_position - global_position).normalized()


func _is_in_attack_range(target: Node) -> bool:
	var dist := global_position.distance_to(target.global_position)
	var y_close := abs(global_position.y - target.global_position.y) < Y_ATTACK_TOLERANCE
	return dist < attack_range and y_close


# ===========================================================================
# Animation & sprite loading
# ===========================================================================

func _play_anim(anim_name: String) -> void:
	if animated_sprite.sprite_frames and animated_sprite.sprite_frames.has_animation(anim_name):
		animated_sprite.play(anim_name)


func _load_sprite_frames(folder_path: String) -> SpriteFrames:
	var frames := SpriteFrames.new()
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


func _setup_shadow() -> void:
	var shadow_width: int = 48
	var shadow_height: int = 14
	var shadow_image := Image.create(shadow_width, shadow_height, false, Image.FORMAT_RGBA8)
	shadow_image.fill(Color(0, 0, 0, 0))
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
