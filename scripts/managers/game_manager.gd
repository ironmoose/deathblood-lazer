## GameManager autoload singleton.
##
## Central game state manager for Golden Brawl. Tracks game state transitions,
## shared lives, per-player scores, and emits signals for UI and system listeners.
extends Node

## Possible states the game can be in.
enum GameState { MENU, PLAYING, PAUSED }

## Emitted when the game transitions to a new state.
signal game_state_changed(new_state: GameState)

## Emitted when the party loses a life. Carries the remaining life count.
signal life_lost(remaining: int)

## Emitted when shared lives reach zero.
signal game_over

## Current state of the game.
var current_state: GameState = GameState.MENU

## Number of active players (0 until start_game is called).
var player_count: int = 0

## Lives shared across all players.
var shared_lives: int = 3

## Per-player score array (index 0 = player 1, index 1 = player 2).
var scores: Array[int] = [0, 0]


## Transition to PLAYING state and reset session values.
func start_game(num_players: int = 2) -> void:
	player_count = num_players
	shared_lives = 3
	scores = [0, 0]
	_set_state(GameState.PLAYING)


## Transition to PAUSED state (only while PLAYING).
func pause_game() -> void:
	if current_state == GameState.PLAYING:
		_set_state(GameState.PAUSED)


## Return to PLAYING state from PAUSED.
func resume_game() -> void:
	if current_state == GameState.PAUSED:
		_set_state(GameState.PLAYING)


## Add [param amount] to the score of [param player_id] (0-indexed).
func add_score(player_id: int, amount: int) -> void:
	if player_id >= 0 and player_id < scores.size():
		scores[player_id] += amount


## Decrement shared lives by one. Emits [signal life_lost] and, if lives
## reach zero, emits [signal game_over].
func lose_life() -> void:
	if shared_lives <= 0:
		return
	shared_lives -= 1
	life_lost.emit(shared_lives)
	if shared_lives <= 0:
		game_over.emit()


## Returns [code]true[/code] when shared lives have been exhausted.
func is_game_over() -> bool:
	return shared_lives <= 0


## Internal helper to change state and emit the signal.
func _set_state(new_state: GameState) -> void:
	current_state = new_state
	game_state_changed.emit(new_state)
