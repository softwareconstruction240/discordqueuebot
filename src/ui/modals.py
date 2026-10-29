import discord
from discord.utils import get

from data_access.bot_incidents_dao import record_bot_issue
from data_access.config_dao import (
    set_devotional_hours,
    set_queue_times,
    set_saturday_hours,
    set_ta_meeting,
)
from data_access.queue_history_dao import get_times_helped_today
from data_access.server_info_dao import get_id
from data_access.students_dao import set_registered_name
from records import format_phase
from ui.helpers.constants import Channels, Messages, Roles
from ui.helpers.discord_helpers import notify_next_if_changed, update_queue_messages
from ui.helpers.queue_helpers import sanitize_details


class QueueRequestModal(discord.ui.Modal, title="Queue Request"):
    name = discord.ui.TextInput(
        label="Your name (as it appears in Canvas)",
        placeholder="John D. Fortnite",
        max_length=100
    )

    online_label = discord.ui.Label(
        text="Where are you?",
        component=discord.ui.Select(
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Remote", value="o"),
                discord.SelectOption(label="TA Office (1066 TMCB)", value="p")
            ]
        )
    )

    def __init__(self, default_name: str | None = None):
        super().__init__()
        if default_name:
            self.name.default = default_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        phase_select: discord.ui.Select = self.phase_label.component
        selected_phase = phase_select.values[0]

        online_select: discord.ui.Select = self.online_label.component
        selected_location = online_select.values[0]

        student_name = self.name.value.strip()
        await set_registered_name(interaction.user.id, student_name)
        try:
            await interaction.user.edit(nick=student_name)
        except discord.HTTPException as e:
            print(f"Could not update nickname for {interaction.user.display_name}: {e}")

        await interaction.client.queue_handler(
            interaction,
            self.queue_details,
            self.is_passoff,
            selected_location == "p",
            student_name,
            selected_phase
        )

        pos = await interaction.client.queue.get_position(interaction.user.id)

        waiting_room_id = await get_id(Channels.WAITING_ROOM_NAME, interaction.guild.id)
        waiting_room: discord.VoiceChannel = get(interaction.guild.voice_channels, id=waiting_room_id)
        voice_message = (
            f" Please join the {waiting_room.mention} voice channel."
            if selected_location != "p"
            else ""
        )

        msg = await interaction.followup.send(
            f"You are #{pos} in the queue.{voice_message}",
            ephemeral=True,
            wait=True
        )

        channel_id = await get_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id)
        ta_channel: discord.TextChannel = get(interaction.guild.text_channels, id=channel_id)
        await self.send_ta_notification(
            ta_channel,
            interaction,
            student_name,
            selected_phase,
            selected_location,
        )

        await msg.delete(delay=60)

    @property
    def queue_details(self) -> str:
        raise NotImplementedError

    @property
    def is_passoff(self) -> bool:
        raise NotImplementedError

    async def send_ta_notification(
        self,
        ta_channel: discord.TextChannel,
        interaction: discord.Interaction,
        student_name: str,
        selected_phase: str,
        selected_location: str,
    ) -> None:
        raise NotImplementedError


class HelpModal(QueueRequestModal, title="Request Help"):
    phase_label = discord.ui.Label(text="Pick the phase you need help with", component=discord.ui.Select(min_values=1, max_values=1, options=[
        discord.SelectOption(label="Phase 0", value="0"),
        discord.SelectOption(label="Phase 1", value="1"),
        discord.SelectOption(label="Phase 2", value="2"),
        discord.SelectOption(label="Phase 3", value="3"),
        discord.SelectOption(label="Phase 4", value="4"),
        discord.SelectOption(label="Phase 5", value="5"),
        discord.SelectOption(label="Phase 6", value="6"),
        discord.SelectOption(label="Programming Exam", value="E"),
        discord.SelectOption(label="GitHub Repository Assignment", value="G"),
        discord.SelectOption(label="Misc", value="?")
    ]))

    display = discord.ui.TextDisplay(content="Loading data...")

    question = discord.ui.TextInput(
        label="What do you need help with?",
        placeholder="Please enter more than just the phase you are currently working on :)",
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    def __init__(self, times_helped: int, default_name: str | None = None):
        super().__init__(default_name)
        display_text = (
            f"You've been helped {times_helped} time{'s' if times_helped != 1 else ''} today."
        )
        if times_helped >= 2:
            display_text += (
                "\nWarning: the max times you can be helped in a day is 3, "
                "but TAs may still help you if they think it is necessary."
            )
        self.display.content = display_text

    @property
    def queue_details(self) -> str:
        return sanitize_details(self.question.value)

    @property
    def is_passoff(self) -> bool:
        return False

    async def send_ta_notification(
        self,
        ta_channel: discord.TextChannel,
        interaction: discord.Interaction,
        student_name: str,
        selected_phase: str,
        selected_location: str,
    ) -> None:
        times_helped = await get_times_helped_today(interaction.user.id)
        mode = "In-person" if selected_location == "p" else "Online"
        await ta_channel.send(
            f"{student_name} (<@!{interaction.user.id}>) has joined the help queue - {mode} - "
            f"{format_phase(selected_phase)} - {self.queue_details} "
            f"(helped {times_helped} time{'s' if times_helped != 1 else ''} today)",
            delete_after=30
        )


class PassoffModal(QueueRequestModal, title="Request Passoff"):
    phase_label = discord.ui.Label(text="Pick the phase you will be passing off", component=discord.ui.Select(min_values=1, max_values=1, options=[
        discord.SelectOption(label="Phase 5", value="5"),
        discord.SelectOption(label="Phase 6", value="6"),
    ]))

    @property
    def queue_details(self) -> str:
        return "Passoff"

    @property
    def is_passoff(self) -> bool:
        return True

    async def send_ta_notification(
        self,
        ta_channel: discord.TextChannel,
        interaction: discord.Interaction,
        student_name: str,
        selected_phase: str,
        selected_location: str,
    ) -> None:
        mode = "In Person" if selected_location == "p" else "Online"
        await ta_channel.send(
            f"{student_name} (<@!{interaction.user.id}>) has requested a passoff - "
            f"{mode} - {format_phase(selected_phase)}",
            delete_after=30
        )

class BotIssueModal(discord.ui.Modal, title="Report Bot Problem"):
    description = discord.ui.TextInput(
        label="Describe the issue",
        placeholder="Describe what is going wrong with the bot.",
        style=discord.TextStyle.paragraph,
        max_length=500,
        min_length=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        msg = await interaction.followup.send("The TAs have been notified. They will reach out to you if needed.", ephemeral=True, wait=True)

        issue_text = self.description.value.strip()
        await record_bot_issue(interaction.user.mention, issue_text)
        ta_role = get(interaction.guild.roles, name="TA")
        ta_mention = ta_role.mention
        id: int = await get_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id)
        channel = get(interaction.guild.text_channels, id=id)
        await channel.send(
            f"ATTENTION {ta_mention}!\n{interaction.user.mention} is having trouble with the bot! Description: {issue_text}"
        )
        await msg.delete(delay=Messages.DEFAULT_TIMEOUT)


class ClearConfirmModal(discord.ui.Modal, title="Clear Confirmation"):
    warning = discord.ui.TextDisplay("Are you sure? This will remove all students from the queue, and cannot be undone.")
    confirmation = discord.ui.TextInput(label="Please confirm", placeholder="y/n", max_length=1)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if self.confirmation.value.lower() != 'y':
            msg = await interaction.followup.send("Clear aborted", ephemeral=True, wait=True)
            await msg.delete(delay=Messages.SHORT_TIMEOUT)
        else:
            await interaction.client.queue.clear()
            await update_queue_messages(interaction.client, interaction.guild)

            msg = await interaction.followup.send("Queue cleared!", wait=True)
            channel_id: int = await get_id(Channels.HELP_CHANNEL_NAME, interaction.guild.id)
            channel: discord.TextChannel = get(interaction.guild.text_channels, id=channel_id)
            await channel.send("All students have been removed from the queue. Sorry we couldn't get to you!", delete_after=60*10)
            
            await msg.delete(delay=Messages.LONG_TIMEOUT)


class RemoveConfirmModal(discord.ui.Modal, title="Removal Confirmation"):
    reason: discord.ui.TextInput = discord.ui.TextInput(
        label="Provide a reason (optional)",
        placeholder="You've used the queue too many times today",
        required=False,
        max_length=200
    )

    def __init__(self, student_user_id: int, student_name: str):
        super().__init__()
        self.student_user_id = student_user_id
        self.student_name = student_name
        self.add_item(discord.ui.TextDisplay(
            f"This will remove {student_name} from the queue."
        ))

    async def on_submit(self, interaction: discord.Interaction):
        response: discord.InteractionCallbackResponse = await interaction.response.defer(thinking=True, ephemeral=True)
        front_before = await interaction.client.queue.get_front()
        user: discord.User = await interaction.client.fetch_user(self.student_user_id)
        await interaction.client.queue.remove(self.student_user_id)
        await update_queue_messages(interaction.client, interaction.guild)

        await notify_next_if_changed(interaction.client, front_before)
        reason_suffix = f" Reason: {self.reason.value}" if self.reason.value else ""
        await user.send(
            f"You have been removed from the CS240 help queue.{reason_suffix}"
        )
        await interaction.channel.send(
            f"{user.mention} has been removed from the queue by {interaction.user.mention}.",
            delete_after=Messages.LONG_TIMEOUT
        )
        await response.resource.delete()



class EditQueueHoursModal(discord.ui.Modal, title="Edit Queue Hours"):
    open = discord.ui.TextInput(
        label="Weekday Open Time (24-hour time)",
        placeholder="08:00",
        min_length=3,
        max_length=5
    )
    close = discord.ui.TextInput(
        label="Weekday Close Time (24-hour time)",
        placeholder="20:00",
        min_length=3,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            open_h, open_m = [int(time) for time in self.open.value.split(":")]
            close_h, close_m = [int(time) for time in self.close.value.split(":")]
            
            if not (0 <= open_h <= 23 and 0 <= open_m <= 59 and 0 <= close_h <= 23 and 0 <= close_m <= 59):
                msg = await interaction.followup.send(
                    "Hours must be 0-23 and minutes must be 0-59.",
                    ephemeral=True,
                    wait=True
                ) 
                await msg.delete(delay=Messages.SHORT_TIMEOUT)
                return
            
            await set_queue_times(open_h, open_m, close_h, close_m)
            ta_role_id = await get_id(Roles.TA_ROLE, interaction.guild.id)
            ta_role = get(interaction.guild.roles, id=ta_role_id)
            await interaction.followup.send(
                f"{ta_role.mention} ANNOUNCEMENT: Queue hours updated: Opens at {open_h:02d}:{open_m:02d}, closes at {close_h:02d}:{close_m:02d}",
                ephemeral=False
            )
        except ValueError:
            msg = await interaction.followup.send(
                "Input should be in the following format: `##:##`. Please enter valid integers for hours and minutes.",
                ephemeral=True,
                wait=True
            )
            await msg.delete(delay=Messages.SHORT_TIMEOUT)

class EditMeetingHoursModal(discord.ui.Modal, title="Edit TA Meeting Hours"):
    day = discord.ui.TextInput(label="Day of Meeting", placeholder="Mon/Tue/Wed/Thu/Fri", min_length=3, max_length=3, required=True)
    time = discord.ui.TextInput(label="Meeting Time (24-hour time)", placeholder="12:00", required=True, min_length=3, max_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            day = self.day.value.upper()
            hour, minute = [int(value) for value in self.time.value.split(":")]
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and day in ("MON", "TUE", "WED", "THU", "FRI")):
                msg = await interaction.followup.send(
                    "Day must be the first three letters of a weekday. Hour must be 0-23 and minute must be 0-59.",
                    ephemeral=True,
                    wait=True
                )
                await msg.delete(delay=Messages.SHORT_TIMEOUT)
                return
            
            await set_ta_meeting(day, hour, minute)
            ta_id = await get_id(Roles.TA_ROLE, interaction.guild.id)
            ta_role = get(interaction.guild.roles, id=ta_id)
            await interaction.followup.send(
                f"{ta_role.mention} ANNOUNCEMENT: TA meeting time updated: {hour:02d}:{minute:02d}",
                ephemeral=False
            )
        except ValueError:
            msg = await interaction.followup.send(
                "Input should be in the following format: `##:##`. Please enter valid integers for hours and minutes.",
                ephemeral=True,
                wait=True
            )
            await msg.delete(delay=Messages.SHORT_TIMEOUT)



class EditDevotionalTimeModal(discord.ui.Modal, title="Edit Devotional Time"):
    day = discord.ui.TextInput(label="Day of Devotional", placeholder="Mon/Tue/Wed/Thu/Fri", min_length=3, max_length=3, required=True)
    time = discord.ui.TextInput(label="Devotional Time (24-hour time)", placeholder="11:00", required=True, min_length=3, max_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            day = self.day.value.upper()
            hour, minute = [int(value) for value in self.time.value.split(":")]
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and day in ("MON", "TUE", "WED", "THU", "FRI")):
                msg = await interaction.followup.send(
                    "Day must be the first three letters of a weekday. Hour must be 0-23 and minute must be 0-59.",
                    ephemeral=True,
                    wait=True
                )
                await msg.delete(delay=Messages.SHORT_TIMEOUT)
                return
            
            await set_devotional_hours(day, hour, minute)
            ta_id = await get_id(Roles.TA_ROLE, interaction.guild.id)
            ta_role = get(interaction.guild.roles, id=ta_id)
            await interaction.followup.send(
                f"{ta_role.mention} ANNOUNCEMENT: Devotional time updated: {hour:02d}:{minute:02d}",
                ephemeral=False
            )
        except ValueError:
            msg = await interaction.followup.send(
                "Input should be in the following format: `##:##`. Please enter valid integers for hours and minutes.",
                ephemeral=True,
                wait=True
            )
            await msg.delete(delay=Messages.SHORT_TIMEOUT)



class EditSaturdayHoursModal(discord.ui.Modal, title="Edit Saturday Hours"):
    open = discord.ui.TextInput(
        label="Saturday Open Time (24-hour time)",
        placeholder="08:00",
        min_length=3,
        max_length=5
    )
    close = discord.ui.TextInput(
        label="Saturday Close Time (24-hour time)",
        placeholder="20:00",
        min_length=3,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        response: discord.InteractionCallbackResponse = await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            open_h, open_m = [int(time) for time in self.open.value.split(":")]
            close_h, close_m = [int(time) for time in self.close.value.split(":")]

            if not (0 <= open_h <= 23 and 0 <= open_m <= 59 and 0 <= open_h <= 23 and 0 <= open_m <= 59):
                msg = await interaction.followup.send(
                    "Hour must be 0-23 and minute must be 0-59.",
                    ephemeral=True,
                    wait=True
                )
                await msg.delete(delay=Messages.SHORT_TIMEOUT)
                return
            
            await set_saturday_hours(open_h, open_m, close_h, close_m)
            ta_id = await get_id(Roles.TA_ROLE, interaction.guild.id)
            ta_role = get(interaction.guild.roles, id=ta_id)
            await response.resource.delete()
            await interaction.channel.send(
                f"{ta_role.mention} ANNOUNCEMENT: Saturday hours updated: {open_h:02d}:{open_m:02d} to {close_h:02d}:{close_m:02d}"
            )
        except ValueError:
            msg: discord.WebhookMessage = await interaction.followup.send(
                "Input should be in the following format: `##:##`. Please enter valid integers for hours and minutes.",
                ephemeral=True,
                wait=True
            )
            await msg.delete(delay=Messages.SHORT_TIMEOUT)