import os
from discord.ext import commands
import discord
from dotenv import load_dotenv

from utils import log, loadCommandModules

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = os.getenv("OWNER")

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
			print(f" - {cmd.name}")
		if not self.synced:
			await self.tree.sync()
			self.synced = True
			log("Commands synced successfully.")
		else:
			log("Commands already synced, skipping sync.")



bot = MyBot()
