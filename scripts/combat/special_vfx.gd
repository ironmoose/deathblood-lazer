## Procedural VFX node that draws an expanding, fading colored circle.
##
## Spawn via SpecialVFX.new(), call setup(), set position, then add_child().
## Frees itself when the animation completes.
class_name SpecialVFX
extends Node2D

var _radius: float = 0.0
var _max_radius: float = 40.0
var _color: Color = Color.CYAN
var _duration: float = 0.3
var _timer: float = 0.0


func setup(max_radius: float, color: Color, duration: float) -> void:
	_max_radius = max_radius
	_color = color
	_duration = duration


func _process(delta: float) -> void:
	_timer += delta
	var t: float = _timer / _duration
	if t >= 1.0:
		queue_free()
		return
	_radius = _max_radius * t
	_color.a = 1.0 - t
	queue_redraw()


func _draw() -> void:
	if _radius > 0.0:
		draw_circle(Vector2.ZERO, _radius, _color)
		draw_arc(Vector2.ZERO, _radius, 0.0, TAU, 32, Color(_color, 0.8), 2.0)
