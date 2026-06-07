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
@export var move_speed: float = 160.0
@export var attack_range: float = 220.0
@export var attack_damage: int = 10
@export var knockback_force: float = 320.0
@export var stagger_duration: float = 0.3
@export var attack_cooldown: float = 1.0

## Sprite folder path — override per-enemy type.
@export var sprite_folder: String = "res://assets/sprites/enemies/Craftpix_Orc/Orc_Warrior/"

const FRAME_SIZE: int = 96
const BELT_MIN_Y: float = 900.0
const BELT_MAX_Y: float = 1380.0

## Vertical speed multiplier for depth feel (same as player).
const VERTICAL_SPEED_FACTOR: float = 0.7

## Y-axis tolerance for lining up to attack.
const Y_ATTACK_TOLERANCE: float = 100.0

## Brief pause in IDLE before re-acquiring a target.
const IDLE_THINK_TIME: float = 0.4

const RETARGET_INTERVAL: float = 0.5
const SEPARATION_RADIUS: float = 160.0
const SEPARATION_FORCE: float = 240.0

## Enemies stop approaching when this close to target.
const STANDOFF_DISTANCE: float = 220.0
## When waiting (denied attack), drift to this distance from target.
const ORBIT_DISTANCE: float = 280.0
## Force pushing enemy away from player when too close.
const PLAYER_REPEL_FORCE: float = 320.0

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
var _target: Node2D = null
var _retarget_timer: float = 0.0
var _last_attacker: Node = null

## Launch physics for combo finisher.
var _launch_height: float = 0.0
var _launch_velocity: float = 0.0
var _is_launched: bool = false
var _launch_h_velocity: float = 0.0
const LAUNCH_GRAVITY: float = 2400.0

## Debug overlay.
var _debug_label: Label = null

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
	_setup_debug_label()
	hitbox.owner_entity = self
	hitbox.damage = attack_damage
	hitbox.knockback_force = knockback_force
	hurtbox.owner_entity = self
	hurtbox.damage_received.connect(_on_damage_received)
	health.initialize(max_hp)
	_change_state(State.IDLE)

	# Apply hit flash shader material.
	var shader_mat := ShaderMaterial.new()
	shader_mat.shader = load("res://shaders/hit_flash.gdshader")
	animated_sprite.material = shader_mat


func _physics_process(delta: float) -> void:
	# Cooldown countdown.
	if _cooldown_timer > 0.0:
		_cooldown_timer -= delta

	# Launch arc physics.
	if _is_launched:
		_launch_velocity += LAUNCH_GRAVITY * delta
		_launch_height += _launch_velocity * delta
		# Horizontal movement during launch.
		velocity = Vector2(_launch_h_velocity, 0.0)
		move_and_slide()
		_launch_h_velocity *= 0.95  # air drag
		if _launch_height >= 0.0 and _launch_velocity > 0.0:
			# Landed.
			_launch_height = 0.0
			_is_launched = false
			_launch_h_velocity = 0.0
			velocity = Vector2.ZERO
			animated_sprite.offset.y = -FRAME_SIZE / 2.0
		else:
			animated_sprite.offset.y = (-FRAME_SIZE / 2.0) + _launch_height

	_update_state(delta)

	# Belt clamp and depth sort.
	position.y = clampf(position.y, BELT_MIN_Y, BELT_MAX_Y)
	z_index = int(position.y)

	# Debug overlay.
	_update_debug()


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
			_retarget_timer = RETARGET_INTERVAL
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
			if _last_attacker and is_instance_valid(_last_attacker):
				var pid: int = int(_last_attacker.get("player_id"))
				if pid > 0:
					GameManager.add_score(pid - 1, max_hp)


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


func _update_approach(delta: float) -> void:
	if not _target or not is_instance_valid(_target):
		_target = _find_nearest_player()
		if not _target:
			_change_state(State.IDLE)
			return

	# Periodically re-evaluate target.
	_retarget_timer -= delta
	if _retarget_timer <= 0.0:
		_retarget_timer = RETARGET_INTERVAL
		var nearest: Node2D = _find_nearest_player()
		if nearest:
			if nearest != _target:
				var current_dist: float = global_position.distance_to(_target.global_position)
				var nearest_dist: float = global_position.distance_to(nearest.global_position)
				if nearest_dist < current_dist * 0.6:
					_target = nearest
			# If current target is dead, always switch
			if _target.has_method("is_dead") and _target.is_dead():
				_target = nearest

	# Check if in attack range and cooldown is done.
	if _is_in_attack_range(_target) and _cooldown_timer <= 0.0:
		if EnemyGroupManager.request_attack(self):
			_change_state(State.ATTACK)
			return
		else:
			# Denied by group manager — back off to orbit distance and spread.
			var to_target: Vector2 = _target.global_position - global_position
			var dist_to_target: float = to_target.length()
			var away_dir: Vector2 = Vector2.ZERO
			if dist_to_target > 0.01:
				away_dir = -to_target.normalized()
			# Push away if too close to the player.
			var repel: Vector2 = Vector2.ZERO
			if dist_to_target < ORBIT_DISTANCE:
				repel = away_dir * PLAYER_REPEL_FORCE * (1.0 - dist_to_target / ORBIT_DISTANCE)
			velocity = repel + _get_separation_force()
			# Keep facing the target.
			if to_target.x != 0.0:
				animated_sprite.flip_h = to_target.x < 0.0
			move_and_slide()
			return

	# Move toward target with separation from other enemies.
	var dir: Vector2 = _get_direction_to_target(_target)
	var separation: Vector2 = _get_separation_force()
	var dist_to_target: float = global_position.distance_to(_target.global_position)

	# Flip sprite to face the target.
	if dir.x != 0.0:
		animated_sprite.flip_h = dir.x < 0.0

	var move_velocity: Vector2
	if dist_to_target <= STANDOFF_DISTANCE:
		# At standoff — stop X but keep aligning Y if needed.
		var y_diff: float = _target.global_position.y - global_position.y
		if absf(y_diff) > Y_ATTACK_TOLERANCE - 5.0:
			move_velocity = Vector2(0.0, signf(y_diff) * move_speed * VERTICAL_SPEED_FACTOR)
		else:
			move_velocity = Vector2.ZERO
	else:
		move_velocity = Vector2(
			dir.x * move_speed,
			dir.y * move_speed * VERTICAL_SPEED_FACTOR
		)

	# Add repel force if too close to player.
	var repel: Vector2 = Vector2.ZERO
	if dist_to_target < STANDOFF_DISTANCE * 0.7:
		var away: Vector2 = (global_position - _target.global_position).normalized()
		repel = away * PLAYER_REPEL_FORCE

	velocity = move_velocity + separation + repel
	move_and_slide()


func _update_attack(_delta: float) -> void:
	# Position hitbox in front of enemy based on facing direction.
	hitbox.position.x = 100.0 if not animated_sprite.flip_h else -100.0

	velocity = Vector2.ZERO
	move_and_slide()


func _update_stagger(delta: float) -> void:
	_state_timer -= delta
	# Apply knockback decay.
	velocity = velocity.lerp(Vector2.ZERO, 0.15)
	move_and_slide()

	if _is_launched:
		return  # Don't recover while airborne.
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
	print("[Enemy] Damage received: %d HP:%d/%d state:%s attacker:%s" % [amount, health.current_hp, health.max_hp, State.keys()[_state], str(attacker)])
	if _state == State.DEATH:
		return
	_last_attacker = attacker
	health.take_damage(amount)
	# Apply knockback direction.
	if attacker and is_instance_valid(attacker):
		var attacker_2d := attacker as Node2D
		if attacker_2d:
			var dir: float = signf(global_position.x - attacker_2d.global_position.x)
			velocity = Vector2(dir * knockback, 0.0)
	var _hit_entities: Array[Node] = [self]
	if attacker and is_instance_valid(attacker):
		_hit_entities.append(attacker)
	HitStop.freeze(0.05, _hit_entities)
	# Screen shake on enemy hit.
	ScreenFX.shake(0.1, 3.0)
	# Launch on heavy combo finisher (Attack_3 does 25+ damage).
	if amount >= 25:
		_is_launched = true
		_launch_velocity = -1400.0
		_launch_height = 0.0
		# Horizontal knockback away from attacker.
		if attacker and is_instance_valid(attacker):
			var attacker_2d := attacker as Node2D
			if attacker_2d:
				_launch_h_velocity = signf(global_position.x - attacker_2d.global_position.x) * 800.0
		ScreenFX.shake(0.25, 8.0)
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
		_change_state(State.DEATH)
	else:
		_change_state(State.STAGGER)


# ===========================================================================
# AI helpers
# ===========================================================================

func _get_separation_force() -> Vector2:
	var force: Vector2 = Vector2.ZERO
	var neighbors: Array[Node] = get_tree().get_nodes_in_group("enemies")
	for n: Node in neighbors:
		var other := n as Node2D
		if not other or other == self or not is_instance_valid(other):
			continue
		var dist: float = global_position.distance_to(other.global_position)
		if dist < SEPARATION_RADIUS and dist > 0.01:
			var away: Vector2 = (global_position - other.global_position).normalized()
			force += away * (1.0 - dist / SEPARATION_RADIUS)
	return (force * SEPARATION_FORCE).limit_length(SEPARATION_FORCE)


func _find_nearest_player() -> Node2D:
	var players := get_tree().get_nodes_in_group("players")
	var closest: Node2D = null
	var closest_dist: float = INF
	for p: Node2D in players:
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


func _get_direction_to_target(target: Node2D) -> Vector2:
	return (target.global_position - global_position).normalized()


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


func _is_in_attack_range(target: Node2D) -> bool:
	var dist: float = global_position.distance_to(target.global_position)
	var y_close: float = absf(global_position.y - target.global_position.y)
	return dist <= attack_range and y_close < Y_ATTACK_TOLERANCE


# ===========================================================================
# Debug overlay
# ===========================================================================

func _setup_debug_label() -> void:
	_debug_label = Label.new()
	_debug_label.add_theme_font_size_override("font_size", 10)
	_debug_label.add_theme_color_override("font_color", Color.TOMATO)
	_debug_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_debug_label.add_theme_constant_override("outline_size", 2)
	_debug_label.position = Vector2(-30, -FRAME_SIZE - 12)
	_debug_label.visible = false
	add_child(_debug_label)


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
	var target_name: String = "none"
	if _target and is_instance_valid(_target):
		target_name = _target.name
	var hitbox_on: bool = hitbox.monitoring
	var hurtbox_mode: String = _process_mode_name(hurtbox.process_mode)
	var entity_mode: String = _process_mode_name(process_mode)
	var cooldown_str: String = "%.2f" % maxf(_cooldown_timer, 0.0)

	_debug_label.text = (
		"%s\nHP:%d/%d tgt:%s\nhit:%s hurt:%s\nproc:%s cd:%s"
		% [state_name, hp_current, hp_max, target_name,
		   "ON" if hitbox_on else "off",
		   hurtbox_mode, entity_mode, cooldown_str]
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
