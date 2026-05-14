from dotenv import load_dotenv
import os
import discord
from discord import app_commands

load_dotenv(".env")

intents = discord.Intents.default()

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# =========================
# Student
# =========================

class Student:

    def __init__(
        self,
        name,
        passoff,
        details=""
    ):
        self.name = name
        self.passoff = passoff
        self.details = details

    def __eq__(self, value):
        return self.name == value

    def __str__(self):

        if self.passoff:
            return f"{self.name} - Passoff ({self.details})"

        return f"{self.name} - Help: {self.details}"


# =========================
# Queue
# =========================

class MemoryHelpQueue:

    def __init__(self):
        self.queue: list[Student] = []

    def add_to_queue(self, student: Student):
        self.queue.append(student)

    def remove_from_queue(self, student: str):
        self.queue.remove(student)

    def get_position_in_queue(self, student: str):

        try:
            return self.queue.index(student) + 1

        except ValueError:
            raise IndexError(f"Student {student} not in queue")

    def contains(self, student: str):

        try:
            self.queue.index(student)
            return True

        except ValueError:
            return False

    def __str__(self):

        if len(self.queue) == 0:
            return "The queue is empty."

        builder = "Students in queue:\n\n"

        for i in range(len(self.queue)):
            builder += f"{i+1}: {self.queue[i]}\n"

        return builder


queue = MemoryHelpQueue()


# =========================
# Middleware
# =========================

def allowed_channels(interaction: discord.Interaction):

    allowed = "help-queue-chat"

    return interaction.channel.name == allowed


# =========================
# Queue Join Logic
# =========================

async def join_queue(
    interaction: discord.Interaction,
    passoff: bool,
    details: str
):

    username = interaction.user.display_name

    if queue.contains(username):

        await interaction.response.send_message(
            "You are already in the queue!",
            ephemeral=True
        )

        return

    queue.add_to_queue(
        Student(
            username,
            passoff,
            details
        )
    )

    position = queue.get_position_in_queue(username)

    # ordinal suffix logic
    if 10 <= position % 100 <= 20:
        suffix = "th"
    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd"
        }.get(position % 10, "th")

    await interaction.response.send_message(
        f"You are now {position}{suffix} in the queue!",
        ephemeral=False
    )


# =========================
# Help Modal
# =========================

class HelpModal(discord.ui.Modal, title="Request Help"):

    description = discord.ui.TextInput(
        label="What do you need help with?",
        placeholder="Describe the issue briefly...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=300
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await join_queue(
            interaction,
            False,
            self.description.value
        )


# =========================
# Passoff Modal
# =========================

class PassoffModal(discord.ui.Modal, title="Request Passoff"):

    phase = discord.ui.TextInput(
        label="Which phase?",
        placeholder="Example: Phase 3",
        required=True,
        max_length=100
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await join_queue(
            interaction,
            True,
            self.phase.value
        )


# =========================
# Button View
# =========================

class QueueView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Need Help",
        style=discord.ButtonStyle.primary,
        custom_id="need_help"
    )
    async def need_help_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            HelpModal()
        )

    @discord.ui.button(
        label="Passoff",
        style=discord.ButtonStyle.success,
        custom_id="passoff"
    )
    async def passoff_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            PassoffModal()
        )

    @discord.ui.button(
        label="Leave Queue",
        style=discord.ButtonStyle.danger,
        custom_id="leave_queue"
    )
    async def leave_queue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        username = interaction.user.display_name

        if not queue.contains(username):

            await interaction.response.send_message(
                "You are not currently in the queue.",
                ephemeral=True
            )

            return

        queue.remove_from_queue(username)

        await interaction.response.send_message(
            "You have been removed from the queue.",
            ephemeral=True
        )

    @discord.ui.button(
        label="View Queue",
        style=discord.ButtonStyle.secondary,
        custom_id="view_queue"
    )
    async def view_queue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            str(queue),
            ephemeral=True
        )


# =========================
# Commands
# =========================

@tree.command(name="queue-panel")
@app_commands.check(allowed_channels)
async def queue_panel(interaction: discord.Interaction):

    embed = discord.Embed(
        title="Help Queue",
        description=(
            "Use the buttons below to interact with the queue.\n\n"
            "🔵 Need Help → Request general help\n"
            "🟢 Passoff → Request a passoff\n"
            "🔴 Leave Queue → Remove yourself\n"
            "⚪ View Queue → See the current queue"
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=QueueView()
    )


# =========================
# Error Handling
# =========================

@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    if isinstance(error, app_commands.CheckFailure):

        allowed = "help-queue-chat"

        allowed_channel = discord.utils.get(
            interaction.guild.channels,
            name=allowed
        )

        if allowed_channel:

            await interaction.response.send_message(
                f"Interact with the Help Queue bot in {allowed_channel.mention}",
                ephemeral=True
            )


# =========================
# Ready Event
# =========================

@client.event
async def on_ready():

    # required for persistent buttons
    client.add_view(QueueView())

    await tree.sync()

    print(f"Logged in as {client.user}")


# =========================
# Main
# =========================

if __name__ == "__main__":

    token = os.getenv("TOKEN")

    client.run(token)