## Manages enemy wave spawning.
##
## Monitors the "enemies" group. When all enemies are dead/freed,
## heals and revives all players, waits a delay, then spawns a new wave.
class_name WaveManager
extends Node

## Packed scene for the grunt enemy.
@export var enemy_scene: PackedScene

## Seconds to wait between wave clear and next spawn.
@export var wave_delay: float = 2.0

## Number of enemies per wave.
@export var enemies_per_wave: int = 3

## Current wave number (starts at 1 for the pre-placed enemies).
var current_wave: int = 1

var _waiting_for_next_wave: bool = false
var _entities: Node2D = null


func _ready() -> void:
	_entities = get_tree().current_scene.get_node("Game/Entities") as Node2D
	assert(_entities != null, "WaveManager: could not find Game/Entities")
	_waiting_for_next_wave = true
	await get_tree().process_frame
	_waiting_for_next_wave = false


func _physics_process(_delta: float) -> void:
	if _waiting_for_next_wave:
		return

	# Check if all enemies are gone.
	var enemies: Array[Node] = get_tree().get_nodes_in_group("enemies")
	if enemies.size() == 0:
		_on_wave_cleared()


func _on_wave_cleared() -> void:
	_waiting_for_next_wave = true

	# Heal and revive all players.
	var players := get_tree().get_nodes_in_group("players")
	for p: Node in players:
		var player := p as Node2D
		if not player:
			continue
		if player.has_method("revive") and player.has_method("is_dead") and player.is_dead():
			player.revive()  # revive() already heals to full
		elif not (player.has_method("is_dead") and player.is_dead()):
			# Alive player -- just heal to full
			var hp_comp := player.get_node("HealthComponent") as HealthComponent
			if hp_comp:
				hp_comp.heal(hp_comp.max_hp)

	# Wait before spawning next wave.
	await get_tree().create_timer(wave_delay).timeout
	if not is_instance_valid(self):
		return
	_spawn_wave()


func _spawn_wave() -> void:
	current_wave += 1
	var spawn_x: float = 2320.0
	for i: int in range(enemies_per_wave):
		var enemy: Node2D = enemy_scene.instantiate() as Node2D
		# Spread enemies across the belt (900-1380 Y range)
		var y_pos: float = 1100.0 + (i * 160.0)
		y_pos = clampf(y_pos, 900.0, 1380.0)
		enemy.position = Vector2(spawn_x + (i * 160), y_pos)
		_entities.add_child(enemy)
	_waiting_for_next_wave = false
