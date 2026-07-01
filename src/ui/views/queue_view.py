import discord
from data_access.user_stats_dao import get_times_helped_today
from ui.modals import HelpModal, PassoffModal, BotIssueModal
from ui.helpers.constants import DEFAULT_TIMEOUT, SHORT_TIMEOUT
from ui.helpers.discord_helpers import count_total_tas_in_voice, update_queue_messages
from ui.helpers.queue_helpers import can_join_queue
from service.queue_history_service import calculate_expected_wait_time, NoTasOnlineError

class QueueRequests(discord.ui.ActionRow[discord.ui.LayoutView]):
    @discord.ui.button(label="Need Help", style=discord.ButtonStyle.primary, custom_id="need_help", emoji="🙏")
    async def help_btn(self, interaction: discord.Interaction, button):
        ok = await can_join_queue(interaction)
        if not ok:
            return

        today_help_count = await get_times_helped_today(interaction.user.id)
        await interaction.response.send_modal(HelpModal(today_help_count))

    @discord.ui.button(label="Passoff", style=discord.ButtonStyle.success, custom_id="passoff", emoji="💪")
    async def passoff_btn(self, interaction: discord.Interaction, button):
        ok = await can_join_queue(interaction)
        if not ok:
            return

        await interaction.response.send_modal(PassoffModal())

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue", emoji="🚪")
    async def leave_btn(self, interaction: discord.Interaction, button):
        # TODO: update queue_history if they are currently being helped by a TA

        if await interaction.client.queue.is_in_queue(interaction.user.id):
            await interaction.client.queue.remove(interaction.user.id)
            await update_queue_messages(interaction.client)
            await interaction.response.send_message("Removed from queue.", ephemeral=True, delete_after=DEFAULT_TIMEOUT)
        else:
            await interaction.response.send_message("You aren't currently in the queue", ephemeral=True, delete_after=SHORT_TIMEOUT)


    @discord.ui.button(label="My Position", style=discord.ButtonStyle.secondary, custom_id="my_position", emoji="📍")
    async def position_btn(self, interaction: discord.Interaction, button):
        pos = await interaction.client.queue.get_position(interaction.user.id)
        queue_size = len(interaction.client.queue.entries)
        
        if pos is None:
            await interaction.response.send_message(
                "You are not currently in the queue",
                ephemeral=True,
                delete_after=DEFAULT_TIMEOUT,
            )
        else:
            num_tas = count_total_tas_in_voice(interaction=interaction)
            try:
                expected_wait = calculate_expected_wait_time(
                    num_tas,
                    queue_size,
                    available_tas = num_tas - len(interaction.client.help_map.keys()),
                    position=pos,
                )
                await interaction.response.send_message(
                    f"You are currently #{pos} in the queue. You will be helped in approximately {expected_wait // 60}m {expected_wait % 60}s.",
                    ephemeral=True,
                    delete_after=DEFAULT_TIMEOUT,
                )
            except NoTasOnlineError:
                await interaction.response.send_message(
                    f"You are currently #{pos} in the queue. There are no TAs online, so we cannot estimate your wait time.",
                    ephemeral=True,
                    delete_after=DEFAULT_TIMEOUT,
                )
            
class EsotericCommands(discord.ui.ActionRow[discord.ui.LayoutView]):
    @discord.ui.button(label="Report Bot Problem", style=discord.ButtonStyle.secondary, custom_id="report_bot_problem", emoji="☢️")
    async def report_bot_problem_btn(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(BotIssueModal())

class QueueView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)


        container = discord.ui.Container[discord.ui.LayoutView](
            discord.ui.TextDisplay("## Queue Requests"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            QueueRequests(),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            EsotericCommands(),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        )

        self.add_item(container)
