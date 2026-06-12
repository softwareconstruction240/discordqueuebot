import discord

async def already_in_queue(interaction: discord.Interaction)->bool:
    return await interaction.client.queue.is_in_queue(interaction.user.id)

async def can_join_queue(interaction: discord.Interaction) -> bool:
    """
    Checks if the help queue is currently open and verifies that the user 
    is not already in it.

    Args:
        interaction (discord.Interaction): The interaction context from the user.

    Returns:
        bool: True if the queue is open and the user is not in it, False otherwise.
    """
    if not interaction.client.queue.is_open:
        await interaction.response.send_message("Queue is closed.", ephemeral=True, delete_after=20)
        return False

    if await already_in_queue(interaction):
        await interaction.response.send_message("You are already in the queue.", ephemeral=True, delete_after=10)
        return False

    return True
