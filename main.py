import os
import random
import json
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

import discord
from discord import app_commands
from discord.ext import commands


INTENTS = discord.Intents.default()
INTENTS.message_content = True  # Required for prefix commands like !mai
BOT = commands.Bot(command_prefix="!", intents=INTENTS)

DEFAULT_GOON_PHRASES = [
    "Good boy"
]

STARTING_BALANCE = 1000
WALLET_FILE = os.path.join(os.path.dirname(__file__), "wallets.json")


class WalletManager:
    """Simple file-backed wallet store."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self._wallets = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as handle:
                json.dump(self._wallets, handle, indent=2)
        except OSError as error:
            print(f"Failed to save wallets: {error}")

    def ensure_user(self, user_id: int) -> None:
        key = str(user_id)
        if key not in self._wallets:
            self._wallets[key] = STARTING_BALANCE
            self._save()

    def get_balance(self, user_id: int) -> int:
        key = str(user_id)
        if key not in self._wallets:
            return STARTING_BALANCE
        return int(self._wallets[key])

    def adjust_balance(self, user_id: int, delta: int) -> int:
        key = str(user_id)
        self.ensure_user(user_id)
        self._wallets[key] = int(self._wallets.get(key, STARTING_BALANCE) + delta)
        self._save()
        return self._wallets[key]

    def all_balances(self) -> dict:
        return self._wallets.copy()


WALLETS = WalletManager(WALLET_FILE)


def _load_goon_phrases(file_name: str = "mai_gifs.txt") -> List[str]:
    """Load goon phrases from a text file, falling back to defaults on error."""
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            phrases = [line.strip() for line in handle if line.strip()]
    except OSError as error:
        print(f"Could not read goon phrases from {file_path}: {error}")
        return DEFAULT_GOON_PHRASES.copy()

    if not phrases:
        print(f"No goon phrases found in {file_path}; using defaults.")
        return DEFAULT_GOON_PHRASES.copy()

    return phrases


GOON_PHRASES = _load_goon_phrases()


class BlackjackGame:
    """Blackjack game logic with single split support."""

    def __init__(self, bet: int) -> None:
        self.deck = self._build_deck()
        self.player_hands: List[List[str]] = [[self._draw_card(), self._draw_card()]]
        self.dealer_hand: List[str] = [self._draw_card(), self._draw_card()]
        self.finished = False
        self.winning_hand_count = 0
        self.result = ""
        self.current_hand_index = 0
        self.split_used = False
        self.hand_statuses: List[str] = ["playing"]  # playing, bust, stood, win, lose, push, blackjack
        self.hand_bets: List[int] = [bet]
        self.hand_doubled: List[bool] = [False]
        self.settled = False
        self._check_initial_blackjack()

    @staticmethod
    def _build_deck() -> List[str]:
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        suits = ["S", "H", "D", "C"]
        deck = [f"{rank}{suit}" for rank in ranks for suit in suits]
        random.shuffle(deck)
        return deck

    def _draw_card(self) -> str:
        if not self.deck:
            self.deck = self._build_deck()
        return self.deck.pop()

    @staticmethod
    def _fmt_card(card: str) -> str:
        suit_symbols = {"S": "♠️", "H": "♥️", "D": "♦️", "C": "♣️"}
        return f"{card[:-1]}{suit_symbols.get(card[-1], '')}"

    @staticmethod
    def _card_rank(card: str) -> str:
        return card[:-1]

    @staticmethod
    def _card_value(card: str) -> int:
        rank = card[:-1]
        if rank in {"J", "Q", "K"}:
            return 10
        if rank == "A":
            return 11
        return int(rank)

    @staticmethod
    def _hand_value(hand: List[str]) -> int:
        total = 0
        aces = 0
        for card in hand:
            value = BlackjackGame._card_value(card)
            if value == 11:
                aces += 1
            total += value

        while total > 21 and aces:
            total -= 10
            aces -= 1

        return total

    @staticmethod
    def _is_blackjack(hand: List[str]) -> bool:
        return len(hand) == 2 and BlackjackGame._hand_value(hand) == 21

    def hand_total(self, index: int) -> int:
        return self._hand_value(self.player_hands[index])

    @property
    def dealer_total(self) -> int:
        return self._hand_value(self.dealer_hand)

    def _check_initial_blackjack(self) -> None:
        player_hand = self.player_hands[0]
        player_blackjack = self._is_blackjack(player_hand)
        dealer_blackjack = self._is_blackjack(self.dealer_hand)

        if player_blackjack and dealer_blackjack:
            self.hand_statuses[0] = "push"
            self.result = "Both you and the dealer have blackjack. Push."
            self.finished = True
            return

        if player_blackjack:
            self.hand_statuses[0] = "blackjack"
            self.winning_hand_count = 1
            self.result = "Blackjack! You win."
            self.finished = True
            return

        if dealer_blackjack:
            self.hand_statuses[0] = "lose"
            self.result = "Dealer has blackjack. You lose."
            self.finished = True

    def can_split(self) -> bool:
        if self.finished or self.split_used:
            return False
        if len(self.player_hands) != 1:
            return False
        hand = self.player_hands[0]
        if len(hand) != 2:
            return False
        return self._card_rank(hand[0]) == self._card_rank(hand[1])

    def split(self) -> bool:
        if not self.can_split():
            return False
        hand = self.player_hands[0]
        first, second = hand
        self.player_hands = [
            [first, self._draw_card()],
            [second, self._draw_card()],
        ]
        self.hand_statuses = ["playing", "playing"]
        original_bet = self.hand_bets[0]
        self.hand_bets = [original_bet, original_bet]
        self.hand_doubled = [False, False]
        self.current_hand_index = 0
        self.split_used = True
        return True

    def can_double(self) -> bool:
        if self.finished:
            return False
        if self.hand_statuses[self.current_hand_index] != "playing":
            return False
        hand = self.player_hands[self.current_hand_index]
        if len(hand) != 2:
            return False
        return not self.hand_doubled[self.current_hand_index]

    def double_down(self) -> None:
        """Double the current hand bet, draw one card, then stand."""
        if not self.can_double():
            return
        self.hand_bets[self.current_hand_index] *= 2
        self.hand_doubled[self.current_hand_index] = True
        hand = self.player_hands[self.current_hand_index]
        hand.append(self._draw_card())
        if self.hand_total(self.current_hand_index) > 21:
            self.hand_statuses[self.current_hand_index] = "bust"
        else:
            self.hand_statuses[self.current_hand_index] = "stood"
        self._advance_hand()
        self._finalize_if_done()

    def player_hit(self) -> None:
        if self.finished:
            return
        hand = self.player_hands[self.current_hand_index]
        hand.append(self._draw_card())
        if self.hand_total(self.current_hand_index) > 21:
            self.hand_statuses[self.current_hand_index] = "bust"
            self._advance_hand()
            self._finalize_if_done()

    def player_stand(self) -> None:
        if self.finished:
            return
        self.hand_statuses[self.current_hand_index] = "stood"
        self._advance_hand()
        self._finalize_if_done()

    def _dealer_play(self) -> None:
        while self.dealer_total < 17:
            self.dealer_hand.append(self._draw_card())

    def _advance_hand(self) -> None:
        while self.current_hand_index < len(self.player_hands):
            if self.hand_statuses[self.current_hand_index] == "playing":
                return
            self.current_hand_index += 1

    def _finalize_if_done(self) -> None:
        if any(status == "playing" for status in self.hand_statuses):
            return
        # Dealer plays only if at least one hand is not bust.
        if any(status != "bust" for status in self.hand_statuses):
            self._dealer_play()
            for idx, status in enumerate(self.hand_statuses):
                if status == "bust":
                    continue
                player = self.hand_total(idx)
                dealer = self.dealer_total
                if player > 21:
                    self.hand_statuses[idx] = "bust"
                elif dealer > 21 or player > dealer:
                    self.hand_statuses[idx] = "win"
                elif player == dealer:
                    self.hand_statuses[idx] = "push"
                else:
                    self.hand_statuses[idx] = "lose"

        self.finished = True
        self.winning_hand_count = sum(
            1 for status in self.hand_statuses if status in {"win", "blackjack"}
        )
        pushes = sum(1 for status in self.hand_statuses if status == "push")

        total_hands = len(self.hand_statuses)
        if self.winning_hand_count == total_hands:
            self.result = "You win all hands!"
        elif self.winning_hand_count > 0:
            self.result = f"You win {self.winning_hand_count} hand(s)."
        elif pushes == total_hands:
            self.result = "All hands push."
        elif pushes > 0:
            self.result = f"No wins. Pushes: {pushes}."
        else:
            self.result = "Dealer wins."

    def render_state(self, reveal_dealer: bool) -> str:
        lines = ["win this game like a good boy.", "```"]

        for idx, hand in enumerate(self.player_hands):
            cards = " ".join(self._fmt_card(card) for card in hand)
            total = self.hand_total(idx)
            status = self.hand_statuses[idx]
            bet = self.hand_bets[idx]
            if self.finished:
                label = status.upper()
            else:
                label = "PLAYING" if idx == self.current_hand_index else status.upper()
            doubled = " x2" if self.hand_doubled[idx] else ""
            lines.append(f"Hand {idx + 1} (${bet}{doubled}) ({total}) [{label}]: {cards}")

        if reveal_dealer:
            dealer_cards = " ".join(self._fmt_card(card) for card in self.dealer_hand)
            dealer_label = f"Dealer ({self.dealer_total}): {dealer_cards}"
        else:
            dealer_cards = f"{self._fmt_card(self.dealer_hand[0])} ??"
            dealer_label = f"Dealer showing: {dealer_cards}"

        lines.append(dealer_label)
        lines.append("```")

        if self.finished:
            lines.append(self.result)
        else:
            lines.append("Hit, Stand, or Split (if available) with the buttons below.")

        return "\n".join(lines)

    def settle_payout(self) -> int:
        """Return total payout after bets have been placed up front."""
        if self.settled:
            return 0
        payout = 0
        for bet, status in zip(self.hand_bets, self.hand_statuses):
            if status in {"win", "blackjack"}:
                payout += bet * 2
            elif status == "push":
                payout += bet
        self.settled = True
        return payout

    def forfeit(self) -> None:
        if self.finished:
            return
        for idx, status in enumerate(self.hand_statuses):
            if status == "playing":
                self.hand_statuses[idx] = "lose"
        self.finished = True
        self.result = "Game timed out. Bets forfeited."


class BlackjackView(discord.ui.View):
    """Interactive blackjack buttons for a single player."""

    def __init__(
        self, game: BlackjackGame, player: discord.Member, wallets: WalletManager
    ) -> None:
        super().__init__(timeout=90)
        self.game = game
        self.player_id = player.id
        self.wallets = wallets
        self.message: Optional[discord.Message] = None
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_id:
            await interaction.response.send_message(
                "This is not your game.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        if self.message and not self.game.finished:
            self.game.forfeit()
            self._update_buttons()
            try:
                await self.message.edit(
                    content=self.game.render_state(reveal_dealer=True),
                    view=self,
                )
            except discord.HTTPException:
                pass

    def _disable_buttons(self) -> None:
        for child in self.children:
            child.disabled = True

    async def _settle_if_done(self, interaction: discord.Interaction) -> None:
        if self.game.finished and not self.game.settled:
            payout = self.game.settle_payout()
            if payout:
                new_balance = self.wallets.adjust_balance(self.player_id, payout)
                await interaction.followup.send(
                    f"You won ${payout}. New balance: ${new_balance}."
                )
            else:
                await interaction.followup.send("No winnings this time.")

    def _update_buttons(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if self.game.finished:
                child.disabled = True
            elif child.label == "Split":
                child.disabled = not self.game.can_split()
            elif child.label == "Double Down":
                child.disabled = not self.game.can_double()
            else:
                child.disabled = False

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.game.player_hit()
        self._update_buttons()
        reveal = self.game.finished

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=reveal),
            view=self,
        )
        await self._settle_if_done(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.game.player_stand()
        self._update_buttons()

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=self.game.finished),
            view=self,
        )
        await self._settle_if_done(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, row=1)
    async def double_down(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not self.game.can_double():
            await interaction.response.send_message(
                "You cannot double right now.", ephemeral=True
            )
            return

        bet_needed = self.game.hand_bets[self.game.current_hand_index]
        balance = self.wallets.get_balance(self.player_id)
        if balance < bet_needed:
            await interaction.response.send_message(
                f"Not enough funds to double. Need ${bet_needed}.", ephemeral=True
            )
            return

        self.wallets.adjust_balance(self.player_id, -bet_needed)
        self.game.double_down()
        self._update_buttons()

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=self.game.finished),
            view=self,
        )
        await self._settle_if_done(interaction)

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary, row=1)
    async def split_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        split_cost = self.game.hand_bets[0]
        balance = self.wallets.get_balance(self.player_id)
        if balance < split_cost:
            await interaction.response.send_message(
                f"Not enough funds to split. Need ${split_cost}.", ephemeral=True
            )
            return
        self.wallets.adjust_balance(self.player_id, -split_cost)
        if not self.game.split():
            await interaction.response.send_message(
                "Split is not available right now.", ephemeral=True
            )
            # Refund since split failed
            self.wallets.adjust_balance(self.player_id, split_cost)
            return

        self._update_buttons()

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=False),
            view=self,
        )
        await self._settle_if_done(interaction)


def _bet_options(balance: int) -> List[discord.SelectOption]:
    """Build bet options up to the user's balance."""
    base = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
    options = [amt for amt in base if amt <= balance]
    if balance not in options:
        options.append(balance)  # all-in option
    # Deduplicate and sort
    unique = sorted(set(options))
    select_options = []
    for amt in unique:
        label = f"${amt}"
        if amt == balance:
            label += " (All-in)"
        select_options.append(discord.SelectOption(label=label, value=str(amt)))
    return select_options


class BetSelect(discord.ui.Select):
    def __init__(self, parent: "BetSelectionView", balance: int) -> None:
        self.parent_view = parent
        options = _bet_options(balance)[:25]  # Discord limit
        super().__init__(
            placeholder="Pick your bet",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message(
                "This menu isn't for you.", ephemeral=True
            )
            return
        bet = int(self.values[0])
        await self.parent_view.start_game(interaction, bet)


class BetSelectionView(discord.ui.View):
    """Bet chooser that then starts blackjack."""

    def __init__(
        self,
        user: discord.Member,
        balance: int,
        ctx: Optional[commands.Context],
        use_dm: bool = False,
        ephemeral: bool = False,
    ) -> None:
        super().__init__(timeout=60)
        self.user_id = user.id
        self.balance = balance
        self.ctx = ctx
        self.use_dm = use_dm
        self.ephemeral = ephemeral
        self.message: Optional[discord.Message] = None
        self.add_item(BetSelect(self, balance))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This menu isn't for you.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Bet selection timed out.", view=self)
            except Exception:
                pass

    async def start_game(self, interaction: discord.Interaction, bet: int) -> None:
        # Stop further interactions on this view
        self.stop()
        for child in self.children:
            child.disabled = True

        balance = WALLETS.get_balance(self.user_id)
        if bet <= 0:
            await interaction.response.edit_message(
                content="Bet must be greater than 0.", view=self
            )
            return
        if bet > balance:
            await interaction.response.edit_message(
                content=f"Insufficient funds. Balance: ${balance}.", view=self
            )
            return

        WALLETS.adjust_balance(self.user_id, -bet)
        game = BlackjackGame(bet)

        # Update the bet selection message to lock the bet.
        await interaction.response.edit_message(
            content=f"Bet locked at ${bet}. Balance: ${WALLETS.get_balance(self.user_id)}.",
            view=None,
        )

        # If blackjack is dealt immediately, resolve without buttons.
        if game.finished:
            await interaction.followup.send(game.render_state(reveal_dealer=True))
            payout = game.settle_payout()
            if payout:
                new_balance = WALLETS.adjust_balance(self.user_id, payout)
                await interaction.followup.send(
                    f"You won ${payout}. New balance: ${new_balance}."
                )
            else:
                await interaction.followup.send(
                    f"No winnings. Balance: ${WALLETS.get_balance(self.user_id)}."
                )
            return

        view = BlackjackView(game, interaction.user, WALLETS)
        # Send the game in DM if we started there, otherwise reply in-channel.
        if self.use_dm:
            dm = interaction.user.dm_channel or await interaction.user.create_dm()
            msg = await dm.send(
                game.render_state(reveal_dealer=False), view=view
            )
        else:
            msg = await interaction.followup.send(
                game.render_state(reveal_dealer=False),
                view=view,
                ephemeral=self.ephemeral,
            )
        view.message = msg
        self.message = msg


class CoinFlipView(discord.ui.View):
    """Guess coin flips; win after a streak."""

    def __init__(self, user: discord.Member) -> None:
        super().__init__(timeout=60)
        self.user_id = user.id
        self.streak = 0
        self.finished = False
        self.message: Optional[discord.Message] = None
        self.status = "Guess heads or tails. Need 5 in a row to earn $500."

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This game isn't for you.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        if self.message and not self.finished:
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(
                    content=f"{self.status}\n\nTimed out.", view=self
                )
            except discord.HTTPException:
                pass

    def _flip(self) -> str:
        return random.choice(["heads", "tails"])

    def _result_text(self) -> str:
        return f"{self.status}\nCurrent streak: {self.streak}/{COIN_TARGET}"

    async def _handle_guess(
        self, interaction: discord.Interaction, guess: str
    ) -> None:
        if self.finished:
            await interaction.response.send_message(
                "Game already finished.", ephemeral=True
            )
            return
        outcome = self._flip()
        if guess == outcome:
            self.streak += 1
            self.status = f"Correct! It was {outcome}."
            if self.streak >= COIN_TARGET:
                self.finished = True
                for child in self.children:
                    child.disabled = True
                WALLETS.adjust_balance(self.user_id, COIN_REWARD)
                self.status += (
                    f" You earned ${COIN_REWARD}. New balance: "
                    f"${WALLETS.get_balance(self.user_id)}."
                )
                await interaction.response.edit_message(
                    content=self._result_text(), view=self
                )
                return
        else:
            self.streak = 0
            self.status = (
                f"Wrong, it was {outcome}. Streak reset. Try again!"
            )
        await interaction.response.edit_message(
            content=self._result_text(), view=self
        )

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary)
    async def heads(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._handle_guess(interaction, "heads")

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.secondary)
    async def tails(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self._handle_guess(interaction, "tails")


def _collect_assignees(*members: Optional[discord.Member]) -> List[discord.Member]:
    """Return only the members that were provided to the command."""
    return [member for member in members if member is not None]


@BOT.event
async def on_ready() -> None:
    """Sync slash commands once the bot is ready."""
    await BOT.tree.sync()
    print(f"Logged in as {BOT.user} (ID: {BOT.user.id})")


@BOT.command(name="mai", help="Send a goon phrase (Mai Sakurajima role required).")
async def mai(ctx: commands.Context) -> None:
    """Send a goon phrase if the caller has the Mai Sakurajima role."""
    required_role = "Mai Sakurajima"
    member = ctx.author
    has_role = any(role.name == required_role for role in getattr(member, "roles", []))
    if not has_role:
        await ctx.send("you arent a good enough boy")
        return

    await ctx.send(random.choice(GOON_PHRASES))


@BOT.command(name="blackjack", help="Play blackjack; bet your balance and settle winnings.")
async def blackjack(ctx: commands.Context) -> None:
    """Start a blackjack game with a bet chosen from a menu."""
    user_id = ctx.author.id
    WALLETS.ensure_user(user_id)
    balance = WALLETS.get_balance(user_id)
    if balance <= 0:
        await ctx.send("You are out of funds. No bets available.")
        return

    # Try to keep games out of public channels by DM'ing the selection; fall back to channel if DMs closed.
    try:
        dm_message = await ctx.author.send(
            f"Balance: ${balance}. Choose your bet to start blackjack (DM).",
            view=(view := BetSelectionView(ctx.author, balance, ctx, use_dm=True)),
        )
        view.message = dm_message
        await ctx.send("Check your DMs to start blackjack.")
    except discord.Forbidden:
        view = BetSelectionView(ctx.author, balance, ctx)
        message = await ctx.send(
            f"Balance: ${balance}. Choose your bet to start blackjack here.",
            view=view,
        )
        view.message = message


@BOT.command(name="leaderboard", help="Show top wallet balances.")
async def leaderboard(ctx: commands.Context) -> None:
    """Display the richest users."""
    balances = WALLETS.all_balances()
    if not balances:
        await ctx.send("No wallets yet.")
        return

    top = sorted(balances.items(), key=lambda item: item[1], reverse=True)[:10]
    lines = []
    guild = ctx.guild
    for idx, (user_id, amount) in enumerate(top, start=1):
        name = f"User {user_id}"
        if guild:
            member = guild.get_member(int(user_id))
            if not member:
                try:
                    member = await guild.fetch_member(int(user_id))
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    member = None
            if member:
                name = member.display_name
        lines.append(f"{idx}. {name}: ${amount}")

    await ctx.send("Top balances:\n" + "\n".join(lines))


@BOT.command(name="balance", help="Show your wallet balance.")
async def balance(ctx: commands.Context) -> None:
    """Display the caller's wallet balance."""
    user_id = ctx.author.id
    WALLETS.ensure_user(user_id)
    balance = WALLETS.get_balance(user_id)
    await ctx.send(f"Your balance: ${balance}.")


ADMIN_USER_ID = 722860021364293735
COIN_TARGET = 5
COIN_REWARD = 500


@BOT.command(name="givemoney", help="Admin-only: give money to a user.")
async def givemoney(
    ctx: commands.Context, member: discord.Member, amount: int
) -> None:
    """Transfer money to a user; restricted to the admin user ID."""
    if ctx.author.id != ADMIN_USER_ID:
        await ctx.send("You do not have permission to use this command.")
        return

    if amount <= 0:
        await ctx.send("Amount must be greater than 0.")
        return

    WALLETS.ensure_user(member.id)
    new_balance = WALLETS.adjust_balance(member.id, amount)
    await ctx.send(
        f"Gave ${amount} to {member.display_name}. New balance: ${new_balance}."
    )


@BOT.command(name="transfer", help="Transfer money to another user.")
async def transfer(ctx: commands.Context, member: discord.Member, amount: int) -> None:
    """Allow users to transfer funds between wallets."""
    if amount <= 0:
        await ctx.send("Amount must be greater than 0.")
        return

    sender_id = ctx.author.id
    recipient_id = member.id
    if sender_id == recipient_id:
        await ctx.send("You cannot transfer money to yourself.")
        return

    WALLETS.ensure_user(sender_id)
    WALLETS.ensure_user(recipient_id)
    balance = WALLETS.get_balance(sender_id)
    if amount > balance:
        await ctx.send(f"Insufficient funds. Your balance: ${balance}.")
        return

    WALLETS.adjust_balance(sender_id, -amount)
    new_balance = WALLETS.adjust_balance(recipient_id, amount)
    await ctx.send(
        f"Transferred ${amount} to {member.display_name}. "
        f"Your new balance: ${WALLETS.get_balance(sender_id)}. "
        f"{member.display_name}'s balance: ${new_balance}."
    )


@BOT.command(name="getmoney", help="Guess 5 coin flips in a row to earn $500.")
async def getmoney(ctx: commands.Context) -> None:
    """Coin flip streak game to earn a reward."""
    user_id = ctx.author.id
    WALLETS.ensure_user(user_id)

    view = CoinFlipView(ctx.author)
    message = await ctx.send(view._result_text(), view=view)
    view.message = message


# ---------------- Slash command equivalents ----------------


async def _display_name_from_id(
    guild: Optional[discord.Guild], user_id: int
) -> str:
    name = f"User {user_id}"
    if guild:
        member = guild.get_member(user_id)
        if not member:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        if member:
            name = member.display_name
    return name


@BOT.tree.command(name="mai", description="Send a goon phrase (Mai Sakurajima role required).")
async def slash_mai(interaction: discord.Interaction) -> None:
    required_role = "Mai Sakurajima"
    member = interaction.user
    has_role = any(role.name == required_role for role in getattr(member, "roles", []))
    if not has_role:
        await interaction.response.send_message("you arent a good enough boy")
        return
    await interaction.response.send_message(random.choice(GOON_PHRASES))


@BOT.tree.command(name="balance", description="Show your wallet balance.")
async def slash_balance(interaction: discord.Interaction) -> None:
    user_id = interaction.user.id
    WALLETS.ensure_user(user_id)
    balance = WALLETS.get_balance(user_id)
    await interaction.response.send_message(
        f"Your balance: ${balance}.", ephemeral=True
    )


@BOT.tree.command(name="leaderboard", description="Show top wallet balances.")
async def slash_leaderboard(interaction: discord.Interaction) -> None:
    balances = WALLETS.all_balances()
    if not balances:
        await interaction.response.send_message("No wallets yet.", ephemeral=True)
        return

    top = sorted(balances.items(), key=lambda item: item[1], reverse=True)[:10]
    lines = []
    for idx, (user_id, amount) in enumerate(top, start=1):
        name = await _display_name_from_id(interaction.guild, int(user_id))
        lines.append(f"{idx}. {name}: ${amount}")

    await interaction.response.send_message(
        "Top balances:\n" + "\n".join(lines), ephemeral=True
    )


@BOT.tree.command(name="givemoney", description="Admin-only: give money to a user.")
@app_commands.describe(member="User to receive money", amount="Amount to give")
async def slash_givemoney(
    interaction: discord.Interaction, member: discord.Member, amount: int
) -> None:
    if interaction.user.id != ADMIN_USER_ID:
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return
    if amount <= 0:
        await interaction.response.send_message(
            "Amount must be greater than 0.", ephemeral=True
        )
        return
    WALLETS.ensure_user(member.id)
    new_balance = WALLETS.adjust_balance(member.id, amount)
    await interaction.response.send_message(
        f"Gave ${amount} to {member.display_name}. New balance: ${new_balance}.",
        ephemeral=True,
    )


@BOT.tree.command(name="transfer", description="Transfer money to another user.")
@app_commands.describe(member="User to receive money", amount="Amount to transfer")
async def slash_transfer(
    interaction: discord.Interaction, member: discord.Member, amount: int
) -> None:
    if amount <= 0:
        await interaction.response.send_message(
            "Amount must be greater than 0.", ephemeral=True
        )
        return
    sender_id = interaction.user.id
    recipient_id = member.id
    if sender_id == recipient_id:
        await interaction.response.send_message(
            "You cannot transfer money to yourself.", ephemeral=True
        )
        return
    WALLETS.ensure_user(sender_id)
    WALLETS.ensure_user(recipient_id)
    balance = WALLETS.get_balance(sender_id)
    if amount > balance:
        await interaction.response.send_message(
            f"Insufficient funds. Your balance: ${balance}.", ephemeral=True
        )
        return
    WALLETS.adjust_balance(sender_id, -amount)
    new_balance = WALLETS.adjust_balance(recipient_id, amount)
    await interaction.response.send_message(
        f"Transferred ${amount} to {member.display_name}. "
        f"Your new balance: ${WALLETS.get_balance(sender_id)}. "
        f"{member.display_name}'s balance: ${new_balance}.",
        ephemeral=True,
    )


@BOT.tree.command(name="getmoney", description="Guess 5 coin flips in a row to earn $500.")
async def slash_getmoney(interaction: discord.Interaction) -> None:
    user_id = interaction.user.id
    WALLETS.ensure_user(user_id)
    view = CoinFlipView(interaction.user)
    await interaction.response.send_message(
        view._result_text(), view=view, ephemeral=True
    )
    view.message = await interaction.original_response()


@BOT.tree.command(name="blackjack", description="Play blackjack; choose your bet.")
async def slash_blackjack(interaction: discord.Interaction) -> None:
    user_id = interaction.user.id
    WALLETS.ensure_user(user_id)
    balance = WALLETS.get_balance(user_id)
    if balance <= 0:
        await interaction.response.send_message(
            "You are out of funds. No bets available.", ephemeral=True
        )
        return

    view = BetSelectionView(interaction.user, balance, None, use_dm=False, ephemeral=True)
    await interaction.response.send_message(
        f"Balance: ${balance}. Choose your bet to start blackjack.",
        view=view,
        ephemeral=True,
    )
    view.message = await interaction.original_response()


@BOT.tree.command(
    name="assign_task",
    description="Create a task thread and notify the assigned team members.",
)
@app_commands.describe(
    task_manager="Team member managing the task.",
    deadline="Deadline for the task (provide any preferred format).",
    description="Task summary; also used as the thread name.",
    difficulty="Difficulty level for the task.",
    person1="First assignee to mention in the task thread.",
    person2="Second assignee to mention in the task thread.",
    person3="Third assignee to mention in the task thread.",
    person4="Fourth assignee to mention in the task thread.",
    person5="Fifth assignee to mention in the task thread.",
    person6="Sixth assignee to mention in the task thread.",
    person7="Seventh assignee to mention in the task thread.",
)
async def assign_task(
    interaction: discord.Interaction,
    task_manager: discord.Member,
    deadline: str,
    description: str,
    difficulty: str,
    person1: Optional[discord.Member] = None,
    person2: Optional[discord.Member] = None,
    person3: Optional[discord.Member] = None,
    person4: Optional[discord.Member] = None,
    person5: Optional[discord.Member] = None,
    person6: Optional[discord.Member] = None,
    person7: Optional[discord.Member] = None,
) -> None:
    """Create a thread named after the description and post task details."""
    await interaction.response.defer(ephemeral=True)

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            "This command can only be used inside a standard text channel.",
            ephemeral=True,
        )
        return

    thread_name = description.strip() or "task-thread"
    if len(thread_name) > 100:
        thread_name = thread_name[:100]

    try:
        thread = await channel.create_thread(
            name=thread_name, type=discord.ChannelType.public_thread
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "I do not have permission to create a thread in this channel.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"Failed to create the task thread: {error}", ephemeral=True
        )
        return

    assignees = _collect_assignees(
        person1,
        person2,
        person3,
        person4,
        person5,
        person6,
        person7,
    )
    assignee_mentions = " ".join(member.mention for member in assignees)
    if not assignee_mentions:
        assignee_mentions = "_No additional assignees provided._"

    summary = (
        f"**Task Manager:** {task_manager.mention}\n"
        f"**Deadline:** {deadline}\n"
        f"**Description:** {description}\n"
        f"**Difficulty:** {difficulty}\n"
        f"**Assigned To:** {assignee_mentions}"
    )

    await thread.send(summary)

    await interaction.followup.send(
        f"Created task thread `{thread.name}` and notified the team.",
        ephemeral=True,
    )


def main() -> None:
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Set the DISCORD_BOT_TOKEN environment variable before starting the bot."
        )
    BOT.run(token)


if __name__ == "__main__":
    main()
