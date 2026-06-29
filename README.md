# discordqueuebot
A help queue bot for the CS 240 Discord server.

## Requirements

- Python 3.11+
- `ffmpeg` installed and available on your PATH

## Python / VS Code setup

#### 1. Install Python

Go to https://www.python.org/downloads/. On Windows, enable "Add Python to PATH" during installation.

#### 2. Clone the repository to your machine.

Open the project folder in VS Code.

> [!IMPORTANT]
> Step 3 is optional, but highly recommended
#### 3. Create and run a virtual environment in the project root:

Refer to the internet for help on this one. It's different depending on your system.
If you're using powershell, do   
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### 4. Upgrade pip and install dependencies:

Run the following commands in the VSCode terminal in the root of the project:

```powershell
python -m pip install --upgrade pip
pip install -r ./src/resources/requirements.txt
```

#### 5. Confirm `ffmpeg` is installed:

Run the following command in the VSCode terminal:

```powershell
ffmpeg -version
```


## Bot Setup

#### 1. Go to the Discord Developer Portal: https://discord.com/developers/applications

#### 2. Create a new application and add a Bot user.

#### 3. Under the Bot section, enable the "Message Content Intent".

#### 4. Save the bot token by clicking the `Reset Token` button

Create a file named `.env` in the `src/resources` directory with the following contents:

```txt
TOKEN=your-token-here
```

#### 5. In OAuth2 > URL Generator, enable scopes:
   - `bot`
   - `applications.commands`

#### 6. In Installation:
 - In Installation Contexts, deselect `User Install`
 - In Install Link, Select `Discord Provided Link`
 - In Default Install Settings, for `Scopes` enable `applications.commands` and `bot`, and for `Permissions` select `Manage Channels`, `Manage Messages`, `Manage Roles`, and `Move Members`


#### 7. Open the Discord Provided link in your browser, and add the bot to your server.


## Running the bot

#### 1. Ensure your `.env` file contains the bot token.
#### 2. If you want voice alerts, ensure there are one or more `.mp3` files in the `resources/` folder.
#### 3. Start the bot from the src directory (using the virtual environment, if you set one up):

```powershell
cd src
python bot.py
```

#### 4. Discord server setup
   Run the `/setup` command in any discord server channel. Assign roles to relevant server members
>[!NOTE] The Professor/TA Roles don't have administrator permissions by default, as the bot cannot grant permissisions higher than its own level of access, so you might want to manually go in and mark the Professor Role as Administrator.

`/setup` should be the only slash command you ever need use, but the following slash commands are also provided in case the buttons are deleted:
   - `/queue`: students' help queue buttons in help-queue-chat
   - `/ta`: TAs' help queue buttons in ta-bot-chat

> [!Note]
> If the commands don't show up, try restarting your discord client. Sometimes it takes a minute or two to sync the commands.

## Conclusion
The bot is now ready to use! When you are available, be sure to join the "Online TAs" voice channel. Use the buttons to deal with helping students, and check the analytics out and analyze them in an excel spreadsheet!

## Notes

- If no MP3 files are present or you don't have fmpegg installed, it will still run but will not play audio.
- You can customize channel names and messages in `ui/helpers/constants.py`.
- To run tests, navigate to the root directory and run the following in the terminal: 
```powershell
python -m unittest discover -s tests
```