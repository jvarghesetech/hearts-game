# Hearts Card Game

A full terminal Hearts card game — you vs 3 AI opponents with distinct personalities. Achievements, leaderboard, spectator mode, tournament mode, auto-pass suggestions, and a ton more.

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
| Tournament | Best of 3 — track series wins across games |
| Spectator | Watch 4 AIs play each other — great for learning strategy |
| Mix & match | Stack any combination of modes |

## How to Play

- 4 players, 13 cards each per round
- **Pass 3 cards** before each round — direction rotates: left → right → across → keep
- **Press Enter** during passing to accept the auto-suggested 3 cards
- **Hand danger rating** shown before passing (Safe / Risky / Dangerous)
- **Passing preview** — hints if the sender has dangerous or safe cards
- **2♣ leads** first trick — no point cards on trick 1
- Must follow suit or play anything if you can't
- Highest card of the led suit wins the trick
- **♥ = 1 pt**, **Q♠ = 13 pts** — avoid them
- **Q♠ Safe rule** — lead Q♠ and win the trick → zero penalty
- Hearts can't be led until broken
- **Shoot the Moon** — take ALL ♥ + Q♠ → everyone else +26, you get 0
- **Omnibus** — J♦ = -10 for whoever wins that trick
- **Blood Hearts** — the first ♥ discarded costs the taker +2 extra pts
- Game ends when someone hits the score limit — lowest score wins

## During Play — Commands

| Key | Action |
|-----|--------|
| `1–13` | Play a card by number |
| `?` | Hint — safest card + reasoning + remaining card context |
| `p` | Show all played cards by suit with count remaining |
| `t` | Toggle hand sort between suit-order and rank-order |
| `s` | Save mid-game and quit — resume from main menu |
| `q` | Quit without saving |

## All Features

| Feature | Description |
|---------|-------------|
| 3 AI personalities | Alex (safe), Jordan (aggressive/moon-shooter), Riley (balanced) |
| 3 difficulty levels | Easy (25% random mistakes), Medium, Hard (near-optimal card tracking) |
| AI taunts | Jordan trash-talks, Alex mutters, Riley stays cool |
| Moon threat bar | Progress bar when any AI hits 8+ pts toward shooting the moon |
| Win animation | ASCII heart shower on victory |
| Achievements | 8 unlockable badges — Moon Hunter, Ironclad, Jordan Slayer, and more |
| Leaderboard | Top 5 all-time lowest winning scores |
| Spectator mode | Watch 4 AIs play — no input needed |
| Tournament mode | Best of 3 series with series-win tracking |
| ASCII score chart | Bar graph of your points per round after each game |
| Round history table | Full per-round breakdown at game end |
| Auto-pass suggestion | Suggested 3 cards with reasoning — press Enter to accept |
| Hand danger rating | Safe / Risky / Dangerous rating shown before passing |
| Passing preview | Hints whether the sender has dangerous cards |
| QS Safe rule | Lead Q♠ and win the trick → zero penalty |
| Blood Hearts | First ♥ discarded costs taker +2 extra pts |
| Sort toggle | Press `t` to switch between suit-sort and rank-sort |
| Played cards display | Per-suit with count of remaining cards |
| Trick history | Last 2 tricks shown above your hand each turn |
| Danger highlights | Q♠ K♠ A♠ yellow, high ♥ bold red, J♦ green |
| Dimmed invalid cards | Illegal cards greyed out automatically |
| Rival tracking | Most-wins AI labeled "Your Rival 👊" on the menu |
| Mid-game save | Press `s` — resume from main menu next session |
| Replay last game | Same random seed, identical cards |
| Colorblind mode | S/H/D/C labels with bold/underline for dangerous cards |
| Head-to-head W/L | Win/loss record vs each AI tracked separately |
| Win streak | Current and all-time best streak |
| Career stats | Avg pts/round, best/worst game, moon shots, J♦ grabs |

## AI Personalities

| AI | Style | Taunt |
|----|-------|-------|
| **Alex** | Safe — dumps Q♠/K♠/A♠, avoids winning | "Playing it safe..." |
| **Jordan** | Aggressive — chases the moon, blocks if threatened | "Feeling lucky? 😈" |
| **Riley** | Balanced — plays smart defense, grabs J♦ in Omnibus | "Calculated." |

## Achievements

| Badge | Condition |
|-------|-----------|
| Moon Hunter | Shot the moon 5+ times |
| Ironclad | Won a game with ≤10 points |
| Jordan Slayer | Beat Jordan 10+ times |
| Veteran | Played 20+ games |
| On a Roll | Won 3+ games in a row |
| Omnibus Pro | Grabbed J♦ 10+ times |
| Perfect | Won a game with 0 points |
| Centurion | Played 100+ rounds total |

## Install command

```
playheart
```
