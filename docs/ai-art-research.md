# AI Art Generation for Deathblood Lazer -- Research Report

*Date: 2026-04-12*

## Executive Summary

AI sprite generation has matured significantly by early 2026, with multiple specialized tools now capable of producing game-ready sprite sheets with reasonable character consistency across animation frames. For Deathblood Lazer, a **hybrid approach** is recommended: use a dedicated sprite generation tool (PixelLab or AutoSprite) for initial frame generation, then do manual cleanup in Aseprite or Pixelorama. Pixel art style at 96x96 is the sweet spot for AI generation -- it is more forgiving of AI inconsistencies than hand-drawn styles, and both PixelLab and AutoSprite have MCP integrations that work directly with Claude Code and Godot.

## Available Tools

### Claude Code / MCP Tools

Three tools can generate sprites directly from within Claude Code sessions:

| Tool | MCP Available | Setup | What It Does |
|------|--------------|-------|--------------|
| **PixelLab MCP** | Yes | `claude mcp add pixellab https://api.pixellab.ai/mcp -t http -H "Authorization: Bearer TOKEN"` | Create characters, animate with skeleton, rotate to 4/8 directions, generate tilesets. Godot-specific tooling. |
| **AutoSprite MCP** | Yes | Add to `~/.claude.json` with API key header | Create characters from prompts/images, generate sprite sheets, export for Godot. 20 MCP tools across 5 categories. |
| **fal.ai (via fal-ai-media skill)** | Yes (ECC skill) | Already configured in ECC | General image generation (FLUX, Nano Banana). Not sprite-specific but can generate reference art and concept images. |

**PixelLab MCP is the strongest option** for this project because:
- It was built specifically for pixel art game assets
- It has Godot-specific tooling ("Claude works particularly well with Godot -- it can run the engine headless and understands GDScript well")
- It generates animation frames with skeleton-based controls
- It can auto-rotate characters to 4 or 8 directions from a single pose
- Assets go straight from generation into game code

**fal.ai / FLUX Kontext** is useful as a supplementary tool:
- FLUX.1 Kontext [pro] ($0.04/image) preserves character consistency across scenes without fine-tuning
- Good for generating concept art and reference images that feed into PixelLab
- Not designed for sprite sheets directly, but can maintain a character across poses

### External AI Art Tools

| Tool | Type | Pricing | Sprite Sheet Support | Best For |
|------|------|---------|---------------------|----------|
| **[PixelLab](https://www.pixellab.ai/)** | Pixel art specialist | Free tier available; paid from ~$9/mo. API: ~$0.007-0.016/image | Skeleton animation, 4/8 direction rotation, walk/run/attack cycles | **Best overall for pixel art games.** MCP + Aseprite plugin + web editor. |
| **[AutoSprite](https://www.autosprite.io/)** | Sprite sheet generator | Free (15 credits/mo); Starter $12/mo (30 exports); Pro $29/mo (100 exports) | Upload one sprite, pick moveset, export engine-ready sheets. 20+ preset animations. | Quick spritesheet generation from existing character art. MCP integration. |
| **[SpriteFlow](https://spriteflow.io/)** | AI sprite animator | Free (50 gens/mo); Starter $12.49/mo; Pro $25/mo; Ultimate $50/mo | Style-locked animations, Godot AnimatedSprite export with JSON metadata | Godot-native export with collision box suggestions. |
| **[Ludo.ai](https://ludo.ai/features/sprite-generator)** | Game dev platform | Free trial (30 credits); Pro $29.99/mo | Pose Editor for consistent proportions, sprite-to-animation pipeline | Pose editor ensures proportions stay consistent across frames. |
| **[Scenario.gg](https://www.scenario.com/)** | Custom AI models | Free (50 credits); Starter $10/mo; Pro $30/mo; Max $50/mo | Train custom models on your art style. ControlNet + style references. | Training a custom model on YOUR art style for maximum consistency. |
| **[Spritefy](https://spritefy.com/)** | Pixel art generator | Free tier available (early access) | Characters, animations, tilesets, effects, backgrounds, items | All-in-one game asset generation with style consistency engine. |
| **[God Mode AI](https://www.godmodeai.co/)** | Sprite animator | Free tier + paid plans | Upload character, select actions, get sprite sheets. Pixel art mode. | Beat-em-up specific animations (hadouken, shoryuken, punch). |
| **[Pixa/Pixelcut](https://www.pixa.com/)** | Spritesheet generator | Free | Upload image or describe character, AI generates animation frames | Simple and free, good for quick prototypes. |
| **[AISpriteSheet](https://www.aispritesheet.com/)** | Anime sprite specialist | Free tier + credit packs | Grid-aligned PNG export, frame interpolation, action pack expansion | Frame interpolation to smooth 4-frame cycles into 12-frame ones. |
| **[SpriteForge AI](https://lbacaj.itch.io/spriteforge-ai)** | Desktop app (Win/Mac) | Name your own price | Uses Gemini API. Built-in pixel editor for touch-ups. | Dad+kid workflow: kids draw, AI animates. Built by a dad for his kids' game. |

### DIY / Open Source Options

| Tool | Type | Pricing | Notes |
|------|------|---------|-------|
| **ComfyUI + IP-Adapter + ControlNet** | Local Stable Diffusion | Free (needs GPU) | Maximum control. IP-Adapter locks character identity, ControlNet controls pose. Steep learning curve. |
| **Retro Diffusion** | SD model for pixel art | Free model | Grid-aligned, palette-limited output. Made by a pixel artist. Needs SD setup. |
| **Aseprite** | Pixel art editor | $19.99 one-time | Not AI, but essential for cleanup. PixelLab has an Aseprite plugin. |
| **Pixelorama** | Free pixel art editor | Free (open source) | PixelLab integrates directly into it in-browser. |

## The Sprite Sheet Challenge

### Why This Is Hard

Generating a single cool-looking character is easy. Generating 6-12 animation frames where:
1. The character looks identical in every frame (same proportions, colors, details)
2. Each frame is exactly 96x96 pixels
3. The motion flows naturally from frame to frame
4. Weapons/accessories stay consistent
5. The style matches across ALL characters and enemies

...is the fundamental challenge of AI sprite generation.

### What Approaches Exist

**Approach 1: Purpose-Built Tools (Recommended)**
Tools like PixelLab, AutoSprite, and SpriteFlow are specifically designed to solve this problem. They use internal consistency engines that lock proportions, color palettes, and style across frames. PixelLab uses skeleton-based animation controls that define bone positions per frame, which is fundamentally more consistent than pure text-to-image generation.

**Approach 2: Reference Image + Pose Variation**
Upload a single character image, then generate each animation frame with pose instructions. Tools like AutoSprite and God Mode AI work this way -- you provide one idle sprite and they generate walk, run, attack, etc. from that reference.

**Approach 3: IP-Adapter + ControlNet (Advanced)**
For maximum control with Stable Diffusion / ComfyUI:
- IP-Adapter locks the character's visual identity from a reference image
- ControlNet (with OpenPose or structure mode) controls the exact pose for each frame
- You create pose reference sheets (stick figures in each animation position)
- The model generates each frame matching the character to the pose
- Requires GPU, technical setup, and significant experimentation

**Approach 4: Generate Base + Manual Animation**
Generate a single high-quality character image with AI, then manually animate it in Aseprite frame by frame. This gives maximum control over animation quality but requires pixel art skill. Many experienced devs recommend this as the most reliable approach for hero characters.

**Approach 5: AI Generate + Manual Cleanup (Hybrid)**
Generate all frames with AI, then manually fix inconsistencies in Aseprite. This is the most common real-world workflow as of early 2026. The AI gets you 70-80% of the way there, and you polish the rest.

## Recommended Pipeline

For Deathblood Lazer specifically, here is the recommended step-by-step pipeline:

### Phase 1: Setup (Day 1)

1. **Install PixelLab MCP** in Claude Code:
   ```
   claude mcp add pixellab https://api.pixellab.ai/mcp -t http -H "Authorization: Bearer YOUR_TOKEN"
   ```
2. **Install Aseprite** ($19.99) or use **Pixelorama** (free) for manual touch-ups
3. **Create a style reference sheet**: Generate 2-3 test characters to establish the visual style you want. Save the best one as your style reference.

### Phase 2: Character Design (Wiley Collaboration)

1. **Wiley draws character concepts** on paper or in a simple drawing app
2. **Photograph/scan the drawings** -- these become the creative direction
3. **Use PixelLab or AutoSprite** to generate pixel art versions from Wiley's concepts
4. **Iterate together** -- "make him more muscular", "add a bigger sword", "make the armor red"
5. **Lock the final character design** as the reference image for all animations

### Phase 3: Animation Generation

For each character (player characters, enemies, bosses):

1. **Generate idle pose first** -- this is the anchor frame all others derive from
2. **Use PixelLab's skeleton animation** or **AutoSprite's moveset system** to generate:
   - Idle (4-6 frames)
   - Walk (6-8 frames)
   - Attack 1 (4-6 frames)
   - Attack 2 / combo (4-6 frames)
   - Hurt/hit reaction (2-3 frames)
   - Death (4-6 frames)
   - Jump (if needed, 3-4 frames)
3. **Review each animation** -- regenerate any frames that look off
4. **Manual cleanup in Aseprite** -- fix weapon positions, smooth transitions, align proportions

### Phase 4: Assembly

1. **Export as PNG sprite sheets** from the generation tool
2. **Verify 96x96 frame size** -- resize/crop if needed
3. **Import into Godot** as sprite sheets, slice via AtlasTexture (matching existing workflow)
4. **Set up AnimationPlayer** with the frame sequences
5. **Test in-game** and iterate

### Phase 5: Backgrounds & Effects

1. **Use PixelLab's scene generation** (supports up to 400x400) for background layers
2. **Use fal.ai / FLUX** for concept art that gets pixelated down
3. **Effects (explosions, blood, lasers)** -- generate with PixelLab or use the simpler free tools

## Sample Prompts

### For PixelLab (pixel art specialist)

**Hero character idle:**
```
A muscular barbarian warrior, side-scrolling beat-em-up style, 16-bit pixel art,
holding a large battle axe, wearing leather armor, standing idle pose,
dark fantasy style, transparent background, 96x96 pixels
```

**Enemy grunt:**
```
A skeleton warrior, side-scrolling beat-em-up enemy, 16-bit pixel art,
holding a rusty sword and wooden shield, hunched aggressive stance,
dark fantasy style, transparent background, 96x96 pixels
```

**Boss character:**
```
A large demon knight boss, side-scrolling beat-em-up, 16-bit pixel art,
twice the size of normal characters, flaming sword, heavy plate armor,
menacing pose, dark fantasy style, transparent background
```

**Background:**
```
A dark medieval dungeon corridor, side-scrolling beat-em-up background,
16-bit pixel art, torches on stone walls, bones on floor,
moody atmospheric lighting, parallax-ready layers
```

### For AutoSprite / General Tools

**Upload your idle sprite, then select:**
- Animation: "sword attack combo, 3 hit sequence"
- Animation: "walking forward, 8 frames"
- Animation: "taking damage, knocked back"
- Animation: "death fall, collapse to ground"

### Prompt Tips for Beat-Em-Up Sprites

1. Always specify "side-scrolling" or "side-view" to get the correct perspective
2. Include "transparent background" to avoid manual background removal
3. Specify "16-bit pixel art" for the Golden Axe aesthetic
4. Include the exact pixel dimensions when the tool supports it
5. Reference "beat-em-up" or "brawler" style -- AI models understand these game genres
6. For enemies, describe them in idle/ready stance -- animation tools handle the rest
7. Lock a color palette early and reference it: "using NES color palette" or "limited to 16 colors"

## Limitations & Gotchas

### What Works Well
- **Idle poses and walk cycles** -- AI handles these reliably
- **Pixel art style** -- more forgiving of small inconsistencies than hand-drawn
- **Batch generation** -- generating 10 enemy variants is fast
- **Directional rotation** -- PixelLab's 4/8 direction auto-rotation is excellent
- **Simple characters** -- fewer details = more consistency

### What Does NOT Work Well
- **Complex weapon animations** -- swords, axes changing position mid-swing often break between frames. Weapons may switch hands, change size, or disappear.
- **Hand/finger detail** -- at 96x96 pixel art this is less of a problem than photorealistic, but hands holding objects are still the weakest point.
- **Multi-character interactions** -- grabbing/throwing enemies requires manual work.
- **Extremely fluid animation** -- AI-generated animations tend toward "snappy" poses rather than smooth interpolation. You may need frame interpolation tools to add in-betweens.
- **Very large sprites** -- bosses that are 2x-3x normal size lose consistency faster.
- **Exact frame count control** -- you may get 6 frames when you wanted 8, or vice versa.

### What Requires Manual Touch-Up
- **Weapon consistency** -- expect to fix weapon positions in 20-40% of frames
- **Color bleeding** -- AI sometimes introduces colors outside your palette
- **Frame alignment** -- characters may shift position slightly between frames (causes "jitter" in-game). Align anchor points manually.
- **Hit/hurt boxes** -- AI does not understand game mechanics. Collision shapes are manual.
- **Looping** -- first and last frames of a cycle may not match. Fix manually or use interpolation.

### Style Recommendations
- **Pixel art is king for AI** -- grid-aligned, limited palette, forgiving of imperfection
- **16-bit style (SNES/Genesis era)** -- perfect for Golden Axe homage, well-represented in training data
- **Avoid anti-aliasing** -- use tools that enforce hard pixel edges (PixelLab, Retro Diffusion)
- **Simpler characters = better consistency** -- a character with 3 colors and simple silhouette will be more consistent across frames than one with 20 colors and intricate armor details
- **Side-view sprites** -- the most common in training data, AI handles this perspective best

### Budget Gotchas
- PixelLab free tier may be enough for prototyping but will need paid for full character roster
- At ~$0.01-0.015 per generation, a full character (idle + walk + 3 attacks + hurt + death = ~7 animations x ~6 frames x multiple attempts) might cost $5-15 per character via API
- AutoSprite free tier (15 credits/mo) is very limited -- plan on Starter ($12/mo) minimum
- The manual cleanup phase in Aseprite/Pixelorama is where most time goes

## Recommendation

### Start Here (This Week)

1. **Sign up for PixelLab** (free tier) at pixellab.ai
2. **Install the PixelLab MCP** in Claude Code
3. **Have Wiley draw 3-4 character sketches** on paper: the hero(es), a basic enemy, a boss concept
4. **Run a test**: Generate one character with idle + walk + attack animations using PixelLab
5. **Import into Godot** and see how it looks in the existing 96x96 AtlasTexture pipeline
6. **Evaluate**: Is the quality good enough? How much cleanup is needed?

### If PixelLab Works Well
- Use it as the primary generation tool via MCP (Claude Code generates sprites AND writes the Godot import code)
- Budget ~$9-22/month during active development
- Use Aseprite/Pixelorama for the 20-30% of frames that need cleanup

### If You Need More Control
- Try AutoSprite (also has MCP) as an alternative -- better for "upload one image, get all animations"
- For maximum consistency, try Scenario.gg with a custom-trained model on your art style
- ComfyUI + ControlNet is the nuclear option -- maximum control but steep learning curve

### The Father-Son Workflow
The recommended creative workflow:
1. **Wiley designs** (draws on paper, describes characters verbally)
2. **Dad generates** (uses Claude Code + PixelLab MCP to create sprites from Wiley's designs)
3. **Both review** (look at the sprites together, decide what to regenerate or tweak)
4. **Dad cleans up** (Aseprite touch-ups) and imports into Godot
5. **Both playtest** (see the characters in action, iterate)

This keeps Wiley in the creative driver's seat while using AI to bridge the gap between his imagination and game-ready assets.

---

## Sources

- [PixelLab](https://www.pixellab.ai/) -- AI pixel art generator with MCP integration
- [PixelLab MCP](https://www.pixellab.ai/mcp) -- Claude Code integration details
- [PixelLab API Pricing](https://www.pixellab.ai/pixellab-api) -- Per-generation API costs
- [PixelLab Review](https://www.jonathanyu.xyz/2025/12/31/pixellab-review-the-best-ai-tool-for-2d-pixel-art-games/) -- In-depth review
- [AutoSprite](https://www.autosprite.io/) -- AI sprite sheet generator with MCP
- [AutoSprite MCP](https://www.autosprite.io/mcp) -- Editor integration
- [SpriteFlow](https://spriteflow.io/) -- AI sprite generator with Godot export
- [Ludo.ai Sprite Generator](https://ludo.ai/features/sprite-generator) -- Pose editor for consistency
- [Scenario.gg](https://www.scenario.com/) -- Custom AI model training for game assets
- [Scenario Spritesheet Guide](https://help.scenario.com/en/articles/create-spritesheets-with-scenario/) -- ControlNet workflow
- [Spritefy](https://spritefy.com/) -- Early access pixel art generator
- [God Mode AI](https://www.godmodeai.co/) -- Beat-em-up sprite animations
- [AISpriteSheet](https://www.aispritesheet.com/) -- Frame interpolation and grid alignment
- [SpriteForge AI](https://lbacaj.itch.io/spriteforge-ai) -- Desktop app, kids+dad workflow
- [Pixa Spritesheet Generator](https://www.pixa.com/create/spritesheet-generator) -- Free AI spritesheet tool
- [Rosebud AI Guide](https://lab.rosebud.ai/blog/ai-sprite-sheet-generator-create-free-game-sprites-with-rosebud-ai) -- Sprite prompt engineering
- [fal.ai Models](https://fal.ai/explore/models) -- FLUX, Nano Banana, and other models
- [FLUX Kontext](https://fal.ai/models/fal-ai/flux-pro/kontext) -- Character consistency without fine-tuning
- [ComfyUI Character Consistency](https://learn.runcomfy.com/create-consistent-characters-with-controlnet-ipadapter) -- ControlNet + IP-Adapter workflow
- [Sprite Sheet Diffusion Paper](https://arxiv.org/html/2412.03685v2) -- Academic research on the topic
- [Reddit: Best AI tools for pixel art spritesheets](https://www.reddit.com/r/gamedev/comments/1s0gsim/best_ai_toolsworkflows_for_generating_pixel_art/) -- Community discussion (March 2026)
- [Sprite-AI Blog: Pixel Art Generators 2026](https://www.sprite-ai.art/blog/best-pixel-art-generators-2026) -- Tested tool comparison
