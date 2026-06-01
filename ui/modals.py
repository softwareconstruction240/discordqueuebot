import discord
from datetime import datetime
from db import get_times_helped_today, record_bot_issue
from ui.helpers.discord_helpers import get_channel, get_role, update_queue_messages
from ui.helpers.constants import SHORT_TIMEOUT, TA_TEXT_CHANNEL_NAME

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

        times_helped = get_times_helped_today(interaction.user.id)
        mode = "In-person" if value == "p" else "Online"
        pos = await interaction.client.queue.get_position(interaction.user.id)

        await interaction.response.send_message(
            f"You are #{pos} in the queue.{f" Please join the {get_channel(interaction, "Waiting Room").mention} voice channel." if not value=="p" else ""}",
            ephemeral=True,
            delete_after=60*5
        )

        ta_channel: discord.TextChannel = get_channel(interaction, TA_TEXT_CHANNEL_NAME)
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

        ta_channel: discord.TextChannel = get_channel(interaction, TA_TEXT_CHANNEL_NAME)
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
        record_bot_issue(datetime.now(), issue_text)
        ta_role = discord.utils.get(interaction.guild.roles, name="TA")
        ta_mention = ta_role.mention
        for channel in interaction.guild.channels:
            if channel.name == TA_TEXT_CHANNEL_NAME:
                await channel.send(
                    f"{ta_mention} {interaction.user.display_name} is having trouble with the bot. Description: {issue_text}"
                )
                break



class ClearConfirmModal(discord.ui.Modal, title="Clear Confirmation"):
    warning = discord.ui.TextDisplay("Are you sure? This will remove all students from the queue, and cannot be undone.")
    confirmation = discord.ui.TextInput(label="Please confirm", placeholder="y/n", max_length=1)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation.value.lower() != 'y':
            await interaction.response.send_message("Clear aborted", ephemeral=True, delete_after=10)
        else:
            await interaction.client.queue.clear()
            await update_queue_messages(interaction.client)
            await interaction.response.send_message("Queue cleared", delete_after=60*5)
            for channel in interaction.guild.channels:
                if channel.name == "help-queue-chat":
                    await channel.send("All students have been removed from the queue. Sorry we couldn't get to you!", delete_after=60*10)


class RemoveConfirmModal(discord.ui.Modal, title="Removal Confirmation"):
    warning = discord.ui.TextDisplay("Are you sure? This will remove the student from the queue.")
    input: discord.ui.TextInput = discord.ui.TextInput(label="Please input student username.", placeholder="bsharplydian", min_length=1)
    reason: discord.ui.TextInput = discord.ui.TextInput(label="Provide a reason (optional)", placeholder="You've used the queue too many times today", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        for entry in interaction.client.queue.entries:
            if entry.username == self.input.value:
                user: discord.User = await interaction.client.fetch_user(entry.user_id)
                await interaction.client.queue.remove(user.id)
                await update_queue_messages(interaction.client)
                await user.send(f"You have been removed from the CS240 help queue. {"Reason: " if self.reason.value != "" else ""}{self.reason.value}")
                await interaction.response.send_message(f"{user.display_name} has been removed from the queue by {interaction.user.display_name}.", delete_after=60*5)
                return
            
        await interaction.response.send_message(f"No student with the username \"{self.input.value}\" in the queue.", ephemeral=True, delete_after=10)


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
        from db import set_queue_times
        
        try:
            open_h = int(self.open_hour.value)
            open_m = int(self.open_minute.value)
            close_h = int(self.close_hour.value)
            close_m = int(self.close_minute.value)
            
            if not (0 <= open_h <= 23 and 0 <= open_m <= 59 and 0 <= close_h <= 23 and 0 <= close_m <= 59):
                await interaction.response.send_message(
                    "Hours must be 0-23 and minutes must be 0-59.",
                    ephemeral=True,
                    delete_after=SHORT_TIMEOUT
                )
                return
            
            set_queue_times(open_h, open_m, close_h, close_m)
            ta_role = get_role(interaction, "TA")
            await interaction.response.send_message(
                f"{ta_role.mention} ANNOUNCEMENT: Queue hours updated: Opens at {open_h:02d}:{open_m:02d}, closes at {close_h:02d}:{close_m:02d}",
                delete_after=60*60*24*7
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid integers for hours and minutes.",
                ephemeral=True,
                delete_after=SHORT_TIMEOUT
            )

