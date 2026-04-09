## Autoload pause overlay — freezes game and shows "PAUSED!!!" text.
extends CanvasLayer


var _paused: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 100

	# Dark semi-transparent background.
	var bg := ColorRect.new()
	bg.color = Color(0, 0, 0, 0.5)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# Center container for the label.
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)

	# Big PAUSED!!! text.
	var label := Label.new()
	label.text = "PAUSED!!!"
	label.add_theme_font_size_override("font_size", 48)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 4)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	center.add_child(label)

	# Start hidden.
	_set_overlay_visible(false)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not event.is_echo():
		_toggle_pause()
		get_viewport().set_input_as_handled()


func _toggle_pause() -> void:
	_paused = not _paused
	get_tree().paused = _paused
	_set_overlay_visible(_paused)


func _set_overlay_visible(show: bool) -> void:
	for child in get_children():
		if child is CanvasItem:
			child.visible = show
