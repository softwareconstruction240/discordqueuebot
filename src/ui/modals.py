import discord
from discord.utils import get
from data_access.user_stats_dao import get_times_helped_today
from data_access.bot_incidents_dao import record_bot_issue
from data_access.config_dao import set_queue_times
from data_access.server_info_dao import get_id
from ui.helpers.discord_helpers import get_channel, get_role, update_queue_messages, notify_next_if_changed
from ui.helpers.constants import Channels, Messages

class HelpModal(discord.ui.Modal, title="Request Help"):

    name = discord.ui.TextInput(
        label="Your name",
        placeholder="John D. Fortnite",
        max_length=100
    )

    question = discord.ui.TextInput(
        label="What do you need help with?",
        placeholder="Please enter more than just the phase you are currently working on :)",
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    in_person = discord.ui.TextInput(
        label="Online or In-Person? (o/p)",
        max_length=1
    )

    def __init__(self, times_helped: int):
        super().__init__()
        self.add_item(discord.ui.TextDisplay(
            f"You've been helped {times_helped} time{'s' if times_helped != 1 else ''} today."
        ))
        if times_helped >= 2:
            self.add_item(discord.ui.TextDisplay(
                "Warning: the max times you can be helped in a day is 3, "
                "but TAs may still help you if they think it is necessary."
            ))

    async def on_submit(self, interaction: discord.Interaction):
        value = self.in_person.value.lower()
        if value not in ("o", "p"):
            await interaction.response.send_message(
                "Join Queue _**Failed**_. Please enter either `o` or `p` to indicate whether you are online or in-person",
                ephemeral=True,
                delete_after=20
            )
            return
        
        student_name = self.name.value.strip()

        await interaction.client.queue_handler(
            interaction,
            self.question.value,
            False,
            value == "p",
            student_name
        )

        times_helped = await get_times_helped_today(interaction.user.id)
        mode = "In-person" if value == "p" else "Online"
        pos = await interaction.client.queue.get_position(interaction.user.id)

        await interaction.response.send_message(
            f"You are #{pos} in the queue.{f" Please join the {get_channel(interaction, "Waiting Room").mention} voice channel." if not value=="p" else ""}",
            ephemeral=True,
            delete_after=60*5
        )

        channel_id = await get_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id)
        ta_channel: discord.TextChannel = get(interaction.guild.channels, id=channel_id)
        await ta_channel.send(
            f"{interaction.user.display_name} ({student_name}) has joined the help queue - {mode} - {self.question.value} "
            f"(helped {times_helped} time{'s' if times_helped != 1 else ''} today)",
            delete_after=30
        )


class PassoffModal(discord.ui.Modal, title="Request Passoff"):

    name = discord.ui.TextInput(
        label="Your name",
        placeholder="John D. Fortnite",
        max_length=100
    )
    phase = discord.ui.TextInput(label="Which phase?", max_length=50)
    in_person = discord.ui.TextInput(label="Online or In-Person? (o/p)", max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.in_person.value.lower()
        if value not in ("o", "p"):
            await interaction.response.send_message(
                "_**Could not join queue**_. Please enter `o` or `p` to indicate whether you are online or in-person",
                ephemeral=True,
                delete_after=30
            )
            return
        
        student_name = self.name.value.strip()

        await interaction.client.queue_handler(
            interaction,
            self.phase.value,
            True,
            self.in_person.value.lower() == "p",
            student_name
        )

        mode = "In-person" if value == "p" else "Online"
        pos = await interaction.client.queue.get_position(interaction.user.id)

        await interaction.response.send_message(
            f"You are #{pos} in the queue.{f" Please join the {get_channel(interaction, "Waiting Room").mention} voice channel." if not value=="p" else ""}",
            ephemeral=True,
            delete_after=60*5
        )
        channel_id = await get_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id)
        ta_channel: discord.TextChannel = get(interaction.guild.text_channels, id=channel_id)
        await ta_channel.send(
            f"{interaction.user.display_name} ({student_name}) has requested a passoff - {mode} - {self.phase.value}",
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
        await interaction.response.send_message("The TAs have been notified. They will reach out to you if needed.", ephemeral=True, delete_after=30)
        issue_text = self.description.value.strip()
        await record_bot_issue(interaction.user.mention, issue_text)
        ta_role = discord.utils.get(interaction.guild.roles, name="TA")
        ta_mention = ta_role.mention
        for channel in interaction.guild.channels:
            if channel.name == Channels.TA_TEXT_CHANNEL_NAME:
                await channel.send(
                    f"ATTENTION {ta_mention}!\n{interaction.user.mention} is having trouble with the bot! Description: {issue_text}"
                )
                break


class ClearConfirmModal(discord.ui.Modal, title="Clear Confirmation"):
    warning = discord.ui.TextDisplay("Are you sure? This will remove all students from the queue, and cannot be undone.")
    confirmation = discord.ui.TextInput(label="Please confirm", placeholder="y/n", max_length=1)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation.value.lower() != 'y':
            await interaction.response.send_message("Clear aborted", ephemeral=True, delete_after=10)
        else:
            # TODO: update queue_history for each student if necessary (add/update a row with done_getting_help_time or time_helped depending on implementation)
            await interaction.client.queue.clear()
            await update_queue_messages(interaction.client, interaction.guild)
            await interaction.response.send_message("Queue cleared", delete_after=60*5)
            channel_id: int = get_id(Channels.HELP_CHANNEL_NAME, interaction.guild.id)
            channel: discord.TextChannel = get(interaction.guild.text_channels, id-channel_id)
            await channel.send("All students have been removed from the queue. Sorry we couldn't get to you!", delete_after=60*10)


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
        # TODO: update queue_history if necessary (add/update a row with done_getting_help_time or time_helped depending on implementation)

        front_before = await interaction.client.queue.get_front()
        user: discord.User = await interaction.client.fetch_user(self.student_user_id)
        await interaction.client.queue.remove(self.student_user_id)
        await update_queue_messages(interaction.client, interaction.guild)

        await notify_next_if_changed(interaction.client, front_before)
        reason_suffix = f" Reason: {self.reason.value}" if self.reason.value else ""
        await user.send(
            f"You have been removed from the CS240 help queue.{reason_suffix}"
        )
        await interaction.response.send_message(
            f"{user.display_name} has been removed from the queue by {interaction.user.display_name}.",
            delete_after=60 * 5
        )

class EditQueueHoursModal(discord.ui.Modal, title="Edit Queue Hours"):
    open_hour = discord.ui.TextInput(
        label="Queue Open Hour (0-23)",
        placeholder="8",
        min_length=1,
        max_length=2
    )
    open_minute = discord.ui.TextInput(
        label="Queue Open Minute (0-59)",
        placeholder="00",
        min_length=1,
        max_length=2
    )
    close_hour = discord.ui.TextInput(
        label="Queue Close Hour (0-23)",
        placeholder="20",
        min_length=1,
        max_length=2
    )
    close_minute = discord.ui.TextInput(
        label="Queue Close Minute (0-59)",
        placeholder="00",
        min_length=1,
        max_length=2
    )

    async def on_submit(self, interaction: discord.Interaction):
        
        try:
            open_h = int(self.open_hour.value)
            open_m = int(self.open_minute.value)
            close_h = int(self.close_hour.value)
            close_m = int(self.close_minute.value)
            
            if not (0 <= open_h <= 23 and 0 <= open_m <= 59 and 0 <= close_h <= 23 and 0 <= close_m <= 59):
                await interaction.response.send_message(
                    "Hours must be 0-23 and minutes must be 0-59.",
                    ephemeral=True,
                    delete_after=Messages.SHORT_TIMEOUT
                )
                return
            
            await set_queue_times(open_h, open_m, close_h, close_m)
            ta_role = get_role(interaction, "TA")
            await interaction.response.send_message(
                f"{ta_role.mention} ANNOUNCEMENT: Queue hours updated: Opens at {open_h:02d}:{open_m:02d}, closes at {close_h:02d}:{close_m:02d}",
                delete_after=60*60*24*7
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid integers for hours and minutes.",
                ephemeral=True,
                delete_after=Messages.SHORT_TIMEOUT
            )
