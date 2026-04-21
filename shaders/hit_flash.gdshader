shader_type canvas_item;

uniform float flash_amount : hint_range(0.0, 1.0) = 0.0;
uniform vec4 flash_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float outline_width : hint_range(0.0, 3.0) = 0.0;
uniform vec4 outline_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);

void fragment() {
    vec4 tex = texture(TEXTURE, UV);

    // Outline: check neighboring pixels
    if (outline_width > 0.0 && tex.a < 0.1) {
        vec2 px = TEXTURE_PIXEL_SIZE * outline_width;
        float neighbor_alpha = 0.0;
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(px.x, 0.0)).a);
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(-px.x, 0.0)).a);
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(0.0, px.y)).a);
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(0.0, -px.y)).a);
        // Diagonals for fuller outline
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(px.x, px.y)).a);
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(-px.x, px.y)).a);
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(px.x, -px.y)).a);
        neighbor_alpha = max(neighbor_alpha, texture(TEXTURE, UV + vec2(-px.x, -px.y)).a);
        if (neighbor_alpha > 0.5) {
            COLOR = outline_color;
            return;
        }
    }

    // Hit flash
    COLOR = mix(tex, vec4(flash_color.rgb, tex.a), flash_amount);
}
