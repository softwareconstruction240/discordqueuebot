# This example requires the 'message_content' intent.

import discord
from dotenv import load_dotenv
import os

load_dotenv("./bot-password.env")
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    #ensure the message is not a message from the bot to avoid infinite loops
    if message.author == client.user:
        return
    
    # ensure the command was sent in the right chat
    if message.channel.name != "help-queue-chat":
        if message.content.startswith('$'):
            await message.channel.send(f'To invoke this bot, send messages in the <#{message.channel.id}>!')
        return
    
    print(f'We have received a message: {message.content}')

    # testing
    if message.content.startswith('$join'):
        await message.channel.send('Hello!')

    # join help queue
    # get the TA role so as to be able to mention it. Not sure if we should keep this or not because it will ping all 
    # TAs and not just the active ones. I feel like we are pretty good at looking at the help queue chat 
    # so I lean towards not needing it, but if we need to know how to mention here it is.
    guild = message.guild
    ta_role = discord.utils.get(guild.roles, name="TA")
    if message.content.startswith('$queue'):        
        await message.channel.send(f'You are now in the queue. The next available {ta_role.mention} will help you!')

    # assist student
    if message.content.startswith('$help'):
        if not message.author.roles.contains(ta_role):
            message.channel.send('Access to this command is denied')
        await message.channel.send('You are now helping a student!')

    # assist next passoff student
    if message.content.startswith('$help-passoff'):
        await message.channel.send('You are now helping a student with their passoff!')

    if message.content.startswith('$done'):
        await message.channel.send('You are now done helping a student!')

    
print(f'{BOT_TOKEN.__class__}')

client.run(BOT_TOKEN)
