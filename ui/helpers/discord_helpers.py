import discord
from discord.utils import get as discord_get
from typing import Optional
from records import QueueEntry
from ui.helpers.constants import BREAKOUT_NAMES, NEXT_IN_LINE_MSG, IN_PERSON_CHANNEL_NAME, SHORT_TIMEOUT

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
    
async def notify_next_if_changed(client: discord.Client, before: Optional[QueueEntry]) -> None:
    after = await client.queue.get_front()
    if before and after and before.user_id != after.user_id:
        await safe_dm_user(client, after.user_id, NEXT_IN_LINE_MSG)

async def update_queue_messages(client: discord.Client) -> None:
    if hasattr(client, "update_student_status_message"):
        await client.update_student_status_message()
    if hasattr(client, "update_ta_status_message"):
        await client.update_ta_status_message()

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
