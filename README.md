# discordqueuebot
A help queue bot for the CS 240 Discord server.

## Overview

This bot manages a help queue in Discord, with TA controls, automatic queue open/close announcements, and voice notifications using MP3 files in the `resources/` folder.

## Requirements

- Python 3.10 or newer (3.11+ recommended)
- `ffmpeg` installed and available on your PATH for voice audio playback
- A Discord application with bot token

## Python / VS Code setup

#### 1. Install Python

Go to https://www.python.org/downloads/. On Windows, enable "Add Python to PATH" during installation.

#### 2. Clone the repository to your machine.

Open the project folder in VS Code.


> [!IMPORTANT]
> Step 3 is optional, but highly recommended
#### 3. Create and run a virtual environment in the project root:

Refer to the internet for help on this one. It's different depending on your system.

#### 4. Upgrade pip and install dependencies:

Run the following commands in the VSCode terminal:

```powershell
python -m pip install --upgrade pip
pip install -r ./src/resources/requirements.txt
```

#### 5. Confirm `ffmpeg` is installed:

Run the following command in the VSCode terminal:

```powershell
ffmpeg -version
```

## Discord server setup

#### Required channels and role names

The bot expects the following channel and role names by default. Names are case-sensitive and must match exactly.. If you use different names, update `ui/helpers/constants.py`.

- Text channels:
  - `help-queue-chat`
  - `ta-bot-chat`
- Voice channels:
  - `Online TAs`
  - `In Person with Student`
  - `Waiting Room`
  - `Breakout Room A`
  - `Breakout Room B`
  - `Breakout Room C`
- Roles:
  - `TA`
  - `Bot` (so you can give it channel-specific permissions manually)

Suggested permissions: 
  - Restrict channel management server-wide.
  - Allow Bot to Move Members server-wide.
  - help-queue-chat: @everyone restrict messages/threads, etc. Keep reactions enabled. @TA and @Bot all permissions.
  - ta-bot-chat: @everyone cannot see the channel. @TA and @Bot all permissions.
  - Online TAs: @everyone cannot join the channel. @TA and @Bot all permissions.
  - Waiting Room/Breakout Rooms: @everyone all permissions
  - In Person with Student: @everyone cannot join the channel, but they can see it. @TA and @Bot all permissions.

## Bot Setup

#### 1. Go to the Discord Developer Portal: https://discord.com/developers/applications

#### 2. Create a new application and add a Bot user.

#### 3. Under the Bot section, enable the "Message Content Intent" because the bot uses `message_content=True`.

#### 4. Save the bot token

Create a file named `.env` with the following contents:

```txt
TOKEN=your-discord-bot-token-here
```

#### 5. Under OAuth2 > URL Generator, enable scopes:
   - `bot`
   - `applications.commands`

#### 6. Under Bot Permissions, grant the following permissions:
   - View Channels
   - Send Messages
   - Read Message History
   - Manage Messages
   - Connect
   - Speak
   - Use Voice Activity
   - Use Slash Commands

#### 7. Generate the invite URL, open it in your browser, and invite the bot to your server.



## Running the bot

#### 1. Ensure your `.env` file contains the bot token.
#### 2. If you want voice alerts, place one or more `.mp3` files in the `resources/` folder.
#### 3. Start the bot from the src directory in the virtual environment:

```powershell
cd src
python bot.py
```

#### 4. Use the application commands

   - Use the command for the students' help queue buttons in help-queue-chat
   - Use the command for the TAs' help queue buttons in ta-bot-chat

> [!Note]
> If the commands don't show up, try restarting your discord client. Sometimes it takes a minute or two to sync the commands.

## Notes

- If the bot cannot find the `resources/` folder or no MP3 files are present, it will still run but will not play audio.
- You can customize channel names and messages in `ui/helpers/constants.py`.
- To run tests, navigate to the project directory and run the following in the terminal: 
```powershell
python -m unittest discover -s tests
```