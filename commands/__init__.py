import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from utils.utils import log, loadCommandModules, getGitInfo, formatGitFooter

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = os.getenv("OWNER")

REPO_URL, LAST_COMMIT = getGitInfo()
FOOTER_TEXT = formatGitFooter(REPO_URL, LAST_COMMIT)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True

addGroup = app_commands.Group(name="add", description="Commands to add channels and admins")
statGroup = app_commands.Group(name="stat", description="Commands to view statistics")
leaderboardGroup = app_commands.Group(name="leaderboard", description="Commands to view leaderboards")
updateGroup = app_commands.Group(name="update", description="Command to update channels")
leaderboardGroup = app_commands.Group(name="leaderboard", description="Show leaderboard info")
graphGroup = app_commands.Group(name="graph", description="Commands to generate graphs")

def printCommands(commandsList, indent=1):
	for cmd in commandsList:
		print("\t" * indent + f"- {cmd.name}")
		if hasattr(cmd, "commands") and cmd.commands:
			printCommands(cmd.commands, indent + 1)

class MyBot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix="!", intents=intents, help_command=None)
		self.synced = False

	async def setup_hook(self):
		loadCommandModules()

		self.tree.add_command(addGroup)
		self.tree.add_command(updateGroup)
		self.tree.add_command(statGroup)
		self.tree.add_command(leaderboardGroup)
		self.tree.add_command(graphGroup)

		print("[DEBUG] Commands currently registered in bot.tree:")
		for cmd in self.tree.get_commands():
			print(f"- {cmd.name}")
			if hasattr(cmd, "commands") and cmd.commands:
				printCommands(cmd.commands)

		if not self.synced:
			await self.tree.sync()
			self.synced = True
			log("Commands synced successfully.")
		else:
			log("Commands already synced, skipping sync.")


def makeEmbed(title: str, description: str) -> discord.Embed:
	embed = discord.Embed(
		title=title,
		description=description + f"\n\n{FOOTER_TEXT}",
		color=discord.Color.purple()
	)
	return embed

bot = MyBot()
