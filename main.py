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

_colorblind  = False
_sort_by_rank = False

def suit_sym(s):
    if _colorblind:
        return SUITS_COLORBLIND[SUITS_NORMAL.index(s)]
    return s

def card_str(card, pad=False):
    rank, suit = card
    dsym = suit_sym(suit)
    is_high_heart = suit == "♥" and RANK_VAL[rank] >= RANK_VAL["10"]
    is_danger = card in DANGER_CARDS
    is_jd     = card == ("J","♦")
    if _colorblind:
        color = "bold underline white" if is_danger else \
                "bold white"           if is_high_heart else \
                "bold cyan"            if is_jd else "white"
    else:
        color = "bold yellow" if is_danger else \
                "bold red"    if is_high_heart else \
                "red"         if suit in ("♥","♦") else \
                "bold green"  if is_jd else "white"
    s = f"{rank}{dsym}"
    if pad:
        s = s.ljust(5 if _colorblind else 4)
    return f"[{color}]{s}[/{color}]"

def card_points(card, omnibus=False, qs_safe=False):
    rank, suit = card
    if suit == "♥":
        return 1
    if suit == "♠" and rank == "Q":
        return 0 if qs_safe else 13
    if omnibus and suit == "♦" and rank == "J":
        return -10
    return 0

def deck():
    return [(r, s) for s in SUITS_NORMAL for r in RANKS]

def sort_hand(hand):
    if _sort_by_rank:
        return sorted(hand, key=lambda c: (RANK_VAL[c[0]], SUITS_NORMAL.index(c[1])))
    return sorted(hand, key=lambda c: (SUITS_NORMAL.index(c[1]), RANK_VAL[c[0]]))

def hand_danger_rating(hand):
    """Rate the danger of a hand before passing."""
    danger_score = 0
    if ("Q","♠") in hand: danger_score += 4
    if ("A","♠") in hand: danger_score += 2
    if ("K","♠") in hand: danger_score += 1
    hearts = [c for c in hand if c[1] == "♥"]
    danger_score += len([h for h in hearts if RANK_VAL[h[0]] >= RANK_VAL["10"]]) * 2
    danger_score += len(hearts)
    if danger_score <= 3:
        return "[green]Safe[/green]"
    elif danger_score <= 7:
        return "[yellow]Risky[/yellow]"
    else:
        return "[red]Dangerous![/red]"

def suggest_pass(hand):
    """Suggest 3 cards to pass and why."""
    hand = sort_hand(hand)
    scored = []
    for c in hand:
        rank, suit = c
        score = 0
        if c == ("Q","♠"):  score += 100
        if c == ("A","♠"):  score += 60
        if c == ("K","♠"):  score += 50
        if suit == "♥" and RANK_VAL[rank] >= RANK_VAL["A"]:  score += 40
        if suit == "♥" and RANK_VAL[rank] >= RANK_VAL["K"]:  score += 30
        if suit == "♥" and RANK_VAL[rank] >= RANK_VAL["Q"]:  score += 20
        if suit == "♥" and RANK_VAL[rank] >= RANK_VAL["10"]: score += 10
        scored.append((score, c))
    scored.sort(reverse=True)
    suggested = [c for _, c in scored[:3]]
    reasons = []
    for c in suggested:
        rank, suit = c
        if c == ("Q","♠"):   reasons.append("Q♠ is lethal — pass it")
        elif c == ("A","♠"): reasons.append("A♠ can be forced to win Q♠ trick")
        elif c == ("K","♠"): reasons.append("K♠ is dangerous with Q♠ still out")
        elif suit == "♥" and RANK_VAL[rank] >= RANK_VAL["Q"]: reasons.append(f"{rank}♥ is a high heart — risky to hold")
        elif suit == "♥":    reasons.append(f"{rank}♥ reduces your heart count")
        else:                reasons.append(f"High card — less useful")
    return suggested, reasons

# ── Played cards tracker ───────────────────────────────────────────────────────

class PlayedTracker:
    def __init__(self):
        self.played = set()
        self.trick_history = []
        self.player_played = defaultdict(set)

    def add_trick(self, trick):
        self.trick_history.append(list(trick))
        for card, player in trick:
            self.played.add(card)
            self.player_played[player].add(card)

    def remaining(self):
        return [c for c in deck() if c not in self.played]

    def show_played(self, suit=None):
        played = sorted(self.played, key=lambda c: (SUITS_NORMAL.index(c[1]), RANK_VAL[c[0]]))
        return [c for c in played if c[1] == suit] if suit else played

    def last_tricks(self, n=2):
        return self.trick_history[-n:]

    def qs_still_out(self):
        return ("Q","♠") not in self.played

    def high_hearts_out(self):
        return [c for c in [("A","♥"),("K","♥"),("Q","♥"),("J","♥")] if c not in self.played]

# ── AI Taunts ─────────────────────────────────────────────────────────────────

AI_NAMES = ["Alex", "Jordan", "Riley"]
AI_PERSONALITIES = {"Alex": "safe", "Jordan": "aggressive", "Riley": "balanced"}

AI_TAUNTS = {
    "Jordan": {
        "going_for_moon": ["Feeling lucky? 😈", "Watch this...", "You can't stop me."],
        "dump_qs":        ["Here's a gift 🙃", "Surprise!", "Oops, dropped something."],
        "win_trick":      ["Mine.", "Thank you!", "I'll take that."],
    },
    "Alex": {
        "safe_play":  ["Playing it safe...", "No thank you.", "Not my problem."],
        "avoid_win":  ["Close one.", "Phew.", "Dodged that."],
        "dump":       ["All yours.", "Don't mind if I do.", "Careful with that."],
    },
    "Riley": {
        "grab_jd":   ["Oh, J♦! Don't mind if I do.", "-10! 🎉", "That's mine."],
        "balanced":  ["Hmm.", "Strategic.", "We'll see."],
        "win_trick": ["Calculated.", "Efficient.", "As expected."],
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
    if max(threats.values(), default=0) < 8:
        return
    console.print()
    for p, pts in threats.items():
        if pts >= 8:
            filled = int((pts / 26) * 20)
            bar    = "█" * filled + "░" * (20 - filled)
            color  = "red" if pts >= 20 else "yellow" if pts >= 14 else "dim yellow"
            console.print(f"  [{color}]⚠ {p}: [{bar}] {pts}/26 toward moon[/{color}]")

# ── Win animation ──────────────────────────────────────────────────────────────

def win_animation():
    for frame in [
        "  ♥   ♥   ♥   ♥   ♥",
        " ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥",
        "  ✨  YOU WON!  ✨",
        " ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥ ♥",
        "  ♥   ♥   ♥   ♥   ♥",
    ]:
        console.print(f"[bold magenta]{frame}[/bold magenta]")
        time.sleep(0.14)

# ── ASCII score chart ──────────────────────────────────────────────────────────

def show_score_chart(game_log, player_name):
    if not game_log:
        return
    rounds = list(range(1, len(game_log) + 1))
    player_scores = [row.get(player_name, 0) for row in game_log]
    max_pts = max(player_scores) if player_scores else 1
    if max_pts == 0:
        max_pts = 1
    console.print("\n[bold]Your points per round (bar chart):[/bold]")
    for i, pts in enumerate(player_scores, 1):
        bar_len = int((pts / max(max_pts, 1)) * 30)
        bar = "█" * bar_len
        color = "red" if pts >= 10 else "yellow" if pts >= 5 else "green"
        console.print(f"  R{i:2}  [{color}]{bar}[/{color}]  [dim]{pts}[/dim]")

# ── Achievements ───────────────────────────────────────────────────────────────

ACHIEVEMENTS = {
    "Moon Hunter":   ("Shot the moon 5+ times total",       lambda s: s["moon_shots"] >= 5),
    "Ironclad":      ("Won a game with ≤10 points",          lambda s: s.get("best_game") is not None and s["best_game"] <= 10),
    "Jordan Slayer": ("Beat Jordan 10+ times",               lambda s: s["vs_jordan"]["wins"] >= 10),
    "Veteran":       ("Played 20+ games",                    lambda s: s["games_played"] >= 20),
    "On a Roll":     ("Won 3+ games in a row",               lambda s: s["max_streak"] >= 3),
    "Omnibus Pro":   ("Grabbed J♦ 10+ times",               lambda s: s.get("omnibus_jd_grabs", 0) >= 10),
    "Perfect":       ("Won a game with 0 points",            lambda s: s.get("best_game") == 0),
    "Centurion":     ("Played 100+ rounds total",            lambda s: s["total_rounds"] >= 100),
}

def check_achievements(stats):
    earned = []
    for name, (desc, check) in ACHIEVEMENTS.items():
        try:
            if check(stats):
                earned.append((name, desc))
        except Exception:
            pass
    return earned

def show_achievements(stats):
    earned = check_achievements(stats)
    table = Table(title="Achievements", box=box.ROUNDED, header_style="bold yellow")
    table.add_column("Badge", min_width=16)
    table.add_column("Description", min_width=30)
    table.add_column("Status", width=10)
    for name, (desc, _) in ACHIEVEMENTS.items():
        unlocked = any(n == name for n, _ in earned)
        status = "[green]✓ Unlocked[/green]" if unlocked else "[dim]Locked[/dim]"
        row_style = "" if unlocked else "dim"
        table.add_row(f"[yellow]{name}[/yellow]" if unlocked else name, desc, status)
    console.print(table)
    return earned

def announce_new_achievements(old_stats, new_stats):
    old_earned = {n for n, _ in check_achievements(old_stats)}
    new_earned = {n for n, _ in check_achievements(new_stats)}
    newly = new_earned - old_earned
    for name in newly:
        desc = ACHIEVEMENTS[name][0]
        console.print(Panel(
            f"[bold yellow]🏅 Achievement Unlocked: {name}[/bold yellow]\n[dim]{desc}[/dim]",
            box=box.ROUNDED, expand=False
        ))

# ── Leaderboard ────────────────────────────────────────────────────────────────

def update_leaderboard(stats, player_name, score):
    lb = stats.get("leaderboard", [])
    lb.append({"name": player_name, "score": score})
    lb = sorted(lb, key=lambda x: x["score"])[:5]
    stats["leaderboard"] = lb

def show_leaderboard(stats):
    lb = stats.get("leaderboard", [])
    if not lb:
        console.print("[dim]No leaderboard entries yet.[/dim]")
        return
    table = Table(title="🏆 All-Time Leaderboard (Lowest Wins)", box=box.ROUNDED, header_style="bold gold1")
    table.add_column("Rank", width=6, justify="right")
    table.add_column("Player", min_width=12)
    table.add_column("Score", justify="right", width=8)
    medals = ["🥇","🥈","🥉","4.","5."]
    for i, entry in enumerate(lb):
        color = "gold1" if i == 0 else "white"
        table.add_row(medals[i], f"[{color}]{entry['name']}[/{color}]", str(entry["score"]))
    console.print(table)

# ── Save / Load ────────────────────────────────────────────────────────────────

def load_save():
    defaults = {
        "games_played": 0, "wins": 0, "moon_shots": 0, "total_rounds": 0,
        "best_game": None, "worst_game": None, "win_streak": 0, "max_streak": 0,
        "avg_score_per_round": 0.0, "rounds_tracked": 0,
        "vs_alex":   {"wins": 0, "games": 0, "losses": 0},
        "vs_jordan": {"wins": 0, "games": 0, "losses": 0},
        "vs_riley":  {"wins": 0, "games": 0, "losses": 0},
        "omnibus_jd_grabs": 0, "rival": None, "last_seed": None,
        "leaderboard": [],
    }
    if SAVE_FILE.exists():
        with open(SAVE_FILE) as f:
            saved = json.load(f)
        for k, v in defaults.items():
            if k not in saved:
                saved[k] = v
        # ensure nested dicts have losses key
        for ai in AI_NAMES:
            key = f"vs_{ai.lower()}"
            if "losses" not in saved.get(key, {}):
                saved[key]["losses"] = 0
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
    most_losses = 0
    rival = None
    for ai in AI_NAMES:
        losses = stats[f"vs_{ai.lower()}"].get("losses", 0)
        if losses > most_losses:
            most_losses = losses
            rival = ai
    stats["rival"] = rival
    return rival

# ── AI ─────────────────────────────────────────────────────────────────────────

def ai_mistake(difficulty):
    return random.random() < (0.25 if difficulty == "easy" else 0.07 if difficulty == "medium" else 0.0)

def ai_pass_cards(hand, name, omnibus=False, difficulty="medium"):
    if ai_mistake(difficulty):
        return random.sample(hand, 3)
    personality = AI_PERSONALITIES[name]
    hand = sort_hand(hand)
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
    followable  = [c for c in hand if c[1] == led_suit] if led_suit else []
    if followable:
        playable = followable
    elif is_first_trick:
        playable = [c for c in hand if card_points(c, omnibus) == 0] or hand
    else:
        playable = hand

    if is_first_trick:
        safe = [c for c in playable if card_points(c, omnibus) == 0]
        if safe:
            playable = safe

    if ai_mistake(difficulty):
        return random.choice(playable)

    other_moon = any(round_points.get(p, 0) >= 18 for p in scores if p != name)

    if personality == "aggressive":
        my_pts = round_points.get(name, 0)
        if my_pts >= 10 or not other_moon:
            if followable:
                ai_taunt(name, "win_trick", fast)
                return max(playable, key=lambda c: RANK_VAL[c[0]])
            qs = [c for c in playable if c == ("Q","♠")]
            if qs:
                ai_taunt(name, "dump_qs", fast)
                return qs[0]
            if my_pts >= 16:
                ai_taunt(name, "going_for_moon", fast)
            return sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]

    if personality == "safe" or (personality == "aggressive" and other_moon):
        if followable and trick:
            led_cards = [c for c, _ in trick if c[1] == led_suit]
            if led_cards:
                hi = max(RANK_VAL[c[0]] for c in led_cards)
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
            ai_taunt(name, "safe_play", fast)
            return sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]
        ai_taunt(name, "safe_play", fast)
        return min(playable, key=lambda c: RANK_VAL[c[0]])

    else:  # balanced
        if not followable:
            qs = [c for c in playable if c == ("Q","♠")]
            if qs:
                return qs[0]
            return sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]
        if omnibus and ("J","♦") in playable and led_suit == "♦":
            led_d = [c for c, _ in trick if c[1] == "♦"]
            if led_d and RANK_VAL["J"] > max(RANK_VAL[c[0]] for c in led_d):
                ai_taunt(name, "grab_jd", fast)
                return ("J","♦")
        ai_taunt(name, "balanced", fast)
        return min(playable, key=lambda c: RANK_VAL[c[0]])

# ── Hint system ────────────────────────────────────────────────────────────────

def hint_card(hand, trick, led_suit, playable, tracker, omnibus):
    if not playable:
        return None, "No legal plays."
    qs_out = tracker.qs_still_out()
    high_h = tracker.high_hearts_out()

    if not led_suit:
        non_point = [c for c in playable if card_points(c, omnibus) >= 0]
        best = min(non_point or playable, key=lambda c: RANK_VAL[c[0]])
        extra = " (Q♠ still in play — be careful)" if qs_out else ""
        return best, f"Lead your lowest safe card.{extra}"

    followable = [c for c in hand if c[1] == led_suit]
    if followable and trick:
        led_cards = [c for c, _ in trick if c[1] == led_suit]
        if led_cards:
            hi = max(RANK_VAL[c[0]] for c in led_cards)
            losing = [c for c in playable if RANK_VAL[c[0]] < hi]
            if losing:
                note = f" ({len(high_h)} high hearts still out)" if high_h else ""
                return max(losing, key=lambda c: RANK_VAL[c[0]]), f"Play highest that won't win.{note}"
        return min(playable, key=lambda c: RANK_VAL[c[0]]), "Can't avoid winning — play lowest."

    qs = [c for c in playable if c == ("Q","♠")]
    if qs:
        return qs[0], "Dump Q♠ now — get rid of it!"
    danger = [c for c in playable if card_points(c, omnibus) > 0]
    if danger:
        best = max(danger, key=lambda c: card_points(c, omnibus))
        note = " (Q♠ still out — watch spades)" if qs_out else ""
        return best, f"Dump your highest point card.{note}"
    return min(playable, key=lambda c: RANK_VAL[c[0]]), "Play lowest safe card."

# ── Shoot the moon ─────────────────────────────────────────────────────────────

def check_shoot_moon(round_points, jd_grabbed_by, omnibus):
    """Return the shooter if someone took all hearts + Q♠ (26 base pts)."""
    for player, pts in round_points.items():
        base = pts
        if omnibus and jd_grabbed_by == player:
            base += 10  # remove J♦ contribution to find base hearts+QS pts
        if base >= 26:
            return player
    return None

# ── Display ────────────────────────────────────────────────────────────────────

def show_hand(hand, selectable=False, playable=None):
    hand = sort_hand(hand)
    parts = []
    for i, card in enumerate(hand):
        num   = f"[dim]{i+1:2}.[/dim] " if selectable else ""
        valid = playable is None or card in playable
        dim_s = "" if valid else "[dim]"
        dim_e = "" if valid else "[/dim]"
        parts.append(f"{dim_s}{num}{card_str(card)}{dim_e}")
    console.print("  " + "  ".join(parts))

def show_scores(scores, round_num=None, score_limit=100, rival=None):
    title = f"Scoreboard — Round {round_num}" if round_num else "Final Scores"
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Player", min_width=12)
    table.add_column("Score",  justify="right", width=8)
    table.add_column("Left",   justify="right", width=8)
    table.add_column("Status", width=20)
    for player, score in sorted(scores.items(), key=lambda x: x[1]):
        left   = score_limit - score
        status = "[green]Leading[/green]" if score == min(scores.values()) else ""
        if score >= score_limit * 0.8:
            status = "[red]Danger zone![/red]"
        if player == rival:
            status += " [dim]👊Rival[/dim]"
        color = "green" if score == min(scores.values()) else "white"
        table.add_row(f"[{color}]{player}[/{color}]", str(score), f"[dim]{left}[/dim]", status)
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
    console.print("\n[dim]Cards played by suit:[/dim]")
    for suit in SUITS_NORMAL:
        played = tracker.show_played(suit)
        if played:
            rem = 13 - len(played)
            color = "red" if suit in ("♥","♦") else "white"
            s = "  ".join(card_str(c) for c in played)
            console.print(f"  [{color}]{suit_sym(suit)}[/{color}]: {s}  [dim]({rem} left)[/dim]")

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

# ── Passing phase ──────────────────────────────────────────────────────────────

PASS_DIRECTIONS = ["left", "right", "across", "none"]

def passing_phase(hands, round_num, players, omnibus=False, difficulty="medium"):
    direction = PASS_DIRECTIONS[(round_num - 1) % 4]
    n         = len(players)
    offsets   = {"left": 1, "right": n-1, "across": n//2, "none": 0}
    offset    = offsets[direction]

    if direction == "none":
        console.print(f"\n[dim]Round {round_num}: No passing.[/dim]")
        return hands

    console.print(f"\n[bold cyan]Passing — [yellow]{direction}[/yellow][/bold cyan]")

    passed = {}
    human  = players[0]
    h_hand = sort_hand(hands[human])

    # Passing preview
    sender   = players[(players.index(human) - offset) % n]
    n_danger = sum(1 for c in hands[sender] if c in DANGER_CARDS or card_points(c) > 3)
    preview  = "dangerous cards ⚠" if n_danger >= 2 else "mostly safe cards"
    console.print(f"[dim]{sender} is sending you {preview}.[/dim]")

    # Hand danger rating
    rating = hand_danger_rating(h_hand)
    console.print(f"[dim]Your hand danger: {rating}[/dim]")

    console.print(f"\nYour hand:")
    show_hand(h_hand, selectable=True)
    if omnibus:
        console.print("[dim]Tip: J♦ = -10 pts (Omnibus)[/dim]")

    # auto-pass suggestion
    suggested, reasons = suggest_pass(h_hand)
    suggested_idxs = [h_hand.index(c)+1 for c in suggested]
    console.print(f"[dim]Suggested: {' '.join(str(i) for i in suggested_idxs)} "
                  f"({', '.join(card_str(c) for c in suggested)}) — {reasons[0]}[/dim]")

    console.print(f"[yellow]Choose 3 cards to pass {direction} (or Enter to use suggestion):[/yellow]")

    while True:
        raw = Prompt.ask("Cards (e.g. 1 5 9)").strip()
        if raw == "":
            chosen = suggested
            break
        try:
            idxs = [int(x)-1 for x in raw.split()]
            if len(idxs) != 3 or len(set(idxs)) != 3:
                raise ValueError
            if any(i < 0 or i >= len(h_hand) for i in idxs):
                raise ValueError
            chosen = [h_hand[i] for i in idxs]
            break
        except (ValueError, IndexError):
            console.print("[red]Pick exactly 3 valid card numbers, or press Enter for suggestion.[/red]")

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

# ── Spectator mode ─────────────────────────────────────────────────────────────

def spectator_mode(omnibus=False, fast=False, score_limit=100, difficulty="medium"):
    """Watch 4 AIs play against each other."""
    global _colorblind
    ai_all = ["Nova", "Blaze", "Echo", "Frost"]
    scores  = {p: 0 for p in ai_all}
    round_num = 1
    game_log  = []

    console.print(Panel(
        f"[bold cyan]👁 Spectator Mode[/bold cyan]\n"
        f"[dim]Watching: {', '.join(ai_all)}\n"
        f"Press Ctrl+C to stop.[/dim]",
        expand=False
    ))

    # temporarily map all spectator AI to personalities cyclically
    spec_personalities = dict(zip(ai_all, ["safe","aggressive","balanced","safe"]))

    def spec_play(hand, trick, led_suit, hb, first, name, rpts, tracker):
        pers = spec_personalities[name]
        followable = [c for c in hand if c[1] == led_suit] if led_suit else []
        playable   = followable if followable else (
            [c for c in hand if card_points(c, omnibus) == 0] or hand if first else hand
        )
        if first:
            safe = [c for c in playable if card_points(c, omnibus) == 0]
            if safe:
                playable = safe
        if pers == "aggressive":
            if followable:
                return max(playable, key=lambda c: RANK_VAL[c[0]])
            qs = [c for c in playable if c == ("Q","♠")]
            return qs[0] if qs else sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]
        elif pers == "safe":
            if followable and trick:
                leds = [c for c, _ in trick if c[1] == led_suit]
                if leds:
                    hi = max(RANK_VAL[c[0]] for c in leds)
                    losing = [c for c in playable if RANK_VAL[c[0]] < hi]
                    if losing:
                        return max(losing, key=lambda c: RANK_VAL[c[0]])
            if not followable:
                qs = [c for c in playable if c == ("Q","♠")]
                if qs:
                    return qs[0]
                return sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]
            return min(playable, key=lambda c: RANK_VAL[c[0]])
        else:
            if not followable:
                qs = [c for c in playable if c == ("Q","♠")]
                return qs[0] if qs else sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)[0]
            return min(playable, key=lambda c: RANK_VAL[c[0]])

    try:
        while max(scores.values()) < score_limit:
            console.rule(f"[bold cyan]Round {round_num}[/bold cyan]")
            d = deck()
            random.shuffle(d)
            hands = {p: d[i*13:(i+1)*13] for i, p in enumerate(ai_all)}

            leader = next(p for p in ai_all if ("2","♣") in hands[p])
            hb = False
            rpts = defaultdict(int)
            tracker = PlayedTracker()
            first = True
            jd_by = None

            for trick_num in range(13):
                trick, led_suit = [], None
                order = ai_all[ai_all.index(leader):] + ai_all[:ai_all.index(leader)]
                for player in order:
                    chosen = spec_play(hands[player], trick, led_suit, hb, first, player, rpts, tracker)
                    if not led_suit:
                        led_suit = chosen[1]
                    if chosen[1] == "♥" or chosen == ("Q","♠"):
                        hb = True
                    trick.append((chosen, player))
                    hands[player].remove(chosen)
                    time.sleep(0.15 if fast else 0.5)

                led_c = [(c, p) for c, p in trick if c[1] == led_suit]
                _, winner = max(led_c, key=lambda x: RANK_VAL[x[0][0]])
                trick_pts = sum(card_points(c, omnibus) for c, _ in trick)
                if omnibus and ("J","♦") in [c for c, _ in trick]:
                    jd_by = winner
                rpts[winner] += trick_pts
                tracker.add_trick(trick)
                leader = winner
                first  = False

                parts = [f"[bold]{p}[/bold]:{card_str(c)}" for c, p in trick]
                console.print("  " + "  |  ".join(parts) + f"  → [bold]{winner}[/bold]")

            shooter = check_shoot_moon(rpts, jd_by, omnibus)
            if shooter:
                console.print(f"[yellow]🌕 {shooter} SHOT THE MOON![/yellow]")
                for p in ai_all:
                    if p != shooter:
                        scores[p] += 26
            else:
                for p in ai_all:
                    scores[p] += rpts[p]

            game_log.append({p: rpts.get(p, 0) for p in ai_all})
            show_scores(scores, round_num, score_limit)
            round_num += 1

            if not fast:
                time.sleep(1.5)

        winner = min(scores.items(), key=lambda x: x[1])
        console.print(f"\n[green bold]🏆 {winner[0]} wins the spectator match![/green bold]")
        show_round_history(game_log, ai_all)

    except KeyboardInterrupt:
        console.print("\n[yellow]Spectator mode stopped.[/yellow]")

# ── Tournament mode ────────────────────────────────────────────────────────────

def tournament_mode(player_name, omnibus=False, fast=False,
                    score_limit=100, difficulty="medium", blood=False, colorblind=False):
    """Best of 3 games — tracks series wins."""
    global _colorblind
    _colorblind = colorblind
    series = {player_name: 0}
    for ai in AI_NAMES:
        series[ai] = 0
    best_of = 3

    console.print(Panel(
        f"[bold magenta]♥ Tournament — Best of {best_of} ♥[/bold magenta]\n"
        f"[dim]{player_name} vs {', '.join(AI_NAMES)}\n"
        f"Win {(best_of//2)+1} game(s) to take the series.[/dim]",
        expand=False
    ))

    game_num = 1
    while max(series.values()) < (best_of // 2) + 1 and game_num <= best_of:
        console.rule(f"[bold]Tournament Game {game_num}[/bold]")
        play_game(player_name, omnibus=omnibus, fast=fast, score_limit=score_limit,
                  difficulty=difficulty, blood=blood, colorblind=colorblind,
                  tournament_series=series)
        game_num += 1

    winner = max(series.items(), key=lambda x: x[1])
    console.print(Panel(
        f"[bold]Series over![/bold]\n\n"
        f"🏆 [green]{winner[0]}[/green] wins the tournament {winner[1]}-{min(series.values())}",
        title="[bold magenta]Tournament Results[/bold magenta]",
        box=box.HEAVY, expand=False
    ))

    tbl = Table(box=box.SIMPLE)
    tbl.add_column("Player"); tbl.add_column("Series Wins", justify="right")
    for p, w in sorted(series.items(), key=lambda x: -x[1]):
        tbl.add_row(p, str(w))
    console.print(tbl)

# ── Round ──────────────────────────────────────────────────────────────────────

def play_round(hands, players, round_num, scores, omnibus=False, fast=False,
               score_limit=100, difficulty="medium", blood=False, rival=None):
    leader = next(p for p in players if ("2","♣") in hands[p])
    hearts_broken   = False
    round_points    = defaultdict(int)
    is_first_trick  = True
    tracker         = PlayedTracker()
    jd_grabbed_by   = None
    first_heart_done = False

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

                sort_mode = "[dim]rank-sort[/dim]" if _sort_by_rank else "[dim]suit-sort[/dim]"
                console.print(f"\n[bold]Your hand ({len(hand)} cards):[/bold]  {sort_mode}")
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
                        hand_sorted, trick, led_suit, playable, tracker, omnibus
                    )
                    valid_str = ", ".join(str(i) for i in sorted(valid_idxs))
                    console.print(
                        f"[yellow]Play ({valid_str})  "
                        f"[dim]?=hint  p=played  t=toggle-sort  s=save  q=quit[/dim]:[/yellow]"
                    )

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

                        if raw == "t":
                            global _sort_by_rank
                            _sort_by_rank = not _sort_by_rank
                            hand_sorted = sort_hand(hand)
                            playable_new = [c for c in hand_sorted if c in playable]
                            show_hand(hand_sorted, selectable=True, playable=playable_new)
                            valid_idxs = {hand_sorted.index(c)+1 for c in playable_new}
                            playable = playable_new
                            continue

                        if raw == "s":
                            state = {
                                "hands": {p: list(hands[p]) for p in players},
                                "scores": dict(scores),
                                "round_num": round_num, "players": players,
                                "omnibus": omnibus, "fast": fast,
                                "score_limit": score_limit,
                                "difficulty": difficulty, "blood": blood,
                            }
                            save_midgame(state)
                            console.print("[green]Game saved! Resume from the main menu.[/green]")
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
                            console.print("[red]Enter a number, ?, p, t, s, or q.[/red]")

            else:  # AI
                time.sleep(0.3 if fast else 0.6)
                chosen = ai_play_card(
                    hand, trick, led_suit, hearts_broken, is_first_trick,
                    player, scores, tracker, round_points, omnibus, fast, difficulty, blood
                )

            # Blood Hearts: first ♥ costs taker +2 extra
            if blood and chosen[1] == "♥" and not first_heart_done:
                first_heart_done = True
                hearts_broken    = True
                round_points[player] += 2
                console.print(f"  [red bold]Blood Hearts! +2 penalty on first ♥![/red bold]")

            if not led_suit:
                led_suit = chosen[1]
            if chosen[1] == "♥" or chosen == ("Q","♠"):
                hearts_broken = True

            trick.append((chosen, player))
            hands[player].remove(chosen)

            if player != players[0]:
                console.print(f"  [dim]{player}[/dim] plays {card_str(chosen)}")

        # who won?
        led_cards = [(c, p) for c, p in trick if c[1] == led_suit]
        winner_card, winner = max(led_cards, key=lambda x: RANK_VAL[x[0][0]])
        qs_led_won = (winner_card == ("Q","♠") and trick[0][0] == ("Q","♠") and trick[0][1] == winner)
        trick_pts  = sum(card_points(c, omnibus, qs_safe=qs_led_won) for c, _ in trick)

        if omnibus and ("J","♦") in [c for c, _ in trick]:
            jd_grabbed_by = winner

        round_points[winner] += trick_pts
        tracker.add_trick(trick)
        leader         = winner
        is_first_trick = False

        color   = "red" if trick_pts > 0 else ("green" if trick_pts < 0 else "dim")
        pts_str = f"[{color}]{'+' if trick_pts > 0 else ''}{trick_pts}pts[/{color}]" if trick_pts != 0 else "[dim]0pts[/dim]"
        console.print(f"  → [bold]{winner}[/bold] wins {pts_str}")
        if qs_led_won:
            console.print("  [green dim](Q♠ Safe — led and won, no penalty)[/green dim]")

    # shoot the moon
    shooter = check_shoot_moon(round_points, jd_grabbed_by, omnibus)
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
    table.add_column("Total",      justify="right", width=8)
    for p in players:
        pts   = round_points.get(p, 0)
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
    table.add_row("Games played",              str(stats["games_played"]))
    table.add_row("Games won",                 str(stats["wins"]))
    table.add_row("Win rate",                  f"{wr:.1f}%")
    table.add_row("Current streak",            str(stats["win_streak"]))
    table.add_row("Best streak",               str(stats["max_streak"]))
    table.add_row("Moon shots",                str(stats["moon_shots"]))
    table.add_row("Avg pts/round",             f"{stats['avg_score_per_round']:.1f}")
    if stats["best_game"]  is not None: table.add_row("Best game (lowest score)",  str(stats["best_game"]))
    if stats["worst_game"] is not None: table.add_row("Worst game (highest score)", str(stats["worst_game"]))
    table.add_row("Total rounds",              str(stats["total_rounds"]))
    if stats.get("omnibus_jd_grabs"):   table.add_row("J♦ grabs (Omnibus)",        str(stats["omnibus_jd_grabs"]))
    if stats.get("rival"):              table.add_row("Your Rival",                 f"[red]{stats['rival']}[/red]")
    console.print(table)

    h2h = Table(title="Head-to-Head", box=box.SIMPLE, header_style="bold")
    h2h.add_column("Opponent", min_width=10)
    h2h.add_column("W/L", justify="right")
    h2h.add_column("Win %", justify="right")
    for ai in AI_NAMES:
        key = f"vs_{ai.lower()}"
        d   = stats[key]
        if d["games"] > 0:
            rate  = 100 * d["wins"] / d["games"]
            color = "green" if rate >= 50 else "red"
            rival_tag = " 👊" if ai == stats.get("rival") else ""
            h2h.add_row(
                f"{ai}{rival_tag}",
                f"[{color}]{d['wins']}W / {d.get('losses',0)}L[/{color}]",
                f"[{color}]{rate:.0f}%[/{color}]"
            )
    console.print(h2h)

# ── Main game loop ─────────────────────────────────────────────────────────────

def play_game(player_name, omnibus=False, fast=False, score_limit=100,
              difficulty="medium", blood=False, colorblind=False,
              resume_state=None, seed=None, tournament_series=None):
    global _colorblind, _sort_by_rank
    _colorblind   = colorblind
    _sort_by_rank = False

    if resume_state:
        players     = resume_state["players"]
        scores      = {k: v for k, v in resume_state["scores"].items()}
        round_num   = resume_state["round_num"]
        omnibus     = resume_state.get("omnibus",     omnibus)
        fast        = resume_state.get("fast",        fast)
        score_limit = resume_state.get("score_limit", score_limit)
        difficulty  = resume_state.get("difficulty",  difficulty)
        blood       = resume_state.get("blood",       blood)
        console.print("[green]Resuming saved game![/green]")
        clear_midgame()
    else:
        players   = [player_name] + AI_NAMES
        scores    = {p: 0 for p in players}
        round_num = 1

    old_stats = load_save()
    stats     = load_save()
    rival     = stats.get("rival")
    moon_shots_this_game = 0
    player_round_scores  = []
    jd_grabs  = 0
    game_log  = []

    if seed is None:
        seed = random.randint(0, 2**31)
    rng = random.Random(seed)
    stats["last_seed"] = seed

    tags = []
    if omnibus:    tags.append("[yellow]Omnibus[/yellow]")
    if blood:      tags.append("[red]Blood Hearts[/red]")
    if fast:       tags.append("[dim]Fast[/dim]")
    if colorblind: tags.append("[dim]Colorblind[/dim]")
    tag_str = "  ".join(tags)

    console.print(Panel(
        f"[bold magenta]♥ Hearts ♥[/bold magenta]  {tag_str}\n"
        f"[dim]{player_name} vs {', '.join(AI_NAMES)}  |  Difficulty: {difficulty}\n"
        f"Points: ♥=1  Q♠=13{'  J♦=-10' if omnibus else ''}{'  First♥=+2' if blood else ''}\n"
        f"Lose at {score_limit} pts  |  ?=hint  p=played  t=sort  s=save  q=quit[/dim]",
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
        f"[dim]Seed: {seed}  (Replay from main menu)[/dim]",
        title="[bold magenta]♥ Hearts ♥[/bold magenta]",
        box=box.HEAVY, expand=False
    ))

    show_round_history(game_log, players)
    show_score_chart(game_log, player_name)

    # update stats
    stats["games_played"] += 1
    if player_won:
        stats["wins"] += 1
        stats["win_streak"] += 1
        stats["max_streak"] = max(stats["max_streak"], stats["win_streak"])
        if stats["best_game"] is None or scores[player_name] < stats["best_game"]:
            stats["best_game"] = scores[player_name]
        update_leaderboard(stats, player_name, scores[player_name])
        console.print("[green bold]You won![/green bold]")
        if tournament_series:
            tournament_series[player_name] = tournament_series.get(player_name, 0) + 1
    else:
        stats["win_streak"] = 0
        if stats["worst_game"] is None or scores[player_name] > stats["worst_game"]:
            stats["worst_game"] = scores[player_name]
        # update tournament series for winning AI
        if tournament_series:
            w = winner[0]
            tournament_series[w] = tournament_series.get(w, 0) + 1

    stats["moon_shots"] += moon_shots_this_game
    if omnibus:
        stats["omnibus_jd_grabs"] += jd_grabs

    n = stats["rounds_tracked"] + len(player_round_scores)
    if n > 0:
        old_avg = stats["avg_score_per_round"] * stats["rounds_tracked"]
        stats["avg_score_per_round"] = (old_avg + sum(player_round_scores)) / n
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
    announce_new_achievements(old_stats, stats)
    show_career_stats(stats)

# ── Main menu ──────────────────────────────────────────────────────────────────

def main():
    global _colorblind
    console.clear()
    stats   = load_save()
    midgame = load_midgame()
    rival   = stats.get("rival")

    header = "[bold magenta]♥  H E A R T S  ♥[/bold magenta]\n\n[dim]Avoid hearts. Fear Q♠. Dare to shoot the moon.[/dim]"
    if rival:
        header += f"\n[dim]Your rival: [red]{rival}[/red] — beat them![/dim]"
    console.print(Panel(header, expand=False))

    if stats["games_played"] > 0:
        wr = 100 * stats["wins"] // max(stats["games_played"], 1)
        console.print(
            f"[dim]{stats['wins']}/{stats['games_played']} wins ({wr}%)  "
            f"|  streak: {stats['win_streak']}  "
            f"|  best: {stats.get('best_game', '—')} pts[/dim]\n"
        )

    menu = (
        "[bold]Menu[/bold]\n"
        "  [cyan]1[/cyan] New game\n"
        "  [cyan]2[/cyan] Omnibus      [dim](J♦ = -10 pts)[/dim]\n"
        "  [cyan]3[/cyan] Blood Hearts [dim](first ♥ costs +2)[/dim]\n"
        "  [cyan]4[/cyan] Fast mode    [dim](AI instant)[/dim]\n"
        "  [cyan]5[/cyan] Custom limit [dim](change 100-pt threshold)[/dim]\n"
        "  [cyan]6[/cyan] Difficulty   [dim](easy/medium/hard)[/dim]\n"
        "  [cyan]7[/cyan] Colorblind   [dim](S/H/D/C symbols)[/dim]\n"
        "  [cyan]t[/cyan] Tournament   [dim](best of 3)[/dim]\n"
        "  [cyan]w[/cyan] Spectator    [dim](watch 4 AIs play)[/dim]\n"
    )
    if midgame:
        menu += "  [cyan]r[/cyan] Resume saved game\n"
    if stats.get("last_seed"):
        menu += "  [cyan]x[/cyan] Replay last game\n"
    menu += (
        "  [cyan]s[/cyan] Stats\n"
        "  [cyan]a[/cyan] Achievements\n"
        "  [cyan]l[/cyan] Leaderboard\n"
        "  [cyan]h[/cyan] Rules\n"
        "  [cyan]q[/cyan] Quit\n"
    )

    choice = Prompt.ask(menu + "\nChoice", default="1").strip().lower()

    if choice == "q":
        return

    if choice == "s":
        show_career_stats(stats)
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    if choice == "a":
        show_achievements(stats)
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    if choice == "l":
        show_leaderboard(stats)
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    if choice == "h":
        console.print(Panel(
            "[bold]How to Play Hearts[/bold]\n\n"
            "• 4 players, 13 cards each\n"
            "• Pass 3 cards (left → right → across → keep), or press Enter for suggestion\n"
            "• 2♣ leads first trick — no points on trick 1\n"
            "• Follow suit or play anything if you can't\n"
            "• Highest card of led suit wins the trick\n"
            "• ♥ = 1 pt  Q♠ = 13 pts — avoid both!\n"
            "• Hearts can't lead until broken\n"
            "• Q♠ Safe: lead Q♠ and win = zero penalty\n"
            "• Shoot the Moon: take ALL ♥ + Q♠ → everyone else +26\n"
            "• Omnibus: J♦ = -10 for whoever wins it\n"
            "• Blood Hearts: first ♥ costs taker +2 extra\n"
            "• Colorblind: S/H/D/C instead of ♠♥♦♣\n"
            "• During play: ? hint  p played  t toggle-sort  s save  q quit\n"
            "• Game ends when someone hits the score limit — lowest wins",
            box=box.ROUNDED, expand=False
        ))
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    if choice == "r" and midgame:
        play_game(midgame["players"][0], resume_state=midgame)
        Prompt.ask("\nPlay again?", choices=["y","n"], default="n")
        main(); return

    if choice == "x" and stats.get("last_seed"):
        name = Prompt.ask("Your name", default="You")
        play_game(name, seed=stats["last_seed"])
        Prompt.ask("\nPlay again?", choices=["y","n"], default="y")
        main(); return

    if choice == "w":
        spectator_mode()
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return

    omnibus     = False
    blood       = False
    fast        = False
    colorblind  = False
    score_limit = 100
    difficulty  = "medium"
    tournament  = False

    if choice == "2":  omnibus    = True
    if choice == "3":  blood      = True
    if choice == "4":  fast       = True
    if choice == "5":
        raw = Prompt.ask("Score limit", default="100")
        try:    score_limit = max(26, int(raw))
        except: score_limit = 100
    if choice == "6":
        difficulty = Prompt.ask("Difficulty", choices=["easy","medium","hard"], default="medium")
    if choice == "7":  colorblind = True
    if choice == "t":  tournament = True

    # stack add-ons
    extras = Prompt.ask(
        "[dim]Add-ons? o=omnibus  b=blood  f=fast  c=colorblind  Enter=skip[/dim]",
        default=""
    ).lower()
    if "o" in extras: omnibus    = True
    if "b" in extras: blood      = True
    if "f" in extras: fast       = True
    if "c" in extras: colorblind = True

    name = Prompt.ask("Your name", default="You")

    if tournament:
        tournament_mode(name, omnibus=omnibus, fast=fast, score_limit=score_limit,
                        difficulty=difficulty, blood=blood, colorblind=colorblind)
    else:
        play_game(name, omnibus=omnibus, fast=fast, score_limit=score_limit,
                  difficulty=difficulty, blood=blood, colorblind=colorblind)

    again = Prompt.ask("\nPlay again?", choices=["y","n"], default="y")
    if again == "y":
        main()

if __name__ == "__main__":
    main()
