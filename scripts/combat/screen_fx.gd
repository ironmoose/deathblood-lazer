## Autoload singleton for screen shake and white flash effects.
##
## Screen shake is applied via the root viewport canvas transform offset.
## Flash is rendered via a CanvasLayer with a ColorRect overlay at layer 100.
##
## Both effects use PROCESS_MODE_ALWAYS so they play correctly during hitstop
## (when entity nodes are set to PROCESS_MODE_DISABLED).
extends Node

## CanvasLayer for the flash overlay (highest layer).
var _flash_layer: CanvasLayer
var _flash_rect: ColorRect
var _shake_timer: float = 0.0
var _shake_intensity: float = 0.0
var _original_offset: Vector2 = Vector2.ZERO
var _flash_tween: Tween = null


func _ready() -> void:
	# Ensure shake and flash always process, even during hitstop.
	process_mode = Node.PROCESS_MODE_ALWAYS

	# Create flash overlay.
	_flash_layer = CanvasLayer.new()
	_flash_layer.layer = 100
	add_child(_flash_layer)

	_flash_rect = ColorRect.new()
	_flash_rect.color = Color(1.0, 1.0, 1.0, 0.0)
	_flash_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_flash_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash_layer.add_child(_flash_rect)


func _process(delta: float) -> void:
	if _shake_timer > 0.0:
		_shake_timer -= delta
		var offset: Vector2 = Vector2(
			randf_range(-_shake_intensity, _shake_intensity),
			randf_range(-_shake_intensity, _shake_intensity)
		)
		get_viewport().canvas_transform.origin = _original_offset + offset
		if _shake_timer <= 0.0:
			get_viewport().canvas_transform.origin = _original_offset
			_shake_intensity = 0.0


## Trigger a screen shake effect.
## [param duration] seconds the shake lasts.
## [param intensity] maximum pixel offset per axis.
func shake(duration: float = 0.3, intensity: float = 6.0) -> void:
	if _shake_timer <= 0.0:
		_original_offset = get_viewport().canvas_transform.origin
	_shake_timer = duration
	_shake_intensity = intensity


## Trigger a full-screen flash effect.
## [param duration] seconds the flash takes to fade out.
## [param color] the flash color (default white).
func flash(duration: float = 0.15, color: Color = Color.WHITE) -> void:
	if _flash_tween and _flash_tween.is_running():
		_flash_tween.kill()
	_flash_rect.color = Color(color.r, color.g, color.b, 0.7)
	_flash_tween = create_tween()
	_flash_tween.tween_property(_flash_rect, "color:a", 0.0, duration)
