## Reusable 3-segment special meter component.
##
## Tracks special meter points earned by dealing and taking damage.
## Attach as a child node. Call [method add_points_from_damage_dealt] or
## [method add_points_from_damage_taken] when damage events fire, and
## [method consume_segment] when the player activates a special move.
class_name SpecialMeter
extends Node

signal meter_changed(current_points: int, max_points: int, segments: int)
signal meter_full
signal meter_empty

## Points needed to fill one segment.
const POINTS_PER_SEGMENT: int = 10

## Maximum number of segments.
const MAX_SEGMENTS: int = 3

## Points earned per damage dealt.
const DEAL_DAMAGE_MULTIPLIER: float = 1.0

## Points earned per damage taken.
const TAKE_DAMAGE_MULTIPLIER: float = 1.5

var _current_points: int = 0
var _max_points: int = POINTS_PER_SEGMENT * MAX_SEGMENTS


func get_segments() -> int:
	return _current_points / POINTS_PER_SEGMENT


func get_points() -> int:
	return _current_points


func get_max_points() -> int:
	return _max_points


func can_use_special() -> bool:
	return get_segments() >= 1


func can_use_tier(tier: int) -> bool:
	return get_segments() >= tier


func consume_segment() -> bool:
	if not can_use_special():
		return false
	_current_points -= POINTS_PER_SEGMENT
	meter_changed.emit(_current_points, _max_points, get_segments())
	if _current_points == 0:
		meter_empty.emit()
	return true


func use_tier(tier: int) -> bool:
	if not can_use_tier(tier):
		return false
	_current_points -= tier * POINTS_PER_SEGMENT
	meter_changed.emit(_current_points, _max_points, get_segments())
	if _current_points == 0:
		meter_empty.emit()
	return true


func add_points_from_damage_dealt(damage: int) -> void:
	var points: int = int(float(damage) * DEAL_DAMAGE_MULTIPLIER)
	_current_points = mini(_current_points + points, _max_points)
	meter_changed.emit(_current_points, _max_points, get_segments())
	if _current_points == _max_points:
		meter_full.emit()


func add_points_from_damage_taken(damage: int) -> void:
	var points: int = int(float(damage) * TAKE_DAMAGE_MULTIPLIER)
	_current_points = mini(_current_points + points, _max_points)
	meter_changed.emit(_current_points, _max_points, get_segments())
	if _current_points == _max_points:
		meter_full.emit()


func reset() -> void:
	_current_points = 0
	meter_changed.emit(_current_points, _max_points, get_segments())
