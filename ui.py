from typing import Optional

import discord
from db import get_last_incident_info, increment_help, get_student_info, get_times_helped_today
from records import QueueEntry
from modals import HelpModal, PassoffModal, ClearConfirmModal, RemoveConfirmModal, BotIssueModal
from discord.utils import get as discord_get

# Constants to centralize configurable names/messages
HELP_CHANNEL_NAME = "help-queue-chat"
ONLINE_TAS_VC_NAME = "Online TAs"
IN_PERSON_CHANNEL_NAME = "In Person with Student"
WAITING_ROOM_NAME = "Waiting Room"
BREAKOUT_NAMES = ("Breakout Room A", "Breakout Room B", "Breakout Room C")
STUDENT_INFO_WIDTH = 25
NEXT_IN_LINE_MSG = "You are next in line! A TA will be with you shortly."
NEXT_IN_LINE_HELP_MSG = "You are next in line for help! A TA will be with you shortly."

# message timeouts
SHORT_TIMEOUT = 10
DEFAULT_TIMEOUT = 20
LONG_TIMEOUT = 60 * 5
OPEN_TTL = 60 * 60 * 4
CLOSE_TTL = 60 * 60 * 13

# Common response templates
NOW_HELPING_TEMPLATE = "{ta} is now helping {student}"
QUEUE_OPENED = "Queue opened."
QUEUE_CLOSED = "Queue closed."
QUEUE_ALREADY_OPEN = "Queue is already open!"
QUEUE_ALREADY_CLOSED = "Queue is already closed!"


class QueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Need Help", style=discord.ButtonStyle.primary, custom_id="need_help", emoji="🙏")
    async def help_btn(self, interaction: discord.Interaction, button):
        ok = await require_queue_open_and_not_in_queue(interaction)
        if not ok:
            return

        today_help_count = get_times_helped_today(interaction.user.id)
        await interaction.response.send_modal(HelpModal(today_help_count))

    @discord.ui.button(label="Passoff", style=discord.ButtonStyle.success, custom_id="passoff", emoji="💪")
    async def passoff_btn(self, interaction: discord.Interaction, button):
        ok = await require_queue_open_and_not_in_queue(interaction)
        if not ok:
            return

        await interaction.response.send_modal(PassoffModal())

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue", emoji="🚪")
    async def leave_btn(self, interaction: discord.Interaction, button):
        if await interaction.client.queue.is_in_queue(interaction.user.id):
            await interaction.client.queue.remove(interaction.user.id)
            await interaction.response.send_message("Removed from queue.", ephemeral=True, delete_after=DEFAULT_TIMEOUT)
        else:
            await interaction.response.send_message("You aren't currently in the queue", ephemeral=True, delete_after=SHORT_TIMEOUT)


    @discord.ui.button(label="My Position", style=discord.ButtonStyle.secondary, custom_id="my_position", emoji="📍")
    async def position_btn(self, interaction: discord.Interaction, button):
        pos = await interaction.client.queue.get_position(interaction.user.id)
        if pos is None:
            await interaction.response.send_message(
                "You are not currently in the queue",
                ephemeral=True,
                delete_after=DEFAULT_TIMEOUT,
            )
        else:
            await interaction.response.send_message(
                f"You are currently #{pos} in the queue",
                ephemeral=True,
                delete_after=DEFAULT_TIMEOUT,
            )

    @discord.ui.button(label="Report Bot Problem", style=discord.ButtonStyle.secondary, custom_id="report_bot_problem", emoji="☢️")
    async def report_bot_problem_btn(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(BotIssueModal())

class TAView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
    
    open_msg: str = "The Help Queue is now open!"
    close_msg: str = "The Help Queue is now closed. If you are still on the queue, the TAs will help until their hours are over."
    
    @discord.ui.button(label="Open Queue", style=discord.ButtonStyle.green, custom_id="open_queue", emoji="🔓")
    async def open(self, interaction: discord.Interaction, button: discord.Button):
        if not queue_is_open(interaction):
            interaction.client.queue.is_open = True
            await interaction.response.send_message(QUEUE_OPENED, ephemeral=True, delete_after=DEFAULT_TIMEOUT)
            help_channel = get_channel(interaction, HELP_CHANNEL_NAME)

            if help_channel and help_channel.last_message is not None and help_channel.last_message.content == self.close_msg:
                await help_channel.last_message.delete()
            if help_channel:
                await help_channel.send(self.open_msg, delete_after=OPEN_TTL)
            return
        else:
            await interaction.response.send_message(QUEUE_ALREADY_OPEN, ephemeral=True, delete_after=SHORT_TIMEOUT)

    @discord.ui.button(label="Close Queue", style=discord.ButtonStyle.red, custom_id="close_queue", emoji="🔏")
    async def close(self, interaction: discord.Interaction, button):
        if queue_is_open(interaction):
            interaction.client.queue.is_open = False
            await interaction.response.send_message(QUEUE_CLOSED, ephemeral=True, delete_after=DEFAULT_TIMEOUT)
            help_channel = get_channel(interaction, HELP_CHANNEL_NAME)
            if help_channel and help_channel.last_message is not None and help_channel.last_message.content == self.open_msg:
                await help_channel.last_message.delete()
            if help_channel:
                await help_channel.send(self.close_msg, delete_after=CLOSE_TTL)
            return
        else:
            await interaction.response.send_message(QUEUE_ALREADY_CLOSED, ephemeral=True, delete_after=SHORT_TIMEOUT)

    @discord.ui.button(label="View Queue", style=discord.ButtonStyle.secondary, custom_id="view_queue", emoji="👀")
    async def view_btn(self, interaction: discord.Interaction, button):
        text = await interaction.client.queue.view()
        await interaction.response.send_message(text, ephemeral=True, delete_after=DEFAULT_TIMEOUT)

    @discord.ui.button(label="Days Since Last Incident", style=discord.ButtonStyle.secondary, custom_id="days_since_incident", emoji="⚠️")
    async def days_since_incident_btn(self, interaction: discord.Interaction, button):
        days, issue_text = get_last_incident_info()
        if days is None:
            message = "No incidents have been reported yet."
        elif days == 1:
            message = f"1 day since last incident. Description: {issue_text or 'No description provided.'}"
        else:
            message = f"{days} days since last incident. Description: {issue_text or 'No description provided.'}"

        await interaction.response.send_message(message, ephemeral=True, delete_after=DEFAULT_TIMEOUT)

    @discord.ui.button(label="Student Info", style=discord.ButtonStyle.secondary, custom_id="student_info", emoji="📝")
    async def student_info(self, interaction: discord.Interaction, button):
        headers, rows = get_student_info()
        width = STUDENT_INFO_WIDTH
        def row_to_line(items):
            return "| ".join(fixed_width(str(x), width) for x in items)

        divider = "-" * (width * len(headers) + 3 * (len(headers)-1))
        body = "\n".join(row_to_line(r) for r in rows)
        builder = f"```Student Info:\n{row_to_line(headers)}\n{divider}\n{body}```"
        await interaction.response.send_message(builder, ephemeral=True, delete_after=LONG_TIMEOUT)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, custom_id="next", emoji="➡️")
    async def next(self, interaction: discord.Interaction, button):
        entry: Optional[QueueEntry] = await interaction.client.queue.next()

        if not entry:
            return await interaction.response.send_message("Queue is empty.", ephemeral=True, delete_after=SHORT_TIMEOUT)

        if not entry.is_passoff:
            increment_help(entry.user_id, entry.username, entry.student_name)

        await move_to_breakout(interaction, entry)

        # Notify the next student in line
        next_entry = await interaction.client.queue.get_front()
        if next_entry:
            await safe_dm_user(interaction.client, next_entry.user_id, NEXT_IN_LINE_MSG)


        # Getting an unknown response here :/
        if not interaction.response.is_done():
            await interaction.response.send_message(NOW_HELPING_TEMPLATE.format(ta=interaction.user.display_name, student=entry.username), delete_after=DEFAULT_TIMEOUT)

    @discord.ui.button(label="Next Online", style=discord.ButtonStyle.blurple, custom_id="next_online", emoji="💻")
    async def next_online(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get who was at front before removal
        front_before = await interaction.client.queue.get_front()
        entry: Optional[QueueEntry] = await interaction.client.queue.next(online_only=True)

        if not entry:
            return await interaction.response.send_message("No online students in the queue.", ephemeral=True, delete_after=SHORT_TIMEOUT)

        if not entry.is_passoff:
            increment_help(entry.user_id, entry.username, entry.student_name)

        await move_to_breakout(interaction, entry)

        # Notify the next student in line only if they changed
        await notify_next_if_changed(interaction.client, front_before)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                NOW_HELPING_TEMPLATE.format(ta=interaction.user.display_name,
                    student=entry.username), 
                    delete_after=DEFAULT_TIMEOUT
            )

    
    @discord.ui.button(label="Next Passoff", style=discord.ButtonStyle.blurple, custom_id="next_passoff", emoji="✅")
    async def next_passoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get who was at front before removal
        front_before = await interaction.client.queue.get_front()

        entry: Optional[QueueEntry] = await interaction.client.queue.next(passoff_only=True)

        if not entry:
            return await interaction.response.send_message("No students awaiting passoff.", ephemeral=True, delete_after=SHORT_TIMEOUT)

        await move_to_breakout(interaction, entry)

        # Notify the next student in line only if they changed
        await notify_next_if_changed(interaction.client, front_before)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                NOW_HELPING_TEMPLATE.format(ta=interaction.user.display_name, student=entry.username), 
                delete_after=DEFAULT_TIMEOUT
            )


    @discord.ui.button(label="Next Online Passoff", style=discord.ButtonStyle.blurple, custom_id="next_online_passoff", emoji="☑️")
    async def next_online_passoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get who was at front before removal
        front_before = await interaction.client.queue.get_front()
        entry: Optional[QueueEntry] = await interaction.client.queue.next(passoff_only=True, online_only=True)

        if not entry:
            return await interaction.response.send_message("No online students awaiting passoff.", ephemeral=True, delete_after=SHORT_TIMEOUT)

        await move_to_breakout(interaction, entry)

        # Notify the next student in line only if they changed
        await notify_next_if_changed(interaction.client, front_before)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                NOW_HELPING_TEMPLATE.format(ta=interaction.user.display_name, student=entry.username), 
                delete_after=DEFAULT_TIMEOUT
            )



    @discord.ui.button(label="Clear Queue", style=discord.ButtonStyle.danger, custom_id="clear_queue", emoji="💥")
    async def clear_queue(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(ClearConfirmModal())

    @discord.ui.button(label="Remove Student", style=discord.ButtonStyle.danger, custom_id="remove_from_queue", emoji="🗑️")
    async def remove_from_queue(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(RemoveConfirmModal())

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.green, custom_id="finish", emoji="🔚")
    async def finish_button(self, interaction: discord.Interaction, button):
        online_ta_vc: discord.VoiceChannel = get_channel(interaction, ONLINE_TAS_VC_NAME)

        try:
            ta_voice_state: discord.VoiceState = await interaction.user.fetch_voice()
            voice_channel: discord.VoiceChannel = ta_voice_state.channel
        except Exception:
            await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True, delete_after=SHORT_TIMEOUT)
            return
        
        if voice_channel == online_ta_vc:
            await interaction.response.send_message("You're not currently helping anyone!", ephemeral=True, delete_after=SHORT_TIMEOUT)
            return
        

        ta_role: discord.Role = get_role(interaction, "TA")
        for member in voice_channel.members:
            if ta_role in member.roles:
                continue
            else:
                await member.move_to(None)
        await interaction.user.move_to(online_ta_vc)
        await interaction.response.defer(thinking=False)


def fixed_width(text: str, width: int) -> str:
    if len(text) > width:
        return text[:width - 3] + "..."
    
    return text.ljust(width)

def queue_is_open(interaction: discord.Interaction)->bool:
    return interaction.client.queue.is_open

async def already_in_queue(interaction: discord.Interaction)->bool:
    return await interaction.client.queue.is_in_queue(interaction.user.id)

def get_channel(interaction: discord.Interaction, channel_name: str) -> Optional[discord.abc.GuildChannel]:
    return discord_get(interaction.guild.channels, name=channel_name)


def get_role(interaction: discord.Interaction, role_name: str) -> Optional[discord.Role]:
    return discord_get(interaction.guild.roles, name=role_name)

def get_next_available_breakout(interaction: discord.Interaction):
    for vc in interaction.guild.voice_channels:
        if vc.name in BREAKOUT_NAMES and vc.members == []:
            return vc

    return None

async def safe_dm_user(client: discord.Client, user_id: int, message: str) -> None:
    try:
        user = await client.fetch_user(user_id)
        await user.send(message)
    except Exception:
        return


async def require_queue_open_and_not_in_queue(interaction: discord.Interaction) -> bool:
    if not queue_is_open(interaction):
        await interaction.response.send_message("Queue is closed.", ephemeral=True, delete_after=20)
        return False

    if await already_in_queue(interaction):
        await interaction.response.send_message("You are already in the queue.", ephemeral=True, delete_after=10)
        return False

    return True


async def notify_next_if_changed(client: discord.Client, before: Optional[QueueEntry]) -> None:
    after = await client.queue.get_front()
    if before and after and before.user_id != after.user_id:
        await safe_dm_user(client, after.user_id, NEXT_IN_LINE_MSG)
async def move_to_breakout(interaction: discord.Interaction, entry: QueueEntry):
    student: discord.Member = interaction.guild.get_member(entry.user_id)
    if student is None:
        student: discord.User = await interaction.client.fetch_user(entry.user_id)
    ta: discord.Member = interaction.guild.get_member(interaction.user.id)
    if ta is None:
        ta: discord.User = interaction.user
    if entry.in_person:
        try:
            await ta.move_to(get_channel(interaction, IN_PERSON_CHANNEL_NAME))
        except Exception:
            await ta.send("Because you weren't in the Online TAs voice channel, you need to join the In Person with Student channel manually. Please do so now.")

    else:
        breakout_channel: discord.VoiceChannel = get_next_available_breakout(interaction)
        if breakout_channel is None: 
            interaction.response.send_message("No breakout rooms available at this time. Tough luck.", ephemeral=True, delete_after=SHORT_TIMEOUT)
        
        try:
            await ta.move_to(breakout_channel)
        except Exception:
            await ta.send(f"Because you didn't join the Online TAs voice channel, you need to join {breakout_channel.mention} manually. Please do so now, the student is waiting.")

        try:
            await student.move_to(breakout_channel)
        except Exception:
            await student.send(f"Because you didn't join the Waiting Room voice channel, you need to join {breakout_channel.mention} manually. Please do so now, the TA is waiting.")
