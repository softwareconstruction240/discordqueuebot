import discord
from discord.utils import get
from db import server_info_dao
from ui.views.queue_view import QueueView
from ui.views.ta_view import TAView
from ui.helpers.constants import Categories, Channels, Roles
from ui.helpers.discord_helpers import update_queue_messages

async def setup_server(interaction: discord.Interaction):
    """Setup necessary channels, roles, and permissions needed for the bot to function properly.  
    
    Raises:
        PermissionError if the necessary permissions are not granted."""
    _verify_permissions(interaction)
    await _roles_init(interaction)

    await _category_init(interaction)
    category: discord.CategoryChannel = get(interaction.guild.categories, id=server_info_dao.get_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id))
    await _help_queue_channel_init(interaction, category)
    await _ta_bot_channel_init(interaction, category)
    await _online_tas_init(interaction, category)
    await _public_vcs_init(interaction, category)
    await _in_person_init(interaction, category)
    await update_queue_messages(interaction.client, interaction.guild)

async def takedown(interaction: discord.Interaction):
    """Only used for testing. Deletes all roles and channels, except for the 'general' text channel."""
    for guild_role in interaction.guild.roles:
        if guild_role not in interaction.guild.me.roles:
            await guild_role.delete()
    
    category_id = server_info_dao.get_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id)
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
    await __save_ta_role_id(interaction)
    await __save_professor_role_id(interaction)

async def __save_ta_role_id(interaction: discord.Interaction):
    ta_role_id: int = server_info_dao.get_id(Roles.TA_ROLE, interaction.guild.id)
    for role in interaction.guild.roles:
        if role.id == ta_role_id:
            return
    
    ta_role = get(interaction.guild.roles, name=Roles.TA_ROLE)
    if not ta_role:
        ta_role: discord.Role = await interaction.guild.create_role(name=Roles.TA_ROLE, colour=discord.Colour.blue(), mentionable=True)
    server_info_dao.set_id(Roles.TA_ROLE, interaction.guild.id, ta_role.id)

async def __save_professor_role_id(interaction: discord.Interaction):
    professor_role_id: int = server_info_dao.get_id(Roles.PROFESSOR_ROLE, interaction.guild.id)
    for role in interaction.guild.roles:
        if role.id == professor_role_id:
            return
        
    professor_role = get(interaction.guild.roles, name=Roles.PROFESSOR_ROLE)
    if not professor_role:
        professor_role: discord.Role = await interaction.guild.create_role(name=Roles.PROFESSOR_ROLE, colour=discord.Colour.orange())
    server_info_dao.set_id(Roles.PROFESSOR_ROLE, interaction.guild.id, professor_role.id)

async def _category_init(interaction: discord.Interaction):
    category_id: int = server_info_dao.get_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id)
    for category in interaction.guild.categories:
        if category.id == category_id:
            return
        
    help_category = get(interaction.guild.categories, name=Categories.HELP_QUEUE_CATEGORY)
    
    if help_category is None:
        help_category = await interaction.guild.create_category(Categories.HELP_QUEUE_CATEGORY)
    
    server_info_dao.set_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id, help_category.id)

    bot_permissions = discord.PermissionOverwrite(move_members=True)
    
    await help_category.set_permissions(interaction.guild.me, overwrite=bot_permissions)

async def _help_queue_channel_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    help_queue_channel_id = server_info_dao.get_id(Channels.HELP_CHANNEL_NAME, interaction.guild.id)
    channels = category.channels
    for channel in category.channels:
        if channel.id == help_queue_channel_id:
            return
    
    help_queue_channel: discord.TextChannel = get(channels, name=Channels.HELP_CHANNEL_NAME)
    if not help_queue_channel:
        help_queue_channel = await category.create_text_channel(Channels.HELP_CHANNEL_NAME, position=0)
        await help_queue_channel.send(view=QueueView())

    server_info_dao.set_id(Channels.HELP_CHANNEL_NAME, interaction.guild.id, help_queue_channel.id)
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
    ta_bot_channel_id = server_info_dao.get_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id)
    for channel in category.channels:
        if channel.id == ta_bot_channel_id:
            return
        
    ta_bot_channel: discord.TextChannel = get(category.channels, name=Channels.TA_TEXT_CHANNEL_NAME)
    if not ta_bot_channel:
        ta_bot_channel = await category.create_text_channel(Channels.TA_TEXT_CHANNEL_NAME, position=1)
        await ta_bot_channel.send(view=TAView())

    server_info_dao.set_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id, ta_bot_channel.id)
    
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
    online_tas_id = server_info_dao.get_id(Channels.TA_VOICE_CHANNEL_NAME, interaction.guild.id)
    for channel in category.voice_channels:
        if channel.id == online_tas_id:
            return
        
    online_tas: discord.VoiceChannel = get(category.voice_channels, name=Channels.TA_VOICE_CHANNEL_NAME)
    if not online_tas:
        online_tas = await category.create_voice_channel(Channels.TA_VOICE_CHANNEL_NAME, position=2, user_limit=5)
    server_info_dao.set_id(Channels.TA_VOICE_CHANNEL_NAME, interaction.guild.id, online_tas.id)
    
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


async def _public_vcs_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    public_vc_names = [Channels.WAITING_ROOM_NAME]
    public_vc_names.extend(Channels.BREAKOUT_NAMES)
    for name in public_vc_names:
        channel_id = server_info_dao.get_id(name, interaction.guild.id)
        for vc in category.voice_channels:
            if vc.id == channel_id:
                continue
        
        voice_channel: discord.VoiceChannel = get(category.voice_channels, name=name)
        if not voice_channel:
            voice_channel = await category.create_voice_channel(name, position=3+public_vc_names.index(name))

        server_info_dao.set_id(name, interaction.guild.id, voice_channel.id)

async def _in_person_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    in_person_vc_id = server_info_dao.get_id(Channels.IN_PERSON_CHANNEL_NAME, interaction.guild.id)
    for channel in category.voice_channels:
        if channel.id == in_person_vc_id:
            return
        
    in_person_vc: discord.VoiceChannel = get(category.voice_channels, name=Channels.IN_PERSON_CHANNEL_NAME)
    if not in_person_vc:
        in_person_vc = await category.create_voice_channel(Channels.IN_PERSON_CHANNEL_NAME, position=7)
    server_info_dao.set_id(Channels.IN_PERSON_CHANNEL_NAME, interaction.guild.id, in_person_vc.id)
    
    other_permissions = discord.PermissionOverwrite(connect=True)
    
    for role in interaction.guild.roles:
        if role == interaction.guild.default_role:
            continue
        elif role in interaction.guild.me.roles:
            await in_person_vc.set_permissions(interaction.guild.me, overwrite=other_permissions)
        else:
            await in_person_vc.set_permissions(role, overwrite=other_permissions)

    # must be done last so that the bot can still see the channel
    everyone_permissions = discord.PermissionOverwrite(connect=False)
    await in_person_vc.set_permissions(interaction.guild.default_role, overwrite=everyone_permissions)