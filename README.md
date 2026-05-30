# Hearts Card Game

A full terminal Hearts card game — you vs 3 AI opponents with distinct personalities. Multiple game modes, AI taunts, difficulty levels, rival tracking, mid-game saves, and replay support.

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
| Omnibus | J♦ = -10 pts for whoever wins it |
| Blood Hearts | First ♥ discarded costs the taker +2 extra points |
| Fast mode | AI plays in 0.3s, minimal pauses |
| Custom limit | Set to 50 (quick) or 150 (marathon) |
| Difficulty | Easy / Medium / Hard — affects AI accuracy |
| Colorblind | Suits shown as S/H/D/C instead of ♠♥♦♣ |
| Mix & match | Stack any combination of modes |

## How to Play

- 4 players, 13 cards each per round
- **Pass 3 cards** before each round — direction rotates: left → right → across → keep
- **Passing preview** — get a hint about whether the sender is giving you dangerous cards
- **2♣ leads** the first trick — no point cards allowed on trick 1
- Must follow suit or play anything if you can't
- Highest card of the led suit wins the trick
- **♥ = 1 pt**, **Q♠ = 13 pts** — avoid them
- **Q♠ Safe rule** — if you lead Q♠ and win the trick, no penalty
- Hearts can't be led until someone discards one (breaking hearts)
- **Shoot the Moon** — take ALL ♥ + Q♠ → everyone else +26, you get 0
- **Omnibus** — J♦ = -10 for whoever wins that trick
- **Blood Hearts** — the first ♥ played costs the taker an extra +2 pts
- Game ends when someone hits the score limit — lowest score wins

## During Play — Commands

| Key | Action |
|-----|--------|
| `1–13` | Play a card by number |
| `?` | Hint — safest card with reasoning + card-count context |
| `p` | Show all cards played so far, sorted by suit with remaining count |
| `s` | Save mid-game and quit — resume from the main menu |
| `q` | Quit without saving |

## All Features

| Feature | Description |
|---------|-------------|
| 3 AI personalities | Alex (safe), Jordan (aggressive/moon-shooter), Riley (balanced) |
| 3 difficulty levels | Easy (mistakes), Medium (current), Hard (near-optimal tracking) |
| AI taunts | Jordan trash-talks when going for the moon; Alex mutters when playing safe |
| Moon threat bar | Progress bar appears next to any AI collecting 8+ pts toward moon |
| QS Safe rule | Lead Q♠ and win the trick → zero penalty |
| Passing preview | Hints whether the sender has dangerous cards before you choose |
| Blood Hearts | First ♥ discarded costs the taker +2 extra penalty points |
| Colorblind mode | S/H/D/C labels instead of suit symbols; bold underline for danger |
| Win animation | ASCII heart shower when you win |
| Round-by-round history | Full table of every round's scores shown at game end |
| Rival tracking | The AI who beats you most is labeled "Your Rival" on the menu |
| Mid-game save | Press `s` to save and quit; resume from the main menu |
| Replay last game | Replay any game using the same random seed |
| Hint system | Context-aware: mentions Q♠ still in play, high hearts remaining |
| Played cards display | Per-suit with count of remaining cards |
| Trick history | Last 2 tricks shown above your hand each turn |
| Danger highlights | Q♠ K♠ A♠ yellow, high ♥ bold red, J♦ green |
| Dimmed invalid cards | Illegal cards greyed out automatically |
| Head-to-head W/L | Win/loss record vs each AI, separate |
| Win streak | Current and best streak tracked |
| Avg pts per round | Career average tracked across all games |
| Best / worst game | Personal records for lowest and highest score |
| Omnibus J♦ grabs | How many times you snagged J♦ across all Omnibus games |

## AI Personalities

| AI | Style | Taunts |
|----|-------|--------|
| **Alex** | Safe — dumps danger cards, never leads high, avoids winning | "Playing it safe..." |
| **Jordan** | Aggressive — chases the moon, switches to blocking if threatened | "Feeling lucky? 😈" |
| **Riley** | Balanced — plays smart defense, chases J♦ in Omnibus | "Calculated." |

## Install command

```
playheart
```
