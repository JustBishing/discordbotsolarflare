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
    """Simple blackjack game logic for a single player vs. dealer."""

    def __init__(self) -> None:
        self.deck = self._build_deck()
        self.player_hand: List[str] = [self._draw_card(), self._draw_card()]
        self.dealer_hand: List[str] = [self._draw_card(), self._draw_card()]
        self.finished = False
        self.player_won = False
        self.result = ""
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

    @property
    def player_total(self) -> int:
        return self._hand_value(self.player_hand)

    @property
    def dealer_total(self) -> int:
        return self._hand_value(self.dealer_hand)

    def _check_initial_blackjack(self) -> None:
        if self.player_total == 21 and self.dealer_total == 21:
            self.finished = True
            self.result = "Both you and the dealer have blackjack. Push."
            return

        if self.player_total == 21:
            self.finished = True
            self.player_won = True
            self.result = "Blackjack! You win."
            return

        if self.dealer_total == 21:
            self.finished = True
            self.player_won = False
            self.result = "Dealer has blackjack. You lose."

    def player_hit(self) -> None:
        self.player_hand.append(self._draw_card())
        if self.player_total > 21:
            self.finished = True
            self.result = "Bust! You lose."

    def player_stand(self) -> None:
        self._dealer_play()
        self._determine_winner()

    def _dealer_play(self) -> None:
        while self.dealer_total < 17:
            self.dealer_hand.append(self._draw_card())

    def _determine_winner(self) -> None:
        self.finished = True
        player = self.player_total
        dealer = self.dealer_total

        if dealer > 21:
            self.player_won = True
            self.result = "Dealer busts. You win!"
            return

        if player > dealer:
            self.player_won = True
            self.result = "You win!"
        elif player == dealer:
            self.player_won = False
            self.result = "Push. No goon phrase this time."
        else:
            self.player_won = False
            self.result = "Dealer wins."

    def render_state(self, reveal_dealer: bool) -> str:
        player_cards = " ".join(self._fmt_card(card) for card in self.player_hand)
        if reveal_dealer:
            dealer_cards = " ".join(self._fmt_card(card) for card in self.dealer_hand)
            dealer_label = f"Dealer ({self.dealer_total}): {dealer_cards}"
        else:
            dealer_cards = f"{self._fmt_card(self.dealer_hand[0])} ??"
            dealer_label = f"Dealer showing: {dealer_cards}"

        body = (
            "win this game like a good boy.\n"
            "```\n"
            f"Your ({self.player_total}): {player_cards}\n"
            f"{dealer_label}\n"
            "```"
        )

        if self.finished:
            body += f"\n{self.result}"
        else:
            body += "\nHit or Stand with the buttons below."

        return body


class BlackjackView(discord.ui.View):
    """Interactive blackjack buttons for a single player."""

    def __init__(self, game: BlackjackGame, player: discord.Member) -> None:
        super().__init__(timeout=90)
        self.game = game
        self.player_id = player.id
        self.message: Optional[discord.Message] = None

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

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.game.player_hit()
        reveal = self.game.finished
        if self.game.finished:
            self._disable_buttons()

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=reveal),
            view=self,
        )

        if self.game.finished and self.game.player_won:
            await interaction.followup.send(random.choice(GOON_PHRASES))

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.game.player_stand()
        self._disable_buttons()

        await interaction.response.edit_message(
            content=self.game.render_state(reveal_dealer=True),
            view=self,
        )

        if self.game.player_won:
            await interaction.followup.send(random.choice(GOON_PHRASES))


def _collect_assignees(*members: Optional[discord.Member]) -> List[discord.Member]:
    """Return only the members that were provided to the command."""
    return [member for member in members if member is not None]


@BOT.event
async def on_ready() -> None:
    """Sync slash commands once the bot is ready."""
    await BOT.tree.sync()
    print(f"Logged in as {BOT.user} (ID: {BOT.user.id})")


@BOT.command(name="mai", help="Play blackjack; win to earn a goon phrase.")
async def mai(ctx: commands.Context) -> None:
    """Start a blackjack game; only winners get a goon phrase."""
    game = BlackjackGame()

    # If blackjack is dealt immediately, resolve without buttons.
    if game.finished:
        await ctx.send(game.render_state(reveal_dealer=True))
        if game.player_won:
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
