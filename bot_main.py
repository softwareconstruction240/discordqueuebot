from dotenv import load_dotenv
import os
import discord
from discord import app_commands

load_dotenv(".env")

intents: discord.Intents = discord.Intents.default()

client: discord.Client = discord.Client(intents=intents)
tree: discord.app_commands.CommandTree = app_commands.CommandTree(client)

class Student:
    def __init__(self, name, passoff):
        self.name = name
        self.passoff = passoff

    def __eq__(self, value):
        return self.name == value

    def __str__(self):
        return f"{self.name}{" - Passoff" if self.passoff else ""}"


class MemoryQueue:
    def __init__(self):
        self.queue: list[Student] = list()

    def add_to_queue(self, student:str, passoff:bool):
        self.queue.append(Student(student, True)) if passoff else self.queue.append(Student(student, False))
    
    def remove_from_queue(self, student:str):
        self.queue.remove(student)
    
    def get_position_in_queue(self, student:str):
        try:
            return self.queue.index(student)+1
        except ValueError:
            raise IndexError(f"Student {student} not in queue")

    def contains(self, student:str):
        try:
            self.queue.index(student)
            return True
        except ValueError:
            return False

    def __str__(self):
        if len(self.queue) == 0:
            return "The queue is empty."
        builder: str = ""
        builder += "Students in queue:\n"
        for i in range(0, len(self.queue)):
            builder += f'{i+1} : {self.queue[i]}\n'

        return builder
        
            
queue: MemoryQueue = MemoryQueue()

# middleware to ensure that the command is sent in the right channel
def allowed_channels(interaction: discord.Interaction):
    allowed: str = "help-queue-chat"
    return allowed == interaction.channel.name
        

# Commands will go here


# adds self to the queue. Whether joining for passoff or not must be indicated.
@tree.command(name="get-help")
@app_commands.check(allowed_channels)
async def get_gelp(interaction: discord.Interaction, passoff:bool):
    if queue.contains(interaction.user.display_name):
        await interaction.response.send_message("You are already in the queue!")
        return
    
    queue.add_to_queue(interaction.user.display_name, passoff)
    position:int = queue.get_position_in_queue(interaction.user.display_name)
    suffix = "st" if position % 10 == 1 else "nd" if position % 10 == 2 else "rd" if position % 10 == 3 else "th"
    await interaction.response.send_message(f"You are now {position}{suffix} the queue! The next available TA will help you!")


# removes self from queue
@tree.command(name="done")
@app_commands.check(allowed_channels)
async def done(interaction: discord.Interaction,):
    queue.remove_from_queue(interaction.user.display_name)
    await interaction.response.send_message("Thanks for coming!")

# gets students in queue
@tree.command(name="get-queue")
@app_commands.check(allowed_channels)
async def get_queue(interaction: discord.Interaction):
    await interaction.response.send_message(str(queue))


# error handling
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.errors.CheckFailure):
            allowed: str = "help-queue-chat"
            channels: list = interaction.guild.channels
            allowed_id = 0
            for channel in channels:
                if channel.name == allowed:
                    allowed_id = channel.id
            await interaction.response.send_message(f"Interact with the Help Queue bot in <#{allowed_id}>")



@client.event
async def on_ready():
    await tree.sync()


if __name__ == "__main__":
    token = os.getenv('TOKEN')
    client.run(token)
