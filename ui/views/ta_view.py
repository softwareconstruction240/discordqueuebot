from typing import Optional

import discord
from db import get_last_incident_info, increment_help, get_student_info
from records import QueueEntry
from ui.modals import ClearConfirmModal, RemoveConfirmModal
from ui.helpers.constants import DEFAULT_TIMEOUT, SHORT_TIMEOUT, QUEUE_OPENED, HELP_CHANNEL_NAME, QUEUE_ALREADY_OPEN, QUEUE_CLOSED, QUEUE_ALREADY_CLOSED, CLOSE_TTL, OPEN_TTL, STUDENT_INFO_WIDTH, LONG_TIMEOUT, NEXT_IN_LINE_MSG, NOW_HELPING_TEMPLATE, ONLINE_TAS_VC_NAME
from ui.helpers.utils import fixed_width
from ui.helpers.discord_helpers import get_channel, get_role, move_to_breakout, safe_dm_user, notify_next_if_changed



class TAView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
    
    open_msg: str = "The Help Queue is now open!"
    close_msg: str = "The Help Queue is now closed. If you are still on the queue, the TAs will help until their hours are over."
    
    @discord.ui.button(label="Open Queue", style=discord.ButtonStyle.green, custom_id="open_queue", emoji="🔓")
    async def open(self, interaction: discord.Interaction, button: discord.Button):
        if not interaction.client.queue.is_open:
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
        if interaction.client.queue.is_open:
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


