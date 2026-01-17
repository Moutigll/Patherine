import discord
from discord.ext import tasks
from commands import TOKEN, bot

from datetime import datetime, time as dtTime, timedelta
from zoneinfo import ZoneInfo

from utils.utils import log
from database.db import createDb, connectDb
from database.migrations.migrate import runMigrations

# Need to be imported even if not called directly
import events.messages
import events.reactions

TARGET_TIME = dtTime(12, 7, 0)

createDb()
log("Database initialized successfully.")

runMigrations()
log("Migrations applied successfully.")

@bot.event
async def on_ready():
	log(f"Bot is ready as {bot.user.name} (ID: {bot.user.id})")
	log("Bot is connected to the following guilds:")
	for guild in bot.guilds:
		print(f"\t\t\t\t- {guild.name} - {guild.member_count} members")
	checkRolesRemoval.start()
	updateStatus.start()

lastChannelMilestone = {}
lastGlobalMilestone = None

async def checkDailyParticipationMilestone(cursor, guild, dbChannelId, todayDate, roleName=None):
	"""
	Check if today is a record day for the channel or global participation.
	Returns a list of messages to send.
	"""
	messages = []

	# --- Channel milestone ---
	cursor.execute("""
		SELECT COUNT(*) FROM messages
		WHERE channel_id = ? AND category='success'
		AND DATE(timestamp, 'localtime') = ?
	""", (dbChannelId, todayDate))
	todayCount = cursor.fetchone()[0]

	cursor.execute("""
		SELECT MAX(count) FROM (
			SELECT COUNT(*) AS count, DATE(timestamp, 'localtime') AS day
			FROM messages
			WHERE channel_id = ? AND category='success'
			GROUP BY day
		)
	""", (dbChannelId,))
	maxCount = cursor.fetchone()[0] or 0

	if todayCount >= maxCount and lastChannelMilestone.get(dbChannelId) != todayDate:
		lastChannelMilestone[dbChannelId] = todayDate
		messages.append(
			f"🎉 Today is the most active day in {guild.name} - #{roleName or 'channel'} with {todayCount} caths!"
		)

	# --- Global milestone ---
	cursor.execute("""
		SELECT COUNT(*) FROM messages
		WHERE category='success'
		AND DATE(timestamp, 'localtime') = ?
	""", (todayDate,))
	globalToday = cursor.fetchone()[0]

	cursor.execute("""
		SELECT MAX(count) FROM (
			SELECT COUNT(*) AS count, DATE(timestamp, 'localtime') AS day
			FROM messages
			WHERE category='success'
			GROUP BY day
		)
	""")
	globalMax = cursor.fetchone()[0] or 0

	globalMessage = None
	global lastGlobalMilestone
	if globalToday >= globalMax and lastGlobalMilestone != todayDate:
		lastGlobalMilestone = todayDate
		globalMessage = f"🌐 Today is a record participation day globally with {globalToday} caths!"

	return messages, globalMessage

@tasks.loop(minutes=1)
async def checkRolesRemoval():
	nowUtc = datetime.now(tz=ZoneInfo("UTC"))

	conn, cursor = connectDb()
	cursor.execute("""
		SELECT discord_channel_id, discord_role_id, timezone, id
		FROM channels
		WHERE discord_role_id IS NOT NULL AND timezone IS NOT NULL
	""")
	channelConfigs = cursor.fetchall()
	conn.close()

	for (channelIdStr, roleIdStr, timezoneName, dbChannelId) in channelConfigs:
		try:
			timezone = ZoneInfo(timezoneName)
		except Exception:
			log(f"Invalid timezone {timezoneName} for role {roleIdStr}")
			continue

		nowLocal = nowUtc.astimezone(timezone)
		targetDatetime = datetime.combine(nowLocal.date(), TARGET_TIME, tzinfo=timezone)
		diffSeconds = abs((nowLocal - targetDatetime).total_seconds())

		if diffSeconds > 60 or diffSeconds < 0:
			continue

		for guild in bot.guilds:
			role = guild.get_role(int(roleIdStr))
			if not role:
				log(f"Role ID {roleIdStr} not found in guild {guild.name}")
				continue

			log(f"Checking {len(role.members)} members for role removal in guild {guild.name}")
			conn, cursor = connectDb()
			todayDate = nowLocal.strftime("%Y-%m-%d")

			for member in role.members:
				userIdStr = str(member.id)

				cursor.execute("SELECT id FROM users WHERE discord_user_id = ?", (userIdStr,))
				userRow = cursor.fetchone()

				if not userRow:
					shouldRemove = True
				else:
					userDbId = userRow[0]
					cursor.execute("""
						SELECT 1 FROM messages
						WHERE user_id = ?
						AND channel_id = ?
						AND category = 'success'
						AND DATE(timestamp, 'localtime') = ?
					""", (userDbId, dbChannelId, todayDate))
					shouldRemove = cursor.fetchone() is None

				if shouldRemove:
					try:
						await member.remove_roles(role, reason="Did not post success message today")
						log(f"Removed role {role.name} from {member.name}")
					except discord.Forbidden:
						log(f"Missing permissions to remove role {role.name} from {member.name}")
					except discord.HTTPException as e:
						log(f"HTTP error removing role: {e}")

		# --- Check milestones ---
		channelMessages, globalMessage = await checkDailyParticipationMilestone(cursor, guild, dbChannelId, todayDate, roleName=role.name)
		conn.close()
		channel = bot.get_channel(int(channelIdStr)) or await bot.fetch_channel(int(channelIdStr))
		if not globalMessage and  channel:
			for msg in channelMessages:
				await channel.send(msg)
		if globalMessage:
			for chIdStr, _, _, _ in channelConfigs:
				ch = bot.get_channel(int(chIdStr)) or await bot.fetch_channel(int(chIdStr))
				if ch:
					await ch.send(globalMessage)

					


@tasks.loop(minutes=5)
async def updateStatus():
	conn, cursor = connectDb()
	cursor.execute("SELECT COUNT(*) FROM messages WHERE category = 'success'")
	totalSuccess = cursor.fetchone()[0] or 0

	cursor.execute("SELECT COUNT(*) FROM reactions")
	totalReactions = cursor.fetchone()[0] or 0

	cursor.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE category = 'success'")
	totalUsersWithSuccess = cursor.fetchone()[0] or 0
	conn.close()

	activity = discord.Game(
		f"{totalSuccess} caths by {totalUsersWithSuccess} users | {totalReactions} reactions 💜"
	)
	try:
		await bot.change_presence(status=discord.Status.online, activity=activity)
	except Exception as e:
		log(f"Failed to update presence: {e}")


if __name__ == "__main__":
	bot.run(TOKEN)
