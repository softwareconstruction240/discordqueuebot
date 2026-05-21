from typing import Optional

import discord
from db import increment_help, get_student_info
from models import QueueEntry

class HelpModal(discord.ui.Modal, title="Request Help"):

    question = discord.ui.TextInput(
        label="What do you need help with?",
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    in_person = discord.ui.TextInput(
        label="Online or In-Person? (o/p)",
        max_length=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        value = self.in_person.value.lower()
        if value not in ("o", "p"):
            await interaction.response.send_message(
                "Join Queue _**Failed**_. Please enter `o` or `p` to indicate whether you are online or in-person",
                ephemeral=True
            )
            return
        
        await interaction.client.queue_handler(
            interaction,
            self.question.value,
            False,
            value == "p"
        )


class PassoffModal(discord.ui.Modal, title="Request Passoff"):

    phase = discord.ui.TextInput(label="Which phase?", max_length=50)

    in_person = discord.ui.TextInput(label="Online or In-Person? (o/p)", max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.in_person.value.lower()
        if value not in ("o", "p"):
            await interaction.response.send_message(
                "Join Queue _**Failed**_. Please enter `o` or `p` to indicate whether you are online or in-person",
                ephemeral=True
            )
            return
        
        await interaction.client.queue_handler(
            interaction,
            self.phase.value,
            True,
            self.in_person.value.lower() == "p"
        )

class QueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Need Help", style=discord.ButtonStyle.primary, custom_id="need_help")
    async def help_btn(self, interaction: discord.Interaction, button):
        if not await queue_is_open(interaction):
            return await interaction.response.send_message(
                "Queue is closed.", ephemeral=True
            )
        
        if await already_in_queue(interaction):
            return await interaction.response.send_message(
                "You are already in the queue.", ephemeral=True
            )

        await interaction.response.send_modal(HelpModal())

    @discord.ui.button(label="Passoff", style=discord.ButtonStyle.success, custom_id="passoff")
    async def passoff_btn(self, interaction: discord.Interaction, button):
        if not await queue_is_open(interaction):
            return await interaction.response.send_message(
                "Queue is closed.", ephemeral=True
            )
        if await already_in_queue(interaction):
            return await interaction.response.send_message(
                "You are already in the queue.", ephemeral=True
            )
        
        await interaction.response.send_modal(PassoffModal())

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue")
    async def leave_btn(self, interaction: discord.Interaction, button):
        await interaction.client.queue.remove(interaction.user.id)
        await interaction.response.send_message("Removed from queue.", ephemeral=True)


class TAView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Open Queue", style=discord.ButtonStyle.green, custom_id="open_queue")
    async def open(self, interaction: discord.Interaction, button):
        interaction.client.queue.is_open = True
        await interaction.response.send_message("Queue opened.", ephemeral=True)

    @discord.ui.button(label="Close Queue", style=discord.ButtonStyle.red, custom_id="close_queue")
    async def close(self, interaction: discord.Interaction, button):
        interaction.client.queue.is_open = False
        await interaction.response.send_message("Queue closed.", ephemeral=True)

    @discord.ui.button(label="View Queue", style=discord.ButtonStyle.secondary, custom_id="view_queue")
    async def view_btn(self, interaction: discord.Interaction, button):
        text = await interaction.client.queue.view()
        await interaction.response.send_message(text, ephemeral=True)


    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, custom_id="next")
    async def next(self, interaction: discord.Interaction, button):
        entry: Optional[QueueEntry] = await interaction.client.queue.next()

        if not entry:
            return await interaction.response.send_message("Queue empty.", ephemeral=True)

        
        increment_help(entry.user_id, entry.username)

        await interaction.response.send_message(
            f"{entry.username} is next. Go help them!",
            ephemeral=True
        )

    @discord.ui.button(label="Student Info", style=discord.ButtonStyle.red, custom_id="student_info")
    async def student_info(self, interaction: discord.Interaction, button):
        info: list = get_student_info()
        builder: str = "```Student Info:\n"
        width: int = 50
        for type in info[0]:
            builder += fixed_width(str(type), width)
        builder += "\n"
        for student in info[1]: 
            for item in student:
                builder += fixed_width(str(item), width)
            builder += "\n"
        
        builder+="```"
        await interaction.response.send_message(builder)

def fixed_width(text: str, width: int) -> str:
    if len(text) > width:
        return text[:width - 3] + "..."
    
    return text.ljust(width)

async def queue_is_open(interaction: discord.Interaction)->bool:
    return interaction.client.queue.is_open

async def already_in_queue(interaction: discord.Interaction)->bool:
    return await interaction.client.queue.is_in_queue(interaction.user.id)