## Reusable Hitbox component for melee/projectile attacks.
##
## Sits on the attacker. When activated, detects overlapping [Hurtbox] areas
## and delivers damage, knockback, and hitstun exactly once per target per
## activation window. Call [method activate] at the start of an attack and
## [method deactivate] when it ends (or on animation finish).
class_name Hitbox
extends Area2D

const Y_HIT_TOLERANCE: float = 28.0

@export var damage: int = 10
@export var knockback_force: float = 100.0
@export var hitstun_duration: float = 0.2

## The entity that owns this hitbox (set by parent).
var owner_entity: Node = null

## Track what we've already hit this attack to prevent multi-hits.
var _hit_targets: Array[Node] = []


func activate() -> void:
	monitoring = true
	_hit_targets.clear()


func deactivate() -> void:
	monitoring = false
	_hit_targets.clear()


func _ready() -> void:
	monitoring = false  # off by default
	area_entered.connect(_on_area_entered)


func _on_area_entered(area: Area2D) -> void:
	if area is Hurtbox:
		var target: Node = area.owner_entity
		if target and target != owner_entity and target not in _hit_targets:
			# Y-axis depth check for 2.5D belt alignment.
			var owner_2d := owner_entity as Node2D
			var target_2d := target as Node2D
			if owner_2d and target_2d:
				if absf(owner_2d.global_position.y - target_2d.global_position.y) > Y_HIT_TOLERANCE:
					return
			_hit_targets.append(target)
			area.take_damage(damage, knockback_force, hitstun_duration, owner_entity)
