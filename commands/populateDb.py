import discord
from datetime import datetime, timezone
from zoneinfo import available_timezones

from commands import OWNER_ID
from utils.utils import connectDb

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

def isUserUntracked(userId, cursor):
	cursor.execute("SELECT 1 FROM untracked_users WHERE discord_user_id = ?", (userId,))
	return cursor.fetchone() is not None

async def authorize(interaction: discord.Interaction) -> bool:
	reqId = str(interaction.user.id)
	conn, cursor = connectDb()
	cursor.execute("SELECT 1 FROM admins WHERE discord_user_id = ?", (reqId,))
	isAdmin = cursor.fetchone() is not None
	conn.close()
	if not isAdmin and reqId != OWNER_ID:
		await interaction.response.send_message("❌ You are not authorized to perform this action", ephemeral=True)
		return False
	return True

def getUserId(conn, cursor, userId):
	"""Fetch the user id from the database, or insert it if it doesn't exist."""
	cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (userId,))
	row = cursor.fetchone()
	if row:
		return row[0]
	cursor.execute("INSERT INTO users (discord_user_id) VALUES (?)", (userId,))
	conn.commit()
	return cursor.lastrowid


async def fetchMessages(
	channel,
	internalChannelId,
	cursor,
	conn,
	tz,
	embedMsg,
	startTime,
	fromDate=None
):
	"""Fetch and store new messages, return map of success messages."""
	stored = 0
	messageMap = []
	userCache = {}

	historyKwargs = {
			"oldest_first": True
	}

	if fromDate is not None:
		historyKwargs["after"] = fromDate

	async for msg in channel.history(**historyKwargs):
		if "cath" not in msg.content.lower():
			continue

		localDt = msg.created_at.replace(tzinfo=timezone.utc).astimezone(tz)
		category = getCategoryFromTime(localDt.time())
		if not category:
			continue

		uidStr = str(msg.author.id)
		if isUserUntracked(uidStr, cursor):
			continue
		if uidStr not in userCache:
			userCache[uidStr] = getUserId(conn, cursor, uidStr)

		userId = userCache[uidStr]
		dayStr = localDt.strftime("%Y-%m-%d")

		cursor.execute(
			"SELECT category FROM messages WHERE user_id = ? AND channel_id = ? AND DATE(timestamp) = ?",
			(userId, internalChannelId, dayStr)
		)
		existing = {r[0] for r in cursor.fetchall()}
		if category in existing:
			continue
		if category == "fail" and existing & {"success", "choke"}:
			continue
		if category == "success" and "choke" in existing:
			continue
		if category == "choke" and "success" in existing:
			continue

		cursor.execute(
			"INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, timestamp, category) VALUES (?, ?, ?, ?, ?)",
			(str(msg.id), internalChannelId, userId, localDt, category)
		)
		conn.commit()
		stored += 1
		if category == "success":
			messageMap.append((cursor.lastrowid, msg.id))

		if stored % 100 == 0:
			elapsed = (datetime.now(timezone.utc) - startTime).total_seconds()
			await embedMsg.edit(content=f"Fetching messages... {stored} fetched\nElapsed: {elapsed:.1f}s\nStarted at: {startTime.strftime('%Y-%m-%d %H:%M:%S UTC')}")
	return stored, messageMap


async def fetchReactions(channel, cursor, conn, messageMap):
	"""Fetch and store new reactions, return count."""
	count = 0
	userCache = {}
	pendingInserts = []

	for internalId, discordId in messageMap:
		try:
			msgObj = await channel.fetch_message(discordId)
		except Exception as e:
			print(f"Failed to fetch message {discordId}: {e}")
			continue

		for react in msgObj.reactions:
			if str(react.emoji) != "💜":
				continue
			try:
				async for user in react.users():
					if user.bot:
						continue

					uidStr = str(user.id)
					if isUserUntracked(uidStr, cursor):
						continue
					if uidStr not in userCache:
						userCache[uidStr] = getUserId(conn, cursor, uidStr)

					pendingInserts.append((userCache[uidStr], internalId))
					count += 1
					if len(pendingInserts) >= 100:
						cursor.executemany(
							"INSERT OR IGNORE INTO reactions (user_id, message_id) VALUES (?, ?)",
							pendingInserts)
						conn.commit()
						pendingInserts.clear()
			except Exception as e:
				print(f"Error fetching users for message {discordId}: {e}")

	if pendingInserts:
		cursor.executemany(
			"INSERT OR IGNORE INTO reactions (user_id, message_id) VALUES (?, ?)",
			pendingInserts)
		conn.commit()

	return count

async def generateSummary(cursor, channelId, stored, reacted):
	cursor.execute("SELECT category,COUNT(*) FROM messages WHERE channel_id=? GROUP BY category", (channelId,))
	counts={r[0]:r[1] for r in cursor.fetchall()}

	cursor.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE channel_id=? AND category='success'", (channelId,))
	successUsers=cursor.fetchone()[0]

	cursor.execute(
		"SELECT COUNT(*) FROM reactions JOIN messages ON reactions.message_id=messages.id WHERE messages.channel_id=?",
		(channelId,))
	totalReacts=cursor.fetchone()[0]
	return (
		f"Stored **{stored}** message(s). Fetched **{reacted}** reactions.\n\n"
		"📊 Summary:\n"
		f"- Fail: {counts.get('fail',0)}\n"
		f"- Success: {counts.get('success',0)}\n"
		f"- Choke: {counts.get('choke',0)}\n"
		f"- Unique success users: {successUsers}\n"
		f"- Total reactions: {totalReacts}"
	)
