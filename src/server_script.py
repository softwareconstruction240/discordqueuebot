import discord
from discord.utils import get
from db import server_info_dao

async def setup_server(interaction: discord.Interaction):
    """Setup necessary channels, roles, and permissions needed for the bot to function properly.  
    
    Raises:
        PermissionError if the necessary permissions are not granted."""
    _verify_permissions(interaction)
    await _roles_init(interaction)

    await _category_init(interaction)
    category: discord.CategoryChannel = get(interaction.guild.categories, id=server_info_dao.get_id("category_id", interaction.guild.id))
    await _help_queue_channel_init(interaction, category)
    await _ta_bot_channel_init(interaction, category)
    await _online_tas_init(interaction, category)
    await _waiting_room_init(interaction, category)

async def takedown(interaction: discord.Interaction):
    """Only used for testing. Deletes all roles and channels, except for the 'general' text channel."""
    for guild_role in interaction.guild.roles:
        if guild_role not in interaction.guild.me.roles:
            await guild_role.delete()
    
    category_id = server_info_dao.get_id("category_id", interaction.guild.id)
    category = get(interaction.guild.categories, id=category_id)

    if category:
        for channel in category.channels:
            if channel.name != "general":
                await channel.delete()
        
        await category.delete()

    
    

    

def _verify_permissions(interaction: discord.Interaction):
    current_permissions: discord.Permissions = interaction.app_permissions
    expected_permissions = [
        ("Manage Channels", current_permissions.manage_channels),
        ("View Channels", current_permissions.read_messages),
        ("Send Messages", current_permissions.send_messages),
        ("Read Message History", current_permissions.read_message_history),
        ("Manage Messages", current_permissions.manage_messages),
        ("Manage Roles", current_permissions.manage_roles),
        ("Connect", current_permissions.connect),
        ("Move Members", current_permissions.move_members),
        ("Speak", current_permissions.speak),
        ("Use Voice Activity", current_permissions.use_voice_activation),
        ("Use Slash Commands", current_permissions.use_application_commands)
    ]

    missing_permissions = [name for name, granted in expected_permissions if not granted]
    
    if not len(missing_permissions) == 0:
        raise PermissionError(f"Missing required permissions: {', '.join(missing_permissions)}")
    

async def _roles_init(interaction: discord.Interaction):
    __save_bot_role_id(interaction)
    await __save_ta_role_id(interaction)
    await __save_professor_role_id(interaction)

def __save_bot_role_id(interaction: discord.Interaction):
    for role in interaction.guild.me.roles:
        if role.name != "everyone":
            server_info_dao.set_id("bot_role_id", interaction.guild.id, role.id)

async def __save_ta_role_id(interaction: discord.Interaction):
    ta_role_id: int = server_info_dao.get_id("ta_role_id", interaction.guild.id)
    for role in interaction.guild.roles:
        if role.id == ta_role_id:
            return
    
    ta_role: discord.Role = await interaction.guild.create_role(name="TA", colour=discord.Colour.blue(), mentionable=True)
    server_info_dao.set_id("ta_role_id", interaction.guild.id, ta_role.id)

async def __save_professor_role_id(interaction: discord.Interaction):
    professor_role_id: int = server_info_dao.get_id("professor_role_id", interaction.guild.id)
    for role in interaction.guild.roles:
        if role.id == professor_role_id:
            return
    
    ta_role: discord.Role = await interaction.guild.create_role(name="Professor", colour=discord.Colour.orange())
    server_info_dao.set_id("professor_role_id", interaction.guild.id, ta_role.id)

async def _category_init(interaction: discord.Interaction):
    category_id: int = server_info_dao.get_id("category_id", interaction.guild.id)
    guild_categories = interaction.guild.categories
    help_category = get(guild_categories, id=category_id)
    if help_category is None:
        help_category = await interaction.guild.create_category("Help Queue")
        server_info_dao.set_id("category_id", interaction.guild.id, help_category.id)

    bot_permissions = discord.PermissionOverwrite(move_members=True)
    
    await help_category.set_permissions(interaction.guild.me, overwrite=bot_permissions)

async def _help_queue_channel_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    help_queue_channel_id = server_info_dao.get_id("help_queue_id", interaction.guild.id)
    channels = category.channels
    help_queue_channel: discord.TextChannel = get(channels, id=help_queue_channel_id)
    if not help_queue_channel:
        help_queue_channel = await category.create_text_channel("help-queue-chat", position=0)
        server_info_dao.set_id("help_queue_id", interaction.guild.id, help_queue_channel.id)

    everyone_permissions = discord.PermissionOverwrite(send_messages=False, create_public_threads=False)

    other_permissions = discord.PermissionOverwrite(send_messages=True)
    for role in interaction.guild.roles:
        if role == interaction.guild.default_role:
            await help_queue_channel.set_permissions(interaction.guild.default_role, overwrite=everyone_permissions)
        elif role in interaction.guild.me.roles:
            await help_queue_channel.set_permissions(interaction.guild.me, overwrite=other_permissions)
        else:
            await help_queue_channel.set_permissions(role, overwrite=other_permissions)

async def _ta_bot_channel_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    ta_bot_channel_id = server_info_dao.get_id("ta_bot_channel_id", interaction.guild.id)
    ta_bot_channel: discord.TextChannel = get(category.channels, id=ta_bot_channel_id)
    if not ta_bot_channel:
        ta_bot_channel = await category.create_text_channel("ta_bot_channel", position=1)
        server_info_dao.set_id("ta_bot_channel_id", interaction.guild.id, ta_bot_channel.id)

    everyone_permissions = discord.PermissionOverwrite(view_channel=False)
    other_permissions = discord.PermissionOverwrite(view_channel=True)

    for role in interaction.guild.roles:
        if role == interaction.guild.default_role:
            continue
        elif role in interaction.guild.me.roles:
            await ta_bot_channel.set_permissions(interaction.guild.me, overwrite=other_permissions)
        else:
            await ta_bot_channel.set_permissions(role, overwrite=other_permissions)
    
    # must be done last so that the bot can still see the channel
    await ta_bot_channel.set_permissions(interaction.guild.default_role, overwrite=everyone_permissions)

async def _online_tas_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    online_tas_id = server_info_dao.get_id("online_tas_id", interaction.guild.id)
    online_tas: discord.VoiceChannel = get(category.voice_channels, id=online_tas_id)
    if not online_tas:
        online_tas = await category.create_voice_channel("Online TAs", position=2, user_limit=5)
        server_info_dao.set_id("online_tas_id", interaction.guild.id, online_tas.id)
    
    other_permissions = discord.PermissionOverwrite(connect=True)
    
    for role in interaction.guild.roles:
        if role == interaction.guild.default_role:
            continue
        elif role in interaction.guild.me.roles:
            await online_tas.set_permissions(interaction.guild.me, overwrite=other_permissions)
        else:
            await online_tas.set_permissions(role, overwrite=other_permissions)

    # must be done last so that the bot can still see the channel
    everyone_permissions = discord.PermissionOverwrite(connect=False)
    await online_tas.set_permissions(interaction.guild.default_role, overwrite=everyone_permissions)


async def _waiting_room_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    waiting_room_id = server_info_dao.get_id("waiting_room_id", interaction.guild.id)
    waiting_room: discord.VoiceChannel = get(category.voice_channels, id=waiting_room_id)
    if not waiting_room:
        waiting_room = await category.create_voice_channel("Waiting Room", position=3)
        server_info_dao.set_id("waiting_room_id", interaction.guild.id, waiting_room.id)