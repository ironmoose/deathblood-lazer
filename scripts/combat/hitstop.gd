## Autoload singleton for per-entity hitstop (frame-freeze) effects.
##
## Call [code]HitStop.freeze(0.05, [attacker, target])[/code] on hit to briefly
## pause only the involved entities for impactful combat feel.
##
## Uses [member Node.process_mode] set to DISABLED to completely freeze each
## entity — no physics, no animation, no input — then restores the original
## mode after the duration.
extends Node


func freeze(duration: float, entities: Array[Node] = []) -> void:
	if entities.is_empty():
		return

	# Freeze each entity by disabling all processing.
	for entity: Node in entities:
		if not is_instance_valid(entity):
			continue
		# Skip if already frozen by another hit.
		if entity.has_meta("_hitstop_active"):
			continue
		entity.set_meta("_hitstop_active", true)
		entity.set_meta("_hitstop_process_mode", entity.process_mode)
		entity.process_mode = Node.PROCESS_MODE_DISABLED

	# Wait using a SceneTree timer (process_always so it fires while entities are disabled).
	await get_tree().create_timer(duration, true, false, true).timeout

	# Restore each entity.
	for entity: Node in entities:
		if not is_instance_valid(entity):
			continue
		if not entity.has_meta("_hitstop_active"):
			continue
		entity.process_mode = entity.get_meta("_hitstop_process_mode", Node.PROCESS_MODE_INHERIT) as Node.ProcessMode
		entity.remove_meta("_hitstop_active")
		entity.remove_meta("_hitstop_process_mode")
