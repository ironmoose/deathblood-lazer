# Deathblood Lazer Vocabulary Reference

Last updated: 2026-06-07

This is the canonical vocabulary for talking, prompting, and researching the painterly belt-scroller pipeline. Terms are grouped by category. For each term: definition, then a use-when note distinguishing it from near-synonyms.

---

## 1. Genre Terminology

- **Belt scroller** — Sub-genre of beat-em-up where the playable area is a *belt*: a horizontally-scrolling stage with a shallow Y-axis for "depth" movement (up/down on screen = forward/back in world). Use this term (not "side-scroller") any time you're talking about Streets of Rage, Final Fight, TMNT: Shredder's Revenge, Streets of Rage 4 (SoR4). Industry-canon term: "belt-scrolling action game" (Capcom internal, Final Fight design docs).
- **Beat-em-up (BEU)** — Genre umbrella: melee-combat action where you fight crowds of enemies. Includes belt scrollers AND single-plane brawlers (e.g. Smash TV-style arena). Use when speaking about the genre at large; use "belt scroller" when the *belt* (depth axis) matters.
- **Side-scrolling brawler** — Loose informal synonym for belt scroller. Avoid in technical contexts; it conflates belt scrollers with pure 2D platformer-brawlers (Castle Crashers leans this way) that lack a real depth axis.
- **2.5D** — 2D gameplay rendered with 3D assets, OR 2D rendering with depth illusion (parallax + Y-sort). Belt scrollers are the canonical 2.5D genre because the *gameplay plane is 2D but the world reads as 3D*. SoR4 = "2.5D painterly belt scroller."
- **Brawler** — Generic. Can mean party brawler (Smash Bros), platform brawler, or beat-em-up. Don't use alone; qualify it.
- **Arena brawler** — Beat-em-up on a *fixed* single screen (no scroll), e.g. Smash TV, Castle Crashers boss arenas. Useful when describing an "encounter zone" inside a belt scroller.
- **Single-plane fighter** — Two characters on one fighting plane, no depth (Street Fighter). Important to contrast: belt scrollers add the second axis specifically to differentiate from this.
- **Boss rush / horde mode** — Mode subtypes, not genres. Note in design docs only.

---

## 2. Camera Framing Terminology

- **Side view (elevation view)** — Pure orthographic side, horizon at character eye level. Use for the *backdrop* (parallax sky/skyline) where you want flat horizontal motion with no perspective distortion. This is what Cuphead / Hollow Knight backgrounds are.
- **Three-quarter view (3/4 view, "TQ view")** — Camera tilted slightly downward so the ground plane is visible as a wedge while characters still read frontally. **This is the canonical framing for belt-scroller *floors*.** Streets of Rage, Final Fight, SoR4 floors are all 3/4. Sometimes called "oblique forced perspective."
- **High-angle view** — Camera looking *down* at the subject. 3/4 view is a constrained high-angle.
- **Eye-level** — Camera at character eye height. Backgrounds in belt scrollers are typically eye-level; floors are not. **This is the source of the backdrop-vs-floor framing conflict** in our project.
- **Bird's-eye / top-down** — Straight-down view (Hotline Miami, classic Zelda). Too steep for belt scrollers.
- **Isometric** — Specific axonometric projection at 30 degrees with equal foreshortening on all three axes. Used in Diablo, classic SimCity. NOT what belt scrollers use; the angle is steeper than 3/4.
- **Axonometric** — Umbrella for parallel projections (isometric, dimetric, trimetric). Use the umbrella term only when you mean "any non-perspective parallel projection."
- **Oblique projection** — Parallel projection where one face is parallel to the picture plane and depth lines go off at an angle. Classic Paper Mario backgrounds use cabinet oblique. Often confused with 3/4 view.
- **Forced perspective** — Painted perspective that breaks 3D geometric rules to read correctly on a flat plane. Belt-scroller floors are a forced perspective: the floor receding into the horizon is faked, not geometrically derived.
- **Locked camera / pinned camera** — Camera with constrained DOF (e.g. follows X only). Belt scroller cameras are X-locked-with-soft-Y.

---

## 3. Parallax + Layer Terminology

- **Parallax** — Apparent shift of layers at different scroll rates to simulate depth. Closer layers scroll faster than distant ones.
- **Parallax scroll factor (parallax coefficient)** — The per-layer scalar (0.0 to 1.0+) applied to camera delta. 0 = locked sky, 1 = scrolls 1:1 with camera, >1 = foreground silhouette ("hyper-parallax").
- **Background (BG)** — Farthest visual layer. Subdivided as sky, far BG, mid BG.
- **Sky panorama / sky dome** — Single very-wide image that wraps or tiles for the farthest layer. In 2D context "skybox" is also used colloquially.
- **Skybox (2D)** — Borrowed from 3D; for 2D, refers to a wrapping seamless sky texture at parallax factor near 0. Prefer "sky panorama" in 2D-native docs.
- **Midground** — Mid-depth content (mid-distance buildings, treelines). Carries most of the scene's silhouette.
- **Foreground (FG)** — Closest layer, often grass/pillars/silhouetted occluders that pass *in front of* characters.
- **Playfield / play layer** — The layer where gameplay happens (the *belt*). Distinct from BG/FG; characters and floor share this layer.
- **Backdrop** — The painted background plate, usually multiple stacked parallax layers, treated as a unit during scene composition.
- **Matte painting** — A single painted backdrop image, traditionally one piece. Hollow Knight uses matte-painted BGs.
- **Motion mirroring** — Parallax repetition where layers wrap or mirror at scene ends to disguise loop seams.
- **Tiling vs scrolling** — Tiled = repeats every N pixels; scrolling = continuous one-shot panorama. Tiled is cheaper; scrolling reads as bespoke.
- **Vertical parallax** — Y-axis parallax (sky shifts as camera tilts up). Rare in belt scrollers; common in vertical shooters.

---

## 4. Scene Composition Terminology

- **Horizon line** — The line where sky meets ground, at *camera eye level*. **All vanishing points sit on the horizon line.**
- **Vanishing point** — The point on the horizon line where parallel receding lines converge.
- **Eye line** — The vertical position of the viewer's eye in the painting. Equivalent to horizon line in single-point perspective.
- **One-point / two-point / three-point perspective** — Number of vanishing points. Belt-scroller floors typically use one-point (a single VP at center horizon); SoR4 uses fluctuating two-point.
- **Vanishing-point conflict** — When two stacked images (e.g. backdrop and floor) imply *different* horizon lines or eye levels, the viewer reads them as disconnected planes. **RELEVANT TO OUR EARLIER FAILURES** — our bg/floor cohesion problem is a vanishing-point conflict: the eye-level backdrop's horizon does not match the 3/4-view floor's horizon. Fix is to paint both from a *shared* horizon line or use a single sketch with both layers planned together.
- **Perspective mismatch** — Generic term for stacked layers whose perspective rules don't align. Subsumes vanishing-point conflict.
- **Occluder** — Foreground silhouette that visually breaks up the scene depth (a tree, a pillar). Real games use FG occluders to mask BG/floor seams.
- **Seam** — The visible line where two layers meet. Belt-scroller seams between backdrop and floor are typically hidden behind midground props or value-break gradients.
- **Value break** — Strong tonal contrast at a layer edge that *sells* the depth break (e.g. dark floor against bright BG sky). SoR4 leans heavily on value breaks.
- **Atmospheric perspective (aerial perspective)** — Distant elements get cooler, lower-contrast, and bluer due to atmospheric scattering. Used to fake depth without geometric perspective. **One of the most powerful tools to make a mismatched bg/floor read as one scene.**
- **Chiaroscuro** — Strong light/shadow contrast for dramatic shape definition. Cuphead and Hollow Knight backgrounds.
- **Silhouette read** — Whether the scene reads from pure silhouette (no internal detail). Strong silhouette read is a Cuphead / Hollow Knight signature.
- **Composition wedge / leading lines** — Painted directionals that pull the eye toward the gameplay belt.

---

## 5. Belt-Scroller Specific Terms

- **The belt** — The playable Y-axis band the players walk on. In Deathblood Lazer this is Y 115-235.
- **Belt bounds / belt extents** — The min/max Y of the belt. Hard collision walls.
- **Playable belt / play band** — Synonyms for the belt. "Play band" is preferred in modern dev (SoR4 dev talks).
- **Fighting plane** — The 2D plane on which combat resolves (X = horizontal screen, Y = depth). Same concept as belt; "fighting plane" is more general.
- **Depth axis / Y-axis depth** — In belt scrollers, on-screen Y = world depth. "Up on screen = farther from camera" is the convention.
- **Y-sort (depth sort)** — Sorting sprites by Y so a character with lower Y draws on top of one behind them. Godot has built-in Y-sort.
- **Z-sort** — Drawing order by an explicit Z value, independent of Y. Use when you need overrides (e.g. a projectile must always draw above).
- **Vertical speed factor** — The X-Y movement ratio. Walking up-down should feel slower than left-right to sell depth. Deathblood Lazer uses 0.7x (per CLAUDE.md).
- **Encounter / encounter zone** — A bounded sub-area where a wave spawns and the camera locks.
- **Screen lock / camera lock / arena lock** — Camera stops scrolling so the player can't bypass a spawn wave. The classic "GO!" arrow appears after the lock releases.
- **Spawn line / spawn edge** — The off-screen X where new enemies enter. Usually just past the screen margin.
- **Exit zone** — Trigger volume that ends the encounter and releases the camera lock.
- **Set piece** — A scripted scene fragment (a falling chandelier, a mini-boss intro). Distinguishes from procedural encounters.
- **Wave** — A spawn group within an encounter. Multi-wave encounters are standard.
- **Stage / level / area** — Top-level scene; one stage = one camera path.

---

## 6. Asset Pipeline Terminology

- **Concept art** — Pre-production exploration art establishing look, mood, color. Not in-game.
- **Blockout / gray-box** — Untextured shape pass to validate composition and gameplay. In 2D this means flat color blockouts.
- **Beauty pass** — The final rendered pass with full polish.
- **Paint-over** — Painting on top of a 3D render or photobash to add detail and unify the image. Standard backdrop technique for SoR4-style work.
- **Photobash** — Compositing photographic elements as a base, then painting over. Common in concept art.
- **Sketch+collision PSD (shared-sketch workflow)** — Industry practice (SoR4 dev confirmed) where one PSD holds both the painted scene and the gameplay collision data, painted together so perspective and gameplay align. **Adopt this term.**
- **Slice / scene slice** — Cutting a cohesive painted scene into BG/MG/FG/floor layers for the engine. Distinct from "sprite slice" which is animation frames.
- **Region mask** — A grayscale mask defining which area of an image gets which prompt or treatment. Used by Regional Prompter and inpainting.
- **Depth pass** — Per-pixel depth map. In ComfyUI, generated by MiDaS / Depth-Anything; fed to ControlNet Depth.
- **Ambient occlusion (AO) pass** — Soft shadow in crevices. Faked in 2D with a multiplied dark layer.
- **Tileable / seamless texture** — Texture whose edges match on opposite sides. Used for floor and sky panoramas.
- **Trim sheet** — A single texture of edge/border details reused across many props.
- **Atlas / texture atlas** — Single image holding many sprites. AtlasTextures in Godot.
- **Sprite sheet (spritesheet)** — Atlas specifically of one character's animation frames.

---

## 7. Godot 4-Specific Names

- **Parallax2D** (Godot 4.3+) — Modern parallax node. Replaces the older ParallaxBackground/ParallaxLayer pair. Use this for new work.
- **ParallaxBackground / ParallaxLayer** — Pre-4.3 parallax. Not deprecated yet in 4.6 but Parallax2D is the recommended path forward.
- **Sprite2D** — Static texture node.
- **AnimatedSprite2D** — Frame-by-frame animation node. Holds a SpriteFrames resource.
- **TileMap** — Legacy tile-based grid node. **Deprecated in 4.3+** in favor of TileMapLayer.
- **TileMapLayer** (Godot 4.3+) — One layer per node. Replaces multi-layer TileMap.
- **Camera2D** — 2D camera. Supports limits, drag margins, smoothing.
- **CanvasItem** — Base class for anything drawn in 2D. Holds modulate, visible, z_index.
- **CanvasLayer** — Layer that draws independently of the 2D world transform (used for HUD).
- **Y-sort enabled** — CanvasItem property that sorts children by Y position. Use on the parent of the play layer.
- **Skeleton2D / Bone2D** — Godot's native 2D bone-rig system. Lightweight; for serious work use Spine or DragonBones import.
- **RenderingServer** — Low-level draw API. Rarely touched directly in 2D work.
- **SubViewport** — Off-screen viewport. Useful for rendering a parallax sub-scene into a texture.
- **Stretch mode: canvas_items / keep aspect** — Project setting that scales 2D content correctly across resolutions. Deathblood Lazer is set this way for the 2560x1440 native render.

---

## 8. SDXL / ComfyUI Vocabulary

- **Base model / checkpoint** — The weights file (`.safetensors`). SDXL base, JuggernautXL, etc.
- **LoRA (Low-Rank Adaptation)** — Small fine-tune file that biases the base model. dbstyle_v4 is a LoRA.
- **LoHa / LoKr** — LoRA variants with different decomposition (Hadamard / Kronecker). Higher capacity, harder to train.
- **LyCORIS** — Umbrella library covering LoRA + LoHa + LoKr + DyLoRA + others.
- **Sampler** — Algorithm that solves the denoising ODE (Euler, DPM++ 2M, DDIM, UniPC).
- **Scheduler** — Noise schedule the sampler walks (Karras, Exponential, Normal, SGM Uniform).
- **CFG (Classifier-Free Guidance)** — How hard the model follows the prompt. SDXL sweet spot 5-8.
- **Denoise / denoising strength** — In img2img, how much of the input is replaced (0 = pass-through, 1 = full regen).
- **Latent** — Compressed image representation (4-channel, 1/8 resolution). VAE encode/decode converts between latent and pixel space.
- **VAE encode / VAE decode** — Image → latent and latent → image.
- **Conditioning** — Text or image embedding fed to the U-Net. "Positive" and "negative" conditioning.
- **t2i (text-to-image)** — Generate from prompt only.
- **img2img (i2i)** — Generate from an input image + prompt, partial denoise.
- **Inpaint** — Generate inside a mask, preserving outside pixels.
- **Outpaint** — Inpaint extending beyond the original canvas edges.
- **IPAdapter** — Image-prompt adapter that conditions on a reference image's style or content.
- **IPAdapter Plus** — Higher-fidelity variant with more reference detail.
- **IPAdapter FaceID** — Identity-locked variant for character consistency.
- **weight_type** — IPAdapter mode (linear, ease in-out, style transfer, composition, strong style transfer). "style transfer" is what you want for painterly look-lock without copying composition.
- **ControlNet** — Conditioning model that constrains generation by an auxiliary signal.
- **ControlNet Canny / Depth / OpenPose / Scribble / Lineart / Softedge / Tile** — The standard control types. **Depth is the load-bearing one for scene composition; Canny for shape preservation in img2img; OpenPose for character pose.**
- **Regional Prompter (Composite Conditioning)** — Apply different prompts to different image regions via masks. Solves "different content in BG vs FG."
- **Hires Fix** — Old SD1.5-era pattern: generate small, upscale, second pass at low denoise. SDXL is native-1024 so use less.
- **Latent upscale** — Upscale in latent space (cheap, blurry).
- **Model upscale** — Use a dedicated upscaler model (RealESRGAN, 4x-UltraSharp, SwinIR). Higher quality.
- **RealESRGAN** — Standard general upscaler. Our project's default.
- **4x-UltraSharp** — Detail-preserving upscaler, popular for SDXL.
- **Daemon detailer / Detail Daemon** — Sampler hack that boosts mid-frequency detail during denoising.
- **Krita-AI-Diffusion (Acly's plugin)** — Krita plugin wrapping ComfyUI for live painting + AI generation. The right tool for shared-sketch workflow.
- **ComfyUI workflow JSON** — Serialized node graph. Shareable; embeds in PNG metadata.
- **Fooocus inpaint patch** — Specialized inpaint head for cleaner inpaints. Required for SOTA inpaint.
- **Crop-and-stitch (comfyui-inpaint-crop-and-stitch)** — Workflow pattern that crops a region, inpaints at full resolution, and stitches back. Necessary for face/detail in wide aspect outputs.

---

## 9. Animation Pipeline Terms

- **Cutout animation** — 2D animation where body parts are separate textures, animated as a puppet. The bone-rig 2D style. Used by Cuphead's bosses, Hollow Knight characters, Rayman Origins/Legends.
- **Bone rig / skeletal rig** — Hierarchy of bones driving texture deformation.
- **Spine** (Esoteric Software) — Industry-standard 2D skeletal tool. Paid. Godot importer available.
- **DragonBones** — Free Spine alternative. Slightly weaker tooling, broad runtime support.
- **Skeleton2D / Bone2D** — Godot's native bone system. Lightweight.
- **Body part separation** — Pre-rig step: split the character art into head / torso / upper arm / forearm / hand / thigh / shin / foot etc. as separate PNGs.
- **Mesh deformation / FFD (free-form deformation)** — Bones deform a mesh instead of moving rigid sprites. Looks more organic.
- **IK (inverse kinematics)** — Solve bone chain from end-effector position. Used for foot-planting and hand-to-target.
- **FK (forward kinematics)** — Animate each bone rotation by hand. The default.
- **Animation state machine** — Graph of animation states with transitions (AnimationTree in Godot).
- **Key frame** — Hand-set frame at a critical pose.
- **In-between / tween** — Interpolated frames between keys.
- **Easing** — Interpolation curve (ease in, ease out, ease in-out, cubic, elastic).
- **Animation FPS** — Frames per second of an animation. 12 fps = "on-twos" (classic cel); 24 fps = "on-ones."
- **On-twos / on-threes** — Hand-drawn animation cadence (each drawing held for 2 or 3 video frames).
- **Frame budget** — How many unique frames a character has. Belt-scroller heroes typically 50-100 across all moves.
- **Onion skin** — Editor overlay showing previous/next frame in semi-transparency.

---

## 10. Color / Palette Terminology

- **Hue** — Position on the color wheel (the "color name").
- **Saturation (chroma)** — Color intensity. Chroma is the perceptual term; saturation the HSL-system term.
- **Value (lightness, luminance)** — Brightness. Value is the painter's term; lightness is HSL; luminance is colorimetric.
- **HSV / HSL** — Color spaces. HSV is for picking, HSL is for adjustment.
- **Warm vs cool palette** — Warm = reds/oranges/yellows; cool = blues/greens/violets. Deathblood Lazer is a warm/cool *dual* palette (orange P1 / blue P2).
- **Limited palette** — Constrained set of colors. Forces unity.
- **Dual palette** — Two contrasting palettes used to differentiate elements (heroes vs enemies, or scene halves).
- **Complementary** — Opposite on the color wheel (orange/blue). Maximum contrast.
- **Analogous** — Adjacent on the color wheel. Maximum harmony.
- **Triadic** — Three colors equally spaced. Bold but balanced.
- **Split-complementary** — One color + the two neighbors of its complement.
- **Color grading** — Post-process color adjustment applied to a finished image or rendered frame.
- **LUT (look-up table)** — Pre-computed color mapping (e.g. .cube file). Apply as a shader for consistent grading.
- **Key light** — Main directional light.
- **Fill light** — Secondary light softening shadows.
- **Rim light (back light)** — Light from behind to separate subject from BG. Standard belt-scroller character treatment.
- **Ambient light** — Non-directional baseline illumination.
- **Mood lighting** — Catch-all for emotionally-coded lighting choices.

---

## 11. Combat / Game-Design Terms

- **Hitstop (hitlag, freeze frames)** — Brief pause on impact for weight feel. Deathblood Lazer uses per-entity hitstop (not Engine.time_scale).
- **Knockback** — Velocity applied to a hit target.
- **Juggle** — Keeping an enemy airborne with successive hits.
- **Launcher** — Move that puts a grounded enemy into juggle state.
- **Combo** — Linked sequence of hits within a window.
- **Cancel** — Interrupting a move's recovery to chain into another move.
- **Super armor / hyper armor** — State where the entity ignores hitstun (still takes damage).
- **i-frames (invincibility frames)** — Frames during which the entity can't be hit. Deathblood Lazer dodge is 0.2s i-frame.
- **Stagger** — Hit reaction that briefly disables actions but isn't a full knockdown.
- **Stun lock** — When an enemy can't act due to repeated stagger.
- **Hitbox** — Volume that *deals* damage when overlapping a hurtbox.
- **Hurtbox** — Volume that *receives* damage from a hitbox.
- **Collider (collision shape)** — Physical collision volume. Distinct from hit/hurtbox.
- **Frame data** — Per-move table: startup / active / recovery, on-block / on-hit advantage.
- **Startup frames** — Frames before the move's hitbox activates.
- **Active frames** — Frames where the hitbox is live.
- **Recovery frames** — Frames after active until the entity can act again.
- **On-block advantage** — Net frames difference after the move is blocked. Positive = attacker recovers first.
- **On-hit advantage** — Same but on hit.
- **Special move** — Resource-cost or input-motion move beyond normals.
- **EX move** — Enhanced version of a special, costs meter.
- **Super (super art)** — Top-tier resource move.
- **Meter (gauge)** — Resource bar feeding specials/EX/supers. Deathblood Lazer: 3 segments, 10 pts each.
- **Grunt** — Basic enemy. Low health, weak attacks.
- **Brute** — Heavy enemy. High health, super armor, big windup.
- **Shielder** — Enemy that blocks frontal attacks; must be flanked or broken.
- **Ranged** — Enemy that attacks from distance (thrower, gunner).
- **Mini-boss** — Mid-encounter elite. Distinct moveset, not a stage boss.
- **Boss** — Stage-ending fight. Multi-phase usually.
- **Encounter / arena lock** — See section 5.
- **AI archetype** — Catch-all for grunt/brute/shielder/ranged categories.

---

## References

- **Belt scroller / belt-scrolling action**: Capcom Final Fight (1989) internal naming; Streets of Rage 4 GDC postmortem (Dotemu/Lizardcube, 2020).
- **Sketch+collision PSD**: Streets of Rage 4 art-direction talks (Ben Fiquet, 2020-2021); Lizardcube concept-to-implementation videos.
- **Vanishing-point conflict**: classical perspective theory (Loomis, "Successful Drawing"); applied to game backdrops by Cuphead studio (StudioMDHR GDC talks).
- **Parallax2D / TileMapLayer**: Godot 4.3 release notes, godotengine.org/article/godot-4-3-is-released.
- **IPAdapter weight_type modes**: cubiq/ComfyUI_IPAdapter_plus README (latyas/2026 fork).
- **Krita-AI-Diffusion**: Acly/krita-ai-diffusion GitHub.
- **Cutout animation lineage**: Spine documentation (esotericsoftware.com), DragonBones docs.
- **Hitstop, frame data, i-frames**: fighting-game-community shared lexicon, Dustloop wiki conventions.

---

## "Aha" Terms to Adopt Immediately

These are the load-bearing terms our earlier passes lacked:

1. **Vanishing-point conflict** — names exactly why our bg/floor cohesion failed.
2. **Sketch+collision PSD (shared-sketch workflow)** — names the SoR4 industry-standard fix.
3. **3/4 view (three-quarter view)** vs **eye-level side view** — names the two incompatible framings stacked in a belt scroller.
4. **Forced perspective** — names the painted-not-derived nature of belt-scroller floors.
5. **Atmospheric perspective** — names the most powerful tool to *unify* a mismatched bg/floor.
6. **Play band / playable belt** — names the gameplay surface distinctly from BG/FG.
7. **Regional Prompter** — names the ComfyUI tool that solves "different prompt per region" for shared-sketch generation.
8. **Cutout animation** — names the Spine/DragonBones style our pipeline targets (vs frame-by-frame sprite sheets).
