# Hearts Card Game

A full terminal Hearts card game — you vs 3 AI opponents with distinct personalities. Avoid hearts, fear the Queen of Spades, chase the Jack of Diamonds, and dare to shoot the moon.

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

## Game Modes

| Mode | Description |
|------|-------------|
| Normal | Classic Hearts to 100 points |
| Omnibus | J♦ = -10 points for whoever wins it — adds risk/reward |
| Fast mode | AI plays instantly, minimal pauses |
| Custom limit | Set score limit to 50 (quick), 150 (long), anything you want |

## How to Play

- 4 players, 13 cards each per round
- **Pass 3 cards** before each round (direction rotates: left → right → across → keep)
- **2♣ leads** the first trick — no point cards allowed on trick 1
- Must follow suit or play anything if you can't
- Highest card of the led suit wins the trick
- **♥ = 1 point**, **Q♠ = 13 points** — avoid them
- Hearts can't be led until someone discards one ("breaking hearts")
- **Shoot the Moon** — take ALL 13 hearts + Q♠ → everyone else gets +26, you get 0
- **Omnibus rule** — J♦ = -10 for whoever wins it; still counts toward shooting the moon
- Game ends when someone hits the score limit — lowest score wins

## During Play — Commands

| Key | Action |
|-----|--------|
| `1–13` | Play a card by number |
| `?` | Show a hint — safest card suggestion with reasoning |
| `p` | Show all cards played so far, sorted by suit |
| `q` | Quit the game |

## Features

| Feature | Description |
|---------|-------------|
| 3 AI personalities | Alex (safe), Jordan (aggressive/moon-shooter), Riley (balanced) |
| AI awareness | Jordan blocks moon shots by other players when threatened |
| Shoot the moon | Full detection and reverse scoring |
| Omnibus mode | J♦ = -10 points — AI adjusts strategy to chase or avoid it |
| Fast mode | AI plays in 0.3s instead of 0.6s |
| Custom score limit | Change 100-point threshold to anything |
| Passing phase | Rotates left → right → across → no pass |
| Hint system | Press `?` for the safest card suggestion with an explanation |
| Played cards display | Press `p` to see every card played this round by suit |
| Trick history | Last 2 tricks shown above your hand each turn |
| Danger highlights | Q♠ K♠ A♠ shown in yellow, high ♥ shown in bold red, J♦ in green |
| Dimmed invalid cards | Cards you can't legally play are greyed out |
| Career stats | Win rate, streak, avg pts/round, best/worst game, moon shots |
| Head-to-head records | Win rate vs each AI opponent tracked separately |
| Omnibus J♦ grabs | Tracks how many times you grabbed J♦ across all games |
| Save file | All stats persisted to `~/.hearts_save.json` |

## AI Personalities

| AI | Style | Strategy |
|----|-------|----------|
| **Alex** | Safe | Dumps Q♠/K♠/A♠ in passing, avoids winning tricks, never leads high |
| **Jordan** | Aggressive | Holds high hearts and Q♠, tries to shoot the moon, switches to block if threatened |
| **Riley** | Balanced | Plays lowest safe card, dumps point cards when can't follow, chases J♦ in omnibus |

## Install command

```
playheart
```
