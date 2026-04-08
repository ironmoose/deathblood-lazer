## Autoload singleton for hitstop (frame-freeze) effects.
##
## Call [code]HitStop.freeze(0.05)[/code] on hit to briefly pause the game
## for impactful combat feel.
extends Node


func freeze(duration: float) -> void:
	Engine.time_scale = 0.05
	await get_tree().create_timer(duration, true, false, true).timeout
	Engine.time_scale = 1.0
