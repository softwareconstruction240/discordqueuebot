import discord
from discord import app_commands
from discord.utils import get
from help_queue import HelpQueue
from ui.views.queue_view import QueueView
from ui.views.ta_view import TAView
from ui.helpers.constants import Channels
from ui.helpers.discord_helpers import update_queue_messages, count_total_tas_in_voice
from server_script import setup_server
from records import QueueEntry
from datetime import datetime, UTC
from data_access.db_manager import db_manager
from data_access.user_stats_dao import daily_reset
from data_access.queue_history_dao import set_time_finished
from data_access.config_dao import auto_queue_scheduler
from data_access.server_info_dao import get_id

import os
import random
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv("./resources/.env")

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
        self.help_map: map[str, tuple[int, int]] = {}

    async def setup_hook(self):
        """
        Initializes bot UI components (views) and starts background scheduling tasks 
        before the bot fully connects to Discord.
        """
        await db_manager.connect()
        self.add_view(QueueView())
        self.add_view(TAView())
        daily_reset.start()
        auto_queue_scheduler.start(self) 
        asyncio.create_task(self._refresh_queue_status_messages())    
        asyncio.create_task(self._refresh_help_map()) 
        await self.tree.sync()

    async def on_ready(self):
        for guild in self.guilds:
            await update_queue_messages(self, guild)
        # ensure player task isn't left running accidentally
        if self._player_task is None and getattr(self.queue, 'entries', None):
            # start player only if queue not empty
            if len(self.queue.entries) > 0:
                self._player_task = asyncio.create_task(self._play_notifications())

    async def _get_ta_voice_channel(self, guild: discord.Guild) -> discord.VoiceChannel | None:
        channel_id = get_id(Channels.TA_VOICE_CHANNEL_NAME, guild.id)
        return get(guild.voice_channels, id=channel_id)
            

    async def _play_notifications(self, guild: discord.Guild) -> None:
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

            channel = await self._get_ta_voice_channel(guild)
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

    async def _get_ta_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel_id = get_id(Channels.TA_TEXT_CHANNEL_NAME, guild.id)
        return get(guild.text_channels, id=channel_id)
        
    async def _get_help_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel_id = get_id(Channels.HELP_CHANNEL_NAME, guild.id)
        return get(guild.text_channels, id=channel_id)
    
    async def _get_wait_time(self, guild: discord.Guild):
        if not self.queue.is_open:
            return ""

        # compute expected wait time using recent queue history, available tas, and queue size
        num_tas = count_total_tas_in_voice(guild=guild)

        from service.queue_history_service import calculate_expected_wait_time, NoTasOnlineError
        async with self.queue.lock:
            queue_size = len(self.queue.entries)
        available_tas = num_tas - len(self.help_map.keys())
        
        #calculate wait time as if you were to join the queue right now
        try:
            time = calculate_expected_wait_time(num_tas, queue_size, available_tas, position=queue_size+1)
            minutes = int(time // 60)
            seconds = time % 60
            return f" — expected wait: {minutes}m {seconds}s"
        except NoTasOnlineError:
            return " — No TAs Online"
    
    async def _build_student_status_message(self, guild: discord.Guild) -> str:
        status = "OPEN" if self.queue.is_open else "CLOSED"
        async with self.queue.lock:
            count = len(self.queue.entries)
        wait_text = await self._get_wait_time(guild)
        return f"**Help Queue Status: {status} — {count} student{'s' if count != 1 else ''} in queue{wait_text}**"


    async def _build_ta_status_message(self, guild: discord.Guild) -> str:
        status = "OPEN" if self.queue.is_open else "CLOSED"
        queue_text = await self.queue.view()
        wait_text = await self._get_wait_time(guild)

        return f"**Help Queue Status: {status}{wait_text}**\n{queue_text}"

    async def _get_ta_status_message(self, guild: discord.Guild) -> discord.Message | None:
        ta_channel = await self._get_ta_channel(guild)
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

        status_message = await ta_channel.send(await self._build_ta_status_message(guild))
        self.queue_status_message_id = status_message.id
        return status_message

    async def _get_student_status_message(self, guild: discord.Guild) -> discord.Message | None:
        help_channel = await self._get_help_channel(guild)
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

        count_message = await help_channel.send(await self._build_student_status_message(guild))
        self.help_queue_count_message_id = count_message.id
        return count_message

    async def update_ta_status_message(self, guild: discord.Guild) -> None:
        ta_status_message = await self._get_ta_status_message(guild)
        if ta_status_message is None:
            return

        await ta_status_message.edit(content=await self._build_ta_status_message(guild))

    async def update_student_status_message(self, guild: discord.Guild) -> None:
        student_status_message = await self._get_student_status_message(guild)
        if student_status_message is None:
            return

        await student_status_message.edit(content=await self._build_student_status_message(guild))

    async def _refresh_queue_status_messages(self) -> None:
        while not self.is_closed():
            try:
                await asyncio.sleep(60)
                for guild in self.guilds:
                    await update_queue_messages(self, guild)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Queue refresh task error: {e}")

    async def _refresh_help_map(self) -> None:
        """Removes any TAs not currently online from the help_map to avoid problems with TAs forgetting to click "finish helping student"."""
        while True:
            try:
                await asyncio.sleep(60*20)
                
                # get all online TAs
                for guild in self.guilds:
                    online_ta_names = []
                    ta_role = get(guild.roles, name="TA")
                    for voice_channel in guild.voice_channels:
                        online_ta_names.extend([member.name for member in voice_channel.members if ta_role in getattr(member, "roles", [])])
                    
                # deduce which TAs should no longer be helping students
                tas_to_remove = []
                for name in self.help_map.keys():
                    if name not in online_ta_names:
                        tas_to_remove.append(name)
                
                # remove them from the help_map and update the db table
                for ta in tas_to_remove:
                    tableid, _ = self.help_map.pop(ta)
                    await set_time_finished(tableid)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Refresh Help map task error: {e}")



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
            timestamp=datetime.now(UTC),
            in_person=in_person
        )

        await self.queue.add(entry)
        await update_queue_messages(self, interaction.guild)
        # start playing notifications while queue has entries
        async with self.queue.lock:
            had = len(self.queue.entries) > 0
        if had and (self._player_task is None or self._player_task.done()):
            self._player_task = asyncio.create_task(self._play_notifications(interaction.guild))


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

@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        await setup_server(interaction)
    except PermissionError as e:
        await interaction.followup.send("Missing required permissions! See logs!")
        raise e
    except Exception as e:
        await interaction.followup.send("Some kind of unknown error occured!")
        raise e
    await interaction.followup.send("Setup complete! Bot is ready to go!")

# @bot.tree.command(name="reset")
# async def reset(interaction: discord.Interaction):
#     await interaction.response.defer(thinking=True, ephemeral=True)
#     await takedown(interaction)
#     try: 
#         await interaction.followup.send("Reset Complete!")
#     except discord.NotFound as e:
#         print(e.with_traceback(None))

    

token: str = os.getenv("TOKEN")
bot.run(token)