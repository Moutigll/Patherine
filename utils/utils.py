import datetime
import discord
from discord.app_commands import Choice
import importlib
import os
from pathlib import Path
import re
import subprocess
from zoneinfo import available_timezones

def log(message):
	timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
	print(f"{timestamp} {message}")

def connectDb():
	import sqlite3
	conn = sqlite3.connect("patherine.db")
	cursor = conn.cursor()
	cursor.execute("PRAGMA foreign_keys = ON;")
	return conn, cursor

def loadCommandModules():
	commandsDir = Path(__file__).resolve().parent.parent / "commands"
	for filename in os.listdir(commandsDir):
		if not filename.endswith(".py") or filename == "__init__.py":
			continue
		moduleName = f"commands.{filename[:-3]}"
		print(f"[DEBUG] Loading command module: {moduleName}")
		importlib.import_module(moduleName)

def getGitInfo():
	try:
		repoURL = subprocess.check_output(
			["git", "config", "--get", "remote.origin.url"],
			stderr=subprocess.DEVNULL
		).decode().strip()

		lastCommit = subprocess.check_output(
			["git", "rev-parse", "--short", "HEAD"],
			stderr=subprocess.DEVNULL
		).decode().strip()

	except Exception:
		repoURL = "unknown"
		lastCommit = "unknown"

	return repoURL, lastCommit

def formatGitFooter(repoURL: str, commitHash: str) -> str:
	if repoURL.startswith("git@"):
		match = re.match(r"git@([^:]+):(.+?)(\.git)?$", repoURL)
		if match:
			host = match.group(1)
			path = match.group(2)
			repoURL = f"https://{host}/{path}"

	repoURL = re.sub(r"\.git$", "", repoURL)

	if "github.com" in repoURL or "gitlab.com" in repoURL:
		commit_url = f"{repoURL}/commit/{commitHash}"
		return f"[Github]({repoURL}) - [{commitHash[:7]}]({commit_url})"
	elif repoURL != "unknown":
		return f"[Github]({repoURL}) - {commitHash[:7]}"
	else:
		return "Unknown repository"

async def timezoneAutocomplete(interaction: discord.Interaction, current: str) -> list[Choice[str]]:
	results = []
	for tz in sorted(available_timezones()):
		if current.lower() in tz.lower():
			results.append(Choice(name=tz, value=tz))
		if len(results) >= 25:
			break
	return results

def escapeMarkdown(text: str) -> str:
	return text.replace("\\", "\\\\") \
			   .replace("*", "\\*") \
			   .replace("_", "\\_") \
			   .replace("~", "\\~") \
			   .replace("`", "\\`")

async def safeEmbed(interaction: discord.Interaction, embed: discord.Embed, message: discord.Message | None = None) -> discord.Message:
	"""
	Try to edit an existing embed message, otherwise send a new one.
	Always returns the final message object.
	"""
	try:
		if message:
			await message.edit(embed=embed)
			return message
		else:
			# If we don't have a message yet, use followup
			return await interaction.followup.send(embed=embed)
	except discord.NotFound:
		# The message was deleted → send a new one
		return await interaction.followup.send(embed=embed)
	except discord.Forbidden:
		# Not allowed to edit → send a new one
		return await interaction.followup.send(embed=embed)
	except discord.HTTPException:
		# Other error → fallback to new message
		return await interaction.followup.send(embed=embed)
