## Weapon data resource for the 2.5D beat 'em up weapon blending system.
##
## Every weapon has a primary subcategory (its identity) and an optional
## secondary subcategory. Tier 1/2/3 specials escalate in cost and power.
## Equip weapons at camp or merchants — never mid-combat.
class_name WeaponData
extends Resource

## Top-level weapon category.
enum Category { OFFENSE, SUPPORT }

## Subcategories for offense weapons.
enum OffenseSub { MELEE, RANGED, AOE, ELEMENTAL }

## Subcategories for support weapons.
enum SupportSub { HEALER, BUFFER, CONTROLLER }

## Display name shown in menus.
@export var weapon_name: String = ""

## Top-level category (offense or support).
@export var category: Category = Category.OFFENSE

## Primary subcategory as int — maps to [enum OffenseSub] or [enum SupportSub]
## depending on [member category].
@export var primary_sub: int = 0

## Secondary subcategory as int. -1 means no secondary (pure weapon).
## May cross category boundaries — a Melee weapon can have a Controller
## secondary, for example.
@export var secondary_sub: int = -1

# ---------------------------------------------------------------------------
# Tier 1 Special — costs 1 meter segment
# ---------------------------------------------------------------------------

@export_group("Tier 1 Special")

## Display name of the Tier 1 special move.
@export var t1_name: String = ""

## Flavour description shown in the move list.
@export var t1_description: String = ""

## Raw damage dealt by the Tier 1 special.
@export var t1_damage: int = 30

## HP restored to the user by the Tier 1 special (0 = none).
@export var t1_heal: int = 0

## Duration of any lingering effect in seconds (0.0 = instant).
@export var t1_duration: float = 0.0

## Optional VFX scene spawned when this special fires.
@export var t1_effect_scene: PackedScene = null

# ---------------------------------------------------------------------------
# Tier 2 Special — costs 2 meter segments
# ---------------------------------------------------------------------------

@export_group("Tier 2 Special")

## Display name of the Tier 2 special move.
@export var t2_name: String = ""

## Flavour description shown in the move list.
@export var t2_description: String = ""

## Raw damage dealt by the Tier 2 special.
@export var t2_damage: int = 60

## HP restored to the user by the Tier 2 special (0 = none).
@export var t2_heal: int = 0

## Duration of any lingering effect in seconds (0.0 = instant).
@export var t2_duration: float = 0.0

## Optional VFX scene spawned when this special fires.
@export var t2_effect_scene: PackedScene = null

# ---------------------------------------------------------------------------
# Tier 3 Special — costs 3 meter segments
# ---------------------------------------------------------------------------

@export_group("Tier 3 Special")

## Display name of the Tier 3 special move.
@export var t3_name: String = ""

## Flavour description shown in the move list.
@export var t3_description: String = ""

## Raw damage dealt by the Tier 3 special.
@export var t3_damage: int = 100

## HP restored to the user by the Tier 3 special (0 = none).
@export var t3_heal: int = 0

## Duration of any lingering effect in seconds (0.0 = instant).
@export var t3_duration: float = 0.0

## Optional VFX scene spawned when this special fires.
@export var t3_effect_scene: PackedScene = null

# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------

## Returns the damage value for the given tier (1, 2, or 3).
## Returns 0 for any other value.
func get_tier_damage(tier: int) -> int:
	match tier:
		1:
			return t1_damage
		2:
			return t2_damage
		3:
			return t3_damage
	return 0


## Returns the heal value for the given tier (1, 2, or 3).
## Returns 0 for any other value.
func get_tier_heal(tier: int) -> int:
	match tier:
		1:
			return t1_heal
		2:
			return t2_heal
		3:
			return t3_heal
	return 0


## Returns the display name for the given tier (1, 2, or 3).
## Returns an empty string for any other value.
func get_tier_name(tier: int) -> String:
	match tier:
		1:
			return t1_name
		2:
			return t2_name
		3:
			return t3_name
	return ""


## Returns the VFX [PackedScene] for the given tier (1, 2, or 3).
## Returns null for any other value or if no scene is assigned.
func get_tier_effect(tier: int) -> PackedScene:
	match tier:
		1:
			return t1_effect_scene
		2:
			return t2_effect_scene
		3:
			return t3_effect_scene
	return null
