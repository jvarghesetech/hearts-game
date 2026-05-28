# Hearts Card Game

A full terminal-based Hearts card game — you vs 3 AI opponents with distinct personalities. Avoid hearts, fear the Queen of Spades, and dare to shoot the moon.

## Setup

```bash
pip install -r requirements.txt
pip install .   # global command: playheart
```

## Play

```bash
playheart
# or
python main.py
```

## How to Play

- 4 players, 13 cards each per round
- **Pass 3 cards** before each round (direction rotates: left → right → across → keep)
- **2♣ leads** the first trick — must follow suit or play anything
- Highest card of the led suit wins the trick
- **♥ = 1 point**, **Q♠ = 13 points** — avoid them!
- Hearts can't be led until someone discards one ("breaking hearts")
- **Shoot the Moon** — take ALL 26 points in one round and everyone else gets 26 instead
- Game ends when someone hits **100 points** — lowest score wins

## Features

| Feature | Description |
|---------|-------------|
| 3 AI personalities | Alex (safe), Jordan (aggressive/moon-shooter), Riley (balanced) |
| Shoot the moon | Full detection — reverse scoring applied automatically |
| Passing phase | Rotates left → right → across → no pass each round |
| Color-coded cards | Red suits for ♥ and ♦, white for ♠ and ♣ |
| Valid move hints | Shows which card numbers are legal to play |
| Round summary | Points per player each round with running total |
| Scoreboard | Sorted leaderboard with danger zone warnings at 80+ |
| Career stats | Win rate, moon shots, games played — saved between sessions |
| Main menu | New game, view stats, read rules |
| Save file | Stats persisted to `~/.hearts_save.json` |

## AI Personalities

- **Alex** — plays it safe, dumps dangerous cards early, avoids winning tricks
- **Jordan** — aggressive moon-shooter, holds high hearts and Q♠, tries to take everything
- **Riley** — balanced, plays the lowest card that won't win a trick

## Install command

```
playheart
```
