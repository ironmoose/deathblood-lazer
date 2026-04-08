## Reusable Hurtbox component that receives damage from [Hitbox] areas.
##
## Attach to any entity that can be damaged. The parent entity should connect
## to [signal damage_received] to react to incoming hits.
class_name Hurtbox
extends Area2D

signal damage_received(amount: int, knockback: float, hitstun: float, attacker: Node)

## The entity that owns this hurtbox.
var owner_entity: Node = null


func take_damage(amount: int, knockback: float, hitstun: float, attacker: Node) -> void:
	damage_received.emit(amount, knockback, hitstun, attacker)
