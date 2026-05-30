"""
Hearts Card Game — terminal-based, fully offline.
You vs 3 AI with distinct personalities, multiple modes, and full stats tracking.
"""
import random
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich.progress import BarColumn, Progress, TextColumn
    from rich import box
    from rich.text import Text
except ImportError:
    print("Run: pip install rich")
    sys.exit(1)

console = Console()
SAVE_FILE    = Path.home() / ".hearts_save.json"
MIDGAME_FILE = Path.home() / ".hearts_midgame.json"

# ── Card representation ────────────────────────────────────────────────────────

SUITS_NORMAL     = ["♠", "♥", "♦", "♣"]
SUITS_COLORBLIND = ["S", "H", "D", "C"]
RANKS    = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_VAL = {r: i for i, r in enumerate(RANKS)}
DANGER_CARDS = {("Q","♠"), ("A","♠"), ("K","♠")}

_colorblind = False

def suits():
    return SUITS_COLORBLIND if _colorblind else SUITS_NORMAL

def suit_sym(s):
    """Map internal suit symbol to display symbol."""
    if _colorblind:
        return SUITS_COLORBLIND[SUITS_NORMAL.index(s)]
    return s

def card_str(card, pad=False):
    rank, suit = card
    dsym = suit_sym(suit)
    is_red   = suit in ("♥","♦")
    is_high_heart = suit == "♥" and RANK_VAL[rank] >= RANK_VAL["10"]
    is_danger = card in DANGER_CARDS
    is_jd     = card == ("J","♦")

    if _colorblind:
        color = "bold underline white" if is_danger else \
                "bold white"           if is_high_heart else \
                "bold cyan"            if is_jd else "white"
    else:
        color = "bold yellow"  if is_danger else \
                "bold red"     if is_high_heart else \
                "red"          if is_red else \
                "bold green"   if is_jd else "white"

    s = f"{rank}{dsym}"
    if pad:
        s = s.ljust(5 if _colorblind else 4)
    return f"[{color}]{s}[/{color}]"

def card_points(card, omnibus=False, blood=False, qs_safe_winner=False):
    rank, suit = card
    pts = 0
    if suit == "♥":
        pts = 1
    elif suit == "♠" and rank == "Q":
        pts = 0 if qs_safe_winner else 13
    if omnibus and suit == "♦" and rank == "J":
        pts -= 10
    return pts

def deck():
    return [(r, s) for s in SUITS_NORMAL for r in RANKS]

def sort_hand(hand):
    return sorted(hand, key=lambda c: (SUITS_NORMAL.index(c[1]), RANK_VAL[c[0]]))

# ── Played cards tracker ───────────────────────────────────────────────────────

class PlayedTracker:
    def __init__(self):
        self.played = set()
        self.trick_history = []
        self.player_played = defaultdict(set)  # who played what

    def add_trick(self, trick):
        self.trick_history.append(list(trick))
        for card, player in trick:
            self.played.add(card)
            self.player_played[player].add(card)

    def remaining(self):
        return [c for c in deck() if c not in self.played]

    def show_played(self, suit=None):
        played = sorted(self.played, key=lambda c: (SUITS_NORMAL.index(c[1]), RANK_VAL[c[0]]))
        if suit:
            played = [c for c in played if c[1] == suit]
        return played

    def last_tricks(self, n=2):
        return self.trick_history[-n:]

    def suit_void(self, player, suit):
        """Has this player shown they're void in this suit?"""
        played_suits = {c[1] for c in self.player_played[player]}
        return suit in played_suits and not any(
            c[1] == suit for c in self.player_played[player]
        )

    def qs_still_out(self):
        return ("Q","♠") not in self.played

    def high_hearts_out(self):
        return [c for c in [("A","♥"),("K","♥"),("Q","♥")] if c not in self.played]

# ── AI Taunts ─────────────────────────────────────────────────────────────────

AI_TAUNTS = {
    "Jordan": {
        "going_for_moon": ["Feeling lucky? 😈", "Watch this...", "You can't stop me now."],
        "dump_qs":        ["Here's a gift 🙃", "Surprise!", "Oops, dropped something."],
        "win_trick":      ["Mine.", "Thank you!", "I'll take that."],
    },
    "Alex": {
        "safe_play":      ["Playing it safe...", "No thank you.", "Not my problem."],
        "avoid_win":      ["Close one.", "Phew.", "Dodged that."],
        "dump":           ["Careful with that.", "All yours.", "Don't mind if I do."],
    },
    "Riley": {
        "grab_jd":        ["Oh, J♦! Don't mind if I do.", "-10! 🎉", "That's mine."],
        "balanced":       ["Hmm.", "Strategic.", "We'll see."],
        "win_trick":      ["Calculated.", "Efficient.", "As expected."],
    },
}

def ai_taunt(name, event, fast=False):
    if fast:
        return
    pool = AI_TAUNTS.get(name, {}).get(event, [])
    if pool and random.random() < 0.35:
        console.print(f"  [dim italic]{name}: \"{random.choice(pool)}\"[/dim italic]")

# ── Moon threat bar ────────────────────────────────────────────────────────────

def show_moon_threat(round_points, players):
    threats = {p: round_points.get(p, 0) for p in players[1:]}
    max_threat = max(threats.values(), default=0)
    if max_threat < 8:
        return
    console.print()
    for p, pts in threats.items():
        if pts >= 8:
            bar_filled = int((pts / 26) * 20)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            color = "red" if pts >= 20 else "yellow" if pts >= 14 else "dim yellow"
            console.print(f"  [{color}]⚠ {p} moon threat: [{bar}] {pts}/26[/{color}]")

# ── Win animation ──────────────────────────────────────────────────────────────

def win_animation():
    frames = [
        "  ♥   ♥   ♥   ♥   ♥",
        " ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥",
        "♥  ♥  ♥  ♥  ♥  ♥  ♥",
        " 🎉  YOU WON!  🎉",
        "♥  ♥  ♥  ♥  ♥  ♥  ♥",
        " ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥",
        "  ♥   ♥   ♥   ♥   ♥",
    ]
    for frame in frames:
        console.print(f"[bold magenta]{frame}[/bold magenta]")
        time.sleep(0.12)

# ── AI difficulty ─────────────────────────────────────────────────────────────

AI_NAMES = ["Alex", "Jordan", "Riley"]
AI_PERSONALITIES = {"Alex": "safe", "Jordan": "aggressive", "Riley": "balanced"}

def ai_mistake(difficulty):
    """Return True if the AI should make a random mistake."""
    if difficulty == "easy":
        return random.random() < 0.25
    if difficulty == "medium":
        return random.random() < 0.07
    return False  # hard — never mistakes

def ai_pass_cards(hand, name, omnibus=False, difficulty="medium"):
    personality = AI_PERSONALITIES[name]
    hand = sort_hand(hand)

    if ai_mistake(difficulty):
        return random.sample(hand, 3)

    if personality == "aggressive":
        risky = [c for c in hand if c[1] == "♥" and RANK_VAL[c[0]] >= RANK_VAL["J"]]
        risky += [c for c in hand if c == ("Q","♠")]
        safe  = [c for c in hand if c not in risky]
        if omnibus:
            safe = [c for c in safe if c != ("J","♦")]
        return (safe + risky)[:3]
    elif personality == "safe":
        danger = [c for c in hand if c in {("Q","♠"),("A","♠"),("K","♠")}]
        danger += [c for c in hand if c[1] == "♥" and RANK_VAL[c[0]] >= RANK_VAL["10"]]
        rest   = [c for c in hand if c not in danger]
        return (danger + rest)[:3]
    else:
        high = sorted(hand, key=lambda c: RANK_VAL[c[0]], reverse=True)
        if omnibus:
            high = [c for c in high if c != ("J","♦")]
        return high[:3]

def ai_play_card(hand, trick, led_suit, hearts_broken, is_first_trick,
                 name, scores, tracker, round_points, omnibus=False,
                 fast=False, difficulty="medium", blood=False):
    personality = AI_PERSONALITIES[name]

    followable = [c for c in hand if c[1] == led_suit] if led_suit else []
    playable = followable if followable else (
        [c for c in hand if card_points(c, omnibus) == 0] or hand
        if is_first_trick else hand
    )
    if is_first_trick:
        safe = [c for c in playable if card_points(c, omnibus) == 0]
        if safe:
            playable = safe

    if ai_mistake(difficulty):
        return random.choice(playable)

    other_moon = any(round_points.get(p, 0) >= 18 for p in scores if p != name)

    # Hard difficulty: use tracker to know exactly what's left
    if difficulty == "hard" and not followable and not is_first_trick:
        remaining = tracker.remaining()
        qs_out = ("Q","♠") not in tracker.played
        # prioritise dumping Q♠ if we have it
        qs_in_hand = [c for c in playable if c == ("Q","♠")]
        if qs_in_hand:
            return qs_in_hand[0]

    if personality == "aggressive":
        my_pts = round_points.get(name, 0)
        if my_pts >= 10 or not other_moon:
            if followable:
                chosen = max(playable, key=lambda c: RANK_VAL[c[0]])
                ai_taunt(name, "win_trick", fast)
                return chosen
            else:
                qs = [c for c in playable if c == ("Q","♠")]
                if qs:
                    ai_taunt(name, "dump_qs", fast)
                    return qs[0]
                if my_pts >= 16:
                    ai_taunt(name, "going_for_moon", fast)
                return sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]

    if personality == "safe" or (personality == "aggressive" and other_moon):
        if followable and trick:
            led_in_trick = [c for c, _ in trick if c[1] == led_suit]
            if led_in_trick:
                hi = max(RANK_VAL[c[0]] for c in led_in_trick)
                losing = [c for c in playable if RANK_VAL[c[0]] < hi]
                if losing:
                    ai_taunt(name, "avoid_win", fast)
                    return max(losing, key=lambda c: RANK_VAL[c[0]])
        if not followable:
            qs = [c for c in playable if c == ("Q","♠")]
            if qs:
                ai_taunt(name, "dump", fast)
                return qs[0]
            if omnibus:
                no_jd = [c for c in playable if c != ("J","♦") and card_points(c, omnibus) > 0]
                if no_jd:
                    return max(no_jd, key=lambda c: card_points(c, omnibus))
            hi_pts = sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)
            ai_taunt(name, "safe_play", fast)
            return hi_pts[0]
        ai_taunt(name, "safe_play", fast)
        return min(playable, key=lambda c: RANK_VAL[c[0]])

    else:  # balanced
        if not followable:
            qs = [c for c in playable if c == ("Q","♠")]
            if qs:
                return qs[0]
            return sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]
        if omnibus and ("J","♦") in playable and led_suit == "♦":
            led_in_trick = [c for c, _ in trick if c[1] == "♦"]
            if led_in_trick and RANK_VAL[("J","♦")[0]] > max(RANK_VAL[c[0]] for c in led_in_trick):
                ai_taunt(name, "grab_jd", fast)
                return ("J","♦")
        ai_taunt(name, "balanced", fast)
        return min(playable, key=lambda c: RANK_VAL[c[0]])

# ── Hint system ────────────────────────────────────────────────────────────────

def hint_card(hand, trick, led_suit, playable, tracker, round_points, omnibus):
    if not playable:
        return None, "No legal plays."

    qs_out = tracker.qs_still_out()
    high_h = tracker.high_hearts_out()

    if not led_suit:
        non_point = [c for c in playable if card_points(c, omnibus) >= 0]
        best = min(non_point or playable, key=lambda c: RANK_VAL[c[0]])
        extra = f" (Q♠ still in play)" if qs_out else ""
        return best, f"Lead your lowest safe card.{extra}"

    followable = [c for c in hand if c[1] == led_suit]
    if followable and trick:
        led_in_trick = [c for c, _ in trick if c[1] == led_suit]
        if led_in_trick:
            hi = max(RANK_VAL[c[0]] for c in led_in_trick)
            losing = [c for c in playable if RANK_VAL[c[0]] < hi]
            if losing:
                extra = f" ({len(high_h)} high hearts still out)" if high_h else ""
                return max(losing, key=lambda c: RANK_VAL[c[0]]), f"Play highest card that won't win this trick.{extra}"
        return min(playable, key=lambda c: RANK_VAL[c[0]]), "Can't avoid winning — play lowest."

    qs = [c for c in playable if c == ("Q","♠")]
    if qs:
        return qs[0], "Dump the Queen of Spades — get rid of it now!"
    danger = [c for c in playable if card_points(c, omnibus) > 0]
    if danger:
        best = max(danger, key=lambda c: card_points(c, omnibus))
        note = f" (Q♠ still out — watch spades)" if qs_out else ""
        return best, f"Dump your highest point card.{note}"
    return min(playable, key=lambda c: RANK_VAL[c[0]]), "Play lowest safe card."

# ── Shoot the moon ─────────────────────────────────────────────────────────────

def check_shoot_moon(round_points, omnibus=False):
    for player, pts in round_points.items():
        base_pts = pts
        if omnibus and pts <= -10 + 26:
            # separate J♦ contribution — check only hearts+QS
            pass
        if pts == 26 or (omnibus and pts == 16):  # 26 - 10 jd
            return player
        if pts == 26:
            return player
    # simpler: whoever has exactly 26 hearts+QS points
    for player, pts in round_points.items():
        if pts >= 26:
            return player
    return None

# ── Display ────────────────────────────────────────────────────────────────────

def show_hand(hand, selectable=False, playable=None):
    hand = sort_hand(hand)
    parts = []
    for i, card in enumerate(hand):
        num = f"[dim]{i+1:2}.[/dim] " if selectable else ""
        is_valid = playable is None or card in playable
        dim_s = "" if is_valid else "[dim]"
        dim_e = "" if is_valid else "[/dim]"
        parts.append(f"{dim_s}{num}{card_str(card)}{dim_e}")
    console.print("  " + "  ".join(parts))

def show_scores(scores, round_num=None, score_limit=100, rival=None):
    title = f"Scoreboard — Round {round_num}" if round_num else "Final Scores"
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Player", min_width=12)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Remaining", justify="right", width=10)
    table.add_column("Status", width=18)

    for player, score in sorted(scores.items(), key=lambda x: x[1]):
        remaining = score_limit - score
        status = "[green]Leading[/green]" if score == min(scores.values()) else ""
        if score >= score_limit * 0.8:
            status = "[red]Danger zone![/red]"
        if player == rival:
            status += " [dim]👊Rival[/dim]"
        color = "green" if score == min(scores.values()) else "white"
        table.add_row(f"[{color}]{player}[/{color}]", str(score), f"[dim]{remaining}[/dim]", status)
    console.print(table)

def show_trick_history(tracker, n=2):
    history = tracker.last_tricks(n)
    if not history:
        return
    console.print(f"[dim]Last {len(history)} trick(s):[/dim]")
    for trick in history:
        parts = [f"[bold]{p}[/bold]:{card_str(c)}" for c, p in trick]
        console.print("  " + "  |  ".join(parts))

def show_played_cards(tracker):
    console.print("\n[dim]Played cards by suit:[/dim]")
    for suit in SUITS_NORMAL:
        played = tracker.show_played(suit)
        if played:
            color = "red" if suit in ("♥","♦") else "white"
            rem_in_suit = [c for c in deck() if c[1] == suit and c not in tracker.played]
            s = "  ".join(card_str(c) for c in played)
            console.print(f"  [{color}]{suit_sym(suit)}[/{color}]: {s}  [dim]({len(rem_in_suit)} left)[/dim]")

def show_round_history(game_log, players):
    if not game_log:
        return
    table = Table(title="Round-by-Round History", box=box.SIMPLE, header_style="bold")
    table.add_column("Round", width=7)
    for p in players:
        table.add_column(p, justify="right", width=10)
    for i, row in enumerate(game_log, 1):
        cells = []
        for p in players:
            pts = row.get(p, 0)
            color = "red" if pts > 0 else ("green" if pts < 0 else "dim")
            cells.append(f"[{color}]{'+' if pts > 0 else ''}{pts}[/{color}]")
        table.add_row(str(i), *cells)
    console.print(table)

# ── Save / Load ────────────────────────────────────────────────────────────────

def load_save():
    defaults = {
        "games_played": 0, "wins": 0, "moon_shots": 0, "total_rounds": 0,
        "best_game": None, "worst_game": None, "win_streak": 0, "max_streak": 0,
        "avg_score_per_round": 0.0, "rounds_tracked": 0,
        "vs_alex": {"wins": 0, "games": 0, "losses": 0},
        "vs_jordan": {"wins": 0, "games": 0, "losses": 0},
        "vs_riley": {"wins": 0, "games": 0, "losses": 0},
        "omnibus_jd_grabs": 0, "rival": None, "last_seed": None,
    }
    if SAVE_FILE.exists():
        with open(SAVE_FILE) as f:
            saved = json.load(f)
        for k, v in defaults.items():
            if k not in saved:
                saved[k] = v
        return saved
    return defaults

def save_stats(stats):
    with open(SAVE_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def save_midgame(state):
    with open(MIDGAME_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_midgame():
    if MIDGAME_FILE.exists():
        with open(MIDGAME_FILE) as f:
            return json.load(f)
    return None

def clear_midgame():
    if MIDGAME_FILE.exists():
        MIDGAME_FILE.unlink()

def update_rival(stats):
    """Find the AI who beats the player most."""
    most_losses = 0
    rival = None
    for ai in AI_NAMES:
        key = f"vs_{ai.lower()}"
        losses = stats[key].get("losses", 0)
        if losses > most_losses:
            most_losses = losses
            rival = ai
    stats["rival"] = rival
    return rival

# ── Passing phase ──────────────────────────────────────────────────────────────

PASS_DIRECTIONS = ["left", "right", "across", "none"]

def passing_phase(hands, round_num, players, omnibus=False, difficulty="medium"):
    direction = PASS_DIRECTIONS[(round_num - 1) % 4]
    n = len(players)
    offsets = {"left": 1, "right": n-1, "across": n//2, "none": 0}
    offset = offsets[direction]

    if direction == "none":
        console.print(f"\n[dim]Round {round_num}: No passing.[/dim]")
        return hands

    console.print(f"\n[bold cyan]Passing — [yellow]{direction}[/yellow][/bold cyan]")

    passed = {}
    human = players[0]
    h_hand = sort_hand(hands[human])

    # Passing preview hint
    sender_idx = (players.index(human) - offset) % n
    sender = players[sender_idx]
    sender_hand = hands[sender]
    n_danger = sum(1 for c in sender_hand if c in DANGER_CARDS or card_points(c) > 0)
    preview = "dangerous cards" if n_danger >= 2 else "mostly safe cards"
    console.print(f"[dim]{sender} is sending you {preview} (approx.).[/dim]")

    console.print(f"\nYour hand:")
    show_hand(h_hand, selectable=True)
    if omnibus:
        console.print("[dim]Tip: J♦ = -10 pts (Omnibus)[/dim]")
    console.print(f"[yellow]Choose 3 cards to pass {direction}:[/yellow]")

    while True:
        raw = Prompt.ask("Cards (e.g. 1 5 9)").strip().split()
        try:
            idxs = [int(x)-1 for x in raw]
            if len(idxs) != 3 or len(set(idxs)) != 3:
                raise ValueError
            if any(i < 0 or i >= len(h_hand) for i in idxs):
                raise ValueError
            chosen = [h_hand[i] for i in idxs]
            break
        except (ValueError, IndexError):
            console.print("[red]Pick exactly 3 valid card numbers.[/red]")

    passed[human] = chosen
    for name in players[1:]:
        passed[name] = ai_pass_cards(hands[name], name, omnibus, difficulty)

    new_hands = {p: list(hands[p]) for p in players}
    for i, player in enumerate(players):
        recipient = players[(i + offset) % n]
        for card in passed[player]:
            new_hands[player].remove(card)
            new_hands[recipient].append(card)

    console.print(f"[green]You passed:[/green]   " + "  ".join(card_str(c) for c in chosen))
    received = passed[players[(players.index(human) - offset) % n]]
    console.print(f"[green]You received:[/green] " + "  ".join(card_str(c) for c in received))
    return new_hands

# ── Round ──────────────────────────────────────────────────────────────────────

def play_round(hands, players, round_num, scores, omnibus=False, fast=False,
               score_limit=100, difficulty="medium", blood=False, rival=None):
    leader = next(p for p in players if ("2","♣") in hands[p])
    hearts_broken = False
    round_points  = defaultdict(int)
    is_first_trick = True
    tracker = PlayedTracker()
    jd_grabbed_by = None
    first_heart_taken = False

    for trick_num in range(13):
        trick    = []
        led_suit = None

        console.rule(f"[dim]Trick {trick_num+1}/13[/dim]")
        if tracker.trick_history:
            show_trick_history(tracker, n=2)
        show_moon_threat(round_points, players)

        order = players[players.index(leader):] + players[:players.index(leader)]

        for player in order:
            hand = hands[player]

            if player == players[0]:  # human
                hand_sorted = sort_hand(hand)
                followable  = [c for c in hand_sorted if c[1] == led_suit] if led_suit else []
                if followable:
                    playable = followable
                elif is_first_trick:
                    playable = [c for c in hand_sorted if card_points(c, omnibus) == 0] or hand_sorted
                else:
                    if not hearts_broken:
                        nh = [c for c in hand_sorted if c[1] != "♥"]
                        playable = nh if nh else hand_sorted
                    else:
                        playable = hand_sorted

                console.print(f"\n[bold]Your hand ({len(hand)} cards):[/bold]")
                show_hand(hand_sorted, selectable=True, playable=playable)

                if trick:
                    parts = [f"[bold]{p}[/bold]:{card_str(c)}" for c, p in trick]
                    console.print("  Table: " + "  |  ".join(parts))

                valid_idxs = {hand_sorted.index(c)+1 for c in playable}

                if is_first_trick and not led_suit:
                    console.print("[dim]You must lead 2♣[/dim]")
                    chosen = ("2","♣")
                else:
                    hint_c, hint_msg = hint_card(
                        hand_sorted, trick, led_suit, playable, tracker, round_points, omnibus
                    )
                    valid_str = ", ".join(str(i) for i in sorted(valid_idxs))
                    console.print(f"[yellow]Play ({valid_str})  [dim]?=hint  p=played  s=save&quit  q=quit[/dim]:[/yellow]")

                    while True:
                        raw = Prompt.ask("Card").strip().lower()

                        if raw == "?":
                            if hint_c:
                                idx = hand_sorted.index(hint_c)+1
                                console.print(f"  [cyan]Hint:[/cyan] #{idx} {card_str(hint_c)} — {hint_msg}")
                            continue

                        if raw == "p":
                            show_played_cards(tracker)
                            continue

                        if raw == "s":
                            state = {
                                "hands":  {p: list(hands[p]) for p in players},
                                "scores": dict(scores),
                                "round_num": round_num,
                                "players": players,
                                "omnibus": omnibus, "fast": fast,
                                "score_limit": score_limit,
                                "difficulty": difficulty,
                                "blood": blood,
                            }
                            save_midgame(state)
                            console.print("[green]Game saved! Resume with 'playheart' → Resume.[/green]")
                            sys.exit(0)

                        if raw == "q":
                            console.print("[yellow]Quitting without saving.[/yellow]")
                            sys.exit(0)

                        try:
                            idx  = int(raw) - 1
                            card = hand_sorted[idx]
                            if card not in playable:
                                console.print("[red]That card isn't valid here.[/red]")
                                continue
                            chosen = card
                            break
                        except (ValueError, IndexError):
                            console.print("[red]Enter a number, ?, p, s, or q.[/red]")

            else:  # AI
                time.sleep(0.3 if fast else 0.6)
                chosen = ai_play_card(
                    hand, trick, led_suit, hearts_broken, is_first_trick,
                    player, scores, tracker, round_points, omnibus, fast, difficulty, blood
                )

            # Blood Hearts: first heart costs +2 extra
            if chosen[1] == "♥" and not first_heart_taken and blood:
                first_heart_taken = True
                hearts_broken = True
                round_points[player if player != players[0] else players[0]] += 2
                console.print(f"  [red bold]Blood Hearts! First ♥ costs +2 extra![/red bold]")

            if not led_suit:
                led_suit = chosen[1]
            if chosen[1] == "♥":
                hearts_broken = True
            if chosen == ("Q","♠"):
                hearts_broken = True

            trick.append((chosen, player))
            hands[player].remove(chosen)

            if player != players[0]:
                console.print(f"  [dim]{player}[/dim] plays {card_str(chosen)}")

        # who won?
        led_cards = [(c, p) for c, p in trick if c[1] == led_suit]
        winner_card, winner = max(led_cards, key=lambda x: RANK_VAL[x[0][0]])

        # QS safe rule: if winner led Q♠ and won, no penalty
        qs_led_and_won = (winner_card == ("Q","♠") and trick[0][0] == ("Q","♠") and trick[0][1] == winner)

        trick_pts = sum(
            card_points(c, omnibus, qs_safe_winner=qs_led_and_won)
            for c, _ in trick
        )

        if omnibus and ("J","♦") in [c for c, _ in trick]:
            jd_grabbed_by = winner

        round_points[winner] += trick_pts
        tracker.add_trick(trick)
        leader = winner
        is_first_trick = False

        color = "red" if trick_pts > 0 else ("green" if trick_pts < 0 else "dim")
        pts_str = f"[{color}]{'+' if trick_pts > 0 else ''}{trick_pts}pts[/{color}]" if trick_pts != 0 else "[dim]0pts[/dim]"
        console.print(f"  → [bold]{winner}[/bold] wins {pts_str}")
        if qs_led_and_won:
            console.print("  [green dim](Q♠ Safe — you led it, no penalty)[/green dim]")

    # shoot the moon check
    hearts_qs = {}
    for p in round_points:
        base = round_points[p]
        if omnibus and jd_grabbed_by == p:
            base += 10  # remove J♦ contribution
        hearts_qs[p] = base

    shooter = next((p for p, v in hearts_qs.items() if v >= 26), None)
    player_shot_moon = False

    if shooter:
        console.print(Panel(
            f"[bold yellow]🌕 {shooter} SHOT THE MOON!\nEveryone else +26![/bold yellow]",
            box=box.HEAVY, style="yellow"
        ))
        for p in players:
            if p != shooter:
                scores[p] += 26
        if omnibus and jd_grabbed_by == shooter:
            scores[shooter] -= 10
        player_shot_moon = (shooter == players[0])
    else:
        for p in players:
            scores[p] += round_points[p]

    if omnibus and jd_grabbed_by and not shooter:
        console.print(f"  [green bold]{jd_grabbed_by} grabbed J♦ → -10![/green bold]")

    return round_points, player_shot_moon, jd_grabbed_by

# ── Round summary ──────────────────────────────────────────────────────────────

def round_summary(round_points, players, scores, round_num):
    table = Table(title=f"Round {round_num} Results", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("Player", min_width=10)
    table.add_column("This Round", justify="right", width=12)
    table.add_column("Total", justify="right", width=8)
    for p in players:
        pts = round_points.get(p, 0)
        color = "red" if pts > 0 else ("green" if pts < 0 else "dim")
        table.add_row(p, f"[{color}]{'+' if pts>0 else ''}{pts}[/{color}]", str(scores[p]))
    console.print(table)

# ── Career stats ───────────────────────────────────────────────────────────────

def show_career_stats(stats):
    if stats["games_played"] == 0:
        console.print("[dim]No games played yet.[/dim]")
        return
    wr = 100 * stats["wins"] / stats["games_played"]

    table = Table(title="Your Career Stats", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Stat", min_width=24)
    table.add_column("Value", justify="right")
    table.add_row("Games played",         str(stats["games_played"]))
    table.add_row("Games won",            str(stats["wins"]))
    table.add_row("Win rate",             f"{wr:.1f}%")
    table.add_row("Current streak",       str(stats["win_streak"]))
    table.add_row("Best streak",          str(stats["max_streak"]))
    table.add_row("Moon shots",           str(stats["moon_shots"]))
    table.add_row("Avg pts/round",        f"{stats['avg_score_per_round']:.1f}")
    if stats["best_game"] is not None:
        table.add_row("Best game (lowest score)", str(stats["best_game"]))
    if stats["worst_game"] is not None:
        table.add_row("Worst game (highest score)", str(stats["worst_game"]))
    table.add_row("Total rounds",         str(stats["total_rounds"]))
    if stats.get("omnibus_jd_grabs"):
        table.add_row("J♦ grabs (Omnibus)",   str(stats["omnibus_jd_grabs"]))
    if stats.get("rival"):
        table.add_row("Your Rival",            f"[red]{stats['rival']}[/red]")
    console.print(table)

    h2h = Table(title="Head-to-Head", box=box.SIMPLE, header_style="bold")
    h2h.add_column("Opponent", min_width=10)
    h2h.add_column("W/L", justify="right")
    h2h.add_column("Win %", justify="right")
    for ai in AI_NAMES:
        key = f"vs_{ai.lower()}"
        d = stats[key]
        if d["games"] > 0:
            rate = 100 * d["wins"] / d["games"]
            color = "green" if rate >= 50 else "red"
            rival_tag = " 👊" if ai == stats.get("rival") else ""
            h2h.add_row(f"{ai}{rival_tag}",
                        f"[{color}]{d['wins']}W/{d.get('losses',0)}L[/{color}]",
                        f"[{color}]{rate:.0f}%[/{color}]")
    console.print(h2h)

# ── Main game loop ─────────────────────────────────────────────────────────────

def play_game(player_name, omnibus=False, fast=False, score_limit=100,
              difficulty="medium", blood=False, colorblind=False,
              resume_state=None, seed=None):
    global _colorblind
    _colorblind = colorblind

    if resume_state:
        players    = resume_state["players"]
        scores     = resume_state["scores"]
        round_num  = resume_state["round_num"]
        omnibus    = resume_state.get("omnibus", omnibus)
        fast       = resume_state.get("fast", fast)
        score_limit= resume_state.get("score_limit", score_limit)
        difficulty = resume_state.get("difficulty", difficulty)
        blood      = resume_state.get("blood", blood)
        console.print("[green]Resuming saved game![/green]")
        clear_midgame()
    else:
        players   = [player_name] + AI_NAMES
        scores    = {p: 0 for p in players}
        round_num = 1

    stats = load_save()
    rival = stats.get("rival")
    moon_shots_this_game = 0
    player_round_scores  = []
    jd_grabs  = 0
    game_log  = []

    # store seed for replay
    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)
    stats["last_seed"] = seed

    tags = []
    if omnibus:   tags.append("[yellow]Omnibus[/yellow]")
    if blood:     tags.append("[red]Blood Hearts[/red]")
    if fast:      tags.append("[dim]Fast[/dim]")
    if colorblind:tags.append("[dim]Colorblind[/dim]")
    tag_str = "  ".join(tags)

    console.print(Panel(
        f"[bold magenta]♥ Hearts ♥[/bold magenta]  {tag_str}\n"
        f"[dim]{player_name} vs {', '.join(AI_NAMES)}  |  Difficulty: {difficulty}\n"
        f"Points: ♥=1  Q♠=13{'  J♦=-10' if omnibus else ''}{'  First♥=+2' if blood else ''}\n"
        f"Lose at {score_limit} pts  |  ?=hint  p=played  s=save  q=quit[/dim]",
        expand=False
    ))

    if rival:
        console.print(f"[dim]Your rival: [red]{rival}[/red] — time for revenge.[/dim]\n")

    while max(scores.values()) < score_limit:
        console.rule(f"[bold magenta]Round {round_num}[/bold magenta]")

        d = deck()
        rng.shuffle(d)
        hands = {p: d[i*13:(i+1)*13] for i, p in enumerate(players)}

        hands = passing_phase(hands, round_num, players, omnibus, difficulty)

        round_points, player_shot_moon, jd_grabbed = play_round(
            hands, players, round_num, scores,
            omnibus, fast, score_limit, difficulty, blood, rival
        )

        if player_shot_moon:
            moon_shots_this_game += 1
        if jd_grabbed == player_name:
            jd_grabs += 1

        player_round_scores.append(round_points.get(player_name, 0))
        game_log.append({p: round_points.get(p, 0) for p in players})

        round_summary(round_points, players, scores, round_num)
        show_scores(scores, round_num, score_limit, rival)

        round_num += 1
        stats["total_rounds"] += 1

        if max(scores.values()) < score_limit:
            if not fast:
                Prompt.ask("\n[dim]Press Enter for next round[/dim]", default="")
            else:
                time.sleep(0.8)

    # ── Game over ──────────────────────────────────────────────────────────────
    winner = min(scores.items(), key=lambda x: x[1])
    loser  = max(scores.items(), key=lambda x: x[1])
    player_won = winner[0] == player_name

    if player_won:
        win_animation()
    console.print(Panel(
        f"[bold]Game Over![/bold]\n\n"
        f"🏆 [green bold]{winner[0]}[/green bold] wins — {winner[1]} pts\n"
        f"💀 [red]{loser[0]}[/red] busts — {loser[1]} pts\n\n"
        f"[dim]Seed: {seed}  (use 'Replay' to play this exact game again)[/dim]",
        title="[bold magenta]♥ Hearts ♥[/bold magenta]",
        box=box.HEAVY, expand=False
    ))

    show_round_history(game_log, players)

    # update stats
    stats["games_played"] += 1
    if player_won:
        stats["wins"] += 1
        stats["win_streak"] += 1
        stats["max_streak"] = max(stats["max_streak"], stats["win_streak"])
        if stats["best_game"] is None or scores[player_name] < stats["best_game"]:
            stats["best_game"] = scores[player_name]
        console.print("[green bold]You won![/green bold]")
    else:
        stats["win_streak"] = 0
        if stats["worst_game"] is None or scores[player_name] > stats["worst_game"]:
            stats["worst_game"] = scores[player_name]

    stats["moon_shots"] += moon_shots_this_game
    if omnibus:
        stats["omnibus_jd_grabs"] += jd_grabs

    n = stats["rounds_tracked"] + len(player_round_scores)
    if n > 0:
        old = stats["avg_score_per_round"] * stats["rounds_tracked"]
        stats["avg_score_per_round"] = (old + sum(player_round_scores)) / n
        stats["rounds_tracked"] = n

    for ai in AI_NAMES:
        key = f"vs_{ai.lower()}"
        stats[key]["games"] += 1
        if player_won:
            stats[key]["wins"] += 1
        else:
            stats[key]["losses"] = stats[key].get("losses", 0) + 1

    update_rival(stats)
    save_stats(stats)
    show_career_stats(stats)

# ── Main menu ──────────────────────────────────────────────────────────────────

def main():
    console.clear()
    stats = load_save()
    midgame = load_midgame()
    rival = stats.get("rival")

    header = "[bold magenta]♥  H E A R T S  ♥[/bold magenta]\n\n[dim]Avoid hearts. Fear Q♠. Dare to shoot the moon.[/dim]"
    if rival:
        header += f"\n[dim]Your rival: [red]{rival}[/red][/dim]"
    console.print(Panel(header, expand=False))

    if stats["games_played"] > 0:
        wr = 100 * stats["wins"] // max(stats["games_played"], 1)
        console.print(f"[dim]{stats['wins']}/{stats['games_played']} wins ({wr}%)  |  streak: {stats['win_streak']}  |  best: {stats.get('best_game','—')} pts[/dim]\n")

    menu_lines = (
        "[bold]Menu[/bold]\n"
        "  [cyan]1[/cyan] New game\n"
        "  [cyan]2[/cyan] Omnibus      [dim](J♦ = -10 pts)[/dim]\n"
        "  [cyan]3[/cyan] Blood Hearts [dim](first ♥ costs +2 extra)[/dim]\n"
        "  [cyan]4[/cyan] Fast mode    [dim](AI plays instantly)[/dim]\n"
        "  [cyan]5[/cyan] Custom limit [dim](change 100-pt threshold)[/dim]\n"
        "  [cyan]6[/cyan] Difficulty   [dim](easy / medium / hard)[/dim]\n"
        "  [cyan]7[/cyan] Colorblind   [dim](S/H/D/C instead of symbols)[/dim]\n"
    )
    if midgame:
        menu_lines += "  [cyan]8[/cyan] Resume saved game\n"
    if stats.get("last_seed"):
        menu_lines += "  [cyan]9[/cyan] Replay last game\n"
    menu_lines += (
        "  [cyan]s[/cyan] Stats\n"
        "  [cyan]r[/cyan] Rules\n"
        "  [cyan]q[/cyan] Quit\n"
    )
    valid = ["1","2","3","4","5","6","7","8","9","s","r","q"]

    choice = Prompt.ask(menu_lines + "\nChoice", default="1")

    if choice == "q":
        return

    if choice == "s":
        show_career_stats(stats)
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    if choice == "r":
        console.print(Panel(
            "[bold]How to Play Hearts[/bold]\n\n"
            "• 4 players, 13 cards each\n"
            "• Pass 3 cards each round (left → right → across → keep)\n"
            "• 2♣ leads first trick — no points on trick 1\n"
            "• Follow suit or play anything if you can't\n"
            "• Highest card of led suit wins the trick\n"
            "• ♥ = 1 pt  Q♠ = 13 pts  (avoid both!)\n"
            "• Hearts can't lead until broken\n"
            "• Q♠ Safe rule: if you lead Q♠ and win, no penalty\n"
            "• Shoot the Moon: take ALL ♥ + Q♠ → everyone else +26\n"
            "• Omnibus: J♦ = -10 for whoever wins it\n"
            "• Blood Hearts: first ♥ discarded costs the taker +2 extra\n"
            "• Colorblind mode: S/H/D/C instead of ♠♥♦♣\n"
            "• During play: ? hint  p played  s save&quit  q quit\n"
            "• Game ends when someone hits the score limit — lowest wins",
            box=box.ROUNDED, expand=False
        ))
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    if choice == "8" and midgame:
        play_game(midgame["players"][0], resume_state=midgame)
        Prompt.ask("\nPlay again?", default="n")
        main(); return

    if choice == "9" and stats.get("last_seed"):
        name = Prompt.ask("Your name", default="You")
        play_game(name, seed=stats["last_seed"])
        Prompt.ask("\nPlay again?", choices=["y","n"], default="y")
        main(); return

    omnibus    = False
    blood      = False
    fast       = False
    colorblind = False
    score_limit = 100
    difficulty  = "medium"

    if choice == "2":  omnibus = True
    if choice == "3":  blood   = True
    if choice == "4":  fast    = True
    if choice == "5":
        raw = Prompt.ask("Score limit", default="100")
        try:
            score_limit = max(26, int(raw))
        except ValueError:
            score_limit = 100
    if choice == "6":
        difficulty = Prompt.ask("Difficulty", choices=["easy","medium","hard"], default="medium")
    if choice == "7":
        colorblind = True

    # allow stacking options
    extras = Prompt.ask(
        "[dim]Add-ons? (o=omnibus  b=blood  f=fast  c=colorblind  or Enter to skip)[/dim]",
        default=""
    ).lower()
    if "o" in extras: omnibus    = True
    if "b" in extras: blood      = True
    if "f" in extras: fast       = True
    if "c" in extras: colorblind = True

    name = Prompt.ask("Your name", default="You")
    play_game(name, omnibus=omnibus, fast=fast, score_limit=score_limit,
              difficulty=difficulty, blood=blood, colorblind=colorblind)

    again = Prompt.ask("\nPlay again?", choices=["y","n"], default="y")
    if again == "y":
        main()

if __name__ == "__main__":
    main()
