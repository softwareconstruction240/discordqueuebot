from typing import Optional

import discord
from discord.utils import get
from data_access.queue_history_dao import set_time_finished, add_queue_history_item, get_queue_history_as_csv
from data_access.bot_incidents_dao import get_last_incident_info
from data_access.user_stats_dao import increment_help, get_student_info
from data_access.server_info_dao import get_id
from data_access.config_dao import remove_saturday_hours, get_config_data
from records import QueueEntry
from ui.modals import ClearConfirmModal, RemoveConfirmModal, EditQueueHoursModal, EditMeetingHoursModal, EditDevotionalTimeModal, EditSaturdayHoursModal
from ui.helpers.constants import Channels, Messages, Roles
from ui.helpers.utils import fixed_width
from ui.helpers.discord_helpers import move_to_breakout, notify_next_if_changed, update_queue_messages




class RemoveStudentView(discord.ui.View):
    def __init__(self, entries):
        super().__init__(timeout=30)

        options = [
            discord.SelectOption(
                label="— Cancel —",
                value="__cancel__",
                description="Reset selection without removing anyone",
                emoji="↩️",
            )
        ]
        for i, entry in enumerate(entries, start=1):
            label = entry.student_name if entry.student_name else entry.username
            if len(label) > 100:
                label = label[:97] + "..."
            desc = entry.details if entry.details else ""
            if len(desc) > 100:
                desc = desc[:93] + "..."  # 96 chars + "#N " prefix ≤ 100

            emoji = "✅" if entry.is_passoff else "❓"

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(entry.user_id),   
                    description=f"#{i} {desc}" if desc else f"#{i} in queue",
                    emoji=emoji,
                )
            )

        select = discord.ui.Select(
            placeholder="Select a student to remove...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        msg: discord.InteractionCallbackResponse = await interaction.response.defer(thinking=True, ephemeral=True)
        selected = self.children[0].values[0]
        if selected == "__cancel__":
            await msg.resource.delete()
            return
        
        user_id = int(self.children[0].values[0])

        entry = next(
            (e for e in interaction.client.queue.entries if e.user_id == user_id),
            None
        )
        if not entry:
            msg = await interaction.followup.send(
                "That student is no longer in the queue.",
                ephemeral=True, wait=True
            )
            await msg.delete(delay=Messages.SHORT_TIMEOUT)
            return

        student_name = entry.student_name if entry.student_name else entry.username
        msg = await interaction.followup.send(f"Removing {student_name} from queue.", view=RemoveConfirmView(user_id, student_name), ephemeral=True, wait=True)
        await msg.delete(delay=Messages.DEFAULT_TIMEOUT)


class RemoveConfirmView(discord.ui.View):
    def __init__(self, student_user_id: int, student_name: str):
        super().__init__(timeout=30)
        self.student_user_id = student_user_id
        self.student_name = student_name
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(RemoveConfirmModal(self.student_user_id, self.student_name))
        

class TAQueueControls1(discord.ui.ActionRow[discord.ui.LayoutView]):
    view: "TAView"
    @discord.ui.button(label="Next Student", style=discord.ButtonStyle.blurple, custom_id="next", emoji="➡️")
    async def next(self, interaction: discord.Interaction, button):
        await help_next_student(interaction)

    @discord.ui.button(label="Next Student (Online)", style=discord.ButtonStyle.blurple, custom_id="next_online", emoji="💻")
    async def next_online(self, interaction: discord.Interaction, button: discord.ui.Button):
        await help_next_student(interaction, online_only=True, error_msg="No online students in the queue.")


class TAQueueControls2(discord.ui.ActionRow[discord.ui.LayoutView]):
    @discord.ui.button(label="Next Passoff", style=discord.ButtonStyle.blurple, custom_id="next_passoff", emoji="✅")
    async def next_passoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await help_next_student(interaction, passoff_only=True, error_msg="No students awaiting passoff.")
        


    @discord.ui.button(label="Next Passoff (Online)", style=discord.ButtonStyle.blurple, custom_id="next_online_passoff", emoji="☑️")
    async def next_online_passoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await help_next_student(interaction, passoff_only=True, online_only=True, error_msg="No online students awaiting passoff.")


async def help_next_student(interaction: discord.Interaction, passoff_only: bool = False, online_only: bool = False, error_msg: str = "Queue is empty."):
    msg: discord.InteractionCallbackResponse = await interaction.response.defer(thinking=True, ephemeral=True)
    if (interaction.user.name in interaction.client.help_map.keys()):
        msg = await interaction.followup.send(
            "You are currently helping a student! Use \"Finish Helping Student\" to be able to help more students!", 
            ephemeral=True, wait=True
        )
        await msg.delete(delay=Messages.SHORT_TIMEOUT)
        return

    front_before = await interaction.client.queue.get_front()

    entry: Optional[QueueEntry] = await interaction.client.queue.next(passoff_only=passoff_only, online_only=online_only)

    if not entry:
        msg = await interaction.followup.send(error_msg, ephemeral=True, wait=True)
        await msg.delete(delay=Messages.SHORT_TIMEOUT)
        return 
    
    if not entry.is_passoff:
        await increment_help(entry.user_id, entry.username, entry.student_name)

    await dequeue_student(interaction, front_before, entry)

    await msg.resource.delete()

async def dequeue_student(interaction: discord.Interaction, front_before: Optional[QueueEntry], entry: QueueEntry):
    student = await interaction.guild.fetch_member(entry.user_id)
    interaction.client.help_map[interaction.user.name] = (await add_queue_history_item(entry, student.display_name, interaction.user.name), entry.user_id)

    await move_to_breakout(interaction, entry)

    await interaction.channel.send(
        Messages.NOW_HELPING_TEMPLATE.format(ta=interaction.user.display_name, student=entry.username), 
        delete_after=Messages.DEFAULT_TIMEOUT
    )

    # Notify the next student in line only if they changed
    await notify_next_if_changed(interaction.client, front_before)
    await update_queue_messages(interaction.client, interaction.guild)

class TAQueueControls3(discord.ui.ActionRow[discord.ui.LayoutView]):
    @discord.ui.button(label="Finish Helping Student", style=discord.ButtonStyle.green, custom_id="finish", emoji="🔚")
    async def finish_button(self, interaction: discord.Interaction, button):
        response: discord.InteractionCallbackResponse = await interaction.response.defer(thinking=True, ephemeral=True)
        channel_id = await get_id(Channels.TA_VOICE_CHANNEL_NAME, interaction.guild.id)
        online_ta_vc: discord.VoiceChannel = get(interaction.guild.voice_channels, id=channel_id)
        
        try:
            ta_voice_state: discord.VoiceState = await interaction.user.fetch_voice()
            voice_channel: discord.VoiceChannel = ta_voice_state.channel
            ta_role_id: int = await get_id(Roles.TA_ROLE, interaction.guild.id)
            ta_role: discord.Role = get(interaction.guild.roles, id=ta_role_id)
            for member in voice_channel.members:
                if ta_role in member.roles:
                    continue
                else:
                    await member.move_to(None)
            await interaction.user.move_to(online_ta_vc)
        except discord.NotFound:
            msg = await interaction.followup.send(f"Rejoin the {online_ta_vc.mention} channel!", ephemeral=True, wait=True)
            await msg.delete(delay=Messages.SHORT_TIMEOUT)
        
        ta_name = interaction.user.name
        try: 
            await set_time_finished(interaction.client.help_map.pop(ta_name)[0])
        except (KeyError, TypeError):
            msg = await interaction.followup.send("Error: Could not find the student you were helping.", ephemeral=True, wait=True)
            await msg.delete(delay=Messages.SHORT_TIMEOUT)
            return
        await response.resource.delete()
        await update_queue_messages(interaction.client, interaction.guild)

class TAQueueManagement(discord.ui.ActionRow[discord.ui.LayoutView]):
    view: "TAView"
    @discord.ui.button(label="Open Queue", style=discord.ButtonStyle.green, custom_id="open_queue", emoji="🔓")
    async def open(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if not interaction.client.queue.is_open:
            interaction.client.queue.is_open = True
            await update_queue_messages(interaction.client, interaction.guild)
            msg = await interaction.followup.send(Messages.QUEUE_OPENED, ephemeral=True, wait=True)
            await msg.delete(delay=Messages.DEFAULT_TIMEOUT)
            return
        else:
            msg = await interaction.followup.send(Messages.QUEUE_ALREADY_OPEN, ephemeral=True, wait=True)
            await msg.delete(delay=Messages.SHORT_TIMEOUT)

    @discord.ui.button(label="Close Queue", style=discord.ButtonStyle.red, custom_id="close_queue", emoji="🔏")
    async def close(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if interaction.client.queue.is_open:
            interaction.client.queue.is_open = False
            await update_queue_messages(interaction.client, interaction.guild)
            msg = await interaction.followup.send(Messages.QUEUE_CLOSED, ephemeral=True, wait=True)
            await msg.delete(delay=Messages.DEFAULT_TIMEOUT)
            return
        else:
            msg = await interaction.followup.send(Messages.QUEUE_ALREADY_CLOSED, ephemeral=True, wait=True)
            await msg.delete(delay=Messages.SHORT_TIMEOUT)

    @discord.ui.button(label="Clear Queue", style=discord.ButtonStyle.danger, custom_id="clear_queue", emoji="💥")
    async def clear_queue(self, interaction: discord.Interaction, button):
        if not interaction.client.queue.entries:
            await interaction.response.send_message("Queue is empty!", ephemeral=True)
            return
        await interaction.response.send_modal(ClearConfirmModal())

    @discord.ui.button(label="Remove Student", style=discord.ButtonStyle.danger, custom_id="remove_from_queue", emoji="🗑️")
    async def remove_from_queue(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        entries = interaction.client.queue.entries
        if not entries:
            msg = await interaction.followup.send(
                "Queue is empty.", ephemeral=True, wait=True
            )
            msg.delete(delay=Messages.SHORT_TIMEOUT)
            return

        view = RemoveStudentView(entries)
        msg = await interaction.followup.send(
            "Select a student to remove:\n✅ = Passoff  |  ❓ = Question",
            view=view, ephemeral=True, wait=True 
        )
        await msg.delete(delay=30)

class TAQueueInformation(discord.ui.ActionRow[discord.ui.LayoutView]):
    view: "TAView"
    @discord.ui.button(label="Days Since Last Incident", style=discord.ButtonStyle.secondary, custom_id="days_since_incident", emoji="⚠️")
    async def days_since_incident_btn(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        reported_by, days, issue_text = await get_last_incident_info()
        if days is None:
            message = "No incidents have been reported yet."
        else:
            message = f"{days} day{'' if days == 1 else 's'} since last incident. Description: {issue_text or 'No description provided'}\nContact {reported_by} for more information."

        msg = await interaction.followup.send(message, ephemeral=True, wait=True)
        await msg.delete(delay=Messages.DEFAULT_TIMEOUT)

    @discord.ui.button(label="Student Info", style=discord.ButtonStyle.secondary, custom_id="student_info", emoji="📝")
    async def student_info(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        headers, rows = await get_student_info()
        width = Messages.STUDENT_INFO_WIDTH
        def row_to_line(items):
            return "| ".join(fixed_width(str(x), width) for x in items)

        divider = "-" * (width * len(headers) + 3 * (len(headers)-1))
        body = "\n".join(row_to_line(r) for r in rows)
        builder = f"```Student Info:\n{row_to_line(headers)}\n{divider}\n{body}```"
        await interaction.followup.send(builder, ephemeral=True)


    @discord.ui.button(label="See Queue History", style=discord.ButtonStyle.secondary, custom_id="queue_history", emoji="🏛️")
    async def display_queue_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        csv_file = await get_queue_history_as_csv()
        await interaction.followup.send(file=csv_file)

class TAConfig(discord.ui.ActionRow[discord.ui.LayoutView]):
    view: "TAView"
    @discord.ui.button(label="Edit Queue Hours", style=discord.ButtonStyle.secondary, custom_id="edit_hours", emoji="🕐")
    async def edit_queue_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditQueueHoursModal())

    @discord.ui.button(label="Edit TA Meeting", style=discord.ButtonStyle.blurple, custom_id="edit_ta_meeting", emoji="🤝")
    async def edit_ta_meeting_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditMeetingHoursModal())

    @discord.ui.button(label="Edit Devotional Time", style=discord.ButtonStyle.red, custom_id="edit_devotional", emoji="🙏")
    async def edit_devotional_time(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EditDevotionalTimeModal())

    @discord.ui.button(label="Saturday Hours", style=discord.ButtonStyle.green, custom_id="saturday_hours", emoji="🗓️")
    async def get_saturday_hours_view(self, interaction: discord.Interaction, button):
        await interaction.response.send_message(view=SaturdayView(), ephemeral=True, delete_after=Messages.DEFAULT_TIMEOUT)

    @discord.ui.button(label="See Current Settings", style=discord.ButtonStyle.gray, custom_id="see_current_config", emoji="⚙️")
    async def see_current_config(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        current_config = await get_config_data()
        msg = await interaction.followup.send(current_config, wait=True)
        await msg.delete(delay=Messages.DEFAULT_TIMEOUT)


class SaturdayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
    
    @discord.ui.button(label="Edit Hours", style=discord.ButtonStyle.green)
    async def edit_hours(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(EditSaturdayHoursModal())

    @discord.ui.button(label="Remove Saturday Hours", style=discord.ButtonStyle.danger)
    async def saturday_offline(self, interaction: discord.Interaction, button):
        await interaction.response.defer(thinking=True)
        await remove_saturday_hours()

        ta_id = await get_id(Roles.TA_ROLE, interaction.guild.id)
        ta_role = get(interaction.guild.roles, id=ta_id)
        await interaction.followup.send(
            f"{ta_role.mention} ANNOUNCEMENT: Saturday hours removed! The queue will no longer auto-start on saturdays."
        )

class TAView(discord.ui.LayoutView):

    def __init__(self):
        super().__init__(timeout=None)
        container = discord.ui.Container[discord.ui.LayoutView](
            discord.ui.TextDisplay("## Queue Controls"),
            # discord.ui.Section(
            #     "## Queue Controls",
            #     accessory=discord.ui.Thumbnail["TAView"]("https://images.seeklogo.com/logo-png/30/1/byu-brigham-young-university-logo-png_seeklogo-306722.png")
            # ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay("### Basic Controls"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            TAQueueControls1(),
            TAQueueControls2(),
            TAQueueControls3(),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay("### Queue Management"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            TAQueueManagement(),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay("### Information/Upkeep"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            TAQueueInformation(),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            discord.ui.TextDisplay("### Configuration"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            TAConfig()

        )
        self.add_item(container)
