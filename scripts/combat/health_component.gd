## Reusable health component for any damageable entity.
##
## Tracks current and maximum HP, emits signals on change and death.
## Attach as a child node and call [method take_damage] / [method heal].
class_name HealthComponent
extends Node

signal health_changed(current: int, maximum: int)
signal died

@export var max_hp: int = 100
var current_hp: int


func _ready() -> void:
	# Parent sets max_hp and calls initialize() after.
	pass


func initialize(hp: int = -1) -> void:
	if hp > 0:
		max_hp = hp
	current_hp = max_hp


func take_damage(amount: int) -> void:
	current_hp = maxi(current_hp - amount, 0)
	health_changed.emit(current_hp, max_hp)
	if current_hp <= 0:
		died.emit()


func heal(amount: int) -> void:
	current_hp = mini(current_hp + amount, max_hp)
	health_changed.emit(current_hp, max_hp)


func is_dead() -> bool:
	return current_hp <= 0
