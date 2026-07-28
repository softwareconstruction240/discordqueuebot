import discord
from discord.utils import get
from data_access.server_info_dao import get_id, set_id
from ui.views.queue_view import QueueView
from ui.views.ta_view import TAView
from ui.helpers.constants import Categories, Channels, Roles
from ui.helpers.discord_helpers import update_queue_messages

async def setup_server(interaction: discord.Interaction):
    """Setup necessary channels, roles, and permissions needed for the bot to function properly.  
    
    Raises:
        PermissionError if the necessary permissions are not granted."""
    

    await _verify_permissions(interaction)
    await _roles_init(interaction)
    await _category_init(interaction)
    category: discord.CategoryChannel = get(interaction.guild.categories, id=await get_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id))
    await _help_queue_channel_init(interaction, category)
    await _ta_bot_channel_init(interaction, category)
    await _online_tas_init(interaction, category)
    await _public_vcs_init(interaction, category)
    await _in_person_init(interaction, category)
    await update_queue_messages(interaction.client, interaction.guild)

async def takedown(interaction: discord.Interaction) -> None:
    """Deletes all roles and channels in the Help Queue Category.
    
    Raises:
        PermissionError if used by a non-administrator or if there are conflicts with the bot's role permissions and the channels/roles being deleted.
    """
    await _verify_permissions(interaction)
    had_problems: bool = False

    for guild_role in interaction.guild.roles:
        if guild_role.id in [Roles.TA_ROLE, Roles.PROFESSOR_ROLE]:
            try: 
                await guild_role.delete()
            except discord.Forbidden:
                had_problems = True
                print(f"Could not delete role {guild_role.name}. Role has higher access level than bot. Continuing with server reset...")
            except discord.HTTPException:
                had_problems = True
                print(f"Could not delete role {guild_role.name} because Role belongs to another application. Continuing with server reset...")
    
    category_id = await get_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id)
    category = get(interaction.guild.categories, id=category_id)

    if category:
        for channel in category.channels:
            if channel.name != "general":
                try: 
                    await channel.delete()
                except discord.Forbidden:
                    had_problems = True
                    print(f"Could not delete channel {channel.name}. Channel has higher access level than bot. Continuing with server reset...")
        
        await category.delete()
    
    if had_problems:
        raise PermissionError("Could not delete all roles and channels. Check logs and delete some roles/channels manually")

    
async def _verify_permissions(interaction: discord.Interaction):
    ta_role_id = await get_id(Roles.TA_ROLE, interaction.guild.id)
    professor_role_id = await get_id(Roles.PROFESSOR_ROLE, interaction.guild.id)
    ta_role = get(interaction.guild.roles, id=ta_role_id)
    professor_role = get(interaction.guild.roles, id=professor_role_id)
    
    if not (interaction.user.guild_permissions.administrator or (ta_role and ta_role in interaction.user.roles) or (professor_role and professor_role in interaction.user.roles)):
        raise PermissionError("Only administrators or TAs/Professors can use this command.")

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
        ("Mute Members", current_permissions.mute_members),
        ("Speak", current_permissions.speak),
        ("Use Voice Activity", current_permissions.use_voice_activation),
        ("Use Slash Commands", current_permissions.use_application_commands)
    ]

    missing_permissions = [name for name, granted in expected_permissions if not granted]
    
    if not len(missing_permissions) == 0:
        raise PermissionError(f"Missing required permissions: {', '.join(missing_permissions)}")
    

async def _apply_channel_permissions(
    guild: discord.Guild,
    channel: discord.abc.GuildChannel,
    everyone_permissions: discord.PermissionOverwrite,
    other_permissions: discord.PermissionOverwrite
):
    for role in guild.roles:
        try:
            if role == guild.default_role:
                continue
            elif role in guild.me.roles:
                await channel.set_permissions(guild.me, overwrite=other_permissions)
            elif role.id in [Roles.TA_ROLE, Roles.PROFESSOR_ROLE]:
                await channel.set_permissions(role, overwrite=other_permissions)
        except discord.Forbidden:
            print(f"Could not set permissions for role {role.name} due to server configuration. Continuing with server setup...")

    # must be done last in case the permission interferes with the bot's ability to see or access the channel
    try: 
        await channel.set_permissions(guild.default_role, overwrite=everyone_permissions)
    except discord.Forbidden:
        print(f"Could not set permissions for role {guild.default_role.name} due to server configuration. Continuing with server setup...")


async def _roles_init(interaction: discord.Interaction):
    await __save_ta_role_id(interaction)
    await __save_professor_role_id(interaction)

async def __save_ta_role_id(interaction: discord.Interaction):
    ta_role_id: int = await get_id(Roles.TA_ROLE, interaction.guild.id)
    ta_role: discord.Role = get(interaction.guild.roles, id=ta_role_id) or get(interaction.guild.roles, name=Roles.TA_ROLE)
    
    if not ta_role:
        ta_role = await interaction.guild.create_role(
            name=Roles.TA_ROLE,
            colour=discord.Colour.blue(),
            mentionable=True,
            permissions=discord.Permissions(mute_members=True)
        )
    else:
        if not ta_role.permissions.mute_members:
            perms = ta_role.permissions
            perms.update(mute_members=True)
            await ta_role.edit(permissions=perms)

    await set_id(Roles.TA_ROLE, interaction.guild.id, ta_role.id)

async def __save_professor_role_id(interaction: discord.Interaction):
    professor_role_id: int = await get_id(Roles.PROFESSOR_ROLE, interaction.guild.id)
    professor_role: discord.Role = get(interaction.guild.roles, id=professor_role_id) or get(interaction.guild.roles, name=Roles.PROFESSOR_ROLE)
    
    if not professor_role:
        professor_role = await interaction.guild.create_role(
            name=Roles.PROFESSOR_ROLE,
            colour=discord.Colour.orange()
        )

    await set_id(Roles.PROFESSOR_ROLE, interaction.guild.id, professor_role.id)

async def _category_init(interaction: discord.Interaction):
    category_id: int = await get_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id)
    help_category: discord.CategoryChannel = get(interaction.guild.categories, id=category_id) or get(interaction.guild.categories, name=Categories.HELP_QUEUE_CATEGORY)
    
    if help_category is None:
        help_category = await interaction.guild.create_category(Categories.HELP_QUEUE_CATEGORY)
    
    await set_id(Categories.HELP_QUEUE_CATEGORY, interaction.guild.id, help_category.id)

    bot_permissions = discord.PermissionOverwrite(move_members=True)
    await help_category.set_permissions(interaction.guild.me, overwrite=bot_permissions)

async def _help_queue_channel_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    help_queue_channel_id = await get_id(Channels.HELP_CHANNEL_NAME, interaction.guild.id)
    help_queue_channel: discord.TextChannel = get(category.text_channels, id=help_queue_channel_id) or get(category.text_channels, name=Channels.HELP_CHANNEL_NAME)
    
    if not help_queue_channel:
        help_queue_channel = await category.create_text_channel(Channels.HELP_CHANNEL_NAME, position=0)
        await help_queue_channel.send(view=QueueView())

    await set_id(Channels.HELP_CHANNEL_NAME, interaction.guild.id, help_queue_channel.id)

    everyone_permissions = discord.PermissionOverwrite(send_messages=False, create_public_threads=False)
    other_permissions = discord.PermissionOverwrite(send_messages=True)

    await _apply_channel_permissions(interaction.guild, help_queue_channel, everyone_permissions, other_permissions)


async def _ta_bot_channel_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    ta_bot_channel_id = await get_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id)
    ta_bot_channel: discord.TextChannel = get(category.text_channels, id=ta_bot_channel_id) or get(category.text_channels, name=Channels.TA_TEXT_CHANNEL_NAME)
    
    if not ta_bot_channel:
        ta_bot_channel = await category.create_text_channel(Channels.TA_TEXT_CHANNEL_NAME, position=1)
        await ta_bot_channel.send(view=TAView())

    await set_id(Channels.TA_TEXT_CHANNEL_NAME, interaction.guild.id, ta_bot_channel.id)
    
    everyone_permissions = discord.PermissionOverwrite(view_channel=False)
    other_permissions = discord.PermissionOverwrite(view_channel=True)

    await _apply_channel_permissions(interaction.guild, ta_bot_channel, everyone_permissions, other_permissions)


async def _online_tas_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    online_tas_id = await get_id(Channels.TA_VOICE_CHANNEL_NAME, interaction.guild.id)
    online_tas: discord.VoiceChannel = get(category.voice_channels, id=online_tas_id) or get(category.voice_channels, name=Channels.TA_VOICE_CHANNEL_NAME)
    
    if not online_tas:
        online_tas = await category.create_voice_channel(Channels.TA_VOICE_CHANNEL_NAME, position=2, user_limit=5)
    await set_id(Channels.TA_VOICE_CHANNEL_NAME, interaction.guild.id, online_tas.id)
    
    everyone_permissions = discord.PermissionOverwrite(connect=False)
    other_permissions = discord.PermissionOverwrite(connect=True, mute_members=True, move_members=True)

    await _apply_channel_permissions(interaction.guild, online_tas, everyone_permissions, other_permissions)


async def _public_vcs_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    public_vc_names = [Channels.WAITING_ROOM_NAME]
    public_vc_names.extend(Channels.BREAKOUT_NAMES)
    for name in public_vc_names:
        channel_id = await get_id(name, interaction.guild.id)
        voice_channel: discord.VoiceChannel = get(category.voice_channels, id=channel_id) or get(category.voice_channels, name=name)
        
        if not voice_channel:
            voice_channel = await category.create_voice_channel(name, position=3+public_vc_names.index(name))

        await set_id(name, interaction.guild.id, voice_channel.id)

async def _in_person_init(interaction: discord.Interaction, category: discord.CategoryChannel):
    in_person_vc_id = await get_id(Channels.IN_PERSON_CHANNEL_NAME, interaction.guild.id)
    in_person_vc: discord.VoiceChannel = get(category.voice_channels, id=in_person_vc_id) or get(category.voice_channels, name=Channels.IN_PERSON_CHANNEL_NAME)
    
    if not in_person_vc:
        in_person_vc = await category.create_voice_channel(Channels.IN_PERSON_CHANNEL_NAME, position=7)
    await set_id(Channels.IN_PERSON_CHANNEL_NAME, interaction.guild.id, in_person_vc.id)
    
    everyone_permissions = discord.PermissionOverwrite(connect=False)
    other_permissions = discord.PermissionOverwrite(connect=True)

    await _apply_channel_permissions(interaction.guild, in_person_vc, everyone_permissions, other_permissions)