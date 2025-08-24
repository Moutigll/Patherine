import discord

from commands import bot
from commands.populateDb import getUserId, isUserUntracked
from utils.utils import connectDb, log


async def getReactionContext(payload):
	"""Fetch guild, channel, message, userId after validation."""
	if str(payload.emoji) != "💜":
		return None, None, None, None

	guild = bot.get_guild(payload.guild_id)
	if guild is None:
		return None, None, None, None

	channel = guild.get_channel(payload.channel_id)
	if channel is None:
		return None, None, None, None

	try:
		message = await channel.fetch_message(payload.message_id)
	except Exception as e:
		log(f"Failed to fetch message: {e}")
		return None, None, None, None

	conn, cursor = connectDb()

	try:
		cursor.execute("SELECT id FROM channels WHERE discord_channel_id = ?", (str(channel.id),))
		row = cursor.fetchone()
		if not row:
			conn.close()
			return None, None, None, None
		channelId = row[0]

		cursor.execute("""
			SELECT id, category FROM messages
			WHERE message_id = ? AND channel_id = ?
		""", (str(message.id), channelId))
		msgRow = cursor.fetchone()

		if not msgRow or msgRow[1] != "success":
			conn.close()
			return None, None, None, None

		messageId = msgRow[0]

		uidStr = str(payload.user_id)
		if isUserUntracked(uidStr, cursor):
			conn.close()
			return None, None, None, None

		userId = getUserId(conn, cursor, uidStr)

		return conn, cursor, messageId, userId

	except Exception as e:
		log(f"Error querying DB: {e}")
		conn.close()
		return None, None, None, None

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
	if payload.member is not None and payload.member.bot:
		return
	conn, cursor, messageId, userId = await getReactionContext(payload)
	if conn is None:
		return

	try:
		cursor.execute("""
			INSERT OR IGNORE INTO reactions (message_id, user_id)
			VALUES (?, ?)
		""", (messageId, userId))
		conn.commit()


	except Exception as e:
		log(f"Error inserting reaction: {e}")

	finally:
		conn.close()


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
	if payload.user_id == bot.user.id:
		return
	conn, cursor, messageId, userId = await getReactionContext(payload)
	if conn is None:
		return
	
	try:
		cursor.execute("""
			DELETE FROM reactions
			WHERE message_id = ? AND user_id = ?
		""", (messageId, userId))
		conn.commit()

	except Exception as e:
		log(f"Error removing reaction: {e}")

	finally:
		conn.close()
