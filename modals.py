import discord
from db import get_times_helped_today
class HelpModal(discord.ui.Modal, title="Request Help"):

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
            )
            return
        
        await interaction.client.queue_handler(
            interaction,
            self.question.value,
            False,
            value == "p"
        )

        times_helped = get_times_helped_today(interaction.user.id)
        for channel in interaction.guild.channels:
            if channel.name == "ta-bot-chat":
                await channel.send(
                    f"{interaction.user.display_name} has joined the help queue - {"In-person" if value=="p" else "Online"} - {self.question.value} "
                    f"(helped {times_helped} time{'s' if times_helped != 1 else ''} today)",
                    delete_after=60*5
                )


class PassoffModal(discord.ui.Modal, title="Request Passoff"):

    phase = discord.ui.TextInput(label="Which phase?", max_length=50)
    in_person = discord.ui.TextInput(label="Online or In-Person? (o/p)", max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.in_person.value.lower()
        if value not in ("o", "p"):
            await interaction.response.send_message(
                "_**Could not join queue**_. Please enter `o` or `p` to indicate whether you are online or in-person",
                ephemeral=True
            )
            return
        
        await interaction.client.queue_handler(
            interaction,
            self.phase.value,
            True,
            self.in_person.value.lower() == "p"
        )

        for channel in interaction.guild.channels:
            if channel.name == "ta-bot-chat":
                await channel.send(f"{interaction.user.display_name} has requested a passoff - {"In-person" if value=="p" else "Online"} - {self.phase.value}",
                                   # disappear after 5 minutes
                                   delete_after=60*5)
                
class ClearConfirmModal(discord.ui.Modal, title="Clear Confirmation"):
    warning = discord.ui.TextDisplay("Are you sure? This will remove all students from the queue, and cannot be undone.")
    confirmation = discord.ui.TextInput(label="Please confirm", placeholder="y/n", max_length=1)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.confirmation.value.lower() != 'y':
            await interaction.response.send_message("Clear aborted", ephemeral=True, delete_after=30)
        else:
            await interaction.client.queue.clear()
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
                await user.send(f"You have been removed from the CS240 help queue. {"Reason: " if self.reason.value != "" else ""}{self.reason.value}")
                await interaction.response.send_message(f"{user.display_name} has been removed from the queue by {interaction.user.display_name}.", delete_after=60*5)
                return
            
        await interaction.response.send_message(f"No student with the username \"{self.input.value}\" in the queue.", ephemeral=True, delete_after=20)
