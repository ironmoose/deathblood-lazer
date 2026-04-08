# Combat System Integration Notes

## Player.gd needs these additions after state machine refactor:

### Node references:
```gdscript
@onready var hitbox: Hitbox = $Hitbox
@onready var hurtbox: Hurtbox = $Hurtbox
@onready var health: HealthComponent = $HealthComponent
```

### In _ready():
```gdscript
hitbox.owner_entity = self
hurtbox.owner_entity = self
hurtbox.damage_received.connect(_on_damage_received)
health.died.connect(_on_died)
```

### Hitbox activation (in state enter/exit):
- ATTACK_1 enter: `hitbox.damage = 10; hitbox.activate()`
- ATTACK_2 enter: `hitbox.damage = 15; hitbox.activate()`
- ATTACK_3 enter: `hitbox.damage = 25; hitbox.activate()`
- All attack exits: `hitbox.deactivate()`

### Hitbox positioning (in state update):
```gdscript
hitbox.position.x = 30 if not animated_sprite.flip_h else -30
```

### Damage handling:
```gdscript
func _on_damage_received(amount, knockback, hitstun, attacker):
    health.take_damage(amount)
    # Change state to HURT
    # Apply knockback
    HitStop.freeze(0.05)

func _on_died():
    # Change state to DEAD
```
