import os
from discord.ext import commands
import discord
from dotenv import load_dotenv

from utils import log, loadCommandModules, getGitInfo, formatGitFooter

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

class MyBot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix="!", intents=intents, help_command=None)
		self.synced = False

	async def setup_hook(self):
		loadCommandModules()

		print("[DEBUG] Commands currently registered in bot.tree:")
		for cmd in self.tree.get_commands():
			print(f"\t - {cmd.name}")
		if not self.synced:
			#await self.tree.sync()
			self.synced = True
			log("Commands synced successfully.")
		else:
			log("Commands already synced, skipping sync.")

import re

def makeEmbed(title: str, description: str) -> discord.Embed:
	embed = discord.Embed(
		title=title,
		description=description + f"\n\n{FOOTER_TEXT}",
		color=discord.Color.purple()
	)
	return embed



bot = MyBot()
