## Main scene controller.
##
## Handles synthwave atmosphere setup: dark ambient modulate and background
## color are applied here so they can be adjusted in code without needing
## separate scene resources.
##
## Also builds the full parallax background (sky, castle, neon underglow,
## floor) and ground fog particles in _ready() so the .tscn stays minimal.
## The underglow ColorRect color-cycles in _process() for a neon pulse effect.
extends Node

var _underglow: ColorRect = null
var _glow_time: float = 0.0

func _ready() -> void:
	# Hide placeholder ColorRect backgrounds.
	var bg_node: Node = get_node_or_null("Background")
	if bg_node:
		bg_node.visible = false
	var floor_node: Node = get_node_or_null("FloorBelt")
	if floor_node:
		floor_node.visible = false

	# Dark ambient tint.
	var canvas_mod := CanvasModulate.new()
	canvas_mod.color = Color(0.5, 0.4, 0.55, 1.0)
	add_child(canvas_mod)

	# === Parallax Background ===
	var parallax_bg := ParallaxBackground.new()
	parallax_bg.name = "ParallaxBG"
	add_child(parallax_bg)
	move_child(parallax_bg, 0)

	# --- Layer 1: Skybox (far, very slow scroll) ---
	var sky_layer := ParallaxLayer.new()
	sky_layer.motion_scale = Vector2(0.05, 0.0)
	sky_layer.motion_mirroring = Vector2(640, 0)
	var sky_sprite := Sprite2D.new()
	sky_sprite.texture = load("res://assets/sprites/environment/skybox.png")
	sky_sprite.centered = false
	sky_sprite.position = Vector2(0, 0)
	sky_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sky_layer.add_child(sky_sprite)
	parallax_bg.add_child(sky_layer)

	# --- Layer 2: Castle walls (mid scroll, transparent arches show sky) ---
	var castle_layer := ParallaxLayer.new()
	castle_layer.motion_scale = Vector2(0.2, 0.0)
	castle_layer.motion_mirroring = Vector2(440, 0)
	var castle_sprite := Sprite2D.new()
	castle_sprite.texture = load("res://assets/sprites/environment/castle_panorama.png")
	castle_sprite.centered = false
	castle_sprite.position = Vector2(0, 0)
	castle_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	castle_layer.add_child(castle_sprite)
	parallax_bg.add_child(castle_layer)

	# --- Layer 3: Neon underglow (behind floor, visible through cracks) ---
	var glow_layer := ParallaxLayer.new()
	glow_layer.motion_scale = Vector2(0.4, 0.0)
	var glow_rect := ColorRect.new()
	glow_rect.color = Color(0.0, 0.8, 0.9, 0.9)
	glow_rect.size = Vector2(1280, 192)
	glow_rect.position = Vector2(-320, 168)
	var glow_mat := CanvasItemMaterial.new()
	glow_mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	glow_rect.material = glow_mat
	glow_layer.add_child(glow_rect)
	parallax_bg.add_child(glow_layer)
	_underglow = glow_rect

	# --- Layer 4: Floor (stone with transparent cracks, near scroll) ---
	var floor_layer := ParallaxLayer.new()
	floor_layer.motion_scale = Vector2(0.4, 0.0)
	floor_layer.motion_mirroring = Vector2(640, 0)
	var floor_sprite := Sprite2D.new()
	floor_sprite.texture = load("res://assets/sprites/environment/floor_base.png")
	floor_sprite.centered = false
	floor_sprite.position = Vector2(0, 168)
	floor_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	floor_layer.add_child(floor_sprite)
	parallax_bg.add_child(floor_layer)

	# --- Ground Fog (rising from cracks) ---
	var fog := GPUParticles2D.new()
	fog.name = "GroundFog"
	fog.amount = 40
	fog.lifetime = 3.0
	fog.preprocess = 3.0
	fog.z_index = 5
	fog.position = Vector2(320, 230)
	fog.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

	var fog_img: Image = Image.create(8, 8, false, Image.FORMAT_RGBA8)
	var fog_center := Vector2(3.5, 3.5)
	for y_px: int in range(8):
		for x_px: int in range(8):
			var dist: float = Vector2(float(x_px), float(y_px)).distance_to(fog_center) / 4.0
			var alpha_val: float = clampf(1.0 - dist, 0.0, 1.0) * 0.5
			fog_img.set_pixel(x_px, y_px, Color(0.7, 0.5, 0.9, alpha_val))
	fog.texture = ImageTexture.create_from_image(fog_img)

	var fog_mat := ParticleProcessMaterial.new()
	fog_mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	fog_mat.emission_box_extents = Vector3(300.0, 5.0, 0.0)
	fog_mat.direction = Vector3(0.0, -1.0, 0.0)
	fog_mat.spread = 50.0
	fog_mat.initial_velocity_min = 8.0
	fog_mat.initial_velocity_max = 20.0
	fog_mat.gravity = Vector3(0.0, -3.0, 0.0)
	fog_mat.scale_min = 4.0
	fog_mat.scale_max = 10.0
	fog_mat.damping_min = 1.0
	fog_mat.damping_max = 2.0

	var fog_color := Gradient.new()
	fog_color.set_color(0, Color(0.3, 0.9, 0.8, 0.0))
	fog_color.add_point(0.2, Color(0.3, 0.8, 0.9, 0.25))
	fog_color.add_point(0.6, Color(0.7, 0.2, 0.9, 0.2))
	fog_color.set_color(1, Color(0.5, 0.1, 0.8, 0.0))
	var fog_color_tex := GradientTexture1D.new()
	fog_color_tex.gradient = fog_color
	fog_mat.color_ramp = fog_color_tex

	fog.process_material = fog_mat
	var fog_canvas_mat := CanvasItemMaterial.new()
	fog_canvas_mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	fog.material = fog_canvas_mat
	add_child(fog)


func _process(delta: float) -> void:
	if not _underglow:
		return
	_glow_time += delta * 0.4
	var t: float = fmod(_glow_time, 3.0) / 3.0
	var color: Color
	if t < 0.333:
		var blend: float = t / 0.333
		color = Color(0.0, 0.8, 0.9).lerp(Color(0.9, 0.0, 0.7), blend)
	elif t < 0.666:
		var blend: float = (t - 0.333) / 0.333
		color = Color(0.9, 0.0, 0.7).lerp(Color(0.0, 0.9, 0.2), blend)
	else:
		var blend: float = (t - 0.666) / 0.334
		color = Color(0.0, 0.9, 0.2).lerp(Color(0.0, 0.8, 0.9), blend)
	color.a = 0.8
	_underglow.color = color
