import discord
from discord import app_commands
from discord.utils import get
from help_queue import HelpQueue
from ui.views.queue_view import QueueView
from ui.views.ta_view import TAView
from ui.helpers.constants import HELP_CHANNEL_NAME, TA_TEXT_CHANNEL_NAME, TA_VOICE_CHANNEL_NAME
from ui.helpers.discord_helpers import update_queue_messages, count_total_tas_in_voice
from records import QueueEntry
from datetime import datetime
from db import daily_reset, auto_queue_scheduler

import os
import random
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv(".env")

intents = discord.Intents.default()
intents.message_content = True

class Bot(discord.Client):
    """
    The core bot client that manages the help queue, UI views, and scheduled tasks.
    Extends discord.Client to handle queue interactions and audio notifications.
    """
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.queue: HelpQueue = HelpQueue()
        self.queue_status_message_id: int | None = None
        self.help_queue_count_message_id: int | None = None
        self._player_task: Optional[asyncio.Task] = None
        self.help_map: map[str, int] = {}

    async def setup_hook(self):
        """
        Initializes bot UI components (views) and starts background scheduling tasks 
        before the bot fully connects to Discord.
        """
        self.add_view(QueueView())
        self.add_view(TAView())
        daily_reset.start()
        auto_queue_scheduler.start(self) 
        asyncio.create_task(self._refresh_queue_status_messages())       
        await self.tree.sync()

    async def on_ready(self):
        await update_queue_messages(self)
        # ensure player task isn't left running accidentally
        if self._player_task is None and getattr(self.queue, 'entries', None):
            # start player only if queue not empty
            if len(self.queue.entries) > 0:
                self._player_task = asyncio.create_task(self._play_notifications())

    async def _get_ta_voice_channel(self) -> discord.VoiceChannel | None:
        for guild in self.guilds:
            return get(guild.voice_channels, name=TA_VOICE_CHANNEL_NAME)
            

    async def _play_notifications(self) -> None:
        """Join TA voice channel and play random mp3 from resources once per minute until queue empty."""
        try:
            resources_dir = os.path.join(os.path.dirname(__file__), "resources")
        except Exception:
            resources_dir = None

        while True:
            async with self.queue.lock:
                empty = len(self.queue.entries) == 0
            if empty:
                break

            channel = await self._get_ta_voice_channel()
            if channel is None:
                await asyncio.sleep(60)
                continue

            try:
                # connect if not connected
                vc = channel.guild.voice_client
                if vc is None:
                    vc = await channel.connect()

                # choose random mp3
                chosen = None
                if resources_dir and os.path.isdir(resources_dir):
                    files = [f for f in os.listdir(resources_dir) if f.lower().endswith('.mp3')]
                    if files:
                        chosen = os.path.join(resources_dir, random.choice(files))

                if chosen:
                    if vc.is_playing():
                        vc.stop()
                    source = discord.FFmpegPCMAudio(chosen)
                    vc.play(source)
                    # wait until finished or 60s
                    waited = 0
                    while vc.is_playing() and waited < 120:
                        await asyncio.sleep(1)
                        waited += 1

                # wait one minute between plays
                await asyncio.sleep(60)
            except Exception as e:
                print(e.with_traceback())
                await asyncio.sleep(60)

        # queue empty, disconnect
        try:
            for guild in self.guilds:
                if guild.voice_client:
                    await guild.voice_client.disconnect()
        except Exception:
            pass

        self._player_task = None

    async def _get_ta_channel(self) -> discord.TextChannel | None:
        for guild in self.guilds:
            return get(guild.text_channels, name=TA_TEXT_CHANNEL_NAME)
        return None

    async def _get_help_channel(self) -> discord.TextChannel | None:
        for guild in self.guilds:
            return get(guild.text_channels, name=HELP_CHANNEL_NAME)
        return None
    
    async def _get_wait_time(self):
        if not self.queue.is_open:
            return ""

        ta_voice_channel = await self._get_ta_voice_channel()
        guild = ta_voice_channel.guild if ta_voice_channel else next(iter(self.guilds), None)
        num_tas = count_total_tas_in_voice(guild=guild)

        # compute expected wait time using recent queue history
        from service.queue_history_service import calculate_expected_wait_time
        async with self.queue.lock:
            queue_size = len(self.queue.entries)
        time = calculate_expected_wait_time(num_tas, queue_size)
        time = max(time, 180)
        minutes = int(time // 60)
        seconds = time % 60
        return f" — expected wait: {minutes}m {seconds}s"
    
    async def _build_student_status_message(self) -> str:
        status = "OPEN" if self.queue.is_open else "CLOSED"
        async with self.queue.lock:
            count = len(self.queue.entries)
        wait_text = await self._get_wait_time()
        return f"**Help Queue Status: {status} — {count} student{'s' if count != 1 else ''} in queue{wait_text}**"


    async def _build_ta_status_message(self) -> str:
        status = "OPEN" if self.queue.is_open else "CLOSED"
        queue_text = await self.queue.view()
        wait_text = await self._get_wait_time()

        return f"**Help Queue Status: {status}{wait_text}**\n{queue_text}"

    async def _get_ta_status_message(self) -> discord.Message | None:
        ta_channel = await self._get_ta_channel()
        if ta_channel is None:
            return None

        if self.queue_status_message_id is not None:
            try:
                return await ta_channel.fetch_message(self.queue_status_message_id)
            except discord.NotFound:
                self.queue_status_message_id = None

        async for message in ta_channel.history(limit=50):
            if message.author == self.user and message.content.startswith("**Help Queue Status:"):
                self.queue_status_message_id = message.id
                return message

        status_message = await ta_channel.send(await self._build_ta_status_message())
        self.queue_status_message_id = status_message.id
        return status_message

    async def _get_student_status_message(self) -> discord.Message | None:
        help_channel = await self._get_help_channel()
        if help_channel is None:
            return None

        if self.help_queue_count_message_id is not None:
            try:
                return await help_channel.fetch_message(self.help_queue_count_message_id)
            except discord.NotFound:
                self.help_queue_count_message_id = None

        async for message in help_channel.history(limit=50):
            if message.author == self.user and message.content.startswith("**Help Queue Status:"):
                self.help_queue_count_message_id = message.id
                return message

        count_message = await help_channel.send(await self._build_student_status_message())
        self.help_queue_count_message_id = count_message.id
        return count_message

    async def update_ta_status_message(self) -> None:
        ta_status_message = await self._get_ta_status_message()
        if ta_status_message is None:
            return

        await ta_status_message.edit(content=await self._build_ta_status_message())

    async def update_student_status_message(self) -> None:
        student_status_message = await self._get_student_status_message()
        if student_status_message is None:
            return

        await student_status_message.edit(content=await self._build_student_status_message())

    async def _refresh_queue_status_messages(self) -> None:
        while not self.is_closed():
            try:
                await asyncio.sleep(60)
                await update_queue_messages(self)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Queue refresh task error: {e}")


    async def queue_handler(self, interaction: discord.Interaction, question, is_passoff, in_person, student_name: str):
        """
        Processes a new request to join the help queue, creates a QueueEntry, 
        updates the UI, and triggers the audio notification system if needed.

        Args:
            interaction (discord.Interaction): The user interaction context.
            question (str): The student's question or issue details.
            is_passoff (bool): Indicates if this is a required pass-off assignment.
            in_person (bool): Indicates if the student is physically present.
            student_name (str): The student's actual name.
        """
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
        await update_queue_messages(self)
        # start playing notifications while queue has entries
        async with self.queue.lock:
            had = len(self.queue.entries) > 0
        if had and (self._player_task is None or self._player_task.done()):
            self._player_task = asyncio.create_task(self._play_notifications())


bot = Bot()

@bot.tree.command(name="queue")
async def queue_panel(interaction: discord.Interaction):
    await interaction.response.send_message(
        view=QueueView()
    )

@bot.tree.command(name="ta")
async def ta_panel(interaction: discord.Interaction):
    await interaction.response.send_message(
        view=TAView()
    )

token: str = os.getenv("TOKEN")
bot.run(token)