# Tools Directory

## sprite_pipeline.py
Main sprite animation pipeline. Takes a canonical character sprite and generates animation frames via PixelLab API.

### Usage
```
python sprite_pipeline.py --character wiley --canonical path/to/east.png --output path/to/output/
python sprite_pipeline.py --character father_stu --canonical path/to/east.png --output path/to/output/
python sprite_pipeline.py --only Idle Walk Attack_1  # specific animations
python sprite_pipeline.py --assemble-only --frames-dir path/  # skip API, assemble existing
python sprite_pipeline.py --estimate-skeleton --canonical path/to/east.png  # get keypoints
python sprite_pipeline.py --dry-run  # preview without API calls
```

### How It Works
- Loads API key from `~/.claude.json` (PixelLab MCP server config)
- Defines 18 skeleton keypoints (normalized 0-1 coordinates)
- 9 animations, all skeleton-based, 3 frames each: Idle, Walk, Run, Jump, Attack_1, Attack_2, Attack_3, Hurt, Dead
- Keypoint modifications per frame define the pose (e.g., legs apart for walk, arms up for slam)
- Currently uses WILEY_BASE_KEYPOINTS — other characters need `--estimate-skeleton` or manual tuning
- Run uses 1.5x walk deltas for bigger strides

### Important
- DO NOT run without user approval — each animation = 1 API generation credit
- The skeleton API is best for combat poses (precise control)
- Movement animations (walk, idle) may look better from PixelLab web editor (Pixelorama)
- Base keypoints are tuned for Wiley's proportions — Father Stu (stout dwarf) needs different keypoints

## skeleton_editor.html
Interactive visual skeleton keypoint editor. Open in Chrome/Edge.

### Usage
1. Open in browser
2. Click "Open Characters Folder" → select `assets/sprites/characters/`
3. Pick character from dropdown
4. Drag keypoints to position them on the sprite
5. Add animation frames, define poses
6. Save → writes `skeleton.json` to character folder

### Features
- Draggable 18-point skeleton overlay on 3x scaled sprite
- Color-coded bones (yellow=head, cyan=left, magenta=right, white=spine)
- Animation frame management (add/delete/switch frames)
- Multiple animations per character
- Save/load skeleton.json per character folder
- Arrow keys for 1px fine adjustment
- Ctrl+S quick save

### Output Format (skeleton.json)
```json
{
  "character": "wiley",
  "sprite_width": 256,
  "sprite_height": 256,
  "base_pose": [{"label": "NOSE", "x": 0.353, "y": 0.271, "z_index": 0}, ...],
  "animations": {
    "Walk": {"direction": "east", "frames": [[...], ...]},
    "Attack_1": {"direction": "east", "frames": [[...], ...]}
  }
}
```

## Other Files
- `create_father_stu.py` — character creation script (historical)
- `skeleton_data.json` — cached skeleton keypoint data (may be stale)

## PixelLab API Reference

### Auth
- Base URL: `https://api.pixellab.ai/v2`
- Auth: `Authorization: Bearer {api_key}` header
- API key loaded from `~/.claude.json` → `mcpServers.pixellab.args` → `--secret=` value
- Full API docs: `https://api.pixellab.ai/v2/llms.txt` (73KB OpenAPI spec)
- MCP wrapper is BROKEN for animations — use direct Python API calls via sprite_pipeline.py

### POST /animate-with-skeleton (proven working format)
Generates animation frames from skeleton keypoints. This is the working payload from sprite_pipeline.py:

```python
payload = {
    "image_size": {"width": 128, "height": 128},
    "skeleton_keypoints": frames,  # list of lists of {label, x, y, z_index} — pixel coords, NOT normalized
    "direction": "south-east",
    "view": "side",
    "guidance_scale": 7.0,
    "reference_image": {"type": "base64", "base64": img_b64, "format": "png"},
    "init_image_strength": 300,
    "seed": 123,
}
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
}
resp = requests.post("https://api.pixellab.ai/v2/animate-with-skeleton", json=payload, headers=headers, timeout=120)
```

**Critical details:**
- `skeleton_keypoints` is `list[list[dict]]` — each frame is a flat list of `{label, x, y, z_index}` keypoint dicts
- Keypoint x/y are in PIXEL coordinates (multiply normalized 0-1 values by image dimensions)
- `image_size` uses `{"width": N, "height": N}` (NOT separate width/height params)
- `reference_image` uses `{"type": "base64", "base64": "...", "format": "png"}` (NOT `{image, width, height}`)
- `guidance_scale` is ONE param (NOT separate reference_guidance_scale / pose_guidance_scale — those are MCP-only)
- Max 3 input keyframes per call (API limit)
- FRAME_SIZE of 128 was used historically — skeleton API may not support 256x256 output

**Response:** `{"images": [{type, base64/rgba_bytes, width, ...}], "usage": {"usd": 0.0}}`

### POST /characters/animations (Character Creator pipeline)
For generating animations from Character Creator characters. Uses character_id, not skeleton keypoints.

```python
payload = {
    "character_id": "d1babc2c-...",
    "mode": "v3",  # or "template", "pro"
    "action_description": "walking forward",
    "frame_count": 4,  # 4-16, even numbers only
    "directions": ["south-east"],
    "async_mode": True,
}
```
Returns `background_job_ids` (plural array). Must poll for completion then download ZIP.

### POST /estimate-skeleton
Extract keypoints from a character image. Returns keypoints in the same format animate-with-skeleton expects.

### Key Gotchas (from past sessions)
- DO NOT call any PixelLab API without user approval — credits are limited (2000/cycle)
- ZIP export is the ONLY reliable way to get clean PNGs from Character Creator
- `rgba_bytes` images from some endpoints decode as garbled — use PIL `Image.frombytes("RGBA", (w,h), data)`
- `background_job_id` not `job_id` in async responses
- animate-with-text-v3 CANNOT do walk/run cycles (legs frozen) — use skeleton for locomotion
- Always read API docs (`llms.txt`) BEFORE making calls — don't guess at parameter names
