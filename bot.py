import discord
from discord import app_commands
from help_queue import HelpQueue
from ui import QueueView, TAView, get_channel
from records import QueueEntry
from datetime import datetime
from db import daily_reset

import os
from dotenv import load_dotenv

load_dotenv(".env")

intents = discord.Intents.default()
intents.message_content = True

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.queue: HelpQueue = HelpQueue()

    async def setup_hook(self):
        # guild = self.get_guild(1503856452027023451)
        # print(guild.name)
        # self.tree.copy_global_to(guild=guild)
        self.add_view(QueueView())
        self.add_view(TAView())
        daily_reset.start()
        await self.tree.sync()

    async def queue_handler(self, interaction: discord.Interaction, question, is_passoff, in_person, student_name: str):
        entry = QueueEntry(
            user_id=interaction.user.id,
            username=interaction.user.display_name,
            student_name=student_name,
            details=question,
            is_passoff=is_passoff,
            timestamp=datetime.now(),
            in_person=in_person
        )

        await self.queue.add(entry)

        pos = await self.queue.get_position(entry.user_id)

        await interaction.response.send_message(
            f"You are #{pos} in the queue.{f" Please join the {get_channel(interaction, "Waiting Room").mention} voice channel." if not in_person else ""}",
            ephemeral=True,
            delete_after=60*5
        )

bot = Bot()

@bot.tree.command(name="queue")
async def queue_panel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Queue Panel",
        view=QueueView()
    )

@bot.tree.command(name="ta")
async def ta_panel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "TA Panel",
        view=TAView()
    )

token: str = os.getenv("TOKEN")
bot.run(token)