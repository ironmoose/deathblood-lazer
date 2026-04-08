## Autoload singleton that limits how many enemies can attack simultaneously.
##
## Enemies call [method request_attack] before entering ATTACK state.
## If the number of active attackers is below [const MAX_ATTACKERS], the
## request is granted. Call [method release_attack] when leaving ATTACK.
extends Node

const MAX_ATTACKERS: int = 3
var _active_attackers: Array[Node] = []


func request_attack(enemy: Node) -> bool:
	# Prune any freed enemies.
	_active_attackers = _active_attackers.filter(func(e): return is_instance_valid(e))
	if _active_attackers.size() < MAX_ATTACKERS:
		_active_attackers.append(enemy)
		return true
	return false


func release_attack(enemy: Node) -> void:
	_active_attackers.erase(enemy)
