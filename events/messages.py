import discord
from datetime import timezone
from zoneinfo import ZoneInfo

from commands import bot
from commands.populateDb import getCategoryFromTime, getUserId
from utils.utils import connectDb, log

@bot.event
async def on_message(message: discord.Message):
	if message.author.bot:
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
	userId = getUserId(conn, cursor, uidStr)  # <-- utilisation de getUserId ici

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

		if roleId:
			guild = message.guild
			role = guild.get_role(int(roleId))
			if role and role not in message.author.roles:
				try:
					await message.author.add_roles(role, reason="Has rightfully worshipped Catherine!")
				except discord.Forbidden:
					log(f"Missing permissions to add role {role.name} to {message.author}")

	conn.close()
