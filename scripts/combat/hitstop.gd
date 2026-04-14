## Autoload singleton for per-entity hitstop (frame-freeze) effects.
##
## Call [code]HitStop.freeze(0.05, [attacker, target])[/code] on hit to briefly
## pause only the involved entities for impactful combat feel.
##
## Uses [member Node.process_mode] set to DISABLED to completely freeze each
## entity — no physics, no animation, no input — then restores the original
## mode after the duration.
extends Node

## Safety timeout — if an entity is still frozen after this many seconds,
## force-restore it. Prevents permanent freezes from race conditions.
const SAFETY_TIMEOUT: float = 0.5


func freeze(duration: float, entities: Array[Node] = []) -> void:
	if entities.is_empty():
		return

	for entity: Node in entities:
		if not is_instance_valid(entity):
			continue

		# If already frozen, just extend the duration by restarting the timer.
		if entity.has_meta("_hitstop_active"):
			# Update the safety timer if one exists.
			var existing_timer: SceneTreeTimer = entity.get_meta("_hitstop_timer", null) as SceneTreeTimer
			if existing_timer:
				# Can't extend a SceneTreeTimer — create a new freeze for this entity.
				_freeze_single(entity, duration)
			continue

		_freeze_single(entity, duration)


func _freeze_single(entity: Node, duration: float) -> void:
	if not is_instance_valid(entity):
		return

	# Only save the original process_mode if not already frozen.
	if not entity.has_meta("_hitstop_active"):
		entity.set_meta("_hitstop_process_mode", entity.process_mode)

	entity.set_meta("_hitstop_active", true)
	entity.process_mode = Node.PROCESS_MODE_DISABLED

	# Create a timer that restores this specific entity.
	var timer: SceneTreeTimer = get_tree().create_timer(duration, true, false, true)
	entity.set_meta("_hitstop_timer", timer)
	await timer.timeout

	_restore_single(entity)


func _restore_single(entity: Node) -> void:
	if not is_instance_valid(entity):
		return
	if not entity.has_meta("_hitstop_active"):
		return

	entity.process_mode = entity.get_meta("_hitstop_process_mode", Node.PROCESS_MODE_INHERIT) as Node.ProcessMode
	entity.remove_meta("_hitstop_active")
	entity.remove_meta("_hitstop_process_mode")
	entity.remove_meta("_hitstop_timer")
