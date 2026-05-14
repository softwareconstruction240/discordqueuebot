import os
import discord
from discord import app_commands

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# Commands will go here


@client.event
async def on_ready():
    await tree.sync()


if __name__ == "__main__":
    token = os.getenv('TOKEN')
    client.run(token)
