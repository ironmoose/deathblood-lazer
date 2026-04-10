## HUD for 2P co-op beat 'em up.
##
## Displays player status (health bar, special meter, score), shared lives,
## and wires to HealthComponent, SpecialMeter, and GameManager signals.
## All nodes are built in code — no .tscn required.
## Sits on CanvasLayer at layer 10, process_mode ALWAYS.
extends CanvasLayer

## Colors matching player characters.
const P1_COLOR: Color = Color(0.9, 0.5, 0.1)       # orange (dad/Orc)
const P2_COLOR: Color = Color(0.2, 0.5, 0.9)       # blue (Wiley/Warrior)
const BAR_BG_COLOR: Color = Color(0.15, 0.15, 0.15)
const METER_EMPTY_COLOR: Color = Color(0.3, 0.3, 0.3)
const METER_FULL_COLOR: Color = Color(1.0, 0.85, 0.0)  # gold

const HEALTH_BAR_WIDTH: float = 80.0
const HEALTH_BAR_HEIGHT: float = 8.0
const METER_SEGMENT_WIDTH: float = 24.0
const METER_SEGMENT_HEIGHT: float = 4.0
const METER_GAP: float = 2.0

## Per-player node references.
var _p1_health_fill: ColorRect
var _p1_health_flash: ColorRect
var _p1_meter_segments: Array[ColorRect] = []
var _p1_score_label: Label

var _p2_health_fill: ColorRect
var _p2_health_flash: ColorRect
var _p2_meter_segments: Array[ColorRect] = []
var _p2_score_label: Label

var _lives_label: Label

## Previous HP tracked for damage-flash detection.
var _p1_prev_hp: int = -1
var _p2_prev_hp: int = -1

## Active tween references for damage flash (one per player prevents stacking).
var _p1_flash_tween: Tween = null
var _p2_flash_tween: Tween = null


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS

	# Root layout: 4 px margins around the whole HUD strip.
	var margin: MarginContainer = MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	margin.add_theme_constant_override("margin_left", 4)
	margin.add_theme_constant_override("margin_right", 4)
	margin.add_theme_constant_override("margin_top", 4)
	margin.add_theme_constant_override("margin_bottom", 4)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(margin)

	# Horizontal row: [P1 status] [spacer] [lives] [spacer] [P2 status]
	var hbox: HBoxContainer = HBoxContainer.new()
	hbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_child(hbox)

	# --- P1 status (left) ---
	var p1_vbox: VBoxContainer = VBoxContainer.new()
	p1_vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_child(p1_vbox)

	var p1_name: Label = _make_name_label("P1", P1_COLOR)
	p1_vbox.add_child(p1_name)

	var p1_bar_result: Array[ColorRect] = _make_health_bar(P1_COLOR)
	_p1_health_fill = p1_bar_result[0]
	_p1_health_flash = p1_bar_result[1]
	p1_vbox.add_child(p1_bar_result[2])

	var p1_meter_hbox: HBoxContainer = _make_meter_hbox()
	_p1_meter_segments = _collect_meter_segments(p1_meter_hbox)
	p1_vbox.add_child(p1_meter_hbox)

	_p1_score_label = _make_score_label()
	p1_vbox.add_child(_p1_score_label)

	# --- Spacer to push lives to center ---
	var left_spacer: Control = Control.new()
	left_spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_child(left_spacer)

	# --- Lives (center) ---
	_lives_label = _make_lives_label()
	hbox.add_child(_lives_label)

	# --- Spacer to push P2 to right ---
	var right_spacer: Control = Control.new()
	right_spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_child(right_spacer)

	# --- P2 status (right) ---
	var p2_vbox: VBoxContainer = VBoxContainer.new()
	p2_vbox.alignment = BoxContainer.ALIGNMENT_END
	p2_vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_child(p2_vbox)

	var p2_name: Label = _make_name_label("P2", P2_COLOR)
	p2_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	p2_vbox.add_child(p2_name)

	var p2_bar_result: Array[ColorRect] = _make_health_bar(P2_COLOR)
	_p2_health_fill = p2_bar_result[0]
	_p2_health_flash = p2_bar_result[1]
	p2_vbox.add_child(p2_bar_result[2])

	var p2_meter_hbox: HBoxContainer = _make_meter_hbox()
	_p2_meter_segments = _collect_meter_segments(p2_meter_hbox)
	p2_vbox.add_child(p2_meter_hbox)

	_p2_score_label = _make_score_label()
	_p2_score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	p2_vbox.add_child(_p2_score_label)

	# Wire signals after one frame so players have finished _ready().
	await get_tree().process_frame
	if not is_instance_valid(self):
		return
	_wire_signals()


# ---------------------------------------------------------------------------
# Signal wiring
# ---------------------------------------------------------------------------

func _wire_signals() -> void:
	# Wire GameManager signals.
	GameManager.life_lost.connect(_on_life_lost)
	GameManager.score_changed.connect(_on_score_changed)

	# Seed initial lives display.
	_lives_label.text = "x %d" % GameManager.shared_lives

	# Seed initial scores.
	_p1_score_label.text = "%06d" % GameManager.scores[0]
	_p2_score_label.text = "%06d" % GameManager.scores[1]

	# Wire per-player components.
	for node: Node in get_tree().get_nodes_in_group("players"):
		if not is_instance_valid(node):
			continue

		# player_id is a property on CharacterBody2D player scripts.
		var pid: int = int(node.get("player_id"))
		if pid < 1 or pid > 2:
			continue

		# Health component — typed child node.
		var health_node: Node = node.get_node_or_null("HealthComponent")
		if health_node and health_node is HealthComponent:
			var health: HealthComponent = health_node as HealthComponent
			health.health_changed.connect(
				func(current: int, maximum: int) -> void:
					_update_health_bar(pid, current, maximum)
			)
			# Seed initial HP.
			_update_health_bar(pid, health.current_hp, health.max_hp)
			# Store previous HP so first real hit triggers a flash.
			if pid == 1:
				_p1_prev_hp = health.current_hp
			else:
				_p2_prev_hp = health.current_hp

		# Special meter — added as child named "SpecialMeter" by player._ready().
		var meter_node: Node = node.get_node_or_null("SpecialMeter")
		if meter_node and meter_node is SpecialMeter:
			var meter: SpecialMeter = meter_node as SpecialMeter
			meter.meter_changed.connect(
				func(current_points: int, max_points: int, segments: int) -> void:
					_update_meter(pid, current_points, max_points, segments)
			)
			# Seed initial meter.
			_update_meter(pid, meter.get_points(), meter.get_max_points(), meter.get_segments())


# ---------------------------------------------------------------------------
# Update handlers
# ---------------------------------------------------------------------------

func _update_health_bar(player_id: int, current: int, maximum: int) -> void:
	var fill: ColorRect = _p1_health_fill if player_id == 1 else _p2_health_fill
	var ratio: float = float(current) / float(maximum) if maximum > 0 else 0.0
	fill.size.x = HEALTH_BAR_WIDTH * ratio

	# Detect damage and trigger flash.
	if player_id == 1:
		if _p1_prev_hp > 0 and current < _p1_prev_hp:
			_flash_bar(1)
		_p1_prev_hp = current
	else:
		if _p2_prev_hp > 0 and current < _p2_prev_hp:
			_flash_bar(2)
		_p2_prev_hp = current


func _update_meter(player_id: int, _current_points: int, _max_points: int, segments: int) -> void:
	var segs: Array[ColorRect] = _p1_meter_segments if player_id == 1 else _p2_meter_segments
	for i: int in range(segs.size()):
		segs[i].color = METER_FULL_COLOR if i < segments else METER_EMPTY_COLOR


func _flash_bar(player_id: int) -> void:
	var flash: ColorRect = _p1_health_flash if player_id == 1 else _p2_health_flash
	if player_id == 1:
		if _p1_flash_tween and _p1_flash_tween.is_running():
			_p1_flash_tween.kill()
	else:
		if _p2_flash_tween and _p2_flash_tween.is_running():
			_p2_flash_tween.kill()

	flash.color = Color(1.0, 1.0, 1.0, 0.6)
	var new_tween: Tween = create_tween()
	new_tween.tween_property(flash, "color:a", 0.0, 0.15)

	if player_id == 1:
		_p1_flash_tween = new_tween
	else:
		_p2_flash_tween = new_tween


# ---------------------------------------------------------------------------
# GameManager signal callbacks
# ---------------------------------------------------------------------------

func _on_life_lost(remaining: int) -> void:
	_lives_label.text = "x %d" % remaining


func _on_score_changed(player_id: int, new_score: int) -> void:
	# GameManager uses 0-indexed player_id; HUD labels map 0->P1, 1->P2.
	if player_id == 0:
		_p1_score_label.text = "%06d" % new_score
	elif player_id == 1:
		_p2_score_label.text = "%06d" % new_score


# ---------------------------------------------------------------------------
# Node factory helpers
# ---------------------------------------------------------------------------

## Returns a Label configured as a player name tag.
func _make_name_label(text: String, color: Color) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 8)
	label.add_theme_color_override("font_color", color)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 1)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


## Builds a health bar composite. Returns [fill_rect, flash_rect, container_rect].
## container is the dark background; fill is sized by HP ratio; flash is the
## white damage overlay (starts fully transparent).
func _make_health_bar(fill_color: Color) -> Array[ColorRect]:
	var container: ColorRect = ColorRect.new()
	container.color = BAR_BG_COLOR
	container.custom_minimum_size = Vector2(HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT)
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var fill: ColorRect = ColorRect.new()
	fill.color = fill_color
	fill.size = Vector2(HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT)
	fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	container.add_child(fill)

	var flash: ColorRect = ColorRect.new()
	flash.color = Color(1.0, 1.0, 1.0, 0.0)
	flash.size = Vector2(HEALTH_BAR_WIDTH, HEALTH_BAR_HEIGHT)
	flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	container.add_child(flash)

	return [fill, flash, container]


## Builds the 3-segment HBoxContainer for the special meter.
func _make_meter_hbox() -> HBoxContainer:
	var hbox: HBoxContainer = HBoxContainer.new()
	hbox.add_theme_constant_override("separation", int(METER_GAP))
	hbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for _i: int in range(SpecialMeter.MAX_SEGMENTS):
		var seg: ColorRect = ColorRect.new()
		seg.color = METER_EMPTY_COLOR
		seg.custom_minimum_size = Vector2(METER_SEGMENT_WIDTH, METER_SEGMENT_HEIGHT)
		seg.mouse_filter = Control.MOUSE_FILTER_IGNORE
		hbox.add_child(seg)
	return hbox


## Collects the ColorRect children of a meter HBox into a typed array.
func _collect_meter_segments(hbox: HBoxContainer) -> Array[ColorRect]:
	var result: Array[ColorRect] = []
	for child: Node in hbox.get_children():
		if child is ColorRect:
			result.append(child as ColorRect)
	return result


## Returns a Label configured as a score display.
func _make_score_label() -> Label:
	var label: Label = Label.new()
	label.text = "000000"
	label.add_theme_font_size_override("font_size", 8)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 1)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label


## Returns a Label configured as the shared lives counter.
func _make_lives_label() -> Label:
	var label: Label = Label.new()
	label.text = "x 3"
	label.add_theme_font_size_override("font_size", 8)
	label.add_theme_color_override("font_color", Color.WHITE)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 1)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label
