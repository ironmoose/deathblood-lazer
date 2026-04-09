## Autoload singleton for per-entity hitstop (frame-freeze) effects.
##
## Call [code]HitStop.freeze(0.05, [attacker, target])[/code] on hit to briefly
## pause only the involved entities for impactful combat feel.
extends Node


func freeze(duration: float, entities: Array[Node] = []) -> void:
	if entities.is_empty():
		return

	# Pause each entity's animation and physics.
	for entity: Node in entities:
		if not is_instance_valid(entity):
			continue
		# Skip if already frozen — don't stomp the saved velocity.
		if entity.has_meta("_hitstop_active"):
			continue
		entity.set_meta("_hitstop_active", true)
		var sprite := entity.get_node_or_null("AnimatedSprite2D") as AnimatedSprite2D
		if sprite:
			entity.set_meta("_hitstop_frame", sprite.frame)
			entity.set_meta("_hitstop_progress", sprite.frame_progress)
			sprite.pause()
		if entity is CharacterBody2D:
			entity.set_meta("_hitstop_vel", entity.velocity)
			entity.velocity = Vector2.ZERO

	# Wait using a SceneTree timer (process_always=true so it fires regardless).
	await get_tree().create_timer(duration, true, false, true).timeout

	# Restore each entity.
	for entity: Node in entities:
		if not is_instance_valid(entity):
			continue
		if not entity.has_meta("_hitstop_active"):
			continue
		entity.remove_meta("_hitstop_active")
		var sprite := entity.get_node_or_null("AnimatedSprite2D") as AnimatedSprite2D
		if sprite:
			var anim: StringName = sprite.animation
			var frame_idx: int = entity.get_meta("_hitstop_frame", 0)
			var frame_prog: float = entity.get_meta("_hitstop_progress", 0.0)
			sprite.play(anim)
			sprite.frame = frame_idx
			sprite.frame_progress = frame_prog
			entity.remove_meta("_hitstop_frame")
			entity.remove_meta("_hitstop_progress")
		if entity is CharacterBody2D and entity.has_meta("_hitstop_vel"):
			entity.velocity = entity.get_meta("_hitstop_vel")
			entity.remove_meta("_hitstop_vel")
