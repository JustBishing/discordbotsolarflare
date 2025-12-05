import os
import random
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

import discord
from discord import app_commands
from discord.ext import commands


INTENTS = discord.Intents.default()
BOT = commands.Bot(command_prefix="!", intents=INTENTS)
GOON_PHRASES = [
    "https://tenor.com/view/mai-sakurajima-besto-waifui-luis301408-gif-22787686",
    "https://tenor.com/view/sakuta-azusagawa-mai-sakurajima-seishun-buta-yarou-wa-bunny-girl-senpai-no-yume-wo-minai-rascal-does-not-dream-funny-gif-2946009759168864042",
    "https://tenor.com/view/mai-sakurajima-anime-anime-girl-hug-bunny-girl-senpai-gif-3880306402977192551",
    "https://tenor.com/view/%D0%B7%D0%B0%D0%B9%D1%87%D0%B8%D0%BA-gif-21592153",
    "https://tenor.com/view/bunny-girl-senpai-mai-sakurajima-sakurajima-mai-gif-5717527464255844686",
    "https://tenor.com/view/rascal-does-not-dream-of-a-knapsack-kid-mai-sakurajima-buta-yarou-waking-up-gif-8618623992027128015",
    "https://tenor.com/view/mai-sakurajima-mai-bunny-girl-senpai-anime-cute-gif-17907056",
    "https://tenor.com/view/mai-sakurajima-bunny-girl-senpai-gif-24086478"
]


def _collect_assignees(*members: Optional[discord.Member]) -> List[discord.Member]:
    """Return only the members that were provided to the command."""
    return [member for member in members if member is not None]


@BOT.event
async def on_ready() -> None:
    """Sync slash commands once the bot is ready."""
    await BOT.tree.sync()
    print(f"Logged in as {BOT.user} (ID: {BOT.user.id})")


@BOT.tree.command(name="goon", description="Send a random goon message.")
async def goon(interaction: discord.Interaction) -> None:
    """Respond with a random mai gif"""
    await interaction.response.send_message(random.choice(GOON_PHRASES))


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
