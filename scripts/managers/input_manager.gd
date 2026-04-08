## InputManager autoload singleton.
##
## Handles controller hot-plugging by remapping joypad device IDs on the
## InputMap at runtime. When controllers connect or disconnect, the p1_* and
## p2_* input actions are updated so their JoypadButton / JoypadMotion events
## point at the correct physical device.
##
## Also provides an optional debug overlay (toggle with F3) showing which
## controllers are connected and their player assignments.
extends Node

## Emitted after device assignments change so other systems can react.
signal devices_remapped(p1_device: int, p2_device: int)

## The device index currently assigned to each player slot (-1 = none).
var player_devices: Array[int] = [-1, -1]

# --- Debug overlay nodes ---
var _debug_layer: CanvasLayer
var _debug_label: Label
var _debug_visible: bool = false


func _ready() -> void:
	_setup_debug_overlay()
	Input.joy_connection_changed.connect(_on_joy_connection_changed)
	_remap_joy_devices()


func _input(event: InputEvent) -> void:
	# Toggle debug overlay with F3.
	if event is InputEventKey and event.pressed and event.keycode == KEY_F3:
		_debug_visible = not _debug_visible
		_debug_layer.visible = _debug_visible


## Returns the physical device index assigned to the given player (0-indexed).
## Returns -1 if no controller is assigned to that slot.
func get_device_for_player(player_id: int) -> int:
	if player_id >= 0 and player_id < player_devices.size():
		return player_devices[player_id]
	return -1


# --------------------------------------------------------------------------- #
#  Core remapping logic                                                        #
# --------------------------------------------------------------------------- #

func _on_joy_connection_changed(_device: int, _connected: bool) -> void:
	_remap_joy_devices()


## Scan connected joypads and update every p1_*/p2_* input action so that
## JoypadButton and JoypadMotion events point at the correct physical device.
func _remap_joy_devices() -> void:
	var connected := Input.get_connected_joypads()

	# Assign first connected pad to P1, second to P2.
	# Fall back to the "expected" device index (0 / 1) when nothing is plugged
	# in so the project.godot defaults still work if a pad was there at launch.
	var p1_device: int = connected[0] if connected.size() > 0 else 0
	var p2_device: int = connected[1] if connected.size() > 1 else 1

	player_devices[0] = p1_device if connected.size() > 0 else -1
	player_devices[1] = p2_device if connected.size() > 1 else -1

	for action_name in InputMap.get_actions():
		var target_device: int = -1
		if action_name.begins_with("p1_"):
			target_device = p1_device if player_devices[0] != -1 else 0
		elif action_name.begins_with("p2_"):
			target_device = p2_device if player_devices[1] != -1 else 1
		else:
			continue

		# Godot returns copies of events, so we must erase + re-add to persist changes.
		var events := InputMap.action_get_events(action_name)
		for event in events:
			if event is InputEventJoypadButton or event is InputEventJoypadMotion:
				var new_event := event.duplicate() as InputEvent
				new_event.device = target_device
				InputMap.action_erase_event(action_name, event)
				InputMap.action_add_event(action_name, new_event)

	devices_remapped.emit(player_devices[0], player_devices[1])
	_update_debug_label()

	# Log to console so hot-plug events are visible during development.
	var pad_names: Array[String] = []
	for idx in connected:
		pad_names.append("  device %d: %s" % [idx, Input.get_joy_name(idx)])
	if pad_names.is_empty():
		print("[InputManager] No controllers connected. Keyboard only.")
	else:
		print("[InputManager] Controllers remapped:")
		for line in pad_names:
			print(line)
		print("  P1 -> device %d | P2 -> device %d" % [p1_device, p2_device])


# --------------------------------------------------------------------------- #
#  Debug overlay                                                               #
# --------------------------------------------------------------------------- #

func _setup_debug_overlay() -> void:
	_debug_layer = CanvasLayer.new()
	_debug_layer.layer = 100  # On top of everything.
	_debug_layer.visible = _debug_visible
	add_child(_debug_layer)

	var panel := PanelContainer.new()
	panel.anchor_left = 0.0
	panel.anchor_top = 0.0
	panel.offset_left = 8.0
	panel.offset_top = 8.0

	# Semi-transparent dark background.
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0, 0, 0, 0.7)
	style.set_corner_radius_all(4)
	style.set_content_margin_all(8)
	panel.add_theme_stylebox_override("panel", style)

	_debug_label = Label.new()
	_debug_label.add_theme_font_size_override("font_size", 14)
	_debug_label.add_theme_color_override("font_color", Color.WHITE)
	panel.add_child(_debug_label)

	_debug_layer.add_child(panel)
	_update_debug_label()


func _update_debug_label() -> void:
	if _debug_label == null:
		return

	var connected := Input.get_connected_joypads()
	var lines: Array[String] = []
	lines.append("[F3] Controller Debug")
	lines.append("Connected: %d" % connected.size())
	lines.append("")

	if connected.is_empty():
		lines.append("No controllers detected.")
		lines.append("Plug in a gamepad — it will be")
		lines.append("assigned automatically.")
	else:
		for idx in connected:
			var role := ""
			if player_devices[0] == idx:
				role = " [P1]"
			elif player_devices[1] == idx:
				role = " [P2]"
			lines.append("device %d: %s%s" % [idx, Input.get_joy_name(idx), role])

	lines.append("")
	lines.append("P1 device: %d" % player_devices[0])
	lines.append("P2 device: %d" % player_devices[1])

	_debug_label.text = "\n".join(lines)
