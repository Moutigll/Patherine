# I forgot to check if the user is a bot in fetchMessages.
# So bot can have been incorrectly stored when adding or updating channels.

import os
import time
from dotenv import load_dotenv
import requests

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
	raise Exception("DISCORD_TOKEN environment variable not set")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def up(cursor):
	"""
	Query the Discord API for each user in the `users` table,
	delete bot accounts (and their messages/reactions via ON DELETE CASCADE),
	and print a summary for each deletion.
	"""
	cursor.execute("SELECT id, discord_user_id FROM users")
	allUsers = cursor.fetchall()

	headers = {"Authorization": f"Bot {TOKEN}"}
	deletedCount = 0
	totalMsgs = 0
	totalReactions = 0

	for user_id, discord_id in allUsers:
		retries = 0
		max_retries = 5
		while True:
			# Call the Discord API to get user information
			resp = requests.get(f"https://discord.com/api/v10/users/{discord_id}", headers=headers)
			if resp.status_code == 200:
				data = resp.json()
				if data.get("bot", False):
					# This is a bot, delete it
					# Get the number of messages and reactions before deletion
					cursor.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,))
					msgs = cursor.fetchone()[0]
					cursor.execute("SELECT COUNT(*) FROM reactions WHERE user_id = ?", (user_id,))
					reacs = cursor.fetchone()[0]

					# Delete the user (foreign keys with ON DELETE CASCADE will clean up messages and reactions)
					cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

					deletedCount += 1
					totalMsgs += msgs
					totalReactions += reacs
					print(f"  {GREEN}✓ Bot deleted – ID: {discord_id} (messages: {msgs}, reactions: {reacs}){RESET}")
				break
			elif resp.status_code == 429:
				retryAfter = float(resp.headers.get("Retry-After", "1"))
				print(f"  {YELLOW}⏳ Rate limited when checking user {discord_id}, retrying after {retryAfter:.2f} seconds...{RESET}")
				time.sleep(retryAfter)
				# continue loop to retry
			elif resp.status_code == 503:
				# Service Unavailable, exponential backoff
				wait = 2 ** retries
				if retries >= max_retries:
					print(f"  {RED}⚠ Max retries reached for user {discord_id} (503) – skipped{RESET}")
					break
				print(f"  {YELLOW}⚠ Service unavailable (503) for user {discord_id}, retrying in {wait}s...{RESET}")
				time.sleep(wait)
				retries += 1
			else:
				print(f"  {RED}⚠ Could not retrieve user {discord_id} (status {resp.status_code}) – skipped{RESET}")
				break

	print(f"\n{GREEN}Cleanup complete: {deletedCount} bot(s) deleted, total messages deleted: {totalMsgs}, total reactions deleted: {totalReactions}{RESET}")
