from commands import TOKEN, bot

from utils import log
from db import createDb

createDb()
log("Database initialized successfully.")

@bot.event
async def on_ready():
	log(f"Bot is ready as {bot.user.name} (ID: {bot.user.id})")
	log("Bot is connected to the following guilds:")
	for guild in bot.guilds:
		print(f"\t\t\t\t- {guild.name} - {guild.member_count} members")

if __name__ == "__main__":
	bot.run(TOKEN)
