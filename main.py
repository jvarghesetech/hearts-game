"""
Hearts Card Game — terminal-based, fully offline.
4 players: you vs 3 AI with different personalities.
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
SAVE_FILE = Path.home() / ".hearts_save.json"

# ── Cards ──────────────────────────────────────────────────────────────────────

SUITS    = ["♠", "♥", "♦", "♣"]
RANKS    = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_VAL = {r: i for i, r in enumerate(RANKS)}

DANGER_CARDS = {("Q","♠"), ("A","♠"), ("K","♠")}

def card_str(card, pad=False, highlight=False):
    rank, suit = card
    color = "red" if suit in ("♥","♦") else "white"
    if card in DANGER_CARDS or (suit == "♥" and RANK_VAL[rank] >= RANK_VAL["10"]):
        color = "bold red" if suit == "♥" else "bold yellow"
    if card == ("J","♦"):
        color = "bold green"
    s = f"{rank}{suit}"
    if pad:
        s = s.ljust(4)
    tag = f"[{color}]{s}[/{color}]"
    return f"[reverse]{tag}[/reverse]" if highlight else tag

def card_points(card, omnibus=False):
    rank, suit = card
    if suit == "♥":
        return 1
    if suit == "♠" and rank == "Q":
        return 13
    if omnibus and suit == "♦" and rank == "J":
        return -10
    return 0

def deck():
    return [(r, s) for s in SUITS for r in RANKS]

def sort_hand(hand):
    return sorted(hand, key=lambda c: (SUITS.index(c[1]), RANK_VAL[c[0]]))

def hand_points(hand, omnibus=False):
    return sum(card_points(c, omnibus) for c in hand)

# ── Played cards tracker ───────────────────────────────────────────────────────

class PlayedTracker:
    def __init__(self):
        self.played = set()
        self.trick_history = []  # list of [(card, player), ...]

    def add(self, card, player):
        self.played.add(card)

    def add_trick(self, trick):
        self.trick_history.append(list(trick))
        for card, player in trick:
            self.played.add(card)

    def remaining(self):
        return set(deck()) - self.played

    def show_played(self, suit=None):
        played = sorted(self.played,
                        key=lambda c: (SUITS.index(c[1]), RANK_VAL[c[0]]))
        if suit:
            played = [c for c in played if c[1] == suit]
        return played

    def last_tricks(self, n=3):
        return self.trick_history[-n:]

# ── AI Personalities ───────────────────────────────────────────────────────────

AI_NAMES = ["Alex", "Jordan", "Riley"]
AI_PERSONALITIES = {
    "Alex":   "safe",
    "Jordan": "aggressive",
    "Riley":  "balanced",
}

def ai_pass_cards(hand, name, omnibus=False):
    personality = AI_PERSONALITIES[name]
    hand = sort_hand(hand)

    if personality == "aggressive":
        risky = [c for c in hand if c[1] == "♥" and RANK_VAL[c[0]] >= RANK_VAL["J"]]
        risky += [c for c in hand if c == ("Q","♠")]
        safe  = [c for c in hand if c not in risky]
        # aggressive keeps J♦ in omnibus
        if omnibus:
            safe = [c for c in safe if c != ("J","♦")]
        to_pass = (safe + risky)[:3]
    elif personality == "safe":
        danger = [c for c in hand if c in {("Q","♠"),("A","♠"),("K","♠")}]
        danger += [c for c in hand if c[1] == "♥" and RANK_VAL[c[0]] >= RANK_VAL["10"]]
        rest   = [c for c in hand if c not in danger]
        to_pass = (danger + rest)[:3]
    else:
        high = sorted(hand, key=lambda c: RANK_VAL[c[0]], reverse=True)
        if omnibus:
            high = [c for c in high if c != ("J","♦")]
        to_pass = high[:3]

    return to_pass[:3]

def ai_moon_progress(round_points, name):
    """How many of the 26 points has this player taken?"""
    return round_points.get(name, 0)

def ai_play_card(hand, trick, led_suit, hearts_broken, is_first_trick,
                 name, scores, tracker, round_points, omnibus=False, fast=False):
    personality = AI_PERSONALITIES[name]

    followable = [c for c in hand if c[1] == led_suit] if led_suit else []
    if followable:
        playable = followable
    else:
        if is_first_trick:
            playable = [c for c in hand if card_points(c, omnibus) == 0] or hand
        else:
            playable = hand

    if is_first_trick:
        safe = [c for c in playable if card_points(c, omnibus) >= 0 and card_points(c, omnibus) == 0]
        if safe:
            playable = safe

    # block moon shot if another player is close
    other_moon = any(
        ai_moon_progress(round_points, p) >= 18
        for p in round_points if p != name
    )

    if personality == "aggressive":
        my_pts = ai_moon_progress(round_points, name)
        if my_pts >= 10 or not other_moon:
            # going for moon: win tricks
            if followable:
                return max(playable, key=lambda c: RANK_VAL[c[0]])
            else:
                dump = [c for c in playable if c == ("Q","♠")]
                dump = dump or sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)
                return dump[0]
        # fall through to safe play if blocked

    if personality == "safe" or (personality == "aggressive" and other_moon):
        if followable and trick:
            led_in_trick = [c for c, _ in trick if c[1] == led_suit]
            if led_in_trick:
                current_high = max(RANK_VAL[c[0]] for c in led_in_trick)
                losing = [c for c in playable if RANK_VAL[c[0]] < current_high]
                if losing:
                    return max(losing, key=lambda c: RANK_VAL[c[0]])
        if not followable:
            dump = [c for c in playable if c == ("Q","♠")]
            if dump:
                return dump[0]
            # in omnibus, avoid J♦ when dumping unless it's all we have
            if omnibus:
                no_jd = [c for c in playable if c != ("J","♦") and card_points(c, omnibus) > 0]
                if no_jd:
                    return max(no_jd, key=lambda c: card_points(c, omnibus))
            dump = sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)
            return dump[0]
        return min(playable, key=lambda c: RANK_VAL[c[0]])

    else:  # balanced
        if not followable:
            dump = [c for c in playable if c == ("Q","♠")]
            dump = dump or sorted(playable, key=lambda c: card_points(c, omnibus), reverse=True)
            return dump[0]
        # try to grab J♦ in omnibus
        if omnibus and ("J","♦") in playable:
            jd = ("J","♦")
            if led_suit == "♦":
                led_in_trick = [c for c, _ in trick if c[1] == "♦"]
                if led_in_trick:
                    high = max(RANK_VAL[c[0]] for c in led_in_trick)
                    if RANK_VAL[jd[0]] > high:
                        return jd
        return min(playable, key=lambda c: RANK_VAL[c[0]])

# ── Hint system ────────────────────────────────────────────────────────────────

def hint_card(hand, trick, led_suit, hearts_broken, is_first_trick,
              playable, scores, tracker, round_points, omnibus):
    """Suggest the safest card to play."""
    if not playable:
        return None, "No legal plays."

    # if must lead
    if not led_suit:
        non_point = [c for c in playable if card_points(c, omnibus) >= 0]
        if non_point:
            best = min(non_point, key=lambda c: RANK_VAL[c[0]])
            return best, "Lead your lowest safe card."
        return playable[0], "All cards have points — lead lowest."

    followable = [c for c in hand if c[1] == led_suit]
    if followable and trick:
        led_in_trick = [c for c, _ in trick if c[1] == led_suit]
        if led_in_trick:
            high = max(RANK_VAL[c[0]] for c in led_in_trick)
            losing = [c for c in playable if RANK_VAL[c[0]] < current_high
                      ] if (current_high := high) else []
            if losing:
                return max(losing, key=lambda c: RANK_VAL[c[0]]), "Play highest card that won't win this trick."
        # no losing option — play lowest
        return min(playable, key=lambda c: RANK_VAL[c[0]]), "Can't avoid winning — play lowest."

    # can't follow — dump dangerous cards
    qs = [c for c in playable if c == ("Q","♠")]
    if qs:
        return qs[0], "Dump the Queen of Spades!"
    danger = [c for c in playable if card_points(c, omnibus) > 0]
    if danger:
        return max(danger, key=lambda c: card_points(c, omnibus)), "Dump your highest point card."

    return min(playable, key=lambda c: RANK_VAL[c[0]]), "Play lowest safe card."

# ── Shooting the moon ──────────────────────────────────────────────────────────

def check_shoot_moon(round_points, omnibus=False):
    for player, pts in round_points.items():
        base = sum(1 for p, pts2 in round_points.items()
                   if p != player for _ in range(pts2 if not omnibus else 0))
        if pts == 26:
            return player
    return None

def check_shoot_moon_omnibus(round_points):
    """In omnibus, shooting the moon means all 13 hearts + Q♠ (J♦ bonus separate)."""
    for player, pts in round_points.items():
        heart_qs = pts + sum(
            10 for p, p2 in round_points.items() if p == player
        )
        if pts >= 26:
            return player
    return None

# ── Display helpers ────────────────────────────────────────────────────────────

def show_hand(hand, selectable=False, playable=None, undo_card=None):
    hand = sort_hand(hand)
    parts = []
    for i, card in enumerate(hand):
        num = f"[dim]{i+1:2}.[/dim] " if selectable else ""
        is_playable = playable is None or card in playable
        is_undo = card == undo_card
        dim = "" if is_playable else "[dim]"
        end_dim = "" if is_playable else "[/dim]"
        star = " [yellow]*[/yellow]" if is_undo else ""
        parts.append(f"{dim}{num}{card_str(card, pad=False)}{end_dim}{star}")
    console.print("  " + "  ".join(parts))

def show_scores(scores, round_num=None, score_limit=100):
    title = f"Scoreboard — Round {round_num}" if round_num else "Final Scores"
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Player", min_width=10)
    table.add_column("Score", justify="right", width=8)
    table.add_column("To limit", justify="right", width=10)
    table.add_column("Status", width=16)

    sorted_players = sorted(scores.items(), key=lambda x: x[1])
    leader = sorted_players[0][0]

    for player, score in sorted_players:
        to_limit = score_limit - score
        status = "[green]Leading[/green]" if player == leader else ""
        if score >= score_limit * 0.8:
            status = "[red]Danger zone[/red]"
        color = "green" if player == leader else "white"
        table.add_row(
            f"[{color}]{player}[/{color}]",
            str(score),
            f"[dim]{to_limit}[/dim]",
            status
        )
    console.print(table)

def show_trick_history(tracker, n=3):
    history = tracker.last_tricks(n)
    if not history:
        return
    console.print(f"\n[dim]Last {len(history)} trick(s):[/dim]")
    for i, trick in enumerate(history, 1):
        parts = [f"[bold]{p}[/bold]: {card_str(c, pad=False)}" for c, p in trick]
        console.print(f"  [dim]{i}.[/dim] " + "  |  ".join(parts))

def show_played_cards(tracker):
    console.print("\n[dim]Cards played so far:[/dim]")
    for suit in SUITS:
        played_in_suit = tracker.show_played(suit)
        if played_in_suit:
            color = "red" if suit in ("♥","♦") else "white"
            cards_str = "  ".join(card_str(c, pad=False) for c in played_in_suit)
            console.print(f"  [{color}]{suit}[/{color}]: {cards_str}")

# ── Save / Load ────────────────────────────────────────────────────────────────

def load_save():
    defaults = {
        "games_played": 0, "wins": 0, "moon_shots": 0, "total_rounds": 0,
        "best_game": None, "worst_game": None, "win_streak": 0, "max_streak": 0,
        "avg_score_per_round": 0.0, "rounds_tracked": 0,
        "vs_alex": {"wins": 0, "games": 0},
        "vs_jordan": {"wins": 0, "games": 0},
        "vs_riley": {"wins": 0, "games": 0},
        "omnibus_jd_grabs": 0,
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

# ── Passing phase ──────────────────────────────────────────────────────────────

PASS_DIRECTIONS = ["left", "right", "across", "none"]

def passing_phase(hands, round_num, players, omnibus=False):
    direction = PASS_DIRECTIONS[(round_num - 1) % 4]
    n = len(players)
    offsets = {"left": 1, "right": n - 1, "across": n // 2, "none": 0}
    offset = offsets[direction]

    if direction == "none":
        console.print(f"\n[dim]Round {round_num}: No passing this round.[/dim]")
        return hands, {}

    console.print(f"\n[bold cyan]Passing — direction: [yellow]{direction}[/yellow][/bold cyan]")

    passed = {}
    human = players[0]
    h_hand = sort_hand(hands[human])

    console.print(f"\nYour hand:")
    show_hand(h_hand, selectable=True)
    if omnibus:
        console.print("[dim]Tip: J♦ = -10 points (Omnibus rule)[/dim]")
    console.print(f"[yellow]Choose 3 cards to pass {direction} (e.g. 1 5 9):[/yellow]")

    while True:
        raw = Prompt.ask("Cards").strip().split()
        try:
            idxs = [int(x) - 1 for x in raw]
            if len(idxs) != 3 or len(set(idxs)) != 3:
                raise ValueError
            if any(i < 0 or i >= len(h_hand) for i in idxs):
                raise ValueError
            chosen = [h_hand[i] for i in idxs]
            break
        except (ValueError, IndexError):
            console.print("[red]Pick exactly 3 valid numbers.[/red]")

    passed[human] = chosen
    for name in players[1:]:
        passed[name] = ai_pass_cards(hands[name], name, omnibus)

    new_hands = {p: list(hands[p]) for p in players}
    for i, player in enumerate(players):
        recipient = players[(i + offset) % n]
        for card in passed[player]:
            new_hands[player].remove(card)
            new_hands[recipient].append(card)

    console.print(f"[green]You passed:[/green] " + "  ".join(card_str(c) for c in chosen))
    received = passed[players[(players.index(human) - offset) % n]]
    console.print(f"[green]You received:[/green] " + "  ".join(card_str(c) for c in received))

    return new_hands, {p: passed[players[(players.index(p) - offset) % n]] for p in players}

# ── Round ──────────────────────────────────────────────────────────────────────

def play_round(hands, players, round_num, scores, omnibus=False, fast=False,
               score_limit=100, undo_limit=1):
    leader = next(p for p in players if ("2","♣") in hands[p])
    hearts_broken = False
    round_points = defaultdict(int)
    is_first_trick = True
    tracker = PlayedTracker()
    undo_used = 0
    last_play = None  # (player, card) for undo
    jd_grabbed_by = None

    for trick_num in range(13):
        trick = []
        led_suit = None
        trick_snapshot = None

        console.rule(f"[dim]Trick {trick_num+1}/13[/dim]")

        # show last few tricks
        if tracker.trick_history:
            show_trick_history(tracker, n=2)

        order = players[players.index(leader):] + players[:players.index(leader)]

        for player in order:
            hand = hands[player]

            if player == players[0]:  # human
                hand_sorted = sort_hand(hand)

                # determine valid plays
                followable = [c for c in hand_sorted if c[1] == led_suit] if led_suit else []
                if followable:
                    playable = followable
                elif is_first_trick:
                    playable = [c for c in hand_sorted if card_points(c, omnibus) == 0] or hand_sorted
                else:
                    if not hearts_broken:
                        non_hearts = [c for c in hand_sorted if c[1] != "♥"]
                        playable = non_hearts if non_hearts else hand_sorted
                    else:
                        playable = hand_sorted

                console.print(f"\n[bold]Your hand ({len(hand)} cards):[/bold]")
                show_hand(hand_sorted, selectable=True, playable=playable)

                if trick:
                    parts = [f"[bold]{p}[/bold]: {card_str(c, pad=False)}" for c, p in trick]
                    console.print("  Table: " + "  |  ".join(parts))

                valid_idxs = {hand_sorted.index(c) + 1 for c in playable}

                if is_first_trick and not led_suit:
                    console.print("[dim]You must lead 2♣[/dim]")
                    chosen = ("2","♣")
                else:
                    hint_c, hint_msg = hint_card(
                        hand_sorted, trick, led_suit, hearts_broken,
                        is_first_trick, playable, scores, tracker, round_points, omnibus
                    )
                    valid_str = ", ".join(str(i) for i in sorted(valid_idxs))
                    prompt_str = f"[yellow]Play a card ({valid_str})  [dim]?=hint  p=played  u=undo[/dim]:[/yellow]"
                    console.print(prompt_str)

                    while True:
                        raw = Prompt.ask("Card").strip().lower()

                        if raw == "?":
                            if hint_c:
                                idx = hand_sorted.index(hint_c) + 1
                                console.print(f"  [cyan]Hint:[/cyan] #{idx} {card_str(hint_c)} — {hint_msg}")
                            continue

                        if raw == "p":
                            show_played_cards(tracker)
                            continue

                        if raw == "u":
                            if undo_used >= undo_limit or last_play is None:
                                console.print(f"[red]No undo available (limit: {undo_limit}/round).[/red]")
                            else:
                                # undo only works before others have played
                                if trick:
                                    console.print("[red]Can't undo after others have played.[/red]")
                                else:
                                    console.print("[yellow]Undo not available mid-trick.[/yellow]")
                            continue

                        if raw == "q":
                            console.print("[yellow]Quitting game...[/yellow]")
                            sys.exit(0)

                        try:
                            idx = int(raw) - 1
                            card = hand_sorted[idx]
                            if card not in playable:
                                console.print("[red]That card isn't valid here.[/red]")
                                continue
                            chosen = card
                            break
                        except (ValueError, IndexError):
                            console.print("[red]Enter a number, ?, p, u, or q.[/red]")

            else:  # AI
                if fast:
                    time.sleep(0.3)
                else:
                    time.sleep(0.6)
                chosen = ai_play_card(
                    hand, trick, led_suit, hearts_broken, is_first_trick,
                    player, scores, tracker, round_points, omnibus, fast
                )

            if not led_suit:
                led_suit = chosen[1]
            if chosen[1] == "♥":
                hearts_broken = True
            if chosen == ("Q","♠"):
                hearts_broken = True

            trick.append((chosen, player))
            hands[player].remove(chosen)
            tracker.add(chosen, player)

            if player != players[0]:
                console.print(f"  [dim]{player}[/dim] plays {card_str(chosen, pad=False)}")

        # who won the trick?
        led_cards = [(c, p) for c, p in trick if c[1] == led_suit]
        winner_card, winner = max(led_cards, key=lambda x: RANK_VAL[x[0][0]])
        trick_pts = sum(card_points(c, omnibus) for c, _ in trick)

        # track J♦ grab
        if omnibus and ("J","♦") in [c for c, _ in trick]:
            jd_grabbed_by = winner

        round_points[winner] += trick_pts
        tracker.add_trick(trick)
        leader = winner
        is_first_trick = False
        last_play = (winner, winner_card)

        pts_color = "red" if trick_pts > 0 else ("green" if trick_pts < 0 else "dim")
        pts_str = f"[{pts_color}]{'+' if trick_pts > 0 else ''}{trick_pts}pts[/{pts_color}]" if trick_pts != 0 else "[dim]0pts[/dim]"
        console.print(f"  → [bold]{winner}[/bold] wins the trick {pts_str}")

    # check shoot the moon (hearts + Q♠ only, J♦ separate in omnibus)
    hearts_qs = defaultdict(int)
    for p, pts in round_points.items():
        if omnibus:
            # separate out J♦ bonus
            jd_bonus = -10 if jd_grabbed_by == p else 0
            hearts_qs[p] = pts - jd_bonus
        else:
            hearts_qs[p] = pts

    shooter = None
    for p, pts in hearts_qs.items():
        if pts == 26:
            shooter = p
            break

    player_shot_moon = False
    if shooter:
        console.print(Panel(
            f"[bold yellow]🌕 {shooter} SHOT THE MOON!\nEveryone else gets 26 points![/bold yellow]",
            box=box.HEAVY, style="yellow"
        ))
        for p in players:
            if p != shooter:
                scores[p] += 26
            elif omnibus and jd_grabbed_by == shooter:
                scores[shooter] -= 10  # still gets J♦ bonus
        player_shot_moon = (shooter == players[0])
    else:
        for p in players:
            scores[p] += round_points[p]

    if omnibus and jd_grabbed_by and not shooter:
        console.print(f"  [green bold]{jd_grabbed_by} grabbed J♦ for -10 points![/green bold]")

    return round_points, player_shot_moon, jd_grabbed_by

# ── Round summary ──────────────────────────────────────────────────────────────

def round_summary(round_points, players, scores, round_num, omnibus=False):
    table = Table(title=f"Round {round_num} Results", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("Player", min_width=10)
    table.add_column("This Round", justify="right", width=12)
    table.add_column("Total", justify="right", width=8)
    for p in players:
        pts = round_points.get(p, 0)
        color = "red" if pts > 0 else ("green" if pts < 0 else "dim")
        table.add_row(p, f"[{color}]{'+' if pts > 0 else ''}{pts}[/{color}]", str(scores[p]))
    console.print(table)

# ── Main game loop ─────────────────────────────────────────────────────────────

def play_game(player_name, omnibus=False, fast=False, score_limit=100):
    players = [player_name] + AI_NAMES
    scores  = {p: 0 for p in players}
    stats   = load_save()
    round_num = 1
    moon_shots_this_game = 0
    player_round_scores = []
    jd_grabs = 0

    mode_str = "[yellow](Omnibus: J♦=-10)[/yellow]" if omnibus else ""
    fast_str  = "[dim](Fast mode)[/dim]" if fast else ""
    console.print(Panel(
        f"[bold magenta]♥ Hearts ♥[/bold magenta] {mode_str} {fast_str}\n"
        f"[dim]You vs {', '.join(AI_NAMES)}\n"
        f"Avoid points — ♥=1pt, Q♠=13pts{'  J♦=-10pts' if omnibus else ''}\n"
        f"First to {score_limit} loses. Lowest score wins.\n"
        f"During play: [yellow]?[/yellow]=hint  [yellow]p[/yellow]=played cards  [yellow]q[/yellow]=quit[/dim]",
        expand=False
    ))

    while max(scores.values()) < score_limit:
        console.rule(f"[bold magenta]Round {round_num}[/bold magenta]")

        d = deck()
        random.shuffle(d)
        hands = {p: d[i*13:(i+1)*13] for i, p in enumerate(players)}

        hands, received_map = passing_phase(hands, round_num, players, omnibus)

        round_points, player_shot_moon, jd_grabbed = play_round(
            hands, players, round_num, scores, omnibus, fast, score_limit
        )

        if player_shot_moon:
            moon_shots_this_game += 1
        if jd_grabbed == player_name:
            jd_grabs += 1

        player_round_scores.append(round_points.get(player_name, 0))

        round_summary(round_points, players, scores, round_num, omnibus)
        show_scores(scores, round_num, score_limit)

        round_num += 1
        stats["total_rounds"] += 1

        if max(scores.values()) < score_limit:
            if not fast:
                Prompt.ask("\n[dim]Press Enter for next round[/dim]", default="")
            else:
                time.sleep(1)

    # ── Game over ──────────────────────────────────────────────────────────────
    winner = min(scores.items(), key=lambda x: x[1])
    loser  = max(scores.items(), key=lambda x: x[1])

    console.print(Panel(
        f"[bold]Game Over![/bold]\n\n"
        f"🏆 Winner: [green bold]{winner[0]}[/green bold] — [green]{winner[1]}[/green] pts\n"
        f"💀 Last:   [red]{loser[0]}[/red] — [red]{loser[1]}[/red] pts",
        title="[bold magenta]♥ Hearts ♥[/bold magenta]",
        box=box.HEAVY, expand=False
    ))

    # update stats
    stats["games_played"] += 1
    player_won = winner[0] == player_name

    if player_won:
        stats["wins"] += 1
        stats["win_streak"] += 1
        stats["max_streak"] = max(stats["max_streak"], stats["win_streak"])
        console.print("[green bold]You won! Great game.[/green bold]")
        if stats["best_game"] is None or scores[player_name] < stats["best_game"]:
            stats["best_game"] = scores[player_name]
    else:
        stats["win_streak"] = 0
        if stats["worst_game"] is None or scores[player_name] > stats["worst_game"]:
            stats["worst_game"] = scores[player_name]

    stats["moon_shots"] += moon_shots_this_game

    # avg score per round
    n = stats["rounds_tracked"] + len(player_round_scores)
    if n > 0:
        old_avg = stats["avg_score_per_round"] * stats["rounds_tracked"]
        stats["avg_score_per_round"] = (old_avg + sum(player_round_scores)) / n
        stats["rounds_tracked"] = n

    if omnibus:
        stats["omnibus_jd_grabs"] += jd_grabs

    # head-to-head vs each AI
    for ai in AI_NAMES:
        key = f"vs_{ai.lower()}"
        stats[key]["games"] += 1
        if player_won:
            stats[key]["wins"] += 1

    save_stats(stats)
    show_career_stats(stats, player_name)

# ── Career stats ───────────────────────────────────────────────────────────────

def show_career_stats(stats, name):
    if stats["games_played"] == 0:
        console.print("[dim]No games played yet.[/dim]")
        return
    win_rate = 100 * stats["wins"] / stats["games_played"]

    table = Table(title="Your Career Stats", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Stat", min_width=22)
    table.add_column("Value", justify="right")

    table.add_row("Games played",       str(stats["games_played"]))
    table.add_row("Games won",          str(stats["wins"]))
    table.add_row("Win rate",           f"{win_rate:.1f}%")
    table.add_row("Current streak",     str(stats["win_streak"]))
    table.add_row("Best streak",        str(stats["max_streak"]))
    table.add_row("Moon shots",         str(stats["moon_shots"]))
    table.add_row("Avg pts/round",      f"{stats['avg_score_per_round']:.1f}")
    if stats["best_game"] is not None:
        table.add_row("Best game score",    str(stats["best_game"]))
    if stats["worst_game"] is not None:
        table.add_row("Worst game score",   str(stats["worst_game"]))
    table.add_row("Total rounds",       str(stats["total_rounds"]))
    if stats.get("omnibus_jd_grabs"):
        table.add_row("J♦ grabs (Omnibus)", str(stats["omnibus_jd_grabs"]))

    console.print(table)

    # head-to-head
    h2h = Table(title="Head-to-Head", box=box.SIMPLE, header_style="bold")
    h2h.add_column("Opponent", min_width=10)
    h2h.add_column("Win rate", justify="right")
    for ai in AI_NAMES:
        key = f"vs_{ai.lower()}"
        d = stats[key]
        if d["games"] > 0:
            rate = 100 * d["wins"] / d["games"]
            color = "green" if rate >= 50 else "red"
            h2h.add_row(ai, f"[{color}]{d['wins']}/{d['games']} ({rate:.0f}%)[/{color}]")
    console.print(h2h)

# ── Main menu ──────────────────────────────────────────────────────────────────

def main():
    console.clear()
    console.print(Panel(
        "[bold magenta]♥  H E A R T S  ♥[/bold magenta]\n\n"
        "[dim]A classic card game — avoid hearts, fear the Queen of Spades,\n"
        "and dare to shoot the moon.[/dim]",
        expand=False
    ))

    stats = load_save()
    if stats["games_played"] > 0:
        win_rate = 100 * stats["wins"] // max(stats["games_played"], 1)
        console.print(
            f"[dim]Welcome back! {stats['wins']}/{stats['games_played']} wins "
            f"({win_rate}% win rate)  |  streak: {stats['win_streak']}[/dim]\n"
        )

    choice = Prompt.ask(
        "[bold]Menu[/bold]\n"
        "  [cyan]1[/cyan] New game\n"
        "  [cyan]2[/cyan] Omnibus mode  [dim](J♦ = -10 pts)[/dim]\n"
        "  [cyan]3[/cyan] Fast mode     [dim](AI plays instantly)[/dim]\n"
        "  [cyan]4[/cyan] Custom limit  [dim](change 100-point threshold)[/dim]\n"
        "  [cyan]5[/cyan] Stats\n"
        "  [cyan]6[/cyan] Rules\n"
        "  [cyan]7[/cyan] Quit\n\nChoice",
        choices=["1","2","3","4","5","6","7"], default="1"
    )

    omnibus = False
    fast    = False
    score_limit = 100

    if choice == "7":
        return
    if choice == "5":
        show_career_stats(load_save(), "You")
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return
    if choice == "6":
        console.print(Panel(
            "[bold]How to play Hearts[/bold]\n\n"
            "• 4 players, 13 cards each\n"
            "• Pass 3 cards before each round (left → right → across → keep)\n"
            "• 2♣ leads the first trick — no point cards on trick 1\n"
            "• Must follow suit — play anything if you can't\n"
            "• Highest card of the led suit wins the trick\n"
            "• [red]♥[/red] = 1 point,  [yellow]Q♠[/yellow] = 13 points\n"
            "• Hearts can't be led until broken (someone discards ♥)\n"
            "• [bold yellow]Shoot the Moon[/bold yellow]: take ALL 13♥ + Q♠ → everyone else +26\n"
            "• [bold green]Omnibus rule[/bold green]: J♦ = -10 points for whoever wins it\n"
            "• Dangerous cards highlighted: Q♠ K♠ A♠ in [yellow]yellow[/yellow], high ♥ in [red]red[/red]\n"
            "• During play: [yellow]?[/yellow] = hint  [yellow]p[/yellow] = show played cards  [yellow]q[/yellow] = quit\n"
            "• Game ends when someone hits the score limit — lowest wins",
            box=box.ROUNDED, expand=False
        ))
        Prompt.ask("\n[dim]Press Enter[/dim]", default="")
        main(); return
    if choice == "2":
        omnibus = True
    if choice == "3":
        fast = True
    if choice == "4":
        raw = Prompt.ask("Score limit", default="100")
        try:
            score_limit = max(26, int(raw))
        except ValueError:
            score_limit = 100

    name = Prompt.ask("Your name", default="You")
    play_game(name, omnibus=omnibus, fast=fast, score_limit=score_limit)

    again = Prompt.ask("\nPlay again?", choices=["y","n"], default="y")
    if again == "y":
        main()

if __name__ == "__main__":
    main()
