# This example requires the 'message_content' intent.

import discord
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    print(f'We have received a message: {message.content}')

    if message.content.startswith('$join'):
        await message.channel.send('Hello!')

    # join help queue
    guild = message.guild
    ta_role = discord.utils.get(guild.roles, name="TA")
    if message.content.startswith('$queue'):
        #The role ID is what goes inside the hoinkies and after the '@&'
        await message.channel.send(f'You are now in the queue. The next available {ta_role.mention} will help you!')

    # assist student
    if message.content.startswith('$help'):
        if message.role != ta_role:
            message.channel.send('Access to this command is denied')
        await message.channel.send('You are now helping a student!')

    # assist next passoff student
    if message.content.startswith('$help-passoff'):
        await message.channel.send('You are now helping a student with their passoff!')

    

client.run(TOKEN)
