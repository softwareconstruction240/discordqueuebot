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


> [! IMPORTANT]
> Steps 3 and 4 are optional, but highly recommended
#### 3. Create a virtual environment in the project root:

Open the terminal using `ctrl+\``

Run the following command:

```powershell
python -m venv .venv
```

#### 4. Activate the environment:

Run the following command in the VSCode terminal:

```powershell
.venv\Scripts\Activate.ps1
```

You should see a (.venv) to the left of the terminal prompt.

#### 5. Upgrade pip and install dependencies:

Run the following commands in the VSCode terminal:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### 6. Confirm `ffmpeg` is installed:

Run the following command in the VSCode terminal:

```powershell
ffmpeg -version
```

## Discord server setup

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
   - View Channels / Read Messages
   - Send Messages
   - Read Message History
   - Manage Messages
   - Connect
   - Speak
   - Use Voice Activity
   - Use Slash Commands

#### 7. Generate the invite URL, open it in your browser, and invite the bot to your server.

## Required channels and role names

The bot expects the following channel and role names by default. If you use different names, update `ui/helpers/constants.py`.

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

## Bot setup and start

#### 1. Ensure your `.env` file contains the bot token.
#### 2. If you want voice alerts, place one or more `.mp3` files in the `resources/` folder.
#### 3. Start the bot from the project root in the virtual environment:

```powershell
python bot.py
```

#### 4. The bot will create `queue.db` automatically in the project folder.

## What it does

- Posts a live queue status message in the TA text channel
- Updates the message when students join or leave the queue
- Announces queue open/close in `help-queue-chat`
- Joins the `Online TAs` voice channel and plays a random MP3 once per minute while the queue is non-empty
- Leaves the voice channel when the queue becomes empty

## Notes

- If the bot cannot find the `resources/` folder or no MP3 files are present, it will still run but will not play audio.
- You can customize channel names and messages in `ui/helpers/constants.py`.
