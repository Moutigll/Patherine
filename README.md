# Patherine

Patherine is a modular Discord bot written in Python using the `discord.py` library.  
It is designed to be lightweight, extensible, and easy to configure and deploy.  
The bot supports slash commands, automatic module loading, database interaction with SQLite, and more.

## Features

- Modular command structure
- SQLite-based persistent storage
- Slash commands with autocompletion and argument validation
- Easy setup with a `.env` file

## Installation

1. Clone the repository:

```
git clone https://github.com/your_username/patherine.git
cd patherine
```

2. Create a virtual environment and install dependencies:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and set your bot token and the owner id:

```
DISCORD_TOKEN=your_discord_bot_token
OWNER=discord_id
```

## Usage

Run the bot:

```
python main.py
```

## Structure

- `main.py`: Entry point of the bot
- `commands/`: Contains all the slash command modules
- `events`: Listener functions for new messages and reactions
- `utils/`: Utility functions and database access
- `db/database.db`: SQLite database file
- `.env`: Stores your token securely

## Notes

- You must have Python 3.10+ installed.
- Database is automatically created if it doesn't exist.

## License

This project is licensed under the GNU-3.0 License. See the `LICENSE` file for more details.
