"""
Hearts Card Game — terminal-based, fully offline.
4 players: you vs 3 AI with different personalities.
"""
import random
import json
import os
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich import box
    from rich.columns import Columns
    from rich.text import Text
except ImportError:
    print("Run: pip install rich")
    sys.exit(1)

console = Console()
SAVE_FILE = Path.home() / ".hearts_save.json"

# ── Cards ──────────────────────────────────────────────────────────────────────

SUITS  = ["♠", "♥", "♦", "♣"]
RANKS  = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_VAL = {r: i for i, r in enumerate(RANKS)}

def card_str(card, pad=True):
    rank, suit = card
    color = "red" if suit in ("♥","♦") else "white"
    s = f"{rank}{suit}"
    if pad:
        s = s.ljust(4)
    return f"[{color}]{s}[/{color}]"

def card_points(card):
    rank, suit = card
    if suit == "♥":
        return 1
    if suit == "♠" and rank == "Q":
        return 13
    return 0

def deck():
    return [(r, s) for s in SUITS for r in RANKS]

def sort_hand(hand):
    return sorted(hand, key=lambda c: (SUITS.index(c[1]), RANK_VAL[c[0]]))

# ── AI Personalities ───────────────────────────────────────────────────────────

AI_NAMES = ["Alex", "Jordan", "Riley"]
AI_PERSONALITIES = {
    "Alex":   "safe",       # avoid points at all costs
    "Jordan": "aggressive", # tries to shoot the moon
    "Riley":  "balanced",   # plays smart middle ground
}

def ai_pass_cards(hand, name):
    """Choose 3 cards to pass based on personality."""
    personality = AI_PERSONALITIES[name]
    hand = sort_hand(hand)

    if personality == "aggressive":
        # keep high hearts and QS, pass low cards
        risky = [c for c in hand if c[1] == "♥" and RANK_VAL[c[0]] >= RANK_VAL["J"]]
        risky += [c for c in hand if c == ("Q", "♠")]
        safe  = [c for c in hand if c not in risky]
        to_pass = (safe + risky)[:3]
    elif personality == "safe":
        # pass highest point cards first
        danger = [c for c in hand if c == ("Q","♠") or c == ("A","♠") or c == ("K","♠")]
        danger += [c for c in hand if c[1] == "♥" and RANK_VAL[c[0]] >= RANK_VAL["10"]]
        rest   = [c for c in hand if c not in danger]
        to_pass = (danger + rest)[:3]
    else:
        # balanced: pass high non-trump cards
        high = sorted(hand, key=lambda c: RANK_VAL[c[0]], reverse=True)
        to_pass = high[:3]

    return to_pass[:3]

def ai_play_card(hand, trick, led_suit, hearts_broken, is_first_trick, name, scores):
    """Choose a card to play."""
    personality = AI_PERSONALITIES[name]

    # must follow suit
    followable = [c for c in hand if c[1] == led_suit] if led_suit else []
    if followable:
        playable = followable
    else:
        # can't follow — can play anything (hearts only after broken or only hearts left)
        if is_first_trick:
            playable = [c for c in hand if card_points(c) == 0] or hand
        else:
            playable = hand

    # first trick: never play points
    if is_first_trick:
        safe = [c for c in playable if card_points(c) == 0]
        if safe:
            playable = safe

    if personality == "aggressive":
        # try to win tricks — play highest in suit, dump low hearts if can't follow
        if followable:
            return max(playable, key=lambda c: RANK_VAL[c[0]])
        else:
            # dump queen of spades or high hearts
            dump = [c for c in playable if c == ("Q","♠")]
            dump = dump or sorted(playable, key=lambda c: card_points(c), reverse=True)
            return dump[0]

    elif personality == "safe":
        # avoid winning: play highest card that won't win, or lowest
        if followable and trick:
            current_winner_rank = max(RANK_VAL[c[0]] for c, _ in trick if c[1] == led_suit)
            # play highest that doesn't win
            losing = [c for c in playable if RANK_VAL[c[0]] < current_winner_rank]
            if losing:
                return max(losing, key=lambda c: RANK_VAL[c[0]])
        # dump queen of spades or high hearts when can't follow
        if not followable:
            dump = [c for c in playable if c == ("Q","♠")]
            if dump:
                return dump[0]
            dump = sorted(playable, key=lambda c: card_points(c), reverse=True)
            return dump[0]
        return min(playable, key=lambda c: RANK_VAL[c[0]])

    else:  # balanced
        if not followable:
            dump = [c for c in playable if c == ("Q","♠")]
            dump = dump or sorted(playable, key=lambda c: card_points(c), reverse=True)
            return dump[0]
        return min(playable, key=lambda c: RANK_VAL[c[0]])

# ── Shooting the moon ──────────────────────────────────────────────────────────

def check_shoot_moon(round_points):
    """If one player took all 26 points, they shot the moon."""
    for player, pts in round_points.items():
        if pts == 26:
            return player
    return None

# ── Display helpers ────────────────────────────────────────────────────────────

def show_hand(hand, selectable=False):
    hand = sort_hand(hand)
    parts = []
    for i, card in enumerate(hand):
        num = f"[dim]{i+1:2}.[/dim] " if selectable else ""
        parts.append(num + card_str(card, pad=False))
    console.print("  " + "  ".join(parts))

def show_scores(scores, round_num=None):
    title = f"Scoreboard — Round {round_num}" if round_num else "Final Scores"
    table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Player", min_width=10)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Status", width=16)

    sorted_players = sorted(scores.items(), key=lambda x: x[1])
    leader = sorted_players[0][0]

    for player, score in sorted_players:
        status = "[green]Leading[/green]" if player == leader else ""
        if score >= 80:
            status = "[red]Danger zone[/red]"
        color = "green" if player == leader else "white"
        table.add_row(f"[{color}]{player}[/{color}]", str(score), status)
    console.print(table)

def show_trick(trick, names):
    parts = [f"[bold]{p}[/bold]: {card_str(c, pad=False)}" for c, p in trick]
    console.print("  Trick: " + "  |  ".join(parts))

# ── Save / Load ────────────────────────────────────────────────────────────────

def load_save():
    if SAVE_FILE.exists():
        with open(SAVE_FILE) as f:
            return json.load(f)
    return {"games_played": 0, "wins": 0, "moon_shots": 0, "total_rounds": 0}

def save_stats(stats):
    with open(SAVE_FILE, "w") as f:
        json.dump(stats, f, indent=2)

# ── Passing phase ──────────────────────────────────────────────────────────────

PASS_DIRECTIONS = ["left", "right", "across", "none"]

def passing_phase(hands, round_num, players):
    direction = PASS_DIRECTIONS[(round_num - 1) % 4]
    n = len(players)
    offsets = {"left": 1, "right": n - 1, "across": n // 2, "none": 0}
    offset = offsets[direction]

    if direction == "none":
        console.print(f"\n[dim]Round {round_num}: No passing this round.[/dim]")
        return hands

    console.print(f"\n[bold cyan]Passing phase — passing [yellow]{direction}[/yellow][/bold cyan]")

    passed = {}
    human = players[0]
    h_hand = sort_hand(hands[human])

    # human picks 3 cards
    console.print(f"\nYour hand:")
    show_hand(h_hand, selectable=True)
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

    # AI picks cards
    for name in players[1:]:
        passed[name] = ai_pass_cards(hands[name], name)

    # exchange
    new_hands = {p: list(hands[p]) for p in players}
    for i, player in enumerate(players):
        recipient = players[(i + offset) % n]
        for card in passed[player]:
            new_hands[player].remove(card)
            new_hands[recipient].append(card)

    console.print(f"[green]You passed:[/green] " + "  ".join(card_str(c, pad=False) for c in chosen))
    received = passed[players[(players.index(human) - offset) % n]]
    console.print(f"[green]You received:[/green] " + "  ".join(card_str(c, pad=False) for c in received))

    return new_hands

# ── Round ──────────────────────────────────────────────────────────────────────

def play_round(hands, players, round_num, scores):
    # find who has 2♣ — they lead first
    leader = next(p for p in players if ("2","♣") in hands[p])
    hearts_broken = False
    round_points = defaultdict(int)
    is_first_trick = True

    for trick_num in range(13):
        trick = []
        led_suit = None

        console.rule(f"[dim]Trick {trick_num+1}[/dim]")

        order = players[players.index(leader):] + players[:players.index(leader)]

        for player in order:
            hand = hands[player]

            if player == players[0]:  # human
                hand_sorted = sort_hand(hand)
                console.print(f"\n[bold]Your hand ({len(hand)} cards):[/bold]")
                show_hand(hand_sorted, selectable=True)

                if trick:
                    show_trick(trick, players)

                # determine valid plays
                followable = [c for c in hand_sorted if c[1] == led_suit] if led_suit else []
                if followable:
                    playable = followable
                elif is_first_trick:
                    playable = [c for c in hand_sorted if card_points(c) == 0] or hand_sorted
                else:
                    if not hearts_broken:
                        non_hearts = [c for c in hand_sorted if c[1] != "♥"]
                        playable = non_hearts if non_hearts else hand_sorted
                    else:
                        playable = hand_sorted

                valid_idxs = {hand_sorted.index(c) + 1 for c in playable}

                if is_first_trick and not led_suit:
                    console.print("[dim]You must lead 2♣[/dim]")
                    chosen = ("2","♣")
                else:
                    console.print(f"[yellow]Play a card (valid: {', '.join(str(i) for i in sorted(valid_idxs))}):[/yellow]")
                    while True:
                        raw = Prompt.ask("Card #").strip()
                        try:
                            idx = int(raw) - 1
                            card = hand_sorted[idx]
                            if card not in playable:
                                raise ValueError
                            chosen = card
                            break
                        except (ValueError, IndexError):
                            console.print("[red]Invalid choice.[/red]")

            else:  # AI
                chosen = ai_play_card(
                    hand, trick, led_suit, hearts_broken,
                    is_first_trick, player, scores
                )

            if not led_suit:
                led_suit = chosen[1]
            if chosen[1] == "♥":
                hearts_broken = True
            if chosen == ("Q","♠"):
                hearts_broken = True

            trick.append((chosen, player))
            hands[player].remove(chosen)

            if player != players[0]:
                console.print(f"  [dim]{player}[/dim] plays {card_str(chosen, pad=False)}")

        # who won the trick?
        led_cards = [(c, p) for c, p in trick if c[1] == led_suit]
        winner_card, winner = max(led_cards, key=lambda x: RANK_VAL[x[0][0]])
        trick_pts = sum(card_points(c) for c, _ in trick)
        round_points[winner] += trick_pts
        leader = winner
        is_first_trick = False

        pts_str = f"[red]+{trick_pts}pts[/red]" if trick_pts else "[dim]0pts[/dim]"
        console.print(f"  → [bold]{winner}[/bold] wins the trick {pts_str}")

    # check shoot the moon
    shooter = check_shoot_moon(round_points)
    if shooter:
        console.print(Panel(
            f"[bold yellow]🌕 {shooter} SHOT THE MOON! Everyone else gets 26 points![/bold yellow]",
            box=box.HEAVY, style="yellow"
        ))
        for p in players:
            if p != shooter:
                scores[p] += 26
        if shooter == players[0]:
            return round_points, True
        return round_points, False
    else:
        for p in players:
            scores[p] += round_points[p]
        return round_points, False

# ── End of round summary ───────────────────────────────────────────────────────

def round_summary(round_points, players, scores, round_num):
    table = Table(title=f"Round {round_num} Results", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("Player", min_width=10)
    table.add_column("This Round", justify="right", width=12)
    table.add_column("Total", justify="right", width=8)
    for p in players:
        pts = round_points.get(p, 0)
        color = "red" if pts > 0 else "green"
        table.add_row(p, f"[{color}]{pts}[/{color}]", str(scores[p]))
    console.print(table)

# ── Main game loop ─────────────────────────────────────────────────────────────

def play_game(player_name):
    players = [player_name] + AI_NAMES
    scores  = {p: 0 for p in players}
    stats   = load_save()
    round_num = 1
    moon_shots_this_game = 0

    console.print(Panel(
        f"[bold magenta]♥ Hearts ♥[/bold magenta]\n"
        f"[dim]You vs {', '.join(AI_NAMES)}\n"
        f"Avoid points — every ♥ = 1pt, Q♠ = 13pts\n"
        f"First to 100 loses. Lowest score wins.[/dim]",
        expand=False
    ))

    while max(scores.values()) < 100:
        console.rule(f"[bold magenta]Round {round_num}[/bold magenta]")

        # deal
        d = deck()
        random.shuffle(d)
        hands = {p: d[i*13:(i+1)*13] for i, p in enumerate(players)}

        # pass
        hands = passing_phase(hands, round_num, players)

        # play
        round_points, player_shot_moon = play_round(hands, players, round_num, scores)
        if player_shot_moon:
            moon_shots_this_game += 1

        # summary
        round_summary(round_points, players, scores, round_num)
        show_scores(scores, round_num)

        round_num += 1
        stats["total_rounds"] += 1

        if max(scores.values()) < 100:
            Prompt.ask("\n[dim]Press Enter for next round[/dim]", default="")

    # Game over
    winner = min(scores.items(), key=lambda x: x[1])
    loser  = max(scores.items(), key=lambda x: x[1])

    console.print(Panel(
        f"[bold]Game Over![/bold]\n\n"
        f"🏆 Winner: [green bold]{winner[0]}[/green bold] with [green]{winner[1]}[/green] points\n"
        f"💀 Eliminated: [red]{loser[0]}[/red] with [red]{loser[1]}[/red] points",
        title="[bold magenta]♥ Hearts ♥[/bold magenta]",
        box=box.HEAVY, expand=False
    ))

    stats["games_played"] += 1
    if winner[0] == player_name:
        stats["wins"] += 1
        console.print("[green bold]You won! Great game.[/green bold]")
    stats["moon_shots"] += moon_shots_this_game
    save_stats(stats)

    show_career_stats(stats, player_name)

# ── Career stats ───────────────────────────────────────────────────────────────

def show_career_stats(stats, name):
    if stats["games_played"] == 0:
        return
    win_rate = 100 * stats["wins"] / stats["games_played"]
    table = Table(title="Your Career Stats", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Stat", min_width=20)
    table.add_column("Value", justify="right")
    table.add_row("Games played",  str(stats["games_played"]))
    table.add_row("Games won",     str(stats["wins"]))
    table.add_row("Win rate",      f"{win_rate:.1f}%")
    table.add_row("Moon shots",    str(stats["moon_shots"]))
    table.add_row("Total rounds",  str(stats["total_rounds"]))
    console.print(table)

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
        console.print(f"[dim]Welcome back! {stats['wins']}/{stats['games_played']} wins ({100*stats['wins']//max(stats['games_played'],1)}% win rate)[/dim]\n")

    choice = Prompt.ask(
        "[bold]Menu[/bold]\n  [cyan]1[/cyan] New game\n  [cyan]2[/cyan] Stats\n  [cyan]3[/cyan] Rules\n  [cyan]4[/cyan] Quit\n\nChoice",
        choices=["1","2","3","4"], default="1"
    )

    if choice == "1":
        name = Prompt.ask("Your name", default="You")
        play_game(name)
    elif choice == "2":
        stats = load_save()
        show_career_stats(stats, "You")
    elif choice == "3":
        console.print(Panel(
            "[bold]How to play Hearts[/bold]\n\n"
            "• 4 players, 13 cards each\n"
            "• Each round: pass 3 cards (direction rotates each round)\n"
            "• 2♣ leads the first trick\n"
            "• Must follow suit — play anything if you can't\n"
            "• Highest card of the led suit wins the trick\n"
            "• [red]♥[/red] = 1 point each, [white]Q♠[/white] = 13 points\n"
            "• Hearts can't be led until 'broken' (someone discards a ♥)\n"
            "• [yellow]Shoot the Moon[/yellow]: take ALL 26 points in one round\n"
            "  → everyone else gets 26, you get 0\n"
            "• Game ends when someone hits 100 — lowest score wins",
            box=box.ROUNDED, expand=False
        ))
        Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")
        main()
        return
    elif choice == "4":
        return

    again = Prompt.ask("\nPlay again?", choices=["y","n"], default="y")
    if again == "y":
        main()

if __name__ == "__main__":
    main()
