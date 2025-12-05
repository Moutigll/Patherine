import discord
from datetime import timezone
from zoneinfo import ZoneInfo

from commands import bot
from commands.populateDb import getCategoryFromTime, getUserId, isUserUntracked
from utils.utils import connectDb, log

@bot.event
async def on_message(message: discord.Message):
	if message.author.bot or  not "cath" in message.content.lower():
		return

	conn, cursor = connectDb()

	cursor.execute(
		"SELECT id, timezone, discord_role_id FROM channels WHERE discord_channel_id = ?", 
		(str(message.channel.id),)
	)
	row = cursor.fetchone()
	if not row:
		conn.close()
		return

	internalId, tzName, roleId = row
	localDt = message.created_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tzName))

	category = getCategoryFromTime(localDt.time())
	if not category:
		conn.close()
		return

	uidStr = str(message.author.id)
	if isUserUntracked(uidStr, cursor):
		conn.close()
		return
	userId = getUserId(conn, cursor, uidStr)

	dateStr = localDt.date().isoformat()

	cursor.execute("""
		SELECT 1 FROM messages WHERE channel_id = ? AND user_id = ? AND category = ? AND DATE(timestamp) = ? LIMIT 1""",
		(internalId, userId, category, dateStr))

	if cursor.fetchone():
		conn.close()
		return

	cursor.execute("""
		INSERT INTO messages (channel_id, user_id, message_id, timestamp, category)
		VALUES (?, ?, ?, ?, ?)
	""", (internalId, userId, str(message.id), localDt.isoformat(), category))
	conn.commit()

	if category == "success":
		try:
			await message.add_reaction("💜")
		except discord.HTTPException:
			pass

		cursor.execute(
			"""
			SELECT DISTINCT c.discord_role_id
			FROM channels c
			JOIN messages m ON m.channel_id = c.id
			WHERE m.user_id = ? AND m.category = 'success' AND c.discord_role_id IS NOT NULL
			""",
			(userId,))
		rows = cursor.fetchall()
		conn.close()

		guild = message.guild
		for (roleId,) in rows:
			try:
				role = guild.get_role(int(roleId))
				if role and role not in message.author.roles:
					await message.author.add_roles(role, reason="Has rightfully worshipped Catherine!")
			except Exception as e:
				log(f"Failed to add role {roleId} to {message.author.id}: {e}")
		return

	conn.close()
