import os
import random
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

    def __init__(self) -> None:
        self.deck = self._build_deck()
        self.player_hands: List[List[str]] = [[self._draw_card(), self._draw_card()]]
        self.dealer_hand: List[str] = [self._draw_card(), self._draw_card()]
        self.finished = False
        self.winning_hand_count = 0
        self.result = ""
        self.current_hand_index = 0
        self.split_used = False
        self.hand_statuses: List[str] = ["playing"]  # playing, bust, stood, win, lose, push, blackjack
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
        self.current_hand_index = 0
        self.split_used = True
        return True

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
            if self.finished:
                label = status.upper()
            else:
                label = "PLAYING" if idx == self.current_hand_index else status.upper()
            lines.append(f"Hand {idx + 1} ({total}) [{label}]: {cards}")

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


class BlackjackView(discord.ui.View):
    """Interactive blackjack buttons for a single player."""

    def __init__(self, game: BlackjackGame, player: discord.Member) -> None:
        super().__init__(timeout=90)
        self.game = game
        self.player_id = player.id
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
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(
                    content=f"{self.game.render_state(reveal_dealer=False)}\n\nGame timed out.",
                    view=self,
                )
            except discord.HTTPException:
                pass

    def _disable_buttons(self) -> None:
        for child in self.children:
            child.disabled = True

    def _update_buttons(self) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if self.game.finished:
                child.disabled = True
            elif child.label == "Split":
                child.disabled = not self.game.can_split()
            else:
                child.disabled = False

    async def _send_rewards(self, interaction: discord.Interaction) -> None:
        for _ in range(self.game.winning_hand_count):
            await interaction.followup.send(random.choice(GOON_PHRASES))

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

        if self.game.finished and self.game.winning_hand_count:
            await self._send_rewards(interaction)

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

        if self.game.finished and self.game.winning_hand_count:
            await self._send_rewards(interaction)

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary, row=1)
    async def split_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not self.game.split():
            await interaction.response.send_message(
                "Split is not available right now.", ephemeral=True
            )
            return

        self._update_buttons()

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=False),
            view=self,
        )


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


@BOT.command(name="blackjack", help="Play blackjack; win to earn goon phrase(s).")
async def blackjack(ctx: commands.Context) -> None:
    """Start a blackjack game; only winners get goon phrase(s)."""
    game = BlackjackGame()

    # If blackjack is dealt immediately, resolve without buttons.
    if game.finished:
        await ctx.send(game.render_state(reveal_dealer=True))
        for _ in range(game.winning_hand_count):
            await ctx.send(random.choice(GOON_PHRASES))
        return

    view = BlackjackView(game, ctx.author)
    message = await ctx.send(game.render_state(reveal_dealer=False), view=view)
    view.message = message


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
