import discord
from datetime import datetime, timezone
from zoneinfo import available_timezones

from commands import OWNER_ID
from utils import connectDb

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

async def fetchMessages(channel, internal_channel_id, cursor, conn, tz, after=None):
	"""Fetch and store new messages, return map of success messages."""
	stored = 0
	messageMap = []
	userCache = {}

	async for msg in channel.history(limit=None, oldest_first=True, after=after):
		if "cath" not in msg.content.lower():
			continue

		localDt = msg.created_at.replace(tzinfo=timezone.utc).astimezone(tz)
		category = getCategoryFromTime(localDt.time())
		if not category:
			continue

		uidStr = str(msg.author.id)
		if uidStr not in userCache:
			cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (uidStr,))
			row = cursor.fetchone()
			if row:
				userCache[uidStr] = row[0]
			else:
				cursor.execute("INSERT INTO users (discord_user_id) VALUES (?)", (uidStr,))
				conn.commit()
				userCache[uidStr] = cursor.lastrowid

		userId = userCache[uidStr]
		dayStr = localDt.strftime("%Y-%m-%d")

		cursor.execute(
			"SELECT category FROM messages WHERE user_id = ? AND channel_id = ? AND DATE(timestamp) = ?",
			(userId, internal_channel_id, dayStr)
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
			"INSERT INTO messages (message_id, channel_id, user_id, timestamp, category) VALUES (?, ?, ?, ?, ?)",
			(str(msg.id), internal_channel_id, userId, localDt, category)
		)
		conn.commit()
		stored += 1
		if category == "success":
			messageMap.append((cursor.lastrowid, msg.id))

	return stored, messageMap


async def fetchReactions(channel, cursor, conn, messageMap):
	"""Fetch and store new reactions, return count."""
	count = 0
	userCache = {}
	for internalId, discordId in messageMap:
		try:
			msgObj = await channel.fetch_message(discordId)
		except:
			continue
		for react in msgObj.reactions:
			if str(react.emoji)!="💜": continue
			async for user in react.users():
				if user.bot: continue
				uidStr = str(user.id)
				if uidStr not in userCache:
					cursor.execute("SELECT id FROM users WHERE discord_user_id=?",(uidStr,))
					row = cursor.fetchone()
					if row: userCache[uidStr]=row[0]
					else:
						cursor.execute("INSERT INTO users (discord_user_id) VALUES (?)",(uidStr,))
						conn.commit()
						userCache[uidStr]=cursor.lastrowid
				cursor.execute(
					"INSERT OR IGNORE INTO reactions (user_id,message_id) VALUES (?,?)",
					(userCache[uidStr], internalId)
				)
				conn.commit()
				count+=1
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
