from datetime import datetime, timezone
import discord
from discord import app_commands
from zoneinfo import ZoneInfo, available_timezones

from commands import bot, makeEmbed, OWNER_ID
from utils import connectDb, timezoneAutocomplete

TIMEZONES = sorted(available_timezones())

CATEGORY_TIME_RANGES = [
	("fail", "12:05:50", "12:06:00"),
	("success", "12:06:00", "12:07:00"),
	("choke", "12:07:00", "12:08:00"),
]

def getCategoryFromTime(time):
	for category, start_str, end_str in CATEGORY_TIME_RANGES:
		start = datetime.strptime(start_str, "%H:%M:%S").time()
		end = datetime.strptime(end_str, "%H:%M:%S").time()
		if start <= time < end:
			return category
	return None

@bot.tree.command(name="add_admin", description="Add a user as admin (only OWNER can do that)")
@app_commands.describe(user="User to add as admin")
async def addAdminCommand(interaction: discord.Interaction, user: discord.User):
	requesterId = str(interaction.user.id)
	targetId = str(user.id)

	if requesterId != OWNER_ID:
		await interaction.response.send_message("❌ You are not authorized to add admins", ephemeral=True)
		return

	conn, cursor = connectDb()
	try:
		cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (targetId,))
		exists = cursor.fetchone()

		if exists:
			await interaction.response.send_message(f"{user.mention} is already an admin ⚠️", ephemeral=True)
		else:
			cursor.execute("INSERT INTO admins (discord_user_id) VALUES (?)", (targetId,))
			conn.commit()
			await interaction.response.send_message(f"✅ {user.mention} has been added as an admin", ephemeral=True)
	finally:
		conn.close()

@bot.tree.command(name="add_channel", description="Add a channel to the database (only ADMIN can do that)")
@app_commands.describe(channel="Channel to add", tz_name="Timezone for message parsing (default: Europe/Paris)")
@app_commands.autocomplete(tz_name=timezoneAutocomplete)
async def add_channel_command(interaction: discord.Interaction, channel: discord.TextChannel, tz_name: str = "Europe/Paris"):
	requesterId = str(interaction.user.id)
	conn, cursor = connectDb()

	try:
		cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (requesterId,))
		isAdmin = cursor.fetchone() is not None

		if not isAdmin and requesterId != OWNER_ID:
			await interaction.response.send_message("❌ You are not authorized to add channels", ephemeral=True)
			return

		try:
			tz = ZoneInfo(tz_name)
		except Exception:
			await interaction.response.send_message("❌ Invalid timezone", ephemeral=True)
			return

		cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
		if cursor.fetchone():
			await interaction.response.send_message(f"{channel.mention} is already in the database ⚠️, pls use /update_channel", ephemeral=True)
			return

		cursor.execute("INSERT INTO channels (discord_channel_id, timezone) VALUES (?, ?)", (str(channel.id), tz_name))
		conn.commit()
		cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
		channelRowId = cursor.fetchone()[0]

		embedMsg = await channel.send(embed=makeEmbed("Fetching activity...", "Looking through message history, please wait ⏳"))

		storedCount = 0
		userCache = {}

		async for msg in channel.history(limit=None, oldest_first=True):
			if "cath" not in msg.content.lower():
				continue

			createdAt = msg.created_at.replace(tzinfo=timezone.utc).astimezone(tz)
			category = getCategoryFromTime(createdAt.time())
			if not category:
				continue

			authorId = str(msg.author.id)
			day = createdAt.strftime("%Y-%m-%d")

			if authorId not in userCache:
				cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (authorId,))
				userRow = cursor.fetchone()
				if userRow:
					userCache[authorId] = userRow[0]
				else:
					cursor.execute("INSERT INTO users (discord_user_id) VALUES (?)", (authorId,))
					conn.commit()
					userCache[authorId] = cursor.lastrowid

			userId = userCache[authorId]

			cursor.execute("SELECT category FROM messages WHERE user_id = ? AND channel_id = ? AND DATE(timestamp) = ?", (userId, channelRowId, day))
			existingCategories = set(row[0] for row in cursor.fetchall())

			if category in existingCategories:
				continue
			if category == "fail" and ("success" in existingCategories or "choke" in existingCategories):
				continue
			if category == "choke" and "success" in existingCategories:
				continue
			if category == "success" and "choke" in existingCategories: # Should not happen
				continue

			cursor.execute("""
				INSERT INTO messages (message_id, channel_id, user_id, timestamp, category)
				VALUES (?, ?, ?, ?, ?)
			""", (str(msg.id), channelRowId, userId, createdAt, category))
			conn.commit()
			storedCount += 1

		await embedMsg.edit(embed=makeEmbed(
			"Fetching reactions...",
			"Looking through reactions on success messages, please wait 💜"
		))

		# process reactions on all 'success' messages
		cursor.execute("SELECT id, message_id FROM messages WHERE channel_id = ? AND category = 'success'", (channelRowId,))
		successRows = cursor.fetchall()  # list of (id, message_id)
		for msgRowId, msgId in successRows:
			try:
				msgObj = await channel.fetch_message(int(msgId))
			except Exception:
				continue

			for reaction in msgObj.reactions:
				if str(reaction.emoji) != "💜":
					continue
				async for user in reaction.users():
					userStr = str(user.id)
					# ensure user exists
					if userStr not in userCache:
						cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (userStr,))
						row = cursor.fetchone()
						if row:
							userCache[userStr] = row[0]
						else:
							cursor.execute("INSERT INTO users (discord_user_id) VALUES (?)", (userStr,))
							conn.commit()
							userCache[userStr] = cursor.lastrowid

					# insert reaction record
					cursor.execute(
						"INSERT OR IGNORE INTO reactions (user_id, message_id) VALUES (?, ?)",
						(userCache[userStr], msgRowId)
					)
					conn.commit()

		cursor.execute("SELECT category, COUNT(*) FROM messages WHERE channel_id = ? GROUP BY category", (channelRowId,))
		counts = {row[0]: row[1] for row in cursor.fetchall()}

		cursor.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE channel_id = ? AND category = 'success'", (channelRowId,))
		successUsers = cursor.fetchone()[0]

		cursor.execute(
			"SELECT COUNT(*) FROM reactions "
			"JOIN messages ON reactions.message_id = messages.id "
			"WHERE messages.channel_id = ?",
			(channelRowId,)
		)
		reactions = cursor.fetchone()[0]


		await embedMsg.edit(embed=makeEmbed(
			"✅ Channel successfully added in database",
			f"Stored **{storedCount}** message(s) from {channel.mention}.\n\n"
			f"📊 Summary:\n"
			f"- 🟧 Fail: {counts.get('fail', 0)}\n"
			f"- 🟩 Success: {counts.get('success', 0)}\n"
			f"- 🟥 Choke: {counts.get('choke', 0)}\n"
			f"- Total of followers: {successUsers}\n"
			f"- Total reactions: {reactions}"
		))
	finally:
		conn.close()
