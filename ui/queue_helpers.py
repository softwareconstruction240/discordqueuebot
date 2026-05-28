import discord

async def already_in_queue(interaction: discord.Interaction)->bool:
    return await interaction.client.queue.is_in_queue(interaction.user.id)

async def require_queue_open_and_not_in_queue(interaction: discord.Interaction) -> bool:
    if not interaction.client.queue.is_open:
        await interaction.response.send_message("Queue is closed.", ephemeral=True, delete_after=20)
        return False

    if await already_in_queue(interaction):
        await interaction.response.send_message("You are already in the queue.", ephemeral=True, delete_after=10)
        return False

    return True
