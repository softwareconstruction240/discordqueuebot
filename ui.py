from typing import Optional

import discord
from db import increment_help, get_student_info, get_times_helped_today
from records import QueueEntry
from modals import HelpModal, PassoffModal, ClearConfirmModal, RemoveConfirmModal


class QueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Need Help", style=discord.ButtonStyle.primary, custom_id="need_help", emoji="🙏")
    async def help_btn(self, interaction: discord.Interaction, button):
        if not await queue_is_open(interaction):
            return await interaction.response.send_message(
                "Queue is closed.", ephemeral=True, delete_after=20
            )
        
        if await already_in_queue(interaction):
            return await interaction.response.send_message(
                "You are already in the queue.", ephemeral=True, delete_after=10
            )

        today_help_count = get_times_helped_today(interaction.user.id)
        await interaction.response.send_modal(HelpModal(today_help_count))

    @discord.ui.button(label="Passoff", style=discord.ButtonStyle.success, custom_id="passoff", emoji="💪")
    async def passoff_btn(self, interaction: discord.Interaction, button):
        if not await queue_is_open(interaction):
            return await interaction.response.send_message(
                "Queue is closed.", ephemeral=True, delete_after=20
            )
        if await already_in_queue(interaction):
            return await interaction.response.send_message(
                "You are already in the queue.", ephemeral=True, delete_after=10
            )
        
        await interaction.response.send_modal(PassoffModal())

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue", emoji="🚪")
    async def leave_btn(self, interaction: discord.Interaction, button):
        if await interaction.client.queue.is_in_queue(interaction.user.id):
            await interaction.client.queue.remove(interaction.user.id)
            await interaction.response.send_message("Removed from queue.", ephemeral=True, delete_after=20)
        else:
            await interaction.response.send_message("You aren't currently in the queue", ephemeral=True, delete_after=10)


class TAView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
    
    open_msg: str = "The Help Queue is now open!"
    close_msg: str = "The Help Queue is now closed. If you are still on the queue, the TAs will help until their hours are over."
    
    @discord.ui.button(label="Open Queue", style=discord.ButtonStyle.green, custom_id="open_queue", emoji="🔓")
    async def open(self, interaction: discord.Interaction, button: discord.Button):
        if not queue_is_open(interaction):
            interaction.client.queue.is_open = True
            await interaction.response.send_message("Queue opened.", ephemeral=True, delete_after=60*5)
            help_channel = get_channel(interaction, "help-queue-chat")

            if help_channel.last_message is not None and help_channel.last_message.content == self.close_msg:
                await help_channel.last_message.delete()
            await help_channel.send(self.open_msg, delete_after=60*60*12)
            return
        else:
            await interaction.response.send_message("Queue is already open!", ephemeral=True, delete_after=10)

    @discord.ui.button(label="Close Queue", style=discord.ButtonStyle.red, custom_id="close_queue", emoji="🔏")
    async def close(self, interaction: discord.Interaction, button):
        if queue_is_open(interaction):
            interaction.client.queue.is_open = False
            await interaction.response.send_message("Queue closed.", ephemeral=True, delete_after=60*5)
            help_channel = get_channel(interaction, "help-queue-chat")
            if help_channel.last_message is not None and help_channel.last_message.content == self.open_msg:
                await help_channel.last_message.delete()
            await help_channel.send(self.close_msg, delete_after=60*60*12)
            return
        else:
            await interaction.response.send_message("Queue is already closed!", ephemeral=True, delete_after=10)

    @discord.ui.button(label="View Queue", style=discord.ButtonStyle.secondary, custom_id="view_queue", emoji="👀")
    async def view_btn(self, interaction: discord.Interaction, button):
        text = await interaction.client.queue.view()
        await interaction.response.send_message(text, ephemeral=True)


    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, custom_id="next", emoji="➡️")
    async def next(self, interaction: discord.Interaction, button):
        entry: Optional[QueueEntry] = await interaction.client.queue.next()

        if not entry:
            return await interaction.response.send_message("Queue is empty.", ephemeral=True, delete_after=10)

        if not entry.is_passoff:
            increment_help(entry.user_id, entry.username)

        await notify_tas(interaction, f"{interaction.user.display_name} is now helping {entry.username}", delete_after=60*5)

        await interaction.response.send_message(
            f"You are now helping: {entry.username} - {"In-Person" if entry.in_person else "Online"} - {"Passoff - " if entry.is_passoff else ""}{entry.details}",
            ephemeral=True,
            delete_after=60*5
        )

    @discord.ui.button(label="Next Online", style=discord.ButtonStyle.blurple, custom_id="next_online", emoji="💻")
    async def next_online(self, interaction: discord.Interaction, button: discord.ui.Button):
        entry: Optional[QueueEntry] = await interaction.client.queue.next(online_only=True)

        if not entry:
            return await interaction.response.send_message("No online students available.", ephemeral=True, delete_after=10)

        if not entry.is_passoff:
            increment_help(entry.user_id, entry.username)

        await notify_tas(interaction, f"{interaction.user.display_name} is now helping {entry.username}",delete_after=60*5)

        await interaction.response.send_message(
            f"You are now helping: {entry.username} - {"In-Person" if entry.in_person else "Online"} - {"Passoff - " if entry.is_passoff else ""}{entry.details}",
            ephemeral=True,
            delete_after=60*5
        )
    
    @discord.ui.button(label="Next Passoff", style=discord.ButtonStyle.blurple, custom_id="next_passoff", emoji="✅")
    async def next_passoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        entry: Optional[QueueEntry] = await interaction.client.queue.next(passoff_only=True)

        if not entry:
            return await interaction.response.send_message("No students awaiting passoff.", ephemeral=True, delete_after=10)

        await notify_tas(interaction, f"{interaction.user.display_name} is now helping {entry.username}")


        await interaction.response.send_message(
            f"You are now helping: {entry.username} - {"In-Person" if entry.in_person else "Online"} - {"Passoff - " if entry.is_passoff else ""}{entry.details}",
            ephemeral=True,
            delete_after=60*5
        )

    @discord.ui.button(label="Next Online Passoff", style=discord.ButtonStyle.blurple, custom_id="next_online_passoff", emoji="☑️")
    async def next_online_passoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        entry: Optional[QueueEntry] = await interaction.client.queue.next(passoff_only=True, online_only=True)

        if not entry:
            return await interaction.response.send_message("No students awaiting online passoff.", ephemeral=True, delete_after=10)

        await notify_tas(interaction, f"{interaction.user.display_name} is now helping {entry.username}")


        await interaction.response.send_message(
            f"You are now helping: {entry.username} - {"In-Person" if entry.in_person else "Online"} - {"Passoff - " if entry.is_passoff else ""}{entry.details}",
            ephemeral=True,
            delete_after=60*5
        )

    @discord.ui.button(label="Student Info", style=discord.ButtonStyle.secondary, custom_id="student_info", emoji="📝")
    async def student_info(self, interaction: discord.Interaction, button):
        info: tuple = get_student_info()
        builder: str = "```Student Info:\n"
        width: int = 25
        for type in info[0]:
            builder += fixed_width(str(type), width) + ("\n" if info[0].index(type) == len(info[0])-1 else "| ")
        for _ in range(width * len(info[0])):
            builder += "-" 
        builder += "\n"
        for student in info[1]: 
            for item in student:
                builder += fixed_width(str(item), width) + ("\n" if student.index(item) == len(student)-1 else "| ")
        
        builder+="```"
        await interaction.response.send_message(builder, ephemeral=True)

    @discord.ui.button(label="Clear Queue", style=discord.ButtonStyle.danger, custom_id="clear_queue", emoji="💥")
    async def clear_queue(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(ClearConfirmModal())

    @discord.ui.button(label="Remove Student", style=discord.ButtonStyle.danger, custom_id="remove_from_queue", emoji="🗑️")
    async def remove_from_queue(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(RemoveConfirmModal())

def fixed_width(text: str, width: int) -> str:
    if len(text) > width:
        return text[:width - 3] + "..."
    
    return text.ljust(width)

async def queue_is_open(interaction: discord.Interaction)->bool:
    return interaction.client.queue.is_open

async def already_in_queue(interaction: discord.Interaction)->bool:
    return await interaction.client.queue.is_in_queue(interaction.user.id)

def get_channel(interaction: discord.Interaction, channel_name: str):
    for channel in interaction.guild.channels:
        if channel.name == channel_name:
            return channel
            
async def notify_tas(interaction: discord.Interaction, msg: str):
    ta_chat: discord.TextChannel = get_channel(interaction, "ta-bot-chat")
    await ta_chat.send(msg, delete_after=60*10)
